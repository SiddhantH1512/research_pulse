# ─────────────────────────────────────────────────────────────────
#  config.py  –  Model & pipeline configuration
#  Quality-first selections (June 2026).
#
#  Six-stage pipeline:
#    1 Research  →  2 Pattern  →  3 Synthesis  →
#    4 Factual Council  →  5 Style Council  →  6 Arbiter
# ─────────────────────────────────────────────────────────────────

# ── Anthropic Claude (June 2026) ─────────────────────────────────
#   claude-opus-4-8         best judgment + writing
#   claude-opus-4-7         excellent analytical
#   claude-sonnet-4-6       fast analytical
#   claude-haiku-4-5-20251001  ultra-fast
#
# ── OpenAI (June 2026) ───────────────────────────────────────────
#   gpt-5.5                 current frontier (released 2026-04-24)
#   gpt-5.5-pro             premium variant (heavier, slower)
#   gpt-5.4                 previous frontier, still supported
#
# ── Perplexity Sonar (June 2026) ─────────────────────────────────
#   sonar                   lightweight, web-grounded
#   sonar-pro               advanced web research, 200K context
#   sonar-reasoning         CoT + web
#   sonar-reasoning-pro     DeepSeek-R1-powered, deep reasoning
#   sonar-deep-research     exhaustive multi-source reports (2–5 min)
#
# ── Groq (June 2026) ─────────────────────────────────────────────
#   llama-3.3-70b-versatile          Meta, 70B, production tier
#   openai/gpt-oss-120b              (overlaps GPT lens — avoid)
#   meta-llama/llama-4-scout-17b-…   newer but preview-tier, 17B active

# ─────────────────────────────────────────────────────────────────
#  Step 1 – Research (Perplexity)
# ─────────────────────────────────────────────────────────────────
# Depth-tiered; per-tier model + budget defined in SEARCHES_PER_DEPTH below.
RESEARCH_MODEL_DEFAULT = "sonar-pro"
RESEARCH_MODEL_DEEP    = "sonar-deep-research"

# ─────────────────────────────────────────────────────────────────
#  Step 2 – Pattern & Gap (Claude)
# ─────────────────────────────────────────────────────────────────
# Pattern is structured JSON extraction over the Perplexity brief. Opus 4.7
# is overkill for the format but the *judgment* dimension (what counts as a
# real gap vs. wishful thinking) genuinely benefits from a frontier model.
PATTERN_MODEL = "claude-opus-4-7"

# ─────────────────────────────────────────────────────────────────
#  Step 3 – Synthesis (Claude) — baseline draft
# ─────────────────────────────────────────────────────────────────
# Opus 4.8 — best writing model available. Quality at this step compounds
# through Council 1, Council 2, and the Arbiter.
SYNTHESIS_MODEL = "claude-opus-4-8"

# ─────────────────────────────────────────────────────────────────
#  Step 4 – Factual Verification Council (Perplexity)
# ─────────────────────────────────────────────────────────────────
# sonar-reasoning-pro is DeepSeek-R1-powered with live web access. It
# catches subtler factual errors (misattributed causation, conflated
# timeframes) that plain sonar-pro misses. Note: this model emits a
# <think>…</think> reasoning block in the content; the Factual Council
# strips it before passing corrections downstream.
FACTUAL_COUNCIL_MODEL = "sonar-reasoning-pro"

# ─────────────────────────────────────────────────────────────────
#  Step 5 – Style & Humanization Council (three lenses, parallel)
# ─────────────────────────────────────────────────────────────────
# Three distinct training distributions for diverse critique:
#   • Anthropic    → narrative flow & cadence
#   • OpenAI       → buzzwords & AI-isms
#   • Meta (Groq)  → grit & directness  (different house style)
STYLE_CLAUDE_MODEL = "claude-opus-4-7"
STYLE_GPT_MODEL = "gpt-5.5"
STYLE_GPT_MODEL_FALLBACK = "gpt-5.5-2026-04-24"
STYLE_LLAMA_MODEL  = "llama-3.3-70b-versatile"   # served by Groq

# Fallback for the Llama lens if GROQ_API_KEY is missing — routes through
# Perplexity's sonar instead (also Llama-backed). Keeps the lens alive.
STYLE_LLAMA_FALLBACK_MODEL    = "sonar"
STYLE_LLAMA_FALLBACK_PROVIDER = "perplexity"

# ─────────────────────────────────────────────────────────────────
#  Step 6 – Synthesis Arbiter (Claude — Editor-in-Chief)
# ─────────────────────────────────────────────────────────────────
ARBITER_MODEL = "claude-opus-4-8"

# ─────────────────────────────────────────────────────────────────
#  Token budgets
# ─────────────────────────────────────────────────────────────────
RESEARCH_MAX_TOKENS         = 8192
PATTERN_MAX_TOKENS          = 6144
SYNTHESIS_MAX_TOKENS        = 12288
FACTUAL_COUNCIL_MAX_TOKENS  = 6144   # ↑ headroom for the <think> block
STYLE_COUNCIL_MAX_TOKENS    = 4096   # per-lens
ARBITER_MAX_TOKENS          = 12288

# ─────────────────────────────────────────────────────────────────
#  Temperatures
#    Step 1 (Research)        — 0.30  modestly creative analytic extraction
#    Step 2 (Pattern)         — 0.30  same shape
#    Step 3 (Synthesis)       — 0.60  fluid prose drafting
#    Step 4 (Factual)         — 0.00  pure determinism
#    Step 5 (Style critique)  — 0.15  deterministic critique
#    Step 6 (Arbiter)         — 0.40  judgment under constraints — we want
#                                     under-editing, not over-editing
# ─────────────────────────────────────────────────────────────────
RESEARCH_TEMPERATURE        = 0.30
PATTERN_TEMPERATURE         = 0.30
SYNTHESIS_TEMPERATURE       = 0.60
FACTUAL_COUNCIL_TEMPERATURE = 0.00
STYLE_COUNCIL_TEMPERATURE   = 0.15
ARBITER_TEMPERATURE         = 0.40

# ─────────────────────────────────────────────────────────────────
#  Depth → Perplexity retrieval intensity
# ─────────────────────────────────────────────────────────────────
SEARCHES_PER_DEPTH = {
    "Quick":    {"model": "sonar-pro",           "queries": 1, "max_tokens": 6144},
    "Standard": {"model": "sonar-pro",           "queries": 2, "max_tokens": 8192},
    "Deep":     {"model": "sonar-deep-research", "queries": 3, "max_tokens": 8192},
}

# ─────────────────────────────────────────────────────────────────
#  Style Council failback sentinel
# ─────────────────────────────────────────────────────────────────
SYSTEM_WARNING_UNPARSED = "[System Warning: Model feedback unparsed; interpret text directly]"

# ─────────────────────────────────────────────────────────────────
#  Misc
# ─────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_FOLDER = "/Users/siddhant/Desktop/projects/Project Documentation/Research Pulse Project Documentation"
AUTHOR_NAME           = "Siddhant Hardikar"

# Endpoints
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
OPENAI_BASE_URL     = "https://api.openai.com/v1"
GROQ_BASE_URL       = "https://api.groq.com/openai/v1"