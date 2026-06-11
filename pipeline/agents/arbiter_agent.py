"""
Step 6 — The Synthesis Arbiter Agent
─────────────────────────────────────
Editor-in-Chief. Ingests three explicit inputs and produces the final,
production-ready humanized report:

  1. The original baseline draft (Step 3)
  2. The Perplexity factual correction list (Step 4)
  3. The structured style critiques from Council 2 (Step 5) —
     three lenses, possibly with unparsed-text warnings

Operational protocol (per spec):
  • Factual fixes  → NON-NEGOTIABLE. Mechanically strip and overwrite.
  • Stylistic fixes → DISCRETIONARY. Merge conflicting feedback, protect the
    core insights of the original draft.

Output: the final markdown report.
"""

import json
from typing import Callable, Optional

import anthropic

from config import ARBITER_MODEL, ARBITER_MAX_TOKENS
from pipeline.templates import ArticleTemplate, get_template, DEFAULT_TEMPLATE_KEY
from pipeline.observability import traced


SYSTEM_TEMPLATE = """You are the Editor-in-Chief of a top-tier publication. Three groups of people just sent
you feedback on a draft, and you have final say on what ships.

INPUTS YOU WILL RECEIVE:
  1. THE BASELINE DRAFT — the article as written.
  2. FACTUAL CORRECTIONS — a bulleted list from a live-web fact-checker.
  3. STYLE CRITIQUES — three separate lenses (Claude / GPT / Llama), each
     returning JSON critique blocks of the form
     {{original_text, issue, suggested_fix}}.

THE ARTICLE STRUCTURE — template: **{template_name}**

The draft must end up with EXACTLY this structure, in this order:
  • An opening 2-3 sentence hook (no header above it)
  • A blockquote starting with `> **The key insight:**`
  • These ## section headers, spelled exactly as shown, in this exact order:
    {section_list}

YOUR PROTOCOL — apply in this exact order:

A. FACTUAL FIXES — non-negotiable.
   • Every flagged claim in the Factual Corrections list MUST be replaced with
     the verified correction.
   • Do this mechanically. No interpretation. If the corrections list says
     "Claim X is wrong, replace with Y" — replace X with Y.
   • If the fact-checker returned 'NO_FACTUAL_ERRORS_FOUND', skip this step.

B. STYLISTIC FIXES — discretionary.
   • Read all three lenses together. They will overlap and sometimes conflict.
   • Adopt edits that strip robotic AI-isms, tighten cadence, and remove
     empty openers / passive constructions / hedge stacks.
   • REJECT edits that:
     - Change the meaning of a sentence
     - Strip a deliberate point of view
     - Replace a vivid concrete word with a generic one
     - Make conflicting demands (pick the better one, drop the other)
     - Try to rename, reorder, merge, or delete any of the template section
       headers listed above
     - Try to remove or rewrite the `> **The key insight:**` blockquote
   • If a lens returned a `[System Warning: Model feedback unparsed; interpret
     text directly]` block, read its raw text and extract whatever sensible
     suggestions you can find. Ignore noise.

C. PROTECT THE DRAFT'S CORE.
   • Do not restructure the article.
   • Do not change section headings — they must match the template list above
     verbatim.
   • Do not add new sections. Do not remove sections.
   • Preserve the opening hook (untitled, before the first ## header) and the
     `> **The key insight:**` blockquote exactly.
   • Preserve the author's perspective, voice, and rhythm choices.

D. OUTPUT.
   • Return ONLY the final markdown report.
   • No preamble. No diff. No commentary. No JSON. No bullet list of what
     you changed.
"""


def _format_council2_for_prompt(style_council_output: dict) -> str:
    """Render the three lenses (or their warning text) into one prompt block."""
    lines: list[str] = []
    for lens in style_council_output.get("lenses", []):
        name = lens.get("lens", "unknown").upper()
        lines.append(f"--- {name} LENS ---")
        warning = lens.get("warning")
        critiques = lens.get("critiques", [])
        if warning and not critiques:
            lines.append(warning)
        else:
            lines.append(json.dumps(critiques, ensure_ascii=False, indent=2))
            if warning:
                lines.append(f"(also: {warning})")
        lines.append("")
    return "\n".join(lines).strip()


@traced(run_type="chain", name="arbiter_agent")
def run_arbiter_agent(
    anthropic_client: anthropic.Anthropic,
    baseline_draft: str,
    factual_corrections: str,
    style_council_output: dict,
    template: Optional[ArticleTemplate] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Run Step 6 — the Synthesis Arbiter. Returns the final markdown report."""

    def log(msg: str):
        if callback:
            callback(msg)

    if template is None:
        template = get_template(DEFAULT_TEMPLATE_KEY)

    log("👨‍⚖️ Synthesis Arbiter — Editor-in-Chief assembling final draft")
    log(f"   📐 Template guardrail: {template.name}")
    log("   📜 Loading baseline draft into memory...")
    log("   🔍 Loading factual corrections (non-negotiable)...")
    log("   🎭 Loading style critiques from all three lenses (discretionary)...")

    council2_block = _format_council2_for_prompt(style_council_output)

    system_prompt = SYSTEM_TEMPLATE.format(
        template_name=template.name,
        section_list=template.section_list_inline(),
    )

    user_prompt = (
        "Apply the protocol. Return ONLY the final markdown report.\n\n"
        "═══════════════════════════════════════════\n"
        "1. BASELINE DRAFT\n"
        "═══════════════════════════════════════════\n"
        f"{baseline_draft}\n\n"
        "═══════════════════════════════════════════\n"
        "2. FACTUAL CORRECTIONS (Council 1 — non-negotiable)\n"
        "═══════════════════════════════════════════\n"
        f"{factual_corrections or 'NO_FACTUAL_ERRORS_FOUND'}\n\n"
        "═══════════════════════════════════════════\n"
        "3. STYLE CRITIQUES (Council 2 — discretionary, three lenses)\n"
        "═══════════════════════════════════════════\n"
        f"{council2_block or '(no critiques returned)'}\n\n"
        "═══════════════════════════════════════════\n\n"
        "Now produce the final report. Markdown only. No preamble, no diff, no commentary."
    )

    log("   🖋  Writing final humanized report...")

    response = anthropic_client.messages.create(
        model=ARBITER_MODEL,
        max_tokens=ARBITER_MAX_TOKENS,
        # temperature=ARBITER_TEMPERATURE,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    final = response.content[0].text.strip()
    log("✅ Arbiter complete — final report assembled")
    return final