"""
Agent 3 — Synthesis Agent
──────────────────────────
Takes the research + pattern output and writes the baseline draft report.
This is the input to Council 1 (factual) and Council 2 (style), and ultimately
the Arbiter.

Tone: senior tech journalist (Wired / MIT Tech Review / Atlantic). Conversational
but credible, opinionated, varied rhythm, no AI-isms.
"""

import json
from typing import Callable, Optional

import anthropic

from config import SYNTHESIS_MODEL, SYNTHESIS_MAX_TOKENS, SYNTHESIS_TEMPERATURE


SYSTEM = """You are a senior technology journalist who has written for publications like Wired, MIT
Tech Review, and The Atlantic. You make complex topics genuinely interesting — not by
dumbing them down, but by finding the human angle, the stakes, and the story.

Your writing has a specific style:
- Conversational but credible — you talk with the reader, not at them
- You lead with what matters, not with context
- Short sentences when making a point. Longer ones when you are building toward something.
- You use real examples and analogies, not abstract descriptions
- You vary your rhythm — some punchy one-liners, some developed paragraphs
- You are not afraid to have a perspective
- You NEVER use these phrases: "it is worth noting", "in conclusion", "furthermore",
  "it is important to understand", "delve into", "in today's rapidly evolving landscape",
  "at the intersection of", "game-changing", "paradigm shift", "leverage", "paramount",
  "testament to", "navigate the landscape"
- You do not overuse bullet points — prose tells a better story
- You occasionally use rhetorical questions to pull the reader forward

REPORT STRUCTURE to follow (use markdown headers):
1. A punchy title (## Title)
2. A 2-3 sentence opening that hooks the reader immediately — no scene-setting
3. THE KEY INSIGHT — a markdown blockquote placed immediately after the opening,
   BEFORE any ## header. Format it exactly like this:

       > **The key insight:** [one or two sentences that compress the entire
       > argument into a screenshot-worthy claim].

   Rules for this line:
     • It must be the single most quotable sentence in the piece — the line a
       reader would underline, screenshot, or paste into a tweet.
     • It must be specific and non-obvious. Generic observations ("AI is changing
       everything") are forbidden. It should make a claim someone could disagree
       with.
     • It must be self-contained — readable without the surrounding article.
     • It must not repeat the title verbatim. The title teases; this line lands.
     • Keep it under 35 words. Tighter is better.

4. ## What's Actually Happening Right Now
5. ## The Voices Shaping the Conversation
6. ## What Everyone's Missing  (most valuable section — lead with the gaps)
7. ## What This Means If You're [technical role] / What This Means If You're [non-technical role]
8. ## The Bottom Line  (3-5 sentences of sharp synthesis — what to watch, what to do)

Length: 1200–1800 words. Dense enough to be useful. Tight enough to finish.

Return only the markdown report — no JSON, no preamble."""


def run_synthesis_agent(
    anthropic_client: anthropic.Anthropic,
    domain: str,
    research_data: dict,
    pattern_data: dict,
    callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Run the Synthesis Agent. Returns the baseline draft markdown."""

    def log(msg: str):
        if callback:
            callback(msg)

    log(f"✍️  Synthesizing report for: **{domain}**")
    log("   📐 Structuring narrative arc...")

    brief = {
        "domain": domain,
        "hot_topics":            research_data.get("hot_topics", [])[:6],
        "top_voices":            research_data.get("top_voices", [])[:6],
        "key_narratives":        research_data.get("key_narratives", [])[:4],
        "concrete_data_points":  research_data.get("concrete_data_points", [])[:8],
        "emerging_signals":      research_data.get("emerging_signals", [])[:4],
        "research_raw_fallback": research_data.get("raw_output", None),
        "gaps_and_missed_angles": pattern_data.get("gaps_and_missed_angles", [])[:4],
        "contrarian_takes":      pattern_data.get("contrarian_takes", [])[:3],
        "hook_patterns":         pattern_data.get("hook_patterns", [])[:3],
        "recommended_angles":    pattern_data.get("recommended_angles", [])[:3],
        "underserved_audiences": pattern_data.get("underserved_audiences", [])[:2],
    }

    payload = json.dumps(brief, ensure_ascii=False, indent=2)

    log("   🖊️  Writing report (this takes a moment)...")

    response = anthropic_client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=SYNTHESIS_MAX_TOKENS,
        # temperature=SYNTHESIS_TEMPERATURE,
        system=[{
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[
            {
                "role": "user",
                "content": (
                    f'Write a research report about "{domain}" using the data below.\n\n'
                    f"RESEARCH BRIEF:\n{payload}\n\n"
                    "Write the full markdown report. Follow the structure. "
                    "Make it feel like a human journalist wrote it — not an AI summary. "
                    "Use the gaps and contrarian takes prominently. "
                    "Start immediately with the title and hook — no preamble."
                ),
            }
        ],
    )

    draft = response.content[0].text.strip()
    log("✅ Synthesis Agent complete — baseline draft written")
    return draft