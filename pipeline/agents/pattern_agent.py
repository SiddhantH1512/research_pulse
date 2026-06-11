"""
Agent 2 — Pattern & Gap Agent
──────────────────────────────
Reads the Perplexity research brief and extracts:
  1. Hook patterns top voices use
  2. Audience engagement tactics
  3. Gaps & missed nuances
  4. Contrarian takes
  5. Underserved audiences
  6. Recommended angles

Unchanged from the Tavily-era version other than:
  - Reads from Perplexity-shaped research_data (citations may be present)
  - Temperature is sourced from config (deterministic-ish analytic mode)
  - Gracefully handles the `raw_output` fallback path
"""

import json
import re
from typing import Callable, Optional

import anthropic

from config import PATTERN_MODEL, PATTERN_MAX_TOKENS
from pipeline.observability import traced


SYSTEM = """You are a content strategist and media analyst who reverse-engineers why content goes
viral and what angles everyone is missing.

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
      "pattern_name": "string",
      "description": "string",
      "example": "string — concrete example from the research data",
      "why_it_works": "string"
    }
  ],
  "audience_engagement_tactics": [
    {
      "tactic": "string",
      "used_by": ["voice name 1", "voice name 2"],
      "effectiveness_signal": "string"
    }
  ],
  "gaps_and_missed_angles": [
    {
      "gap": "string",
      "evidence_of_absence": "string",
      "why_it_matters": "string",
      "potential_angle": "string"
    }
  ],
  "contrarian_takes": [
    {
      "mainstream_belief": "string",
      "contrarian_view": "string",
      "supporting_evidence": "string"
    }
  ],
  "underserved_audiences": [
    {
      "audience": "string",
      "what_they_need": "string"
    }
  ],
  "recommended_angles": [
    {
      "angle": "string",
      "rationale": "string"
    }
  ]
}"""


def _extract_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


@traced(run_type="chain", name="pattern_agent")
def run_pattern_agent(
    anthropic_client: anthropic.Anthropic,
    research_data: dict,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Run the Pattern & Gap Analysis Agent."""

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
        # temperature=PATTERN_TEMPERATURE,
        system=[{
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"},
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
    parsed = _extract_json(raw_text)

    if parsed is None:
        log("⚠️  JSON parse failed — returning raw output")
        return {"raw_output": raw_text}

    log("✅ Pattern & Gap Agent complete")
    return parsed