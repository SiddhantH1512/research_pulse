"""
app.py — Research Pulse
────────────────────────
Streamlit frontend for the multi-agent research pipeline.
Warm editorial light theme. Topic suggestions for broad inputs.
"""

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline.post_frameworks       import POST_FRAMEWORKS, get_post_framework, DEFAULT_POST_FRAMEWORK_KEY
from pipeline.agents.discovery_agent import run_discovery_agent

load_dotenv()


# ─────────────────────────────────────────────────────────────────
#  Helpers defined early (used throughout)
# ─────────────────────────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    try:
        import markdown2
        return markdown2.markdown(md, extras=["fenced-code-blocks", "tables", "strike"])
    except ImportError:
        import re
        html = md
        html = re.sub(r"^## (.+)$",  r"<h2>\1</h2>",  html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>",  html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         html)
        paras = []
        for line in html.split("\n"):
            if line.strip() and not line.startswith("<"):
                paras.append(f"<p>{line}</p>")
            else:
                paras.append(line)
        return "\n".join(paras)


def _is_broad(domain: str) -> bool:
    """True when the input looks like a generic category (≤ 2 words)."""
    words = domain.strip().split()
    return len(words) <= 2 and len(domain.strip()) <= 20


def get_topic_suggestions(api_key: str, broad_domain: str) -> list[str]:
    """Call Claude Haiku to generate 6 specific sub-topic angles."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f'Give me 6 specific, interesting research angles within "{broad_domain}" '
                "that would make for a compelling, focused report.\n"
                "Each should be 3–6 words, concrete and timely.\n"
                "Return ONLY a JSON array of 6 strings. No explanation, no markdown."
            ),
        }],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ─────────────────────────────────────────────────────────────────
#  Page config  ← must be the first Streamlit call
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Research Pulse",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────
#  CSS — Warm editorial light theme
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>

/* ══ Base ══════════════════════════════════════════════════════════ */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #f7f4ef !important;
    font-family: 'DM Sans', sans-serif;
    color: #1c1917;
}

/* ── Kill the black Streamlit header bar ─────────────────────────── */
header[data-testid="stHeader"] {
    background-color: #f7f4ef !important;
    border-bottom: none !important;
}
[data-testid="stDecoration"] { display: none !important; }
#stDecoration               { display: none !important; }

[data-testid="stSidebar"] {
    background-color: #edeae2 !important;
    border-right: 1px solid #d8d3c8;
}
[data-testid="stSidebar"] > div { padding-top: 0 !important; }

/* ══ Header ════════════════════════════════════════════════════════ */
.rp-header {
    padding: 1.5rem 0 1.8rem;
    border-bottom: 2px solid #e2ddd4;
    margin-bottom: 1.8rem;
}
.rp-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 2.6rem;
    font-weight: 900;
    color: #1c1917;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.rp-accent { color: #b45309; }
.rp-subtitle {
    font-size: 0.78rem;
    color: #9c8b7a;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 0.3rem;
}

/* ══ Sidebar branding ══════════════════════════════════════════════ */
.sb-brand {
    padding: 1.4rem 1rem 1.2rem;
    border-bottom: 1px solid #d0cbc0;
    margin-bottom: 1.2rem;
}
.sb-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 1.35rem;
    font-weight: 900;
    color: #1c1917;
}
.sb-title span { color: #b45309; }
.sb-tagline {
    font-size: 0.68rem;
    color: #a09080;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 3px;
}
.sb-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9c8b7a;
    margin-bottom: 5px;
    font-weight: 600;
}

/* ══ Agent cards ═══════════════════════════════════════════════════ */
.agent-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
    margin-bottom: 1.4rem;
}
@media (max-width: 1100px) {
    .agent-grid { grid-template-columns: repeat(3, 1fr); }
}
.agent-card {
    background: #ffffff;
    border: 1.5px solid #ddd8ce;
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.agent-card::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: transparent;
    transition: background 0.3s ease;
}
.agent-card.pending { opacity: 0.45; }

.agent-card.running {
    border-color: #2563eb;
    background: #eff6ff;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.10);
}
.agent-card.running::after  { background: #2563eb; }
.agent-card.running .c-status { color: #2563eb; font-weight: 600; }

.agent-card.complete {
    border-color: #16a34a;
    background: #f0fdf4;
}
.agent-card.complete::after { background: #16a34a; }
.agent-card.complete .c-status { color: #16a34a; font-weight: 600; }

.agent-card.error {
    border-color: #dc2626;
    background: #fef2f2;
}
.agent-card.error::after   { background: #dc2626; }
.agent-card.error .c-status { color: #dc2626; }

.c-icon   { font-size: 1.3rem; display: block; margin-bottom: 6px; }
.c-label  { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: #a09080; margin-bottom: 2px; }
.c-name   { font-size: 0.88rem; font-weight: 600; color: #2c2417; }
.c-status { font-size: 0.7rem; margin-top: 5px; color: #a09080; }

/* ══ Log panel ═════════════════════════════════════════════════════ */
.log-panel {
    background: #faf8f4;
    border: 1px solid #ddd8ce;
    border-left: 3px solid #b45309;
    border-radius: 0 8px 8px 0;
    padding: 12px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #7a6e60;
    max-height: 220px;
    overflow-y: auto;
    margin-bottom: 1.5rem;
    line-height: 1.65;
}
.log-line         { margin: 1px 0; }
.log-line.success { color: #15803d; }
.log-line.warn    { color: #b45309; }
.log-line.error   { color: #dc2626; }

/* ══ Empty state ═══════════════════════════════════════════════════ */
.empty-state {
    background: #ffffff;
    border: 1.5px dashed #d8d3c8;
    border-radius: 12px;
    padding: 3.5rem 2rem;
    text-align: center;
    margin-bottom: 1.5rem;
}
.empty-icon   { font-size: 2.2rem; margin-bottom: 0.8rem; }
.empty-title  {
    font-family: 'Playfair Display', serif;
    font-size: 1.15rem;
    color: #6b5e52;
    margin-bottom: 0.4rem;
}
.empty-sub    { font-size: 0.82rem; color: #a09080; }

/* ══ Topic suggestion chips ════════════════════════════════════════ */
.suggest-wrap {
    background: #fff9f0;
    border: 1px solid #e8d8bc;
    border-radius: 8px;
    padding: 10px 12px;
    margin-top: 8px;
}
.suggest-title {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #b45309;
    font-weight: 600;
    margin-bottom: 8px;
}

/* ══ Report display ════════════════════════════════════════════════ */
.report-wrapper {
    background: #ffffff;
    border: 1.5px solid #ddd8ce;
    border-radius: 12px;
    padding: 2.8rem 3.2rem;
    margin-top: 1rem;
    line-height: 1.82;
    color: #2c2417;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.report-wrapper h1, .report-wrapper h2 {
    font-family: 'Playfair Display', Georgia, serif;
    color: #1c1917;
}
.report-wrapper h2 {
    font-size: 1.25rem;
    margin-top: 2.2rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #e8e2d8;
    color: #2c2417;
}
.report-wrapper h3   { color: #5c4a38; font-size: 1rem; margin-top: 1.5rem; }
.report-wrapper strong { color: #92400e; }
.report-wrapper p    { margin-bottom: 1.1rem; }
.report-wrapper ul, .report-wrapper ol { margin: 0.4rem 0 1rem 1.4rem; }
.report-wrapper li   { margin-bottom: 0.3rem; }

/* ══ Report header row ═════════════════════════════════════════════ */
.report-hdr {
    display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;
}
.report-hdr-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.25rem;
    font-weight: 700;
    color: #1c1917;
}
.report-badge {
    background: #fef3c7;
    color: #92400e;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 3px 9px;
    border-radius: 20px;
    border: 1px solid #fcd34d;
}

/* ══ Hide Streamlit's black top header bar ══════════════════════ */
header[data-testid="stHeader"] {
    background-color: #f7f4ef !important;
    background:       #f7f4ef !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ══ Streamlit widget overrides ════════════════════════════════════ */
[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1.5px solid #d0cbc0 !important;
    color: #1c1917 !important;
    border-radius: 7px !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #b45309 !important;
    box-shadow: 0 0 0 3px rgba(180,83,9,0.12) !important;
}
[data-testid="stSelectbox"] > div > div {
    background: #ffffff !important;
    border: 1.5px solid #d0cbc0 !important;
    border-radius: 7px !important;
    color: #1c1917 !important;
}

/* ══ Run button — override ALL Streamlit button states ════════════ */
div[data-testid="stSidebar"] .stButton > button,
div[data-testid="stSidebar"] .stButton > button:link,
div[data-testid="stSidebar"] .stButton > button:visited,
div[data-testid="stSidebar"] .stButton > button:focus,
div[data-testid="stSidebar"] .stButton > button:active {
    background: #b45309 !important;
    background-color: #b45309 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.04em !important;
    border: none !important;
    outline: none !important;
    border-radius: 7px !important;
    padding: 0.65rem 1.2rem !important;
    width: 100% !important;
    transition: background 0.2s !important;
    box-shadow: 0 2px 6px rgba(180,83,9,0.25) !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background: #92400e !important;
    background-color: #92400e !important;
    color: #ffffff !important;
}
div[data-testid="stSidebar"] .stButton > button:disabled,
div[data-testid="stSidebar"] .stButton > button[disabled] {
    background: #e0dbd3 !important;
    background-color: #e0dbd3 !important;
    box-shadow: none !important;
    color: #a09080 !important;
    cursor: not-allowed !important;
}

/* ══ Generic buttons anywhere outside the sidebar (e.g. Discover Topics) ══ */
.stButton > button:not(.chip),
.stButton > button:not(.chip):link,
.stButton > button:not(.chip):visited,
.stButton > button:not(.chip):focus,
.stButton > button:not(.chip):active {
    background: #b45309 !important;
    background-color: #b45309 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.04em !important;
    border: none !important;
    outline: none !important;
    border-radius: 7px !important;
    padding: 0.65rem 1.2rem !important;
    transition: background 0.2s !important;
    box-shadow: 0 2px 6px rgba(180,83,9,0.25) !important;
}
.stButton > button:not(.chip):hover {
    background: #92400e !important;
    background-color: #92400e !important;
    color: #ffffff !important;
}
.stButton > button:not(.chip):disabled,
.stButton > button:not(.chip)[disabled] {
    background: #e0dbd3 !important;
    background-color: #e0dbd3 !important;
    box-shadow: none !important;
    color: #a09080 !important;
    cursor: not-allowed !important;
}

/* Suggestion chip buttons */
.stButton > button.chip {
    background: #ffffff !important;
    color: #b45309 !important;
    border: 1px solid #e8d8bc !important;
    border-radius: 20px !important;
    padding: 0.3rem 0.9rem !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    width: auto !important;
    transition: all 0.18s !important;
}
.stButton > button.chip:hover {
    background: #fff3e0 !important;
    border-color: #b45309 !important;
}

/* Download buttons */
div[data-testid="stDownloadButton"] > button {
    background: #ffffff !important;
    color: #1c1917 !important;
    border: 1.5px solid #d0cbc0 !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    border-color: #b45309 !important;
    color: #b45309 !important;
}

/* Misc overrides */
div[data-testid="stMarkdownContainer"] p { color: #2c2417; }
hr { border-color: #e2ddd4 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Session state
# ─────────────────────────────────────────────────────────────────
AGENTS_ARTICLE = [
    {"key": "research",  "icon": "🔍",   "name": "Research"},
    {"key": "pattern",   "icon": "🔎",   "name": "Pattern & Gap"},
    {"key": "synthesis", "icon": "✍️",   "name": "Synthesis"},
    {"key": "factual",   "icon": "🔬",   "name": "Factual Council"},
    {"key": "style",     "icon": "🎭",   "name": "Style Council"},
    {"key": "arbiter",   "icon": "👨‍⚖️", "name": "Arbiter"},
]

AGENTS_POST = [
    {"key": "research",       "icon": "🔍", "name": "Research"},
    {"key": "pattern",        "icon": "🔎", "name": "Pattern & Gap"},
    {"key": "post_synthesis", "icon": "💼", "name": "Post Synthesis"},
]

def _current_agents() -> list:
    """Return the agent list for the currently selected output mode."""
    return AGENTS_POST if st.session_state.get("output_mode") == "post" else AGENTS_ARTICLE

# Kept as a compatibility alias — anywhere the old code says AGENTS, resolve it
# to whichever list matches the current mode.
AGENTS = AGENTS_ARTICLE   # default so early code paths work

defaults = {
    "agent_states":    {a["key"]: "pending" for a in AGENTS_ARTICLE},
    "logs":            [],
    "final_report":    "",
    "saved_paths":     {},
    "running":         False,
    "done":            False,
    "error":           None,
    "pipeline_result": None,
    "domain_value":    "",
    "suggestions":     [],
    "show_suggestions":False,
    "loading_suggestions": False,
    # ── Post mode additions ────────────────────────────────────────
    "output_mode":           "article",   # "article" | "post"
    "post_framework_key":    DEFAULT_POST_FRAMEWORK_KEY,
    "discovery_candidates":  [],
    "discovery_focus":       "",
    "loading_discovery":     False,
    "post_candidates":       [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────
#  Agent card renderer
# ─────────────────────────────────────────────────────────────────
STATUS_LABELS = {
    "pending":  "Waiting",
    "running":  "Running…",
    "complete": "Complete",
    "error":    "Error",
}

def render_agent_cards() -> str:
    html = '<div class="agent-grid">'
    for a in _current_agents():
        state = st.session_state.agent_states.get(a["key"], "pending")
        label = STATUS_LABELS.get(state, state)
        html += (
            f'<div class="agent-card {state}">'
            f'  <span class="c-icon">{a["icon"]}</span>'
            f'  <div class="c-label">Agent</div>'
            f'  <div class="c-name">{a["name"]}</div>'
            f'  <div class="c-status">{label}</div>'
            f'</div>'
        )
    return html + "</div>"


# ─────────────────────────────────────────────────────────────────
#  Log panel renderer
# ─────────────────────────────────────────────────────────────────
def render_log_panel() -> str:
    lines = st.session_state.logs[-50:]
    html_lines = []
    for line in lines:
        css = ""
        if any(line.startswith(p) for p in ["✅", "🎉"]):
            css = "success"
        elif any(line.startswith(p) for p in ["⚠️", "🔑", "🚀", "🔍", "💾", "🔬", "🎭", "👨‍⚖️"]):
            css = "warn"
        elif line.startswith("❌"):
            css = "error"
        safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        html_lines.append(f'<div class="log-line {css}">{safe}</div>')
    return f'<div class="log-panel">{"".join(html_lines)}</div>'


# ─────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sb-brand">
      <div class="sb-title">Research<span>Pulse</span></div>
      <div class="sb-tagline">Multi-Agent Trend Research</div>
    </div>
    """, unsafe_allow_html=True)

    # ── API key status ─────────────────────────────────────────────
    api_key        = os.getenv("ANTHROPIC_API_KEY", "")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    openai_key     = os.getenv("OPENAI_API_KEY", "")
    groq_key       = os.getenv("GROQ_API_KEY", "")

    missing_required = []
    if not api_key:
        missing_required.append("ANTHROPIC_API_KEY")
    if not perplexity_key:
        missing_required.append("PERPLEXITY_API_KEY")

    if missing_required:
        st.error(
            "⚠️ Missing required keys:\n- " + "\n- ".join(missing_required) +
            "\n\nAdd them to your .env file."
        )
    else:
        gpt_badge = (
            '<span style="color:#15803d;">GPT-5.5 ✓</span>'
            if openai_key else
            '<span style="color:#a16207;">GPT lens skipped (no OPENAI_API_KEY)</span>'
        )
        llama_badge = (
            '<span style="color:#15803d;">Llama-Groq ✓</span>'
            if groq_key else
            '<span style="color:#a16207;">Llama fallback → Perplexity</span>'
        )
        st.markdown(
            '<div style="font-size:0.72rem;color:#15803d;margin-bottom:1rem;'
            'background:#f0fdf4;padding:8px 10px;border-radius:6px;border:1px solid #bbf7d0;'
            'line-height:1.5;">'
            '✅ Anthropic ✓ · Perplexity ✓<br>'
            f'<span style="font-size:0.65rem;">{gpt_badge} · {llama_badge}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── LangSmith observability status ────────────────────────────
    from pipeline.observability import langsmith_status as _ls_status
    _ls_text = _ls_status()
    if _ls_text.startswith("LangSmith: ✓"):
        _ls_bg, _ls_color, _ls_border = "#eef2ff", "#4338ca", "#c7d2fe"
    else:
        _ls_bg, _ls_color, _ls_border = "#fefce8", "#a16207", "#fde68a"
    st.markdown(
        f'<div style="font-size:0.68rem;color:{_ls_color};margin-bottom:1rem;'
        f'background:{_ls_bg};padding:6px 10px;border-radius:6px;border:1px solid {_ls_border};">'
        f'🔭 {_ls_text}</div>',
        unsafe_allow_html=True,
    )

    # ── OUTPUT MODE TOGGLE ─────────────────────────────────────────
    st.markdown('<div class="sb-label">Output Mode</div>', unsafe_allow_html=True)
    mode_choice = st.radio(
        label="output_mode_radio",
        label_visibility="collapsed",
        options=["📰 Article", "💼 LinkedIn Post"],
        index=0 if st.session_state.output_mode == "article" else 1,
        horizontal=True,
        key="output_mode_radio_key",
    )
    new_mode = "article" if mode_choice == "📰 Article" else "post"
    if new_mode != st.session_state.output_mode:
        st.session_state.output_mode          = new_mode
        st.session_state.discovery_candidates = []
        st.session_state.post_candidates      = []
        # Reset agent_states to match the new mode's agent list
        st.session_state.agent_states = {a["key"]: "pending" for a in _current_agents()}
        st.rerun()

    output_mode = st.session_state.output_mode

    # ── Domain input ───────────────────────────────────────────────
    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Domain / Topic</div>', unsafe_allow_html=True)
    domain_input = st.text_input(
        label="domain",
        label_visibility="collapsed",
        value=st.session_state.domain_value,
        placeholder="e.g. AI Agents, Climate Tech…",
        key="domain_text_input",
    )
    # Keep session state in sync
    if domain_input != st.session_state.domain_value:
        st.session_state.domain_value    = domain_input
        st.session_state.suggestions     = []
        st.session_state.show_suggestions = False

    # ── Topic suggestion button (shown when input is broad) ────────
    if domain_input.strip() and _is_broad(domain_input) and not st.session_state.running:
        st.markdown(
            '<div style="font-size:0.72rem;color:#b45309;margin-top:4px;">'
            '💡 That\'s quite broad — want specific angles?</div>',
            unsafe_allow_html=True,
        )
        if st.button("✨ Suggest specific angles", key="suggest_btn", disabled=not api_key):
            st.session_state.loading_suggestions = True
            with st.spinner("Thinking of angles…"):
                try:
                    st.session_state.suggestions = get_topic_suggestions(api_key, domain_input.strip())
                    st.session_state.show_suggestions = True
                except Exception as e:
                    st.error(f"Could not fetch suggestions: {e}")
            st.session_state.loading_suggestions = False

    # ── Show suggestion chips ──────────────────────────────────────
    if st.session_state.show_suggestions and st.session_state.suggestions:
        st.markdown("""
        <div class="suggest-wrap">
          <div class="suggest-title">Pick an angle ↓</div>
        </div>
        """, unsafe_allow_html=True)

        for suggestion in st.session_state.suggestions:
            if st.button(f"→ {suggestion}", key=f"chip_{suggestion}"):
                st.session_state.domain_value     = suggestion
                st.session_state.suggestions      = []
                st.session_state.show_suggestions = False
                st.rerun()

    # ── Depth & folder ─────────────────────────────────────────────
    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Your Name (for byline)</div>',
                unsafe_allow_html=True)
    author_name = st.text_input(
        label="author",
        label_visibility="collapsed",
        value="",
        placeholder="e.g. Siddhant Hardikar",
        help="Shown in the HTML byline. Leave blank to omit.",
    )

    # ── Writer persona (atomic domain switch) ─────────────────────
    from pipeline.personas import PERSONAS, DEFAULT_PERSONA_KEY
    _persona_keys = list(PERSONAS.keys())
    _persona_default_idx = _persona_keys.index(DEFAULT_PERSONA_KEY)
    _persona_help = "\n".join(f"• {p.name}: {p.description}" for p in PERSONAS.values())

    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Writer Persona</div>',
                unsafe_allow_html=True)
    persona_key = st.selectbox(
        label="persona",
        label_visibility="collapsed",
        options=_persona_keys,
        format_func=lambda k: PERSONAS[k].name,
        index=_persona_default_idx,
        help=_persona_help,
    )
    _persona_obj = PERSONAS[persona_key]
    _persona_badge_color = "#a16207" if _persona_obj.domain_guardrails else "#666"
    st.markdown(
        f'<div style="font-size:0.68rem;color:{_persona_badge_color};margin-top:-4px;'
        f'line-height:1.4;">'
        f'<em>{_persona_obj.description}</em>'
        + ("<br>⚠️ Strict guardrails: knowledge only, no advice." if _persona_obj.domain_guardrails else "")
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Research Depth</div>',
                unsafe_allow_html=True)
    depth = st.selectbox(
        label="depth",
        label_visibility="collapsed",
        options=["Quick", "Standard", "Deep"],
        index=1,
        help="Quick ≈ 2 min · Standard ≈ 4 min · Deep ≈ 7 min",
    )

    # ── Article template OR Post framework (mode-dependent) ──────
    from pipeline.templates import TEMPLATES, DEFAULT_TEMPLATE_KEY

    if output_mode == "article":
        _template_keys = list(TEMPLATES.keys())
        _default_idx   = _template_keys.index(DEFAULT_TEMPLATE_KEY)
        _template_help = "\n".join(f"• {t.name}: {t.best_for}" for t in TEMPLATES.values())

        st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Article Template</div>',
                    unsafe_allow_html=True)
        template_key = st.selectbox(
            label="template",
            label_visibility="collapsed",
            options=_template_keys,
            format_func=lambda k: TEMPLATES[k].name,
            index=_default_idx,
            help=_template_help,
        )
        st.markdown(
            f'<div style="font-size:0.68rem;color:#888;margin-top:-4px;line-height:1.4;">'
            f'<em>Best for: {TEMPLATES[template_key].best_for}</em></div>',
            unsafe_allow_html=True,
        )
        post_framework_key = DEFAULT_POST_FRAMEWORK_KEY   # placeholder — unused in article mode

    else:  # post mode
        _pf_keys = list(POST_FRAMEWORKS.keys())
        _pf_default_idx = _pf_keys.index(st.session_state.post_framework_key)
        _pf_help = "\n".join(f"• {p.name}: {p.best_for}" for p in POST_FRAMEWORKS.values())

        st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Post Framework</div>',
                    unsafe_allow_html=True)
        post_framework_key = st.selectbox(
            label="post_framework",
            label_visibility="collapsed",
            options=_pf_keys,
            format_func=lambda k: POST_FRAMEWORKS[k].name,
            index=_pf_default_idx,
            help=_pf_help,
        )
        st.session_state.post_framework_key = post_framework_key
        _pf_obj = POST_FRAMEWORKS[post_framework_key]
        st.markdown(
            f'<div style="font-size:0.68rem;color:#888;margin-top:-4px;line-height:1.4;">'
            f'<em>Best for: {_pf_obj.best_for}</em><br>'
            f'<span style="color:#a09080;">Optimizes for: {", ".join(_pf_obj.optimizes_for)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        template_key = DEFAULT_TEMPLATE_KEY   # placeholder — unused in post mode

    # ── Output folders — auto-set by persona ─────────────────────
    _BASE = "/Users/siddhant/Desktop/projects/Project Documentation/Research Pulse Project Documentation"
    _FOLDER_DEFAULTS = {
        "tech":   {
            "md":    f"{_BASE}/AI Obsidian Files",
            "html":  f"{_BASE}/AI HTML Files",
            "posts": f"{_BASE}/AI LinkedIn Posts",
        },
        "health": {
            "md":    f"{_BASE}/Health Obsidian Files",
            "html":  f"{_BASE}/Health HTML Files",
            "posts": f"{_BASE}/Health LinkedIn Posts",
        },
    }
    _defaults = _FOLDER_DEFAULTS.get(persona_key, _FOLDER_DEFAULTS["tech"])

    if output_mode == "article":
        st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Markdown Folder (.md)</div>',
                    unsafe_allow_html=True)
        md_folder = st.text_input(
            label="md_folder",
            label_visibility="collapsed",
            value=_defaults["md"],
            help="Obsidian / markdown file saved here",
        )

        st.markdown('<div class="sb-label" style="margin-top:0.6rem;">HTML Folder (_publish.html)</div>',
                    unsafe_allow_html=True)
        html_folder = st.text_input(
            label="html_folder",
            label_visibility="collapsed",
            value=_defaults["html"],
            help="Publish-ready HTML file saved here",
        )
        posts_folder = _defaults["posts"]   # unused in article mode
    else:
        st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Posts Folder</div>',
                    unsafe_allow_html=True)
        posts_folder = st.text_input(
            label="posts_folder",
            label_visibility="collapsed",
            value=_defaults["posts"],
            help="All 3 post candidates saved to a single .md file here",
        )
        md_folder   = _defaults["md"]     # unused in post mode
        html_folder = _defaults["html"]   # unused in post mode

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # Use domain_value from session state (updated by chip clicks)
    active_domain = st.session_state.domain_value.strip()

    run_button = st.button(
        "▶  Generate LinkedIn Posts" if output_mode == "post" else "▶  Generate Article",
        disabled=(not active_domain or st.session_state.running or bool(missing_required)),
    )

    # ── Last report paths ──────────────────────────────────────────
    if st.session_state.done and st.session_state.saved_paths:
        st.markdown(
            "<hr style='border-color:#d0cbc0;margin:1.2rem 0'>",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sb-label">Saved Files</div>', unsafe_allow_html=True)
        p = st.session_state.saved_paths
        if output_mode == "post":
            st.markdown(
                f'<div style="font-size:0.7rem;color:#6b5e52;word-break:break-all;'
                f'background:#fff;border:1px solid #ddd8ce;border-radius:5px;padding:6px 8px;">'
                f'💼 {p.get("post_path","")}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:0.7rem;color:#6b5e52;word-break:break-all;'
                f'background:#fff;border:1px solid #ddd8ce;border-radius:5px;padding:6px 8px;margin-bottom:6px;">'
                f'📄 {p.get("md_path","")}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="font-size:0.7rem;color:#6b5e52;word-break:break-all;'
                f'background:#fff;border:1px solid #ddd8ce;border-radius:5px;padding:6px 8px;">'
                f'🌐 {p.get("html_path","")}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.65rem;color:#c0b8aa;text-align:center;">'
        'Built with Claude · Research Pulse</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────
#  Main area — header
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rp-header">
  <div class="rp-title">Research<span class="rp-accent">Pulse</span></div>
  <div class="rp-subtitle">AI-Powered Trend Research &amp; Report Generation</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Discovery panel (Post mode only, when idle)
# ─────────────────────────────────────────────────────────────────
if output_mode == "post" and not st.session_state.running and not st.session_state.post_candidates:
    st.markdown("""
    <div style="background:#fff9f0;border:1px solid #e8d8bc;border-radius:10px;
                padding:14px 18px;margin-bottom:1.2rem;">
      <div style="font-family:'Playfair Display',serif;font-size:1rem;color:#92400e;
                  font-weight:700;margin-bottom:6px;">
        💡 Don't have a topic in mind?
      </div>
      <div style="font-size:0.82rem;color:#7a6e60;line-height:1.55;">
        Let Discovery scan the last 7-14 days of AI industry signal and surface
        candidate story angles scored against the 6-criteria filter.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_focus, col_discover = st.columns([3, 1])
    with col_focus:
        focus_area = st.text_input(
            label="focus_area",
            label_visibility="collapsed",
            value=st.session_state.discovery_focus,
            placeholder="Optional focus area (e.g. enterprise AI, infrastructure)",
            key="discovery_focus_input",
        )
    with col_discover:
        discover_clicked = st.button(
            "🔍 Discover Topics",
            key="discover_btn",
            disabled=st.session_state.loading_discovery,
            use_container_width=True,
        )

    if discover_clicked:
        st.session_state.loading_discovery = True
        st.session_state.discovery_focus   = focus_area
        with st.spinner("Scanning the AI industry for high-signal angles..."):
            try:
                disc = run_discovery_agent(
                    focus_area=focus_area.strip(),
                    max_candidates=8,
                )
                st.session_state.discovery_candidates = disc.get("candidates", [])
                if not st.session_state.discovery_candidates:
                    st.warning("No candidates scoring 4+ found. Try a different focus area or run again.")
            except Exception as e:
                st.error(f"Discovery failed: {e}")
        st.session_state.loading_discovery = False

    # ── Candidate cards ────────────────────────────────────────────
    if st.session_state.discovery_candidates:
        st.markdown(
            f'<div style="font-size:0.75rem;color:#92400e;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.08em;margin:1.4rem 0 0.6rem;">'
            f'📋 {len(st.session_state.discovery_candidates)} Candidates Found — Pick One</div>',
            unsafe_allow_html=True,
        )

        _criteria_labels = {
            "timely":            "Timely",
            "non_obvious":       "Non-obvious",
            "audience_specific": "Audience",
            "point_of_view":     "POV",
            "evidence_backed":   "Evidence",
            "discussion_worthy": "Discussion",
        }

        for i, cand in enumerate(st.session_state.discovery_candidates):
            criteria = cand.get("criteria", {})
            hits_html = " ".join(
                f'<span style="background:{"#dcfce7" if v else "#fee2e2"};'
                f'color:{"#166534" if v else "#991b1b"};padding:2px 8px;border-radius:12px;'
                f'font-size:0.68rem;font-weight:600;margin-right:3px;">'
                f'{"✓" if v else "✗"} {_criteria_labels.get(k, k)}</span>'
                for k, v in criteria.items()
            )
            source_url = cand.get("primary_source", "")
            source_html = (
                f'<a href="{source_url}" target="_blank" '
                f'style="color:#b45309;font-size:0.72rem;text-decoration:none;">→ Primary source</a>'
                if source_url else ""
            )

            st.markdown(f"""
            <div style="background:#fff;border:1.5px solid #ddd8ce;border-radius:10px;
                        padding:16px 20px;margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;
                          gap:12px;margin-bottom:8px;">
                <div style="font-family:'Playfair Display',serif;font-size:1.02rem;
                            color:#1c1917;font-weight:600;line-height:1.35;flex:1;">
                  {cand.get("topic", "")}
                </div>
                <div style="background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:14px;
                            font-size:0.72rem;font-weight:700;white-space:nowrap;">
                  {cand.get("score", 0)}/6
                </div>
              </div>
              <div style="font-size:0.82rem;color:#4b4238;margin-bottom:10px;line-height:1.55;">
                {cand.get("story", "")}
              </div>
              <div style="margin-bottom:10px;">{hits_html}</div>
              <div style="font-size:0.74rem;color:#7a6e60;font-style:italic;margin-bottom:8px;">
                {cand.get("why_it_scores", "")}
              </div>
              <div style="font-size:0.72rem;color:#a09080;">
                <strong>Audience:</strong> {cand.get("audience", "")}<br>
                {source_html}
              </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("→ Use this topic", key=f"use_cand_{i}"):
                st.session_state.domain_value        = cand.get("topic", "")
                st.session_state.discovery_candidates = []
                st.rerun()


# ─────────────────────────────────────────────────────────────────
#  Trigger pipeline
# ─────────────────────────────────────────────────────────────────
if run_button and active_domain:
    _mode_agents = _current_agents()
    st.session_state.agent_states     = {a["key"]: "pending" for a in _mode_agents}
    st.session_state.logs             = ["🚀 Pipeline starting…"]
    st.session_state.final_report     = ""
    st.session_state.post_candidates  = []
    st.session_state.saved_paths      = {}
    st.session_state.running          = True
    st.session_state.done             = False
    st.session_state.error            = None
    st.session_state.suggestions      = []
    st.session_state.show_suggestions = False


# ─────────────────────────────────────────────────────────────────
#  Pipeline execution (live)
# ─────────────────────────────────────────────────────────────────
if st.session_state.running and not st.session_state.done:
    from pipeline.orchestrator import run_pipeline

    cards_ph = st.empty()
    log_ph   = st.empty()
    cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
    log_ph.markdown(render_log_panel(),    unsafe_allow_html=True)

    AGENT_ORDER = [a["key"] for a in _current_agents()]

    def callback(msg: str, agent_key: str):
        if msg:
            st.session_state.logs.append(msg)
        if agent_key in AGENT_ORDER:
            idx = AGENT_ORDER.index(agent_key)
            for i, key in enumerate(AGENT_ORDER):
                if i < idx:
                    if st.session_state.agent_states[key] == "running":
                        st.session_state.agent_states[key] = "complete"
                elif i == idx:
                    if st.session_state.agent_states[key] == "pending":
                        st.session_state.agent_states[key] = "running"
                    if msg and msg.startswith("✅"):
                        st.session_state.agent_states[key] = "complete"
                    if msg and msg.startswith("❌"):
                        st.session_state.agent_states[key] = "error"
        cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
        log_ph.markdown(render_log_panel(),    unsafe_allow_html=True)

    result = run_pipeline(
        domain=active_domain,
        depth=depth,
        output_mode=output_mode,
        template_key=template_key,
        persona_key=persona_key,
        post_framework_key=post_framework_key,
        md_folder=md_folder.strip() if isinstance(md_folder, str) else md_folder,
        html_folder=html_folder.strip() if isinstance(html_folder, str) else html_folder,
        posts_folder=posts_folder.strip() if isinstance(posts_folder, str) else posts_folder,
        author_name=author_name.strip(),
        callback=callback,
    )

    # Mark remaining running agents complete
    for key in AGENT_ORDER:
        if st.session_state.agent_states[key] == "running":
            st.session_state.agent_states[key] = "complete"

    st.session_state.final_report    = result.final_report
    st.session_state.post_candidates = result.post_candidates
    st.session_state.saved_paths     = result.saved_paths
    st.session_state.error           = result.error
    st.session_state.running         = False
    st.session_state.done            = True
    st.session_state.pipeline_result = result

    cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
    log_ph.markdown(render_log_panel(),    unsafe_allow_html=True)

    if not result.error:
        if output_mode == "post":
            st.success(f"🎉 Generated {len(result.post_candidates)} post candidates! Scroll down to review.")
        else:
            st.success("🎉 Report complete! Scroll down to read it.")
    else:
        st.error(f"Pipeline error: {result.error}")


# ─────────────────────────────────────────────────────────────────
#  Static display (idle / between runs)
# ─────────────────────────────────────────────────────────────────
elif not st.session_state.running:
    st.markdown(render_agent_cards(), unsafe_allow_html=True)

    if st.session_state.logs:
        st.markdown(render_log_panel(), unsafe_allow_html=True)
    else:
        if output_mode == "post":
            _empty_flow = "Research → Pattern → Post Synthesis (×3 candidates)"
            _empty_title = "Pick a framework and enter a topic — or use Discovery above"
        else:
            _empty_flow = "Research → Patterns → Synthesis → Factual → Style → Arbiter"
            _empty_title = "Enter a topic and run the pipeline"
        st.markdown(f"""
        <div class="empty-state">
          <div class="empty-icon">{"💼" if output_mode == "post" else "🔬"}</div>
          <div class="empty-title">{_empty_title}</div>
          <div class="empty-sub">{_empty_flow}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Final report display — article mode
# ─────────────────────────────────────────────────────────────────
if output_mode == "article" and st.session_state.final_report:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
    <div class="report-hdr">
      <span class="report-hdr-title">Final Report</span>
      <span class="report-badge">✓ Reviewed</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div class="report-wrapper">{_md_to_html(st.session_state.final_report)}</div>',
        unsafe_allow_html=True,
    )

    # Download row
    col1, col2, col3 = st.columns([1, 1.4, 2])
    with col1:
        st.download_button(
            label="📥 Download .md",
            data=st.session_state.final_report,
            file_name=f"report_{active_domain[:30].replace(' ','_')}.md",
            mime="text/markdown",
        )
    with col2:
        html_path = st.session_state.saved_paths.get("html_path", "")
        if html_path:
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    html_data = f.read()
                st.download_button(
                    label="📤 Download for Substack/Medium",
                    data=html_data,
                    file_name=f"report_{active_domain[:30].replace(' ','_')}_publish.html",
                    mime="text/html",
                )
            except Exception:
                pass

    if st.session_state.saved_paths:
        folder = st.session_state.saved_paths.get("folder", "")
        st.markdown(
            f'<div style="font-size:0.72rem;color:#a09080;margin-top:0.5rem;">'
            f'📁 Saved to: <code style="color:#6b5e52;background:#f0ece4;'
            f'padding:1px 5px;border-radius:3px;">{folder}</code></div>',
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────────
#  Post candidates display — post mode
# ─────────────────────────────────────────────────────────────────
if output_mode == "post" and st.session_state.post_candidates:
    st.markdown("<hr>", unsafe_allow_html=True)
    _fw = POST_FRAMEWORKS.get(st.session_state.post_framework_key)
    _fw_name = _fw.name if _fw else "Post"
    st.markdown(f"""
    <div class="report-hdr">
      <span class="report-hdr-title">LinkedIn Post Candidates</span>
      <span class="report-badge">{len(st.session_state.post_candidates)} Drafts · {_fw_name}</span>
    </div>
    """, unsafe_allow_html=True)

    _angle_labels = [
        "Leads with strongest evidence",
        "Leads with sharpest contrarian angle",
        "Leads with second-order implication",
    ]

    for i, post in enumerate(st.session_state.post_candidates, 1):
        _angle = _angle_labels[i-1] if i-1 < len(_angle_labels) else ""
        st.markdown(f"""
        <div style="background:#fff;border:1.5px solid #ddd8ce;border-radius:10px;
                    padding:22px 26px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-bottom:14px;">
            <div style="font-size:0.72rem;color:#92400e;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.08em;">
              Candidate {i}
            </div>
            <div style="font-size:0.7rem;color:#a09080;font-style:italic;">
              {_angle}
            </div>
          </div>
          <div style="font-family:'Inter',sans-serif;font-size:0.94rem;color:#2c2417;
                      white-space:pre-wrap;line-height:1.7;">{post}</div>
        </div>
        """, unsafe_allow_html=True)

        col_dl, _blank = st.columns([1, 4])
        with col_dl:
            st.download_button(
                label=f"📥 Download #{i}",
                data=post,
                file_name=f"post_{active_domain[:30].replace(' ','_')}_{i}.txt",
                mime="text/plain",
                key=f"dl_post_{i}",
            )

    if st.session_state.saved_paths.get("post_path"):
        st.markdown(
            f'<div style="font-size:0.72rem;color:#a09080;margin-top:1rem;">'
            f'📁 All candidates saved to: <code style="color:#6b5e52;background:#f0ece4;'
            f'padding:1px 5px;border-radius:3px;">'
            f'{st.session_state.saved_paths.get("post_path", "")}</code></div>',
            unsafe_allow_html=True,
        )