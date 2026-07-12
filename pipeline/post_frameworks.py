"""
pipeline/post_frameworks.py
────────────────────────────
LinkedIn post framework registry.

Each framework defines the *shape* of the post — the opening hook style, the
argumentative move it makes, and the way it closes. All frameworks share the
same universal shape (hook → context → insight → tension → discussion prompt)
but each optimizes for a different subset of the 6-criteria filter:

    1. Timely           4. Point of view
    2. Non-obvious      5. Evidence-backed
    3. Audience-specific 6. Discussion-worthy

Add new frameworks by appending to POST_FRAMEWORKS.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PostFramework:
    key:            str          # short identifier
    name:           str          # UI display name
    best_for:       str          # one-line UI tooltip
    optimizes_for:  tuple        # which of the 6 criteria this framework naturally hits
    shape:          str          # multi-line block describing the post's argumentative move


# ─────────────────────────────────────────────────────────────────
#  Framework registry
# ─────────────────────────────────────────────────────────────────

POST_FRAMEWORKS: dict[str, PostFramework] = {
    "reframe": PostFramework(
        key="reframe",
        name="The Reframe",
        best_for="Everyone's calling this X — but it's actually Y",
        optimizes_for=("Non-obvious", "Point of view", "Discussion-worthy"),
        shape=(
            "SHAPE — The Reframe:\n"
            "  • HOOK (1 sentence): State the dominant narrative that everyone else is "
            "reporting. Make it concrete — name what people are saying.\n"
            "  • THE FRAME BREAK (2-3 sentences): Introduce a specific piece of evidence "
            "— a data point, quote, benchmark, or observed pattern — that reframes what "
            "the story is actually about. This is the whole payload of the post.\n"
            "  • THE IMPLICATION (2-3 sentences): Explain what the reframe means for a "
            "specific audience. Who now needs to think differently, and about what?\n"
            "  • THE DISCUSSION HOOK (1 sentence): A question people can genuinely "
            "disagree on — NOT 'what do you think?'. Frame two credible positions and "
            "invite the reader to pick a side.\n"
            "\n"
            "The reframe should feel like a scalpel — precise, specific, and load-bearing. "
            "If you can remove the reframe and the post still makes sense, it's not a reframe."
        ),
    ),

    "signal": PostFramework(
        key="signal",
        name="The Signal",
        best_for="A new data point/report just dropped — what it *means*",
        optimizes_for=("Timely", "Evidence-backed", "Non-obvious"),
        shape=(
            "SHAPE — The Signal:\n"
            "  • HOOK (1-2 sentences): Lead with the specific new fact. Name the source "
            "(company, study, report, earnings call). Do not editorialize yet.\n"
            "  • THE SURFACE READ (1 sentence): Acknowledge what most people will take from "
            "this at face value. This makes the next move earn its keep.\n"
            "  • THE DEEPER READ (2-3 sentences): Your interpretation. What does the number "
            "or event actually indicate about the underlying dynamics? Reference the "
            "mechanism, not just the outcome.\n"
            "  • WHY IT MATTERS (2 sentences): Who should change what they're doing, and "
            "why. Be specific about the audience — practitioners, execs, product teams.\n"
            "  • DISCUSSION HOOK (1 sentence): A question that surfaces a live debate. "
            "Something a smart reader could plausibly argue either side of.\n"
            "\n"
            "The whole post rests on one primary source. Name it. If you don't have one "
            "primary source that carries the piece, use a different framework."
        ),
    ),

    "tradeoff": PostFramework(
        key="tradeoff",
        name="The Trade-off",
        best_for="Everyone's celebrating X — here's the cost",
        optimizes_for=("Point of view", "Non-obvious", "Discussion-worthy"),
        shape=(
            "SHAPE — The Trade-off:\n"
            "  • HOOK (1-2 sentences): Name the widely celebrated development or trend. "
            "Do not dismiss it — genuinely acknowledge the wins first. Credibility comes "
            "from steelmanning the mainstream view before you complicate it.\n"
            "  • THE HIDDEN COST (3-4 sentences): The core payload. Identify a specific "
            "second-order effect, unintended consequence, or trade-off that the "
            "celebratory framing ignores. Use evidence — data, examples, patterns.\n"
            "  • WHO PAYS (1-2 sentences): Be concrete about who absorbs the cost. Vague "
            "'society' answers weaken the post. Which people, which teams, which decisions?\n"
            "  • THE HONEST FRAMING (1 sentence): Land the plane. This isn't 'X is bad' — "
            "it's 'here's what X costs, and whether it's worth it depends on…'\n"
            "  • DISCUSSION HOOK (1 sentence): Ask readers where they'd draw the line. "
            "The answer shouldn't be obvious.\n"
            "\n"
            "This framework fails when it reads as contrarian for contrarian's sake. "
            "The trade-off must be real, evidence-backed, and non-obvious — not just an "
            "inversion of the popular take."
        ),
    ),

    "prediction": PostFramework(
        key="prediction",
        name="The Prediction",
        best_for="Where this goes in 12 months — and why the mainstream is wrong",
        optimizes_for=("Point of view", "Discussion-worthy", "Non-obvious"),
        shape=(
            "SHAPE — The Prediction:\n"
            "  • HOOK (1-2 sentences): State your prediction as a claim, not a question. "
            "Specific, time-bounded, falsifiable. 'In 12 months, X will Y' — not 'AI will "
            "change everything soon.' The more falsifiable, the more credible.\n"
            "  • WHY MOST PEOPLE ARE WRONG (2-3 sentences): Identify the dominant "
            "prediction and explain why it's likely to miss. Point to a specific "
            "assumption people are making that isn't holding up.\n"
            "  • THE UNDERLYING DYNAMIC (2-3 sentences): The mechanism that makes your "
            "prediction more likely than the consensus. This is where evidence matters — "
            "cite the trend, data point, or structural shift that grounds the call.\n"
            "  • THE STAKES (1-2 sentences): What happens if you're right, and who "
            "should be preparing for it now.\n"
            "  • DISCUSSION HOOK (1 sentence): Invite readers to name the assumption "
            "you're making that they'd most challenge. Not 'agree/disagree' — 'where's "
            "the weakest link in this?'\n"
            "\n"
            "A good prediction post is 40% claim, 60% mechanism. If the reader can't "
            "reconstruct why you believe it, they can't engage seriously."
        ),
    ),

    "pattern": PostFramework(
        key="pattern",
        name="The Pattern",
        best_for="Connects 2-3 seemingly unrelated developments into a thesis",
        optimizes_for=("Non-obvious", "Evidence-backed", "Point of view"),
        shape=(
            "SHAPE — The Pattern:\n"
            "  • HOOK (1 sentence): State the pattern as a discovered thesis — 'Three "
            "things happened this quarter that most people are treating as unrelated…'\n"
            "  • THE THREE (OR TWO) DATA POINTS (3-4 sentences): Enumerate the specific "
            "developments. Each one should stand on its own as a real, verifiable event "
            "— a launch, an earnings call quote, a study, a policy move.\n"
            "  • THE CONNECTION (2-3 sentences): The core payload. Name the underlying "
            "dynamic that links them. Why is this a pattern and not a coincidence? The "
            "argument here is what earns the post.\n"
            "  • WHAT IT SIGNALS (1-2 sentences): What the pattern predicts about the "
            "next 6-12 months, or what it reveals about a shift that's already happened.\n"
            "  • DISCUSSION HOOK (1 sentence): Ask readers what else might fit the "
            "pattern — or what evidence would break it.\n"
            "\n"
            "This framework requires *real* specific developments, not vague trends. "
            "'Companies are hiring more AI engineers' is not a data point. "
            "'Anthropic's headcount grew 3x in Q1 while three FAANG teams shrank' is."
        ),
    ),
}


# Sensible default
DEFAULT_POST_FRAMEWORK_KEY = "signal"


def get_post_framework(key: str) -> PostFramework:
    """Look up a post framework by key; falls back to default if unknown."""
    return POST_FRAMEWORKS.get(key, POST_FRAMEWORKS[DEFAULT_POST_FRAMEWORK_KEY])