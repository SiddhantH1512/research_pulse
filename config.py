# ─────────────────────────────────────────────────────────────────
#  config.py  –  Model & pipeline configuration
#  Change models here without touching agent logic
# ─────────────────────────────────────────────────────────────────

# Available Claude models (as of May 2026)
# claude-opus-4-8 | claude-opus-4-7 | claude-opus-4-6
# claude-sonnet-4-6 | claude-haiku-4-5-20251001

# Agent model assignments
RESEARCH_MODEL   = "claude-opus-4-6"    # needs strong web reasoning
PATTERN_MODEL    = "claude-sonnet-4-6"  # analytical, fast enough
SYNTHESIS_MODEL  = "claude-opus-4-6"    # best writing quality
REVIEWER_MODEL   = "claude-sonnet-4-6"  # lighter editing task

# Token budgets per agent
RESEARCH_MAX_TOKENS  = 8192
PATTERN_MAX_TOKENS   = 6144
SYNTHESIS_MAX_TOKENS = 12288
REVIEWER_MAX_TOKENS  = 12288

# Search settings
SEARCHES_PER_DEPTH = {
    "Quick":    {"queries": 3, "results": 5},
    "Standard": {"queries": 6, "results": 7},
    "Deep":     {"queries": 10, "results": 10},
}

# Default output folder (relative to project root)
DEFAULT_OUTPUT_FOLDER = "reports"

# Author name shown in the published HTML byline (leave blank to omit)
AUTHOR_NAME = "Siddhant Hardikar"