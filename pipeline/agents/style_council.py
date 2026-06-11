"""
Step 5 — Council 2: Parallel Stylistic & Humanization Council
──────────────────────────────────────────────────────────────
Three lenses run *concurrently* via asyncio.gather:

  • Claude lens — narrative flow, paragraph transitions, cadence
                  (claude-opus-4-7)
  • GPT lens    — corporate buzzwords / AI-isms (delve, paramount, leverage)
                  (gpt-5.5)
  • Llama lens  — structural grit, conversational directness
                  (llama-3.3-70b-versatile on Groq;
                   falls back to Perplexity `sonar` if GROQ_API_KEY missing)

All three receive the baseline draft AND the Council 1 factual correction
list. They are FORBIDDEN from rewriting the manuscript. They return a JSON
array of critique blocks:

  [{"original_text": "...", "issue": "...", "suggested_fix": "..."}]

Robust failback (per spec):
  1. Try strict JSON parse.
  2. Regex-strip to outermost [...] and try again.
  3. If still unparsable, return raw text with a system-warning sentinel
     and let the Arbiter interpret it.

Total latency = slowest single model (asyncio.gather).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Callable, Optional

import anthropic
import openai

from config import (
    STYLE_CLAUDE_MODEL,
    STYLE_GPT_MODEL,
    STYLE_GPT_MODEL_FALLBACK,
    STYLE_LLAMA_MODEL,
    STYLE_LLAMA_FALLBACK_MODEL,
    STYLE_COUNCIL_MAX_TOKENS,
    STYLE_COUNCIL_TEMPERATURE,
    SYSTEM_WARNING_UNPARSED,
    GROQ_BASE_URL,
)
from pipeline.clients.perplexity_client import perplexity_complete_async
from pipeline.personas import WriterPersona, UNIVERSAL_BUZZWORDS
from pipeline.observability import (
    traced,
    wrap_anthropic_client,
    wrap_openai_client,
)


# ─────────────────────────────────────────────────────────────────
#  Per-lens system prompts
# ─────────────────────────────────────────────────────────────────

_OUTPUT_CONTRACT = """
CRITICAL OUTPUT RULES:
- You are FORBIDDEN from rewriting the entire manuscript.
- You ONLY emit a JSON array of critique blocks.
- Each block targets ONE specific span of the original text.
- Use the EXACT original text (a short snippet, 3–20 words) so the Arbiter
  can find it later.
- Schema, exactly:
[
  {
    "original_text": "It is paramount to leverage this data...",
    "issue": "Highly robotic AI-ism ('paramount', 'leverage').",
    "suggested_fix": "We need to use this data..."
  }
]
- Return ONLY the JSON array. No prose before or after. No markdown fences.
- If you have nothing to critique, return: []
"""

CLAUDE_LENS_SYSTEM = (
    "You are a developmental editor evaluating the NARRATIVE FLOW of an article.\n"
    "Focus exclusively on:\n"
    "  • Paragraph transitions (do they connect? or jolt?)\n"
    "  • Cadence and rhythm (three same-length sentences in a row = flag it)\n"
    "  • Readability — moments where the reader would lose the thread\n"
    "  • Structural pacing — where the article slows down or rushes\n"
    "Ignore word choice and factual accuracy — other lenses handle those.\n"
    + _OUTPUT_CONTRACT
)


def _build_gpt_lens_system(persona: Optional[WriterPersona]) -> str:
    """Compose the GPT lens system prompt — universal AI-isms plus persona extras."""
    extras = persona.gpt_buzzword_extras if persona else ()
    all_buzzwords = list(UNIVERSAL_BUZZWORDS) + list(extras)
    formatted = ", ".join(all_buzzwords)
    return (
        "You are an editor obsessed with hunting CORPORATE BUZZWORDS and AI-ISMS.\n"
        "Flag (and propose fixes for) words and phrases like:\n"
        f"  {formatted}\n"
        "Ignore narrative flow and factual accuracy — other lenses handle those.\n"
        + _OUTPUT_CONTRACT
    )


LLAMA_LENS_SYSTEM = (
    "You are a blunt newsroom editor judging STRUCTURAL GRIT.\n"
    "Your bar: the article must sound like a person who actually wanted to write it.\n"
    "Flag (and propose fixes for):\n"
    "  • Empty openers — 'It is...', 'There are...', 'In a world where...'\n"
    "  • Hedge stacking — 'might potentially seem like it could possibly'\n"
    "  • Passive voice where active is sharper\n"
    "  • Conversational dead air — where the writer disappears\n"
    "Be direct. Be terse. Don't be polite about it.\n"
    + _OUTPUT_CONTRACT
)


# ─────────────────────────────────────────────────────────────────
#  Robust critique-JSON parser
# ─────────────────────────────────────────────────────────────────

def _parse_critique_json(raw: str) -> tuple[Optional[list], Optional[str]]:
    """
    Returns (parsed_list, warning_text).
      parsed_list = list of {original_text, issue, suggested_fix} dicts on success
      warning_text = raw text + sentinel if parsing failed
    """
    if not raw:
        return [], None

    text = raw.strip()

    # 1. Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # 2. Strict parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed, None
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v, None
    except json.JSONDecodeError:
        pass

    # 3. Regex extraction — outermost [...] block
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                return parsed, None
        except json.JSONDecodeError:
            pass

    # 4. Give up — surface raw text with sentinel for the Arbiter
    return None, f"{SYSTEM_WARNING_UNPARSED}\n\n{raw}"


# ─────────────────────────────────────────────────────────────────
#  Per-lens async functions
# ─────────────────────────────────────────────────────────────────

def _build_user_prompt(draft: str, factual_corrections: str) -> str:
    return (
        "Review the DRAFT below through your assigned lens.\n\n"
        "While reviewing, also visually track the pending FACTUAL "
        "CORRECTIONS — do not flag any text whose meaning will already "
        "be changed by those corrections.\n\n"
        "FACTUAL CORRECTIONS (pending — applied later by the Arbiter):\n"
        f"```\n{factual_corrections or 'None.'}\n```\n\n"
        "DRAFT:\n"
        f"```\n{draft}\n```\n\n"
        "Return ONLY the JSON array of critique blocks. Nothing else."
    )


@traced(run_type="llm", name="style_claude_lens")
async def _claude_lens(draft: str, factual_corrections: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"lens": "claude", "model": STYLE_CLAUDE_MODEL,
                "critiques": [], "warning": "ANTHROPIC_API_KEY missing"}

    client = wrap_anthropic_client(anthropic.AsyncAnthropic(api_key=api_key))
    try:
        resp = await client.messages.create(
            model=STYLE_CLAUDE_MODEL,
            max_tokens=STYLE_COUNCIL_MAX_TOKENS,
            # temperature=STYLE_COUNCIL_TEMPERATURE,
            system=CLAUDE_LENS_SYSTEM,
            messages=[{"role": "user",
                       "content": _build_user_prompt(draft, factual_corrections)}],
        )
        raw = resp.content[0].text.strip()
    except Exception as e:
        return {"lens": "claude", "model": STYLE_CLAUDE_MODEL,
                "critiques": [], "warning": f"Claude lens failed: {e}"}

    critiques, warning = _parse_critique_json(raw)
    return {
        "lens": "claude",
        "model": STYLE_CLAUDE_MODEL,
        "critiques": critiques if critiques is not None else [],
        "warning": warning,
    }


@traced(run_type="llm", name="style_gpt_lens")
async def _gpt_lens(draft: str, factual_corrections: str,
                    persona: Optional[WriterPersona] = None) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"lens": "gpt", "model": STYLE_GPT_MODEL,
                "critiques": [], "warning": "OPENAI_API_KEY missing"}

    client = wrap_openai_client(openai.AsyncOpenAI(api_key=api_key))

    async def _call(model: str):
        return await client.chat.completions.create(
            model=model,
            max_completion_tokens=STYLE_COUNCIL_MAX_TOKENS,
            # temperature=STYLE_COUNCIL_TEMPERATURE,
            messages=[
                {"role": "system", "content": _build_gpt_lens_system(persona)},
                {"role": "user",   "content": _build_user_prompt(draft, factual_corrections)},
            ],
        )

    try:
        resp = await _call(STYLE_GPT_MODEL)
    except openai.NotFoundError:
        try:
            resp = await _call(STYLE_GPT_MODEL_FALLBACK)
        except Exception as e:
            return {"lens": "gpt", "model": STYLE_GPT_MODEL_FALLBACK,
                    "critiques": [], "warning": f"GPT lens failed (fallback): {e}"}
    except Exception as e:
        return {"lens": "gpt", "model": STYLE_GPT_MODEL,
                "critiques": [], "warning": f"GPT lens failed: {e}"}

    raw = (resp.choices[0].message.content or "").strip()
    critiques, warning = _parse_critique_json(raw)
    return {
        "lens": "gpt",
        "model": STYLE_GPT_MODEL,
        "critiques": critiques if critiques is not None else [],
        "warning": warning,
    }


@traced(run_type="llm", name="style_llama_lens_groq")
async def _llama_lens_via_groq(draft: str, factual_corrections: str) -> dict:
    """Preferred path: Llama 3.3 70B on Groq (OpenAI-compatible API)."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None  # signal caller to try Perplexity fallback

    # Groq is OpenAI-compatible — reuse the openai SDK with a base_url.
    client = wrap_openai_client(
        openai.AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    )
    try:
        resp = await client.chat.completions.create(
            model=STYLE_LLAMA_MODEL,
            max_tokens=STYLE_COUNCIL_MAX_TOKENS,
            temperature=STYLE_COUNCIL_TEMPERATURE,
            messages=[
                {"role": "system", "content": LLAMA_LENS_SYSTEM},
                {"role": "user",   "content": _build_user_prompt(draft, factual_corrections)},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return {"lens": "llama", "model": f"groq:{STYLE_LLAMA_MODEL}",
                "critiques": [], "warning": f"Groq Llama lens failed: {e}"}

    critiques, warning = _parse_critique_json(raw)
    return {
        "lens": "llama",
        "model": f"groq:{STYLE_LLAMA_MODEL}",
        "critiques": critiques if critiques is not None else [],
        "warning": warning,
    }


@traced(run_type="llm", name="style_llama_lens_perplexity")
async def _llama_lens_via_perplexity(draft: str, factual_corrections: str) -> dict:
    """Fallback path: Llama-backed sonar on Perplexity."""
    if not os.getenv("PERPLEXITY_API_KEY"):
        return {"lens": "llama", "model": "(none)",
                "critiques": [], "warning": "Neither GROQ_API_KEY nor PERPLEXITY_API_KEY set"}

    try:
        result = await perplexity_complete_async(
            messages=[
                {"role": "system", "content": LLAMA_LENS_SYSTEM},
                {"role": "user",   "content": _build_user_prompt(draft, factual_corrections)},
            ],
            model=STYLE_LLAMA_FALLBACK_MODEL,
            temperature=STYLE_COUNCIL_TEMPERATURE,
            max_tokens=STYLE_COUNCIL_MAX_TOKENS,
        )
        raw = (result["content"] or "").strip()
    except Exception as e:
        return {"lens": "llama", "model": f"perplexity:{STYLE_LLAMA_FALLBACK_MODEL}",
                "critiques": [], "warning": f"Perplexity Llama fallback failed: {e}"}

    critiques, warning = _parse_critique_json(raw)
    return {
        "lens": "llama",
        "model": f"perplexity:{STYLE_LLAMA_FALLBACK_MODEL}",
        "critiques": critiques if critiques is not None else [],
        "warning": warning,
    }


@traced(run_type="chain", name="style_llama_lens")
async def _llama_lens(draft: str, factual_corrections: str) -> dict:
    """Try Groq first, fall back to Perplexity sonar if no Groq key."""
    primary = await _llama_lens_via_groq(draft, factual_corrections)
    if primary is not None:
        return primary
    return await _llama_lens_via_perplexity(draft, factual_corrections)


# ─────────────────────────────────────────────────────────────────
#  Orchestration entry point
# ─────────────────────────────────────────────────────────────────

async def _run_council_async(draft: str, factual_corrections: str,
                             persona: Optional[WriterPersona] = None) -> list[dict]:
    """asyncio.gather the three lenses — total latency ≈ slowest lens."""
    return await asyncio.gather(
        _claude_lens(draft, factual_corrections),
        _gpt_lens(draft, factual_corrections, persona),
        _llama_lens(draft, factual_corrections),
    )


@traced(run_type="chain", name="style_council")
def run_style_council(
    draft_report: str,
    factual_corrections: str,
    persona: Optional[WriterPersona] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Synchronous wrapper around the three parallel style lenses."""

    def log(msg: str):
        if callback:
            callback(msg)

    using_groq = bool(os.getenv("GROQ_API_KEY"))
    llama_label = (
        f"Llama 3.3 70B on Groq"
        if using_groq else
        f"Llama (Perplexity sonar fallback)"
    )
    persona_label = persona.name if persona else "(none)"

    log("🎭 Council 2 — Parallel Style & Humanization Council")
    log(f"   🎙️  Persona context: {persona_label}")
    log("   ⚡ Dispatching three lenses concurrently (asyncio.gather)...")
    log(f"      • Claude lens — {STYLE_CLAUDE_MODEL}")
    log(f"      • GPT lens    — {STYLE_GPT_MODEL}")
    log(f"      • Llama lens  — {llama_label}")

    # Fresh event loop — safe inside Streamlit's sync context.
    try:
        results = asyncio.run(_run_council_async(draft_report, factual_corrections, persona))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                _run_council_async(draft_report, factual_corrections, persona)
            )
        finally:
            loop.close()

    for r in results:
        n = len(r.get("critiques", []))
        warn = r.get("warning")
        emoji = "⚠️" if warn else "✅"
        msg = f"   {emoji} {r['lens']:<6} → {n} critique(s)"
        if warn:
            msg += f"  ({warn[:60]})"
        log(msg)

    log("✅ Style Council complete")
    return {"lenses": results}