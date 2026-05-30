"""
pipeline/orchestrator.py
─────────────────────────
Wires the four agents together in sequence and returns a
PipelineResult dataclass with all outputs.
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

import anthropic

from pipeline.agents.research_agent  import run_research_agent
from pipeline.agents.pattern_agent   import run_pattern_agent
from pipeline.agents.synthesis_agent import run_synthesis_agent
from pipeline.agents.reviewer_agent  import run_reviewer_agent
from utils.report_saver import save_report


# ── optional Tavily ───────────────────────────────────────────────
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


@dataclass
class PipelineResult:
    domain:         str
    depth:          str
    research_data:  dict        = field(default_factory=dict)
    pattern_data:   dict        = field(default_factory=dict)
    draft_report:   str         = ""
    final_report:   str         = ""
    saved_paths:    dict        = field(default_factory=dict)
    error:          Optional[str] = None


def run_pipeline(
    domain: str,
    depth: str = "Standard",
    output_folder: str = "reports",
    callback: Optional[Callable[[str, str], None]] = None,
) -> PipelineResult:
    """
    Run the full research pipeline.

    callback(message, agent_key) — called for live progress updates.
    agent_key is one of: "research", "pattern", "synthesis", "reviewer", "save"
    """

    def log(msg: str, agent: str = "orchestrator"):
        if callback:
            callback(msg, agent)

    result = PipelineResult(domain=domain, depth=depth)

    # ── Init clients ──────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        result.error = "ANTHROPIC_API_KEY not set in environment."
        log(f"❌ {result.error}", "orchestrator")
        return result

    anthropic_client = anthropic.Anthropic(api_key=api_key)

    tavily_client = None
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if tavily_key and TAVILY_AVAILABLE:
        tavily_client = TavilyClient(api_key=tavily_key)
        log("🔑 Tavily API active — using as primary search provider", "orchestrator")
    else:
        log("🔍 No Tavily key found — using DuckDuckGo as fallback search", "orchestrator")

    # ── Agent 1: Research ─────────────────────────────────────────
    log("", "research")
    try:
        result.research_data = run_research_agent(
            anthropic_client=anthropic_client,
            domain=domain,
            depth=depth,
            tavily_client=tavily_client,
            callback=lambda msg: log(msg, "research"),
        )
    except Exception as e:
        result.error = f"Research Agent failed: {e}"
        log(f"❌ {result.error}", "research")
        return result

    # ── Agent 2: Pattern & Gap ────────────────────────────────────
    log("", "pattern")
    try:
        result.pattern_data = run_pattern_agent(
            anthropic_client=anthropic_client,
            research_data=result.research_data,
            callback=lambda msg: log(msg, "pattern"),
        )
    except Exception as e:
        result.error = f"Pattern Agent failed: {e}"
        log(f"❌ {result.error}", "pattern")
        return result

    # ── Agent 3: Synthesis ────────────────────────────────────────
    log("", "synthesis")
    try:
        result.draft_report = run_synthesis_agent(
            anthropic_client=anthropic_client,
            domain=domain,
            research_data=result.research_data,
            pattern_data=result.pattern_data,
            callback=lambda msg: log(msg, "synthesis"),
        )
    except Exception as e:
        result.error = f"Synthesis Agent failed: {e}"
        log(f"❌ {result.error}", "synthesis")
        return result

    # ── Agent 4: Reviewer ─────────────────────────────────────────
    log("", "reviewer")
    try:
        result.final_report = run_reviewer_agent(
            anthropic_client=anthropic_client,
            draft_report=result.draft_report,
            callback=lambda msg: log(msg, "reviewer"),
        )
    except Exception as e:
        # Fallback to draft if reviewer fails
        log(f"⚠️  Reviewer failed ({e}) — using draft", "reviewer")
        result.final_report = result.draft_report

    # ── Save report ───────────────────────────────────────────────
    log("💾 Saving report to disk...", "save")
    try:
        result.saved_paths = save_report(
            report_markdown=result.final_report,
            domain=domain,
            output_folder=output_folder,
            research_data=result.research_data,
        )
        log(f"✅ Saved → {result.saved_paths['md_path']}", "save")
        log(f"✅ HTML  → {result.saved_paths['html_path']}", "save")
    except Exception as e:
        log(f"⚠️  Save failed: {e}", "save")

    log("🎉 Pipeline complete!", "orchestrator")
    return result