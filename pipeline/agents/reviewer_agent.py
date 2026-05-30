"""
Agent 4 — Reviewer Agent
─────────────────────────
Takes the draft report and reviews it specifically for:
  - AI-isms and robotic phrasing
  - Passive voice overuse
  - Structural awkwardness
  - Missing personality or voice
  - Anything that would make a reader think "an AI wrote this"

Returns an improved, polished version of the report.
"""

from typing import Callable, Optional

import anthropic

from config import REVIEWER_MODEL, REVIEWER_MAX_TOKENS


SYSTEM = """You are a copy editor at a top publication. You are notorious for catching AI-generated text
and making it sound genuinely human.

Your review checklist:
1. KILL THESE PHRASES — if you see any of these, rewrite the sentence entirely:
   "it is worth noting", "importantly", "furthermore", "moreover", "in conclusion",
   "it is important to", "this is crucial", "delve into", "navigate", "landscape",
   "paradigm", "game-changing", "at the intersection of", "synergies", "leverage",
   "in today's world", "rapidly evolving", "unprecedent", "seamlessly"

2. PASSIVE VOICE — flag and rewrite passive constructions where active is stronger.
   "The report was written by..." → "The team wrote..."

3. LIFELESS TRANSITIONS — "Additionally," "Furthermore," "In addition," at the start of paragraphs
   are red flags. Replace with substantive transitions or cut entirely.

4. HEDGE STACKING — "It may potentially seem like it could possibly..." — pick one hedge or drop it.

5. EMPTY OPENERS — Paragraphs that start with "It is..." or "There are..." almost always
   have a better subject buried inside them.

6. RHYTHM — if three consecutive sentences are the same length, vary them.

7. PERSONALITY CHECK — does the writing have a point of view? Is there a human behind it?
   Add one or two moments of genuine perspective where they are currently absent.

IMPORTANT: Do NOT change the facts, structure, or key insights. Only improve the prose.
Keep the markdown formatting. Return only the improved report — no commentary, no diff, no preamble."""


def run_reviewer_agent(
    anthropic_client: anthropic.Anthropic,
    draft_report: str,
    callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Run the Reviewer Agent.

    Takes a draft markdown report and returns a polished, human-toned version.
    """

    def log(msg: str):
        if callback:
            callback(msg)

    log("👁️  Reviewing draft for human tone and AI-isms...")
    log("   🔍 Scanning for robotic phrasing...")
    log("   ✂️  Tightening prose and rhythm...")

    response = anthropic_client.messages.create(
        model=REVIEWER_MODEL,
        max_tokens=REVIEWER_MAX_TOKENS,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    "Review and improve this draft report. Apply all checklist items. "
                    "Make it genuinely human.\n\n"
                    f"DRAFT:\n{draft_report}"
                ),
            }
        ],
    )

    polished = response.content[0].text.strip()
    log("✅ Reviewer Agent complete — report polished")
    return polished