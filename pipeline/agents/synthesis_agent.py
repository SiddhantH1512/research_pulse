"""
Agent 3 — Synthesis Agent
──────────────────────────
Takes the research + pattern output and writes the baseline draft report.
This is the input to Council 1 (factual) and Council 2 (style), and ultimately
the Arbiter.

Tone: senior tech journalist (Wired / MIT Tech Review / Atlantic). Conversational
but credible, opinionated, varied rhythm, no AI-isms.
"""

import json
from typing import Callable, Optional

import anthropic

from config import SYNTHESIS_MODEL, SYNTHESIS_MAX_TOKENS
from pipeline.templates import ArticleTemplate, get_template, DEFAULT_TEMPLATE_KEY
from pipeline.personas import WriterPersona, get_persona, DEFAULT_PERSONA_KEY
from pipeline.observability import traced


def _build_system_prompt(template: ArticleTemplate, persona: WriterPersona) -> str:
    """Compose the Synthesis system prompt around the chosen persona + template."""
    structure_block = template.structure_for_prompt(start_index=4)

    # Persona-specific block — voice + (optional) domain guardrails.
    guardrails_block = ""
    if persona.domain_guardrails:
        guardrails_block = "\n\n" + persona.domain_guardrails + "\n"

    return f"""You are {persona.persona_intro}
You have written for publications like {persona.publication_examples}.

{persona.voice_guidance}{guardrails_block}

Your writing has a specific style:
- Conversational but credible — you talk with the reader, not at them
- You lead with what matters, not with context
- Short sentences when making a point. Longer ones when you are building toward something.
- You use real examples and analogies, not abstract descriptions
- You vary your rhythm — some punchy one-liners, some developed paragraphs
- You are not afraid to have a perspective
- You NEVER use these phrases: "it is worth noting", "in conclusion", "furthermore",
  "it is important to understand", "delve into", "in today's rapidly evolving landscape",
  "at the intersection of", "game-changing", "paradigm shift", "leverage", "paramount",
  "testament to", "navigate the landscape"
- You do not overuse bullet points — prose tells a better story
- You occasionally use rhetorical questions to pull the reader forward

REPORT STRUCTURE — Template: {template.name}
(Best for: {template.best_for})

The structure has three UNIVERSAL elements followed by the template's section list.

1. ## Title
   A punchy title. Specific. Not generic.

2. Opening hook — 2 to 3 sentences immediately after the title, NO ## header
   above it. Hook the reader instantly. No scene-setting, no history, no
   "in today's world."

3. THE KEY INSIGHT — a markdown blockquote placed immediately after the
   opening, BEFORE any ## header. Format exactly like this:

       > **The key insight:** [one or two sentences that compress the entire
       > argument into a screenshot-worthy claim].

   Rules:
     • The single most quotable sentence in the piece — what a reader would
       underline, screenshot, or paste into a tweet.
     • Specific and non-obvious. Generic claims ("AI is changing everything")
       are forbidden. It should make a claim someone could disagree with.
     • Self-contained — readable without the surrounding article.
     • Must not repeat the title verbatim. The title teases; this line lands.
     • Under 35 words. Tighter is better.

Then continue with the TEMPLATE STRUCTURE — use these EXACT section headers
in this EXACT order (do not rename, reorder, add, or remove sections):

{structure_block}

Notes on the template structure:
  • Each ## header above must appear, spelled exactly as shown.
  • If the template's first section name overlaps semantically with the
    opening hook (e.g. "The Hook", "The Question", "The Story"), treat that
    section as a deeper expansion of the opening — NOT a redundant repeat
    of the same lines. The opening is 2-3 sentences; the section is a full
    developed paragraph or two.
  • Each section should be one to three paragraphs of prose. Avoid turning
    sections into bullet lists unless the template's nature demands it
    (e.g. "Step 1 / Step 2 / Step 3" can be more procedural).

Length: 1200–1800 words. Dense enough to be useful. Tight enough to finish.

Return only the markdown report — no JSON, no preamble, no commentary."""


@traced(run_type="chain", name="synthesis_agent")
def run_synthesis_agent(
    anthropic_client: anthropic.Anthropic,
    domain: str,
    research_data: dict,
    pattern_data: dict,
    template: Optional[ArticleTemplate] = None,
    persona: Optional[WriterPersona] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Run the Synthesis Agent. Returns the baseline draft markdown."""

    def log(msg: str):
        if callback:
            callback(msg)

    if template is None:
        template = get_template(DEFAULT_TEMPLATE_KEY)
    if persona is None:
        persona = get_persona(DEFAULT_PERSONA_KEY)

    log(f"✍️  Synthesizing report for: **{domain}**")
    log(f"   🎙️  Persona: {persona.name}")
    log(f"   📐 Template: {template.name}")

    system_prompt = _build_system_prompt(template, persona)

    brief = {
        "domain": domain,
        "hot_topics":            research_data.get("hot_topics", [])[:6],
        "top_voices":            research_data.get("top_voices", [])[:6],
        "key_narratives":        research_data.get("key_narratives", [])[:4],
        "concrete_data_points":  research_data.get("concrete_data_points", [])[:8],
        "emerging_signals":      research_data.get("emerging_signals", [])[:4],
        "research_raw_fallback": research_data.get("raw_output", None),
        "gaps_and_missed_angles": pattern_data.get("gaps_and_missed_angles", [])[:4],
        "contrarian_takes":      pattern_data.get("contrarian_takes", [])[:3],
        "hook_patterns":         pattern_data.get("hook_patterns", [])[:3],
        "recommended_angles":    pattern_data.get("recommended_angles", [])[:3],
        "underserved_audiences": pattern_data.get("underserved_audiences", [])[:2],
    }

    payload = json.dumps(brief, ensure_ascii=False, indent=2)

    log("   🖊️  Writing report (this takes a moment)...")

    # For personas with strict guardrails (e.g. health), reinforce in the user
    # prompt — system-prompt rules can fade across long generations.
    guardrail_reminder = ""
    if persona.domain_guardrails:
        guardrail_reminder = (
            "\n\nREMINDER: This is a KNOWLEDGE piece, not advice. Discuss what "
            "the science shows; describe protocols used in studies; do NOT tell "
            "the reader what to do, take, or follow. No dosing recommendations. "
            "No imperatives directed at the reader. Frame everything as "
            "\"here is what the research shows\" — not \"here is what you should do\"."
        )

    response = anthropic_client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=SYNTHESIS_MAX_TOKENS,
        # temperature=SYNTHESIS_TEMPERATURE,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[
            {
                "role": "user",
                "content": (
                    f'Write a research report about "{domain}" using the data below.\n\n'
                    f"Persona: **{persona.name}**.\n"
                    f"Template to follow: **{template.name}** "
                    f"(best for: {template.best_for}).\n\n"
                    f"RESEARCH BRIEF:\n{payload}\n\n"
                    "Write the full markdown report. Follow the structure exactly. "
                    "Make it feel like a human journalist wrote it — not an AI summary. "
                    "Use the gaps and contrarian takes prominently. "
                    "Start immediately with the title and hook — no preamble."
                    f"{guardrail_reminder}"
                ),
            }
        ],
    )

    draft = response.content[0].text.strip()
    log("✅ Synthesis Agent complete — baseline draft written")
    return draft