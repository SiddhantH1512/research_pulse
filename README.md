# Research Pipeline

A six-stage multi-model research pipeline that takes a domain or question and
produces a publication-ready report. Built with Streamlit.

---

## What It Does

You type a domain. The pipeline does the rest:

1. Searches the live web for current topics, voices, and data points
2. Extracts patterns, engagement hooks, and gaps in the existing coverage
3. Writes a baseline draft — the raw material for everything that follows
4. Fact-checks every specific claim against the live web
5. Runs three style lenses in parallel to strip AI-isms and tighten prose
6. An Arbiter reconciles all feedback and produces the final report

Output: a polished markdown report saved as `.md` and `.html` to `/reports`.

---

## Pipeline Architecture

```
Domain Input
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1 │ Research Agent          │ Perplexity sonar-pro    │
│         │ Live web retrieval       │ (sonar-deep-research    │
│         │ Citation-grounded brief  │  at Deep depth)         │
├─────────────────────────────────────────────────────────────┤
│  Step 2 │ Pattern & Gap Agent     │ Claude Opus 4.7         │
│         │ Hook patterns            │                         │
│         │ Gaps & contrarian takes  │                         │
├─────────────────────────────────────────────────────────────┤
│  Step 3 │ Synthesis Agent         │ Claude Opus 4.8         │
│         │ Baseline draft           │ temp 0.6               │
│         │ 1200–1800 word target    │                         │
├─────────────────────────────────────────────────────────────┤
│  Step 4 │ Factual Council         │ Perplexity              │
│         │ Live fact-check          │ sonar-reasoning-pro     │
│         │ Returns corrections list │ (DeepSeek R1) temp 0.0 │
├─────────────────────────────────────────────────────────────┤
│  Step 5 │ Style Council           │ Three lenses, parallel  │
│         │ asyncio.gather           │ ─────────────────────  │
│         │                          │ Claude Opus 4.7        │
│         │                          │ GPT-5.5                │
│         │                          │ Llama 3.3 70B (Groq)   │
│         │                          │ → fallback: Perplexity │
├─────────────────────────────────────────────────────────────┤
│  Step 6 │ Arbiter Agent           │ Claude Opus 4.8         │
│         │ Editor-in-chief          │ temp 0.4               │
│         │ Factual fixes: mandatory │                         │
│         │ Style fixes: discretion  │                         │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
Final Report (.md + .html)
```

---

## Project Structure

```
project_root/
│
├── app.py                          # Streamlit UI
├── config.py                       # All model assignments + temperatures
├── README.md
│
├── pipeline/
│   ├── orchestrator.py             # Wires all six steps, returns PipelineResult
│   │
│   ├── agents/
│   │   ├── research_agent.py       # Step 1 — Perplexity Sonar
│   │   ├── pattern_agent.py        # Step 2 — Claude
│   │   ├── synthesis_agent.py      # Step 3 — Claude
│   │   ├── factual_council.py      # Step 4 — Perplexity sonar-reasoning-pro
│   │   ├── style_council.py        # Step 5 — Claude + GPT + Llama (parallel)
│   │   └── arbiter_agent.py        # Step 6 — Claude
│   │
│   └── clients/
│       └── perplexity_client.py    # Sync + async httpx wrapper for Perplexity
│
├── utils/
│   └── report_saver.py             # Saves .md and renders .html
│
└── reports/                        # Output directory (auto-created)
```

---

## Setup

**1. Clone and install dependencies**

```bash
pip install anthropic openai httpx streamlit
# Optional search libraries (legacy — no longer needed for research):
# pip install tavily-python duckduckgo-search
```

**2. Set environment variables**

Create a `.env` file in the project root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
PERPLEXITY_API_KEY=pplx-...

# Optional — GPT-5.5 style lens (Step 5)
OPENAI_API_KEY=sk-...

# Optional — Llama 3.3 70B style lens (Step 5, preferred over Perplexity fallback)
GROQ_API_KEY=gsk_...
```

The pipeline degrades gracefully when optional keys are absent:
- No `OPENAI_API_KEY` → GPT style lens skipped, 2/3 lenses run
- No `GROQ_API_KEY` → Llama lens falls back to Perplexity `sonar`

**3. Run**

```bash
streamlit run app.py
```

---

## Configuration

Everything lives in `config.py`. The key knobs:

| Variable | Default | What it controls |
|---|---|---|
| `SYNTHESIS_MODEL` | `claude-opus-4-8` | Baseline draft writer |
| `ARBITER_MODEL` | `claude-opus-4-8` | Final editor |
| `FACTUAL_COUNCIL_MODEL` | `sonar-reasoning-pro` | Fact-checker |
| `STYLE_CLAUDE_MODEL` | `claude-opus-4-7` | Narrative flow lens |
| `STYLE_GPT_MODEL` | `gpt-5.5` | Buzzword / AI-ism lens |
| `STYLE_LLAMA_MODEL` | `llama-3.3-70b-versatile` | Grit / directness lens |
| `SYNTHESIS_TEMPERATURE` | `0.60` | Draft creativity |
| `ARBITER_TEMPERATURE` | `0.40` | Final edit conservatism |
| `FACTUAL_COUNCIL_TEMPERATURE` | `0.00` | Fact-check determinism |

**Depth tiers** control Perplexity retrieval intensity:

| Depth | Model | Use case |
|---|---|---|
| Quick | `sonar-pro` | Fast scan, 5–10 min |
| Standard | `sonar-pro` | Default |
| Deep | `sonar-deep-research` | Exhaustive, 15–30 min |

> **Note:** `sonar-deep-research` visits 100+ pages per run. Expect 5–15 minutes for the Research step at Deep depth. This is expected behavior, not a hang.

---

## How the Style Council Works

Step 5 runs three independent critique lenses concurrently via `asyncio.gather`.
Each lens receives the baseline draft and the factual corrections list. Each
returns a JSON array of critique blocks:

```json
[
  {
    "original_text": "It is paramount to leverage this data...",
    "issue": "AI-isms: 'paramount', 'leverage'",
    "suggested_fix": "We need to use this data..."
  }
]
```

If a lens returns malformed JSON, the pipeline falls back in order:
1. Strip markdown fences, retry parse
2. Regex-extract outermost `[...]`, retry parse
3. Pass raw text to Arbiter with a `[System Warning: Model feedback unparsed]` sentinel

The Arbiter then applies **factual corrections as mandatory** and **style
critiques as discretionary** — it merges conflicting feedback and protects the
core insights of the draft.

---

## The Key Insight Block

The Synthesis agent is instructed to produce one crystallizing insight
immediately after the opening, formatted as a markdown blockquote:

```markdown
> **The key insight:** [one or two sentences that compress the whole argument
> into a screenshot-worthy claim, under 35 words]
```

This renders as a left-border callout block in the HTML output using the
existing `blockquote` CSS — no extra styling required.

---

## Output Format

Each run produces two files in `/reports`:

- `report_{slug}.md` — raw markdown
- `report_{slug}_publish.html` — styled HTML ready to copy into Substack,
  Medium, or a CMS. Uses Lora (body) and Inter (headings) from Google Fonts.

The HTML report includes:
- Byline with author name and original query
- Full article with all markdown elements rendered
- Blockquote callout for the key insight
- Footer

---

## Known Behaviors

**`sonar-reasoning-pro` emits `<think>` blocks.** This model outputs its
reasoning chain inline by default. The Factual Council strips these before
passing corrections to the Arbiter. If Perplexity changes this behavior, the
strip becomes a no-op — no breakage.

**`reviewer_agent.py` is deprecated.** Its role is now absorbed by the
Arbiter (Step 6). The file is safe to delete.

**Streamlit + asyncio.** The Style Council calls `asyncio.run()` inside a
synchronous Streamlit context. If a running event loop is detected (rare, can
happen in notebooks), it falls back to `asyncio.new_event_loop()` in a thread.

---

## API Keys Reference

| Key | Provider | Required | Used in |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | ✅ | Steps 2, 3, 5a, 6 |
| `PERPLEXITY_API_KEY` | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) | ✅ | Steps 1, 4, 5c fallback |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Optional | Step 5b (GPT lens) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Optional | Step 5c (Llama lens) |