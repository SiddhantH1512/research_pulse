"""
pipeline/templates.py
──────────────────────
Article structure templates.

Each template defines an ordered list of section titles that becomes the body
structure of the synthesised report. The universal elements — title, opening
hook, and key insight blockquote — are always emitted by Synthesis BEFORE the
template's first section.

Add new templates by appending to TEMPLATES. The orchestrator and UI pick them
up automatically.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleTemplate:
    key:      str           # short identifier (e.g. "paradox")
    name:     str           # display name shown in the UI
    best_for: str           # one-line guidance for when to pick it
    sections: tuple         # ordered tuple of section titles (## headers)

    def structure_for_prompt(self, start_index: int = 4) -> str:
        """Render the template's sections as a numbered markdown structure."""
        return "\n".join(f"{i}. ## {title}"
                         for i, title in enumerate(self.sections, start=start_index))

    def section_list_inline(self) -> str:
        """Plain comma-separated section names — used by the Arbiter."""
        return ", ".join(f'"{s}"' for s in self.sections)


# ─────────────────────────────────────────────────────────────────
#  Registry
# ─────────────────────────────────────────────────────────────────

TEMPLATES: dict[str, ArticleTemplate] = {
    "paradox": ArticleTemplate(
        key="paradox",
        name="Paradox Framework",
        best_for="contradictory findings, tension, nuance",
        sections=(
            "The Hook",
            "The Common Belief",
            "The Contradiction",
            "Why Both Can Be True",
            "What This Means",
            "The Bottom Line",
        ),
    ),
    "investigation": ArticleTemplate(
        key="investigation",
        name="Investigation Framework",
        best_for="questions, uncertain topics, research-led posts",
        sections=(
            "The Question",
            "What Supports the Idea",
            "What Challenges It",
            "What We Know So Far",
            "What We Still Do Not Know",
            "The Conclusion",
        ),
    ),
    "hidden_cost": ArticleTemplate(
        key="hidden_cost",
        name="Hidden Cost Framework",
        best_for="trade-offs, second-order effects, unintended consequences",
        sections=(
            "The New Trend",
            "The Obvious Benefit",
            "The Hidden Cost",
            "Why It Matters Long-Term",
            "How to Respond",
            "The Bottom Line",
        ),
    ),
    "missing": ArticleTemplate(
        key="missing",
        name="What Everyone's Missing Framework",
        best_for="contrarian commentary, overlooked angles",
        sections=(
            "What People Are Saying",
            "Why That Story Feels Incomplete",
            "The Missing Piece",
            "The Overlooked Implication",
            "Why This Changes the Picture",
            "The Takeaway",
        ),
    ),
    "future": ArticleTemplate(
        key="future",
        name="Future Projection Framework",
        best_for="emerging tech, forward-looking analysis",
        sections=(
            "Where We Are Today",
            "The First-Order Effect",
            "The Second-Order Effect",
            "The Third-Order Effect",
            "What the Future Probably Looks Like",
            "What to Watch Next",
        ),
    ),
    "mental_model": ArticleTemplate(
        key="mental_model",
        name="Mental Model Framework",
        best_for="teaching, simplifying complexity",
        sections=(
            "The Core Idea",
            "The First Part of the Model",
            "The Second Part of the Model",
            "The Third Part of the Model",
            "How It Works in Real Life",
            "Why It Matters",
        ),
    ),
    "debate": ArticleTemplate(
        key="debate",
        name="Debate Framework",
        best_for="polarized topics, comparing viewpoints",
        sections=(
            "Side A",
            "Side B",
            "The Best Argument for Side A",
            "The Best Argument for Side B",
            "My Synthesis",
            "The Practical Conclusion",
        ),
    ),
    "case_study": ArticleTemplate(
        key="case_study",
        name="Case Study Framework",
        best_for="one company, one study, one example with lessons",
        sections=(
            "The Story",
            "What Happened",
            "Why It Happened",
            "What Makes It Interesting",
            "What We Can Learn",
            "The Bigger Lesson",
        ),
    ),
    "playbook": ArticleTemplate(
        key="playbook",
        name="Playbook Framework",
        best_for="practical, actionable, how-to articles",
        sections=(
            "The Problem",
            "Why Current Approaches Fail",
            "Step 1",
            "Step 2",
            "Step 3",
            "How to Put It Into Practice",
        ),
    ),
    "contrarian": ArticleTemplate(
        key="contrarian",
        name="Contrarian Framework",
        best_for="strong opinion pieces, reframing common beliefs",
        sections=(
            "The Popular Belief",
            "Why It Sounds Right",
            "Why It Is Incomplete",
            "The Contrarian View",
            "The Evidence",
            "The Final Take",
        ),
    ),
}

# Closest to the previous default output style.
DEFAULT_TEMPLATE_KEY = "missing"


def get_template(key: str) -> ArticleTemplate:
    """Look up a template by key; falls back to default if unknown."""
    return TEMPLATES.get(key, TEMPLATES[DEFAULT_TEMPLATE_KEY])