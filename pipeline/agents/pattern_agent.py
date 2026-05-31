"""
Agent 2 — Pattern & Gap Agent
──────────────────────────────
Takes the research output and does two things:
  1. Extracts the engagement hook patterns used by top voices
  2. Identifies the angles and nuances that no one (or very few) are covering
"""

import json
from typing import Callable, Optional

import anthropic

from config import PATTERN_MODEL, PATTERN_MAX_TOKENS


SYSTEM = """You are a content strategist and media analyst who reverse-engineers why content goes viral
and what angles everyone is missing.

Given structured research data from a domain, your job is to:

1. HOOK PATTERNS — How are top voices framing their content?
   Look for: opening hook structures, emotional levers, narrative devices,
   contrast/tension setups, data-first vs story-first approaches.

2. GAPS & MISSED NUANCES — What is the majority of voices NOT saying?
   These must be evidence-based gaps — you can only claim something is missed
   if you can point to its *absence* in the research data.
   Look for: counter-intuitive angles, underserved audiences, second-order effects,
   practical implications that theorists skip, expert blind spots.

Return ONLY valid JSON — no preamble, no markdown, no commentary.

Output schema:
{
  "hook_patterns": [
    {
      "pattern_name": "string — short memorable name",
      "description": "string — how this pattern works",
      "example": "string — concrete example from the research data",
      "why_it_works": "string — psychological or strategic reason"
    }
  ],
  "audience_engagement_tactics": [
    {
      "tactic": "string",
      "used_by": ["voice name 1", "voice name 2"],
      "effectiveness_signal": "string — why this seems to resonate"
    }
  ],
  "gaps_and_missed_angles": [
    {
      "gap": "string — the specific angle being missed",
      "evidence_of_absence": "string — what in the research shows this is missing",
      "why_it_matters": "string — why this gap is worth filling",
      "potential_angle": "string — how to frame this for an article"
    }
  ],
  "contrarian_takes": [
    {
      "mainstream_belief": "string — what everyone is saying",
      "contrarian_view": "string — the opposite or nuanced counter-view",
      "supporting_evidence": "string — any data or signal that supports the contrarian view"
    }
  ],
  "underserved_audiences": [
    {
      "audience": "string — who is being ignored",
      "what_they_need": "string — what content would serve them"
    }
  ],
  "recommended_angles": [
    {
      "angle": "string — specific recommended angle for the report",
      "rationale": "string — why this angle is differentiated"
    }
  ]
}"""


def run_pattern_agent(
    anthropic_client: anthropic.Anthropic,
    research_data: dict,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run the Pattern & Gap Analysis Agent.

    Takes research_data (output of research_agent) and returns
    hook patterns, gaps, contrarian takes, and recommended angles.
    """

    def log(msg: str):
        if callback:
            callback(msg)

    domain = research_data.get("domain", "the domain")
    log(f"🔎 Analyzing patterns and gaps in: **{domain}**")

    payload = json.dumps(research_data, ensure_ascii=False, indent=2)
    if len(payload) > 80_000:
        payload = payload[:80_000] + "\n... [truncated]"

    log("   🧠 Identifying hook patterns used by top voices...")
    log("   🕵️  Hunting for gaps the majority are missing...")

    response = anthropic_client.messages.create(
        model=PATTERN_MODEL,
        max_tokens=PATTERN_MAX_TOKENS,
        system=[{
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[
            {
                "role": "user",
                "content": (
                    f'Analyze this research data about "{domain}".\n\n'
                    f"RESEARCH DATA:\n{payload}\n\n"
                    "Identify hook patterns, engagement tactics, gaps, and recommended angles. "
                    "Return only the JSON object — nothing else."
                ),
            }
        ],
    )

    raw_text = response.content[0].text.strip()

    try:
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        result = json.loads(raw_text)
        log("✅ Pattern & Gap Agent complete")
        return result
    except json.JSONDecodeError:
        log("⚠️  JSON parse failed — returning raw output")
        return {"raw_output": raw_text}