"""
pipeline/orchestrator.py
─────────────────────────
Two output modes:

  output_mode = "article"  (default)
      6-stage flow:
        1 Research → 2 Pattern → 3 Synthesis → 4 Factual Council
        → 5 Style Council → 6 Arbiter → save_report

  output_mode = "post"
      3-stage flow (shorter, cheaper):
        1 Research → 2 Pattern → 3 Post Synthesis (3 parallel candidates)
        → save_post

Returns a PipelineResult dataclass with every intermediate artifact preserved.
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

import anthropic

from pipeline.agents.research_agent        import run_research_agent
from pipeline.agents.pattern_agent         import run_pattern_agent
from pipeline.agents.synthesis_agent       import run_synthesis_agent
from pipeline.agents.factual_council       import run_factual_council
from pipeline.agents.style_council         import run_style_council
from pipeline.agents.arbiter_agent         import run_arbiter_agent
from pipeline.agents.post_synthesis_agent  import run_post_synthesis_agent
from pipeline.templates                    import get_template, DEFAULT_TEMPLATE_KEY
from pipeline.personas                     import get_persona, DEFAULT_PERSONA_KEY
from pipeline.post_frameworks              import (
    get_post_framework, DEFAULT_POST_FRAMEWORK_KEY,
)
from pipeline.observability                import (
    traced,
    wrap_anthropic_client,
    make_session_id,
    attach_session_metadata,
    langsmith_status,
)
from utils.report_saver import save_report, save_post


@dataclass
class PipelineResult:
    domain:               str
    depth:                str
    output_mode:          str  = "article"
    template_key:         str  = DEFAULT_TEMPLATE_KEY
    persona_key:          str  = DEFAULT_PERSONA_KEY
    post_framework_key:   str  = DEFAULT_POST_FRAMEWORK_KEY
    session_id:           str  = ""
    research_data:        dict = field(default_factory=dict)
    pattern_data:         dict = field(default_factory=dict)
    draft_report:         str  = ""
    factual_council:      dict = field(default_factory=dict)
    style_council:        dict = field(default_factory=dict)
    final_report:         str  = ""
    post_candidates:      list = field(default_factory=list)
    saved_paths:          dict = field(default_factory=dict)
    error:                Optional[str] = None


@traced(run_type="chain", name="research_pipeline")
def run_pipeline(
    domain: str,
    depth: str = "Standard",
    output_mode: str = "article",              # "article" | "post"
    template_key: str = DEFAULT_TEMPLATE_KEY,
    persona_key: str = DEFAULT_PERSONA_KEY,
    post_framework_key: str = DEFAULT_POST_FRAMEWORK_KEY,
    md_folder: str = "reports",
    html_folder: str = "reports",
    posts_folder: str = "posts",
    author_name: str = "",
    callback: Optional[Callable[[str, str], None]] = None,
) -> PipelineResult:
    """
    Run the pipeline in either article or post mode.

    output_mode         — "article" runs the full 6-stage flow;
                          "post" runs a 3-stage flow generating 3 candidates.
    md_folder           — destination for the article .md
    html_folder         — destination for the article _publish.html
    posts_folder        — destination for the post candidates .md
    template_key        — article structure (article mode only)
    persona_key         — writer voice (both modes)
    post_framework_key  — LinkedIn post framework (post mode only)

    callback(message, agent_key) — live progress updates.
    """

    def log(msg: str, agent: str = "orchestrator"):
        if callback:
            callback(msg, agent)

    # ── Look up template + persona + post framework ──────────────
    template       = get_template(template_key)
    persona        = get_persona(persona_key)
    post_framework = get_post_framework(post_framework_key)
    session_id     = make_session_id(domain)

    result = PipelineResult(
        domain=domain,
        depth=depth,
        output_mode=output_mode,
        template_key=template.key,
        persona_key=persona.key,
        post_framework_key=post_framework.key,
        session_id=session_id,
    )

    attach_session_metadata(
        session_id,
        domain=domain,
        depth=depth,
        output_mode=output_mode,
        template=template.key,
        persona=persona.key,
        post_framework=post_framework.key,
    )

    log(langsmith_status(), "orchestrator")
    log(f"🧵 Session ID: {session_id}", "orchestrator")
    log(f"📤 Output mode: {output_mode.upper()}", "orchestrator")
    log(f"🎙️  Persona: {persona.name}", "orchestrator")
    if output_mode == "article":
        log(f"📐 Article template: {template.name}", "orchestrator")
    else:
        log(f"🧩 Post framework: {post_framework.name}", "orchestrator")

    # ── Validate keys ─────────────────────────────────────────────
    anthropic_key  = os.getenv("ANTHROPIC_API_KEY")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")

    if not anthropic_key:
        result.error = "ANTHROPIC_API_KEY not set."
        log(f"❌ {result.error}", "orchestrator")
        return result
    if not perplexity_key:
        result.error = "PERPLEXITY_API_KEY not set."
        log(f"❌ {result.error}", "orchestrator")
        return result

    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key   = os.getenv("GROQ_API_KEY")
    log("🔑 Anthropic ✓ · Perplexity ✓", "orchestrator")
    if output_mode == "article":
        if openai_key: log("🔑 OpenAI ✓ — GPT-5.5 style lens active", "orchestrator")
        else:          log("⚠️  OpenAI key missing — GPT style lens will be skipped", "orchestrator")
        if groq_key:   log("🔑 Groq ✓ — Llama 3.3 70B style lens active", "orchestrator")
        else:          log("⚠️  Groq key missing — Llama lens falls back to Perplexity sonar", "orchestrator")

    anthropic_client = wrap_anthropic_client(anthropic.Anthropic(api_key=anthropic_key))

    # ═══════════════════════════════════════════════════════════════
    #  Stage 1: Research (both modes)
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    #  Stage 2: Pattern & Gap (both modes)
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    #  BRANCH: post mode ends here after Post Synthesis
    # ═══════════════════════════════════════════════════════════════
    if output_mode == "post":
        log("", "post_synthesis")
        try:
            synth_out = run_post_synthesis_agent(
                anthropic_client=anthropic_client,
                domain=domain,
                research_data=result.research_data,
                pattern_data=result.pattern_data,
                framework=post_framework,
                persona=persona,
                callback=lambda msg: log(msg, "post_synthesis"),
            )
            result.post_candidates = synth_out["candidates"]
        except Exception as e:
            result.error = f"Post Synthesis failed: {e}"
            log(f"❌ {result.error}", "post_synthesis")
            return result

        if not result.post_candidates:
            result.error = "No post candidates were generated."
            log(f"❌ {result.error}", "post_synthesis")
            return result

        # ── Save posts ─────────────────────────────────────────────
        log("💾 Saving post candidates to disk...", "save")
        try:
            result.saved_paths = save_post(
                candidates=result.post_candidates,
                domain=domain,
                framework_name=post_framework.name,
                posts_folder=posts_folder,
            )
            log(f"✅ Saved → {result.saved_paths['post_path']}", "save")
        except Exception as e:
            log(f"⚠️  Save failed: {e}", "save")

        log("🎉 Post pipeline complete!", "orchestrator")
        return result

    # ═══════════════════════════════════════════════════════════════
    #  Article mode continues: Stages 3, 4, 5, 6
    # ═══════════════════════════════════════════════════════════════

    # ── Stage 3: Synthesis (Claude Opus 4.8) → baseline draft ─────
    log("", "synthesis")
    try:
        result.draft_report = run_synthesis_agent(
            anthropic_client=anthropic_client,
            domain=domain,
            research_data=result.research_data,
            pattern_data=result.pattern_data,
            template=template,
            persona=persona,
            callback=lambda msg: log(msg, "synthesis"),
        )
    except Exception as e:
        result.error = f"Synthesis Agent failed: {e}"
        log(f"❌ {result.error}", "synthesis")
        return result

    # ── Stage 4: Council 1 — Factual ──────────────────────────────
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

    # ── Stage 5: Council 2 — Style (parallel) ─────────────────────
    log("", "style")
    try:
        result.style_council = run_style_council(
            draft_report=result.draft_report,
            factual_corrections=result.factual_council.get("corrections_markdown", ""),
            persona=persona,
            callback=lambda msg: log(msg, "style"),
        )
    except Exception as e:
        log(f"⚠️  Style Council failed ({e}) — proceeding without style critiques", "style")
        result.style_council = {"lenses": []}

    # ── Stage 6: Synthesis Arbiter ────────────────────────────────
    log("", "arbiter")
    try:
        result.final_report = run_arbiter_agent(
            anthropic_client=anthropic_client,
            baseline_draft=result.draft_report,
            factual_corrections=result.factual_council.get("corrections_markdown", ""),
            style_council_output=result.style_council,
            template=template,
            callback=lambda msg: log(msg, "arbiter"),
        )
    except Exception as e:
        log(f"⚠️  Arbiter failed ({e}) — falling back to baseline draft", "arbiter")
        result.final_report = result.draft_report

    # ── Save article ──────────────────────────────────────────────
    log("💾 Saving report to disk...", "save")
    try:
        result.saved_paths = save_report(
            report_markdown=result.final_report,
            domain=domain,
            md_folder=md_folder,
            html_folder=html_folder,
            author_name=author_name,
            research_data=result.research_data,
        )
        log(f"✅ Saved → {result.saved_paths['md_path']}", "save")
        log(f"✅ HTML  → {result.saved_paths['html_path']}", "save")
    except Exception as e:
        log(f"⚠️  Save failed: {e}", "save")

    log("🎉 Article pipeline complete!", "orchestrator")
    return result