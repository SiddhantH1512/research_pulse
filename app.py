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
AGENTS = [
    {"key": "research",  "icon": "🔍",   "name": "Research"},
    {"key": "pattern",   "icon": "🔎",   "name": "Pattern & Gap"},
    {"key": "synthesis", "icon": "✍️",   "name": "Synthesis"},
    {"key": "factual",   "icon": "🔬",   "name": "Factual Council"},
    {"key": "style",     "icon": "🎭",   "name": "Style Council"},
    {"key": "arbiter",   "icon": "👨‍⚖️", "name": "Arbiter"},
]

defaults = {
    "agent_states":    {a["key"]: "pending" for a in AGENTS},
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
    for a in AGENTS:
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

    # ── Domain input ───────────────────────────────────────────────
    st.markdown('<div class="sb-label">Domain / Topic</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Research Depth</div>',
                unsafe_allow_html=True)
    depth = st.selectbox(
        label="depth",
        label_visibility="collapsed",
        options=["Quick", "Standard", "Deep"],
        index=1,
        help="Quick ≈ 2 min · Standard ≈ 4 min · Deep ≈ 7 min",
    )

    st.markdown('<div class="sb-label" style="margin-top:1.2rem;">Output Folder</div>',
                unsafe_allow_html=True)
    output_folder = st.text_input(
        label="folder",
        label_visibility="collapsed",
        value=str(Path.home() / "research_pulse_reports"),
        help="Reports saved here as .md and _publish.html",
    )

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # Use domain_value from session state (updated by chip clicks)
    active_domain = st.session_state.domain_value.strip()

    run_button = st.button(
        "▶  Run Pipeline",
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
#  Trigger pipeline
# ─────────────────────────────────────────────────────────────────
if run_button and active_domain:
    st.session_state.agent_states  = {a["key"]: "pending" for a in AGENTS}
    st.session_state.logs          = ["🚀 Pipeline starting…"]
    st.session_state.final_report  = ""
    st.session_state.saved_paths   = {}
    st.session_state.running       = True
    st.session_state.done          = False
    st.session_state.error         = None
    st.session_state.suggestions   = []
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

    AGENT_ORDER = [a["key"] for a in AGENTS]

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
        output_folder=output_folder.strip() or "reports",
        author_name=author_name.strip(),
        callback=callback,
    )

    # Mark remaining running agents complete
    for key in AGENT_ORDER:
        if st.session_state.agent_states[key] == "running":
            st.session_state.agent_states[key] = "complete"

    st.session_state.final_report    = result.final_report
    st.session_state.saved_paths     = result.saved_paths
    st.session_state.error           = result.error
    st.session_state.running         = False
    st.session_state.done            = True
    st.session_state.pipeline_result = result

    cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
    log_ph.markdown(render_log_panel(),    unsafe_allow_html=True)

    if not result.error:
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
        st.markdown("""
        <div class="empty-state">
          <div class="empty-icon">🔬</div>
          <div class="empty-title">Enter a topic and run the pipeline</div>
          <div class="empty-sub">Research → Patterns → Synthesis → Factual → Style → Arbiter</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Final report display
# ─────────────────────────────────────────────────────────────────
if st.session_state.final_report:
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
