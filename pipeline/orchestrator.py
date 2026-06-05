"""
pipeline/orchestrator.py
─────────────────────────
Wires the six-stage pipeline:

  1. Research              → Perplexity Sonar
  2. Pattern & Gap         → Claude (Opus 4.7)
  3. Synthesis             → Claude (Opus 4.8) — baseline draft
  4. Council 1 (Factual)   → Perplexity (sonar-reasoning-pro / DeepSeek R1)
  5. Council 2 (Style)     → Claude Opus 4.7 + GPT-5.5 + Llama 3.3 70B (Groq)
                             — parallel asyncio.gather
  6. Arbiter               → Claude Opus 4.8 — editor-in-chief

Returns a PipelineResult dataclass with every intermediate artifact preserved.
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

import anthropic

from pipeline.agents.research_agent   import run_research_agent
from pipeline.agents.pattern_agent    import run_pattern_agent
from pipeline.agents.synthesis_agent  import run_synthesis_agent
from pipeline.agents.factual_council  import run_factual_council
from pipeline.agents.style_council    import run_style_council
from pipeline.agents.arbiter_agent    import run_arbiter_agent
from utils.report_saver               import save_report


@dataclass
class PipelineResult:
    domain:               str
    depth:                str
    research_data:        dict = field(default_factory=dict)
    pattern_data:         dict = field(default_factory=dict)
    draft_report:         str  = ""
    factual_council:      dict = field(default_factory=dict)
    style_council:        dict = field(default_factory=dict)
    final_report:         str  = ""
    saved_paths:          dict = field(default_factory=dict)
    error:                Optional[str] = None


def run_pipeline(
    domain: str,
    depth: str = "Standard",
    output_folder: str = "reports",
    author_name: str = "",
    callback: Optional[Callable[[str, str], None]] = None,
) -> PipelineResult:
    """
    Run the full 6-stage research pipeline.

    callback(message, agent_key) — called for live progress updates.
    agent_key is one of:
      "research", "pattern", "synthesis", "factual", "style", "arbiter", "save"
    """

    def log(msg: str, agent: str = "orchestrator"):
        if callback:
            callback(msg, agent)

    result = PipelineResult(domain=domain, depth=depth)

    # ── Validate keys ─────────────────────────────────────────────
    anthropic_key  = os.getenv("ANTHROPIC_API_KEY")
    openai_key     = os.getenv("OPENAI_API_KEY")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    groq_key       = os.getenv("GROQ_API_KEY")

    if not anthropic_key:
        result.error = "ANTHROPIC_API_KEY not set (required for steps 2, 3, 5a, 6)."
        log(f"❌ {result.error}", "orchestrator")
        return result
    if not perplexity_key:
        result.error = "PERPLEXITY_API_KEY not set (required for steps 1 and 4)."
        log(f"❌ {result.error}", "orchestrator")
        return result

    log("🔑 Anthropic ✓ · Perplexity ✓", "orchestrator")
    if openai_key:
        log("🔑 OpenAI ✓ — GPT-5.5 style lens active", "orchestrator")
    else:
        log("⚠️  OpenAI key missing — GPT style lens will be skipped", "orchestrator")
    if groq_key:
        log("🔑 Groq ✓ — Llama 3.3 70B style lens active", "orchestrator")
    else:
        log("⚠️  Groq key missing — Llama lens falling back to Perplexity sonar", "orchestrator")

    anthropic_client = anthropic.Anthropic(api_key=anthropic_key)

    # ── Step 1: Research (Perplexity) ─────────────────────────────
    log("", "research")
    try:
        result.research_data = run_research_agent(
            domain=domain,
            depth=depth,
            callback=lambda msg: log(msg, "research"),
        )
    except Exception as e:
        result.error = f"Research Agent failed: {e}"
        log(f"❌ {result.error}", "research")
        return result

    # ── Step 2: Pattern & Gap (Claude Opus 4.7) ───────────────────
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

    # ── Step 3: Synthesis (Claude Opus 4.8) → baseline draft ──────
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

    # ── Step 4: Council 1 — Factual (sonar-reasoning-pro) ─────────
    log("", "factual")
    try:
        result.factual_council = run_factual_council(
            draft_report=result.draft_report,
            callback=lambda msg: log(msg, "factual"),
        )
    except Exception as e:
        log(f"⚠️  Factual Council failed ({e}) — proceeding without corrections", "factual")
        result.factual_council = {
            "corrections_markdown": "NO_FACTUAL_ERRORS_FOUND",
            "had_errors": False,
            "citations": [],
        }

    # ── Step 5: Council 2 — Style (parallel) ──────────────────────
    log("", "style")
    try:
        result.style_council = run_style_council(
            draft_report=result.draft_report,
            factual_corrections=result.factual_council.get("corrections_markdown", ""),
            callback=lambda msg: log(msg, "style"),
        )
    except Exception as e:
        log(f"⚠️  Style Council failed ({e}) — proceeding without style critiques", "style")
        result.style_council = {"lenses": []}

    # ── Step 6: Synthesis Arbiter (Claude Opus 4.8) ───────────────
    log("", "arbiter")
    try:
        result.final_report = run_arbiter_agent(
            anthropic_client=anthropic_client,
            baseline_draft=result.draft_report,
            factual_corrections=result.factual_council.get("corrections_markdown", ""),
            style_council_output=result.style_council,
            callback=lambda msg: log(msg, "arbiter"),
        )
    except Exception as e:
        log(f"⚠️  Arbiter failed ({e}) — falling back to baseline draft", "arbiter")
        result.final_report = result.draft_report

    # ── Save report ───────────────────────────────────────────────
    log("💾 Saving report to disk...", "save")
    try:
        result.saved_paths = save_report(
            report_markdown=result.final_report,
            domain=domain,
            output_folder=output_folder,
            author_name=author_name,
            research_data=result.research_data,
        )
        log(f"✅ Saved → {result.saved_paths['md_path']}", "save")
        log(f"✅ HTML  → {result.saved_paths['html_path']}", "save")
    except Exception as e:
        log(f"⚠️  Save failed: {e}", "save")

    log("🎉 Pipeline complete!", "orchestrator")
    return result