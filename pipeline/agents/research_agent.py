# """
# Agent 1 — Research Agent
# ─────────────────────────
# Searches the web for hot topics, top voices, key data points, and
# emerging signals in the requested domain.
# Search priority: Tavily (primary) → DuckDuckGo (fallback)
# Claude handles structured extraction from raw results.
# """

# import json
# import time
# from typing import Callable, Optional

# import anthropic

# from config import RESEARCH_MODEL, RESEARCH_MAX_TOKENS, SEARCHES_PER_DEPTH

# # ── optional Tavily upgrade ────────────────────────────────────────
# try:
#     from tavily import TavilyClient
#     TAVILY_AVAILABLE = True
# except ImportError:
#     TAVILY_AVAILABLE = False

# # ── DuckDuckGo fallback ───────────────────────────────────────────
# try:
#     from duckduckgo_search import DDGS
#     DDG_AVAILABLE = True
# except ImportError:
#     DDG_AVAILABLE = False


# # ─────────────────────────────────────────────────────────────────
# #  Search helpers
# # ─────────────────────────────────────────────────────────────────

# def _search_tavily(client, query: str, max_results: int) -> list[dict]:
#     try:
#         resp = client.search(query=query, max_results=max_results, search_depth="advanced")
#         return [
#             {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
#             for r in resp.get("results", [])
#         ]
#     except Exception:
#         return []


# def _search_ddg(query: str, max_results: int) -> list[dict]:
#     try:
#         time.sleep(0.8)          # be polite to DDG
#         results = []
#         with DDGS() as ddgs:
#             for r in ddgs.text(query, max_results=max_results, timelimit="m"):
#                 results.append({
#                     "title": r.get("title", ""),
#                     "url":   r.get("href", r.get("url", "")),
#                     "content": r.get("body", ""),
#                 })
#         return results
#     except Exception:
#         return []


# def search_web(query: str, max_results: int = 7, tavily_client=None) -> list[dict]:
#     """
#     Search using Tavily (primary) → DuckDuckGo (fallback).
#     Tavily gives richer, more recent content — always preferred when key is set.
#     """
#     # ── Primary: Tavily ───────────────────────────────────────────
#     if tavily_client and TAVILY_AVAILABLE:
#         results = _search_tavily(tavily_client, query, max_results)
#         if results:
#             return results
#         # Tavily returned nothing — fall through to DDG

#     # ── Fallback: DuckDuckGo ──────────────────────────────────────
#     if DDG_AVAILABLE:
#         return _search_ddg(query, max_results)

#     return []


# # ─────────────────────────────────────────────────────────────────
# #  System prompt
# # ─────────────────────────────────────────────────────────────────

# SYSTEM = """You are a senior trend analyst at a top-tier research firm.
# Your job is to look at raw web search data and extract the *signal* from the noise.

# Rules:
# - Be specific. "AI is growing" is useless. "OpenAI's o3 scored 88% on ARC-AGI" is useful.
# - Only name voices/publications that genuinely appear in the data.
# - Hot topics must be things being actively discussed RIGHT NOW, not evergreen concepts.
# - Emerging signals are things gaining momentum but not yet mainstream coverage.
# - Return ONLY a valid JSON object — no markdown fences, no preamble, no commentary.

# Output schema (return exactly this structure):
# {
#   "domain": "string",
#   "hot_topics": [
#     {
#       "topic": "string",
#       "why_hot_now": "string — what specific event/release/debate caused this",
#       "key_claims": ["concrete claim 1", "concrete claim 2"],
#       "sources": ["url1", "url2"]
#     }
#   ],
#   "top_voices": [
#     {
#       "name": "string",
#       "affiliation": "string — company, publication, or independent",
#       "platform": "string — where they primarily publish",
#       "angle": "string — what unique angle or take they bring",
#       "recent_focus": "string — what they have been covering recently",
#       "url": "string"
#     }
#   ],
#   "key_narratives": [
#     {
#       "narrative": "string",
#       "supporters": ["name1", "name2"],
#       "pushback": "string — counter-view if one exists"
#     }
#   ],
#   "concrete_data_points": [
#     "string — specific stat, benchmark, figure, or finding"
#   ],
#   "emerging_signals": [
#     "string — early trend not yet covered by mainstream voices"
#   ]
# }"""


# # ─────────────────────────────────────────────────────────────────
# #  Main agent function
# # ─────────────────────────────────────────────────────────────────

# def run_research_agent(
#     anthropic_client: anthropic.Anthropic,
#     domain: str,
#     depth: str = "Standard",
#     tavily_client=None,
#     callback: Optional[Callable[[str], None]] = None,
# ) -> dict:
#     """
#     Run the Research Agent.

#     Returns a structured dict with hot_topics, top_voices,
#     key_narratives, concrete_data_points, emerging_signals.
#     """

#     def log(msg: str):
#         if callback:
#             callback(msg)

#     cfg = SEARCHES_PER_DEPTH.get(depth, SEARCHES_PER_DEPTH["Standard"])
#     n_queries   = cfg["queries"]
#     n_results   = cfg["results"]

#     log(f"🔍 Researching domain: **{domain}**")
#     log(f"   Depth: {depth} ({n_queries} queries × {n_results} results each)")

#     # ── Build queries ─────────────────────────────────────────────
#     all_queries = [
#         f"trending topics {domain} 2025 2026",
#         f"latest news {domain} this week",
#         f"top thought leaders influencers {domain}",
#         f"{domain} debate controversy opinion",
#         f"{domain} new research findings breakthroughs",
#         f"{domain} community discussion Reddit Twitter",
#         f"{domain} predictions future outlook",
#         f"criticism problems challenges {domain}",
#         f"{domain} case study real world results",
#         f"underrated overlooked {domain} insights",
#     ][:n_queries]

#     # ── Execute searches ──────────────────────────────────────────
#     raw_data = []
#     for i, query in enumerate(all_queries, 1):
#         log(f"   🌐 Search {i}/{n_queries}: *{query}*")
#         results = search_web(query, max_results=n_results, tavily_client=tavily_client)
#         raw_data.append({"query": query, "results": results})
#         if not results:
#             log(f"   ⚠️  No results for query {i}")

#     total_results = sum(len(d["results"]) for d in raw_data)
#     log(f"   📦 Retrieved {total_results} raw results — sending to Claude for analysis...")

#     # ── Truncate to stay within context ──────────────────────────
#     payload = json.dumps(raw_data, ensure_ascii=False)
#     if len(payload) > 120_000:
#         payload = payload[:120_000] + "\n... [truncated]"

#     # ── Claude analysis ───────────────────────────────────────────
#     response = anthropic_client.messages.create(
#         model=RESEARCH_MODEL,
#         max_tokens=RESEARCH_MAX_TOKENS,
#         system=[{
#             "type": "text",
#             "text": SYSTEM,
#             "cache_control": {"type": "ephemeral"}
#         }],
#         messages=[
#             {
#                 "role": "user",
#                 "content": (
#                     f'Analyze this web research data about "{domain}".\n\n'
#                     f"SEARCH DATA:\n{payload}\n\n"
#                     "Extract structured insights. Return only the JSON object — nothing else."
#                 ),
#             }
#         ],
#     )

#     raw_text = response.content[0].text.strip()

#     # ── Parse JSON ────────────────────────────────────────────────
#     try:
#         # Strip accidental markdown fences
#         if raw_text.startswith("```"):
#             raw_text = raw_text.split("```")[1]
#             if raw_text.startswith("json"):
#                 raw_text = raw_text[4:]
#         result = json.loads(raw_text)
#         result["domain"] = domain          # guarantee domain key
#         log("✅ Research Agent complete")
#         return result
#     except json.JSONDecodeError:
#         log("⚠️  JSON parse failed — returning raw text")
#         return {"domain": domain, "raw_output": raw_text}




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