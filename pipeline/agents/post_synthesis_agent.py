"""
Post Synthesis Agent
─────────────────────
Generates 3 LinkedIn post candidates from research + pattern data using a
single chosen framework. Each candidate is a fresh, independent draft — same
research, same framework, different execution.

Design notes:
  • Runs 3 parallel Claude calls with high temperature to force divergence.
  • Uses SYNTHESIS_MODEL (Opus 4.8) — writing quality is the whole point.
  • The 6-criteria filter is embedded in the system prompt as a rubric.
  • Persona guardrails apply here too (e.g. health persona → no dosing advice).
  • Post length target: 150-300 words (LinkedIn attention-span sweet spot).
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import anthropic

from config import SYNTHESIS_MODEL, SYNTHESIS_MAX_TOKENS
from pipeline.post_frameworks import (
    PostFramework, get_post_framework, DEFAULT_POST_FRAMEWORK_KEY,
)
from pipeline.personas import WriterPersona, get_persona, DEFAULT_PERSONA_KEY
from pipeline.observability import traced


def _build_system_prompt(framework: PostFramework, persona: WriterPersona) -> str:
    """Compose the system prompt around the chosen framework + persona."""

    persona_guardrails = ""
    if persona.domain_guardrails:
        persona_guardrails = "\n\n" + persona.domain_guardrails + "\n"

    return f"""You are {persona.persona_intro}
You have written for publications like {persona.publication_examples}.

{persona.voice_guidance}{persona_guardrails}

Right now, you are writing a LinkedIn post — NOT an article. A LinkedIn post has
different constraints than long-form:
  • 150-300 words. Anything longer loses the reader mid-scroll.
  • No section headers. No H2s. No markdown scaffolding.
  • Short paragraphs. 1-3 sentences each. Whitespace between them.
  • Written to be read on a phone.
  • The first line has to earn the second click ("...see more").

THE 6-CRITERIA FILTER — your post MUST hit at least 4 of these:
  1. TIMELY — Rooted in something specific that changed recently
  2. NON-OBVIOUS — Reader learns something past the headline
  3. AUDIENCE-SPECIFIC — Written to a named audience, not "everyone"
  4. POINT OF VIEW — Takes a stance, not just a summary
  5. EVIDENCE-BACKED — At least one specific source or data point
  6. DISCUSSION-WORTHY — Contains real tension or a genuine debate

Rule 7: Don't compete on reporting. Compete on INTERPRETATION.

FRAMEWORK — this post uses **{framework.name}**
(Best for: {framework.best_for})
(This framework naturally optimizes for: {', '.join(framework.optimizes_for)})

{framework.shape}

FORBIDDEN — never use these:
  • "In today's rapidly evolving landscape…"
  • "It is important to note…" / "Furthermore" / "Moreover"
  • "Delve into" / "navigate the landscape" / "paradigm shift"
  • "Game-changing" / "seamlessly" / "leverage" / "unlock"
  • Emoji-heavy formatting (max 1 emoji, only if it earns its place)
  • Hashtag spam at the end (max 2-3 hashtags, all relevant)
  • Rhetorical questions in the first line
  • "What do you think?" as the closing question — LAZY. Ask something
    specific that people can genuinely disagree on.

TONE — you are a thoughtful practitioner posting, not a marketer.
  • Confident, not salesy
  • Interpretive, not descriptive
  • Specific, not sweeping
  • Human — this should read like something a person wrote at 10pm after
    thinking about a story for 20 minutes, not like an AI-generated caption.

Return ONLY the post text. No preamble. No commentary. No "here's your post:".
Do not wrap in quotes. Do not add a title. Just the post, ready to paste."""


def _build_user_prompt(
    domain: str,
    research_data: dict,
    pattern_data: dict,
    variant_num: int,
    variant_direction: str,
) -> str:
    """Build the per-candidate user prompt with a divergence instruction."""

    # Compress the research brief — LinkedIn posts don't need the full brief
    brief = {
        "topic":                domain,
        "hot_topics":           research_data.get("hot_topics", [])[:3],
        "top_voices":           research_data.get("top_voices", [])[:4],
        "concrete_data_points": research_data.get("concrete_data_points", [])[:6],
        "emerging_signals":     research_data.get("emerging_signals", [])[:3],
        "gaps_and_missed_angles": pattern_data.get("gaps_and_missed_angles", [])[:3],
        "contrarian_takes":     pattern_data.get("contrarian_takes", [])[:2],
        "recommended_angles":   pattern_data.get("recommended_angles", [])[:2],
    }

    import json
    payload = json.dumps(brief, ensure_ascii=False, indent=2)

    return (
        f'Write a LinkedIn post about "{domain}".\n\n'
        f"This is CANDIDATE #{variant_num} of 3. Your specific angle for this draft:\n"
        f"→ {variant_direction}\n\n"
        f"RESEARCH BRIEF:\n{payload}\n\n"
        "Write the full post. Apply the framework. Hit the 6-criteria filter. "
        "150-300 words. Ready to paste into LinkedIn. Nothing else."
    )


# Three divergence instructions so the 3 candidates aren't near-duplicates
VARIANT_DIRECTIONS = [
    "Lead with the strongest single piece of evidence in the brief. Build the "
    "entire post around that one data point or source. Prioritize concreteness.",

    "Lead with the sharpest contrarian angle or gap from the brief. Take the "
    "position most likely to spark constructive disagreement. Prioritize POV.",

    "Lead with the second-order implication most people are missing. What "
    "happens next because of this, that hasn't been reported yet. Prioritize "
    "non-obviousness.",
]


async def _generate_one_candidate(
    anthropic_client: anthropic.Anthropic,
    domain: str,
    research_data: dict,
    pattern_data: dict,
    system_prompt: str,
    variant_num: int,
    variant_direction: str,
) -> str:
    """Single async Claude call for one post candidate."""
    user_prompt = _build_user_prompt(
        domain, research_data, pattern_data, variant_num, variant_direction,
    )

    # Anthropic SDK has async support via AsyncAnthropic — but we already have
    # a sync client here. Run the sync call in a thread pool so we can gather.
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: anthropic_client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=2048,   # posts are short — no need for full budget
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        ),
    )
    return response.content[0].text.strip()


@traced(run_type="chain", name="post_synthesis_agent")
def run_post_synthesis_agent(
    anthropic_client: anthropic.Anthropic,
    domain: str,
    research_data: dict,
    pattern_data: dict,
    framework: Optional[PostFramework] = None,
    persona: Optional[WriterPersona] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Generate 3 LinkedIn post candidates using the chosen framework.

    Returns:
        {
          "framework": PostFramework,
          "candidates": [str, str, str],
          "domain": str,
        }
    """
    def log(msg: str):
        if callback:
            callback(msg)

    if framework is None:
        framework = get_post_framework(DEFAULT_POST_FRAMEWORK_KEY)
    if persona is None:
        persona = get_persona(DEFAULT_PERSONA_KEY)

    log(f"✍️  Post Synthesis — domain: **{domain}**")
    log(f"   🎙️  Persona: {persona.name}")
    log(f"   🧩 Framework: {framework.name}")
    log("   🔀 Generating 3 divergent candidates in parallel...")

    system_prompt = _build_system_prompt(framework, persona)

    async def gather_all():
        tasks = [
            _generate_one_candidate(
                anthropic_client, domain, research_data, pattern_data,
                system_prompt, i + 1, VARIANT_DIRECTIONS[i],
            )
            for i in range(3)
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # Run the 3 parallel calls
    try:
        results = asyncio.run(gather_all())
    except RuntimeError:
        # If there's already an event loop running (rare in Streamlit sync flow),
        # fall back to sequential.
        log("   ⚠️  Async loop conflict — falling back to sequential generation")
        results = []
        for i in range(3):
            try:
                results.append(asyncio.run(_generate_one_candidate(
                    anthropic_client, domain, research_data, pattern_data,
                    system_prompt, i + 1, VARIANT_DIRECTIONS[i],
                )))
            except Exception as e:
                results.append(e)

    # Filter out any exceptions, keep successful drafts
    candidates: list[str] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log(f"   ⚠️  Candidate {i+1} failed: {r}")
        else:
            candidates.append(r)

    if not candidates:
        log("❌ All 3 candidates failed to generate")
    else:
        log(f"✅ Post Synthesis complete — {len(candidates)}/3 candidates generated")

    return {
        "framework":  framework,
        "candidates": candidates,
        "domain":     domain,
    }