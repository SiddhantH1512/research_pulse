"""
Step 4 — Council 1: Factual Verification Council
────────────────────────────────────────────────
Feeds the baseline draft to Perplexity Sonar for live-web fact checking.

Model: sonar-reasoning-pro  (DeepSeek-R1-powered).
  • Catches subtler factual errors than plain sonar-pro:
    misattributed causation, conflated timeframes, off-by-version claims.
  • Emits a <think>…</think> chain-of-thought block in the content — we
    strip it before passing corrections to the Arbiter.

Temperature 0.0 — pure determinism. There is nothing creative to preserve
in a fact-check.

Constraints (per spec):
  • The model MUST NOT rewrite the draft.
  • It isolates: metrics, dates, public names, and analytical claims.
  • Output: a clean, minimal markdown bulleted list of factual errors and
    real-time corrections, or `NO_FACTUAL_ERRORS_FOUND` if everything is clean.
"""

import re
from typing import Callable, Optional

from config import (
    FACTUAL_COUNCIL_MODEL,
    FACTUAL_COUNCIL_MAX_TOKENS,
    FACTUAL_COUNCIL_TEMPERATURE,
)
from pipeline.clients.perplexity_client import perplexity_complete
from pipeline.observability import traced


SYSTEM = """You are a fact-checker at a major newsroom with live web access.

Your job is to validate a draft article. You are NOT a copy editor and you are NOT
a stylist. You do not rewrite, you do not suggest tone changes, you do not paraphrase.

You verify ONLY these categories of claims:
  • Specific metrics, statistics, percentages, dollar amounts
  • Dates, timelines, "X launched in Y"
  • Named public figures, companies, products, publications
  • Quantitative analytical claims ("X grew 40% YoY", "Y is the largest…")

For each item you check, decide:
  (a) Confirmed — do nothing.
  (b) Wrong — flag it and provide the correct value with a source URL.
  (c) Unverifiable from public web sources — flag as such.

Output FORMAT — strictly this markdown structure, nothing else:

If errors found:
- **Claim:** "<exact phrase from draft>"
  **Issue:** <what's wrong>
  **Correction:** <verified replacement>
  **Source:** <URL>

If no errors found, return exactly:
NO_FACTUAL_ERRORS_FOUND

No preamble. No closing remarks. No rewriting of the draft. No stylistic notes.
Do NOT include your reasoning chain in the final output — only the corrections list."""


# ─────────────────────────────────────────────────────────────────
#  <think>…</think> stripper for reasoning-tier Sonar
# ─────────────────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning_block(text: str) -> str:
    """Remove sonar-reasoning-pro's <think>…</think> chain-of-thought."""
    if not text:
        return text
    cleaned = _THINK_RE.sub("", text)
    # Handle truncated/unclosed think blocks too (rare but possible).
    cleaned = re.sub(r"^.*?</think>", "", cleaned, count=1, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


@traced(run_type="chain", name="factual_council")
def run_factual_council(
    draft_report: str,
    callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run Council 1 — Factual Verification.

    Returns:
        {
          "corrections_markdown": str,
          "had_errors":            bool,
          "citations":             list,
        }
    """

    def log(msg: str):
        if callback:
            callback(msg)

    log(f"🔬 Council 1 — Factual Verification (`{FACTUAL_COUNCIL_MODEL}`)")
    log("   📏 Isolating metrics, dates, names, and analytical claims...")
    log("   🧠 DeepSeek-R1 reasoning over live web sources...")

    user_prompt = (
        "Fact-check the draft below against the live web. "
        "Do NOT rewrite anything. Return only a markdown bullet list of "
        "verified errors in the exact format specified, or "
        "`NO_FACTUAL_ERRORS_FOUND` if everything checks out.\n\n"
        "DRAFT:\n```\n" + draft_report + "\n```"
    )

    result = perplexity_complete(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        model=FACTUAL_COUNCIL_MODEL,
        temperature=FACTUAL_COUNCIL_TEMPERATURE,
        max_tokens=FACTUAL_COUNCIL_MAX_TOKENS,
    )

    raw_content = result["content"]
    corrections = _strip_reasoning_block(raw_content).strip()
    citations   = result["citations"]

    had_errors = (
        bool(corrections)
        and "NO_FACTUAL_ERRORS_FOUND" not in corrections.upper()
    )

    if had_errors:
        n_bullets = corrections.count("**Claim:**")
        log(f"   ⚠️  Found {n_bullets} factual flag(s)")
    else:
        log("   ✅ No factual errors flagged")

    log("✅ Factual Council complete")

    return {
        "corrections_markdown": corrections,
        "had_errors":           had_errors,
        "citations":            citations,
    }