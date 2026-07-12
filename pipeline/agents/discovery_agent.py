"""
Discovery Agent (standalone helper)
────────────────────────────────────
Optional pre-step for LinkedIn post mode. Runs on demand — not part of
run_pipeline(). When the user has no topic in mind, this agent surfaces
5-8 recent, high-signal candidates scored against the 6-criteria filter.

Contract:
    Input:  none (or optional focus_area hint like "enterprise AI")
    Output: list of candidate dicts, each with topic, score, criteria hits,
            and a 2-sentence rationale.

The user picks one card in the UI; that topic becomes the input to the
normal post-generation flow. Discovery itself never triggers generation.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from config import RESEARCH_TEMPERATURE
from pipeline.clients.perplexity_client import perplexity_complete
from pipeline.observability import traced


# Use sonar-pro for discovery — needs strong web + good structuring
DISCOVERY_MODEL = "sonar-pro"
DISCOVERY_MAX_TOKENS = 6144


SYSTEM = """You are a senior editor at an AI-industry publication. Your job is to scan the last
7-14 days of AI industry developments and surface story angles worth a considered
LinkedIn post from a thoughtful practitioner — NOT news summaries, NOT headline recaps.

You have live web access. You will return 5 to 8 candidate story angles.

Every candidate must be evaluated against these 6 criteria. Score each as HIT or MISS
based on strict standards, not generosity:

1. TIMELY — Something concrete changed in the last 7-14 days. A launch, a study, a
   quote, an earnings call, a regulatory move, a benchmark, a leaked doc. Not
   evergreen speculation. Not "AI is growing." A specific dated event or artifact.

2. NON-OBVIOUS — Reading the headline should NOT tell you what the post's angle is.
   "OpenAI released GPT-6" is a headline. "OpenAI's GPT-6 launch changed the pricing
   dynamics between hyperscalers and API-first startups" is a non-obvious angle.

3. AUDIENCE-SPECIFIC — Name the specific audience who should care. AI practitioners?
   Product teams? Enterprise buyers? Founders? Policy people? If the post would
   interest "everyone in AI," it's too vague — mark as MISS.

4. POINT OF VIEW — The angle takes a stance, not just a summary. Can you write it
   as "I think X, and here's why" — or would the post be strictly descriptive?

5. EVIDENCE-BACKED — There is at least one strong primary source: a report, benchmark,
   earnings call, research paper, or credible news article. Cite the URL.

6. DISCUSSION-WORTHY — There is genuine tension, uncertainty, or trade-off. Smart
   people could disagree. If the post's conclusion is what everyone already believes,
   mark as MISS.

STANDARD: A candidate is worth surfacing if it scores at least 4/6. Reject anything
scoring 3 or below. Better to return 4 strong candidates than 8 mediocre ones.

Return ONLY a valid JSON object matching this schema — no preamble, no markdown fences:

{
  "candidates": [
    {
      "topic": "string — the specific angle, 8-14 words, written as it would appear in a topic field",
      "story": "string — 2 sentences describing what actually happened and what it means",
      "criteria": {
        "timely": true,
        "non_obvious": true,
        "audience_specific": true,
        "point_of_view": true,
        "evidence_backed": true,
        "discussion_worthy": false
      },
      "score": 5,
      "audience": "string — who specifically should care",
      "primary_source": "string — URL of the strongest supporting source",
      "why_it_scores": "string — 1 sentence on why this passes the filter"
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
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


@traced(run_type="chain", name="discovery_agent")
def run_discovery_agent(
    focus_area: str = "",
    max_candidates: int = 8,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run the Discovery Agent to surface topic candidates for LinkedIn posts.

    focus_area — optional narrowing hint, e.g. "enterprise AI adoption"
                 or "AI infrastructure". Leave blank for broad AI industry scan.

    Returns:
        {
          "candidates": [ {topic, story, criteria, score, audience,
                          primary_source, why_it_scores}, ... ],
          "citations":  [ ...perplexity citations... ],
          "focus_area": str,
        }
    """
    def log(msg: str):
        if callback:
            callback(msg)

    focus_block = (
        f" Focus specifically within: {focus_area}." if focus_area.strip() else
        " Scan across the AI industry broadly — enterprise adoption, model releases, "
        "infrastructure, funding, regulation, agentic workflows, developer tooling, "
        "research findings, and unusual business-model shifts."
    )

    log("🔍 Discovery — scanning the last 7-14 days of AI-industry signal")
    if focus_area.strip():
        log(f"   🎯 Focus area: {focus_area}")
    log("   ⚖️  Scoring against 6-criteria filter (must hit ≥ 4)")

    user_prompt = (
        "Return up to "
        f"{max_candidates} candidate story angles that pass the 6-criteria filter.{focus_block}\n\n"
        "Each candidate should be something a thoughtful AI practitioner could write "
        "a considered LinkedIn post about — not a news recap. Prioritize angles where "
        "your interpretation adds value beyond the primary source.\n\n"
        "Reject:\n"
        "  • Anything without a concrete recent event or artifact\n"
        "  • Anything scoring 3 or fewer criteria\n"
        "  • Anything with no identifiable primary source URL\n"
        "  • Vague trends dressed up as topics ('AI is transforming X')\n\n"
        "Return the JSON object specified in the system prompt. Nothing else."
    )

    result = perplexity_complete(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        model=DISCOVERY_MODEL,
        temperature=RESEARCH_TEMPERATURE,
        max_tokens=DISCOVERY_MAX_TOKENS,
    )

    content   = result["content"]
    citations = result["citations"]

    parsed = _extract_json(content)
    if parsed is None or "candidates" not in parsed:
        log("⚠️  Discovery JSON parse failed — no candidates returned")
        return {
            "candidates": [],
            "citations":  citations,
            "focus_area": focus_area,
            "raw_output": content,
        }

    # Sort by score descending, keep only 4+
    candidates = [c for c in parsed["candidates"] if c.get("score", 0) >= 4]
    candidates.sort(key=lambda c: c.get("score", 0), reverse=True)

    log(f"✅ Discovery complete — surfaced {len(candidates)} candidate(s) scoring ≥ 4/6")

    return {
        "candidates": candidates,
        "citations":  citations,
        "focus_area": focus_area,
    }