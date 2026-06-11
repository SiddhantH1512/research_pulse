"""
Agent 1 — Research Agent (Perplexity Sonar)
────────────────────────────────────────────
Swapped from Tavily/DDG → Perplexity Sonar Engine.

Perplexity does retrieval + summarisation in a single hop, so we no longer
need a separate scraper or a secondary reading agent. We ask Sonar for a
citation-grounded, structured JSON brief that matches the schema the rest of
the pipeline already expects (hot_topics, top_voices, key_narratives,
concrete_data_points, emerging_signals).

If Perplexity returns malformed JSON we fall back to embedding the raw
prose brief under `raw_output` — downstream agents (Pattern + Synthesis)
gracefully degrade rather than crash.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from config import (
    SEARCHES_PER_DEPTH,
    RESEARCH_TEMPERATURE,
    RESEARCH_MAX_TOKENS,
)
from pipeline.clients.perplexity_client import perplexity_complete
from pipeline.observability import traced


SYSTEM = """You are a senior trend analyst at a top-tier research firm.
You have live web access. Your job is to extract the SIGNAL from real-time
sources and return a structured research brief.

Rules:
- Be specific. "AI is growing" is useless. "OpenAI's o3 scored 88% on ARC-AGI" is useful.
- Only name voices/publications that genuinely appear in your sources.
- Hot topics must be things being actively discussed RIGHT NOW (last 1–4 weeks).
- Emerging signals are things gaining momentum but not yet mainstream.
- Cite real URLs in the `sources` arrays — the ones you actually used.
- Return ONLY a valid JSON object. No prose, no markdown fences, no preamble.

Output schema (return exactly this structure, nothing else):
{
  "domain": "string",
  "hot_topics": [
    {
      "topic": "string",
      "why_hot_now": "string — what specific event/release/debate caused this",
      "key_claims": ["concrete claim 1", "concrete claim 2"],
      "sources": ["url1", "url2"]
    }
  ],
  "top_voices": [
    {
      "name": "string",
      "affiliation": "string",
      "platform": "string",
      "angle": "string — their unique take",
      "recent_focus": "string",
      "url": "string"
    }
  ],
  "key_narratives": [
    {
      "narrative": "string",
      "supporters": ["name1", "name2"],
      "pushback": "string — counter-view if one exists"
    }
  ],
  "concrete_data_points": [
    "string — specific stat, benchmark, figure, or finding (with attribution)"
  ],
  "emerging_signals": [
    "string — early trend not yet covered by mainstream voices"
  ]
}"""


def _extract_json(raw: str) -> Optional[dict]:
    """Try hard to recover a JSON object from a model response."""
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Last-ditch: greedy match the outermost { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


@traced(run_type="chain", name="research_agent")
def run_research_agent(
    domain: str,
    depth: str = "Standard",
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run the Research Agent against Perplexity Sonar.

    Returns:
        dict with hot_topics, top_voices, key_narratives,
              concrete_data_points, emerging_signals, citations.
        If parsing fails: {"domain": ..., "raw_output": ..., "citations": [...]}.
    """

    def log(msg: str):
        if callback:
            callback(msg)

    cfg = SEARCHES_PER_DEPTH.get(depth, SEARCHES_PER_DEPTH["Standard"])
    model = cfg["model"]
    max_tokens = cfg["max_tokens"]

    log(f"🔍 Researching domain: **{domain}**")
    log(f"   Engine: Perplexity Sonar · model: `{model}` · depth: {depth}")
    log("   🌐 Querying live web sources...")

    user_prompt = (
        f'Produce a research brief on "{domain}".\n\n'
        "Focus on what is happening RIGHT NOW: the active debates, the loudest voices, "
        "the freshest data points, and the signals that haven't broken into mainstream coverage yet. "
        "Use the live web. Cite the URLs you actually used in each `sources` array.\n\n"
        "Return ONLY the JSON object specified in the system prompt — nothing else."
    )

    result = perplexity_complete(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        model=model,
        temperature=RESEARCH_TEMPERATURE,
        max_tokens=max_tokens,
    )

    content   = result["content"]
    citations = result["citations"]

    log(f"   📚 Perplexity returned {len(citations)} citation(s)")

    parsed = _extract_json(content)
    if parsed is None:
        log("⚠️  JSON parse failed — passing raw brief downstream")
        return {
            "domain":      domain,
            "raw_output":  content,
            "citations":   citations,
        }

    parsed["domain"]    = domain          # guarantee
    parsed["citations"] = citations       # surface Perplexity sources
    log("✅ Research Agent complete")
    return parsed