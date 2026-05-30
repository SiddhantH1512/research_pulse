"""
app.py — Research Pulse
────────────────────────
Streamlit frontend for the multi-agent research pipeline.
Dark editorial aesthetic, live progress, beautiful report display.
"""

import os
import threading
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────
#  Inline markdown → HTML helper  (defined early — used later)
# ─────────────────────────────────────────────────────────────────
def _md_to_html(md: str) -> str:
    try:
        import markdown2
        return markdown2.markdown(md, extras=["fenced-code-blocks", "tables", "strike"])
    except ImportError:
        import re
        html = md
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        paras = []
        for line in html.split("\n"):
            if line.strip() and not line.startswith("<"):
                paras.append(f"<p>{line}</p>")
            else:
                paras.append(line)
        return "\n".join(paras)


# ─────────────────────────────────────────────────────────────────
#  Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Research Pulse",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
#  CSS — Dark editorial theme
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
/* ── Base ─────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #080810 !important;
    font-family: 'Inter', sans-serif;
}

[data-testid="stSidebar"] {
    background-color: #0d0d1a !important;
    border-right: 1px solid #1a1a2e;
}

/* ── Header ──────────────────────────────────────────────────── */
.rp-header {
    padding: 1.2rem 0 2rem 0;
    border-bottom: 1px solid #1a1a2e;
    margin-bottom: 2rem;
}
.rp-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 2.4rem;
    font-weight: 900;
    color: #f0f0fc;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}
.rp-subtitle {
    font-size: 0.85rem;
    color: #555570;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.rp-accent { color: #f5b800; }

/* ── Agent Cards ─────────────────────────────────────────────── */
.agent-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 1.5rem;
}
.agent-card {
    background: #10101e;
    border: 1px solid #1a1a2e;
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.35s ease;
    position: relative;
    overflow: hidden;
}
.agent-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: transparent;
    transition: background 0.35s ease;
}
.agent-card.pending  { opacity: 0.45; }
.agent-card.running  { border-color: #f5b800; opacity: 1; }
.agent-card.running::before { background: #f5b800; }
.agent-card.running .card-status { color: #f5b800; }
.agent-card.complete { border-color: #22c55e; opacity: 1; }
.agent-card.complete::before { background: #22c55e; }
.agent-card.complete .card-status { color: #22c55e; }
.agent-card.error    { border-color: #ef4444; }
.agent-card.error::before { background: #ef4444; }
.agent-card.error .card-status { color: #ef4444; }

.card-icon  { font-size: 1.4rem; margin-bottom: 6px; display: block; }
.card-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: #555570; margin-bottom: 2px; }
.card-name  { font-size: 0.92rem; font-weight: 600; color: #c8c8e0; }
.card-status{ font-size: 0.72rem; margin-top: 6px; font-weight: 500; color: #555570; }

/* ── Log Panel ───────────────────────────────────────────────── */
.log-panel {
    background: #06060e;
    border: 1px solid #14142a;
    border-radius: 8px;
    padding: 14px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #666688;
    max-height: 240px;
    overflow-y: auto;
    margin-bottom: 1.5rem;
    line-height: 1.6;
}
.log-line { margin: 1px 0; }
.log-line.success { color: #22c55e; }
.log-line.warn    { color: #f5b800; }
.log-line.error   { color: #ef4444; }

/* ── Report Section ──────────────────────────────────────────── */
.report-wrapper {
    background: #0d0d1c;
    border: 1px solid #1a1a2e;
    border-radius: 12px;
    padding: 2.5rem 3rem;
    margin-top: 1rem;
    font-family: 'Inter', sans-serif;
    color: #d8d8f0;
    line-height: 1.8;
}
.report-wrapper h1, .report-wrapper h2 {
    font-family: 'Playfair Display', Georgia, serif;
    color: #f0f0fc;
}
.report-wrapper h2 {
    font-size: 1.35rem;
    margin-top: 2rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1e1e30;
}
.report-wrapper h3 { color: #b0b0cc; font-size: 1.05rem; }
.report-wrapper strong { color: #f5b800; }
.report-wrapper p { margin-bottom: 1rem; }

/* ── Sidebar ─────────────────────────────────────────────────── */
.sidebar-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #555570;
    margin-bottom: 0.4rem;
}

/* ── Streamlit overrides ─────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] select,
[data-testid="stTextArea"] textarea {
    background: #10101e !important;
    border: 1px solid #1e1e2e !important;
    color: #d8d8f0 !important;
    border-radius: 6px !important;
}
.stButton > button {
    background: #f5b800 !important;
    color: #080810 !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.4rem !important;
    width: 100% !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stButton > button:disabled { opacity: 0.35 !important; }
div[data-testid="stMarkdownContainer"] p { color: #d8d8f0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Session state init
# ─────────────────────────────────────────────────────────────────
AGENTS = [
    {"key": "research",  "icon": "🔍", "name": "Research"},
    {"key": "pattern",   "icon": "🔎", "name": "Pattern & Gap"},
    {"key": "synthesis", "icon": "✍️",  "name": "Synthesis"},
    {"key": "reviewer",  "icon": "👁️",  "name": "Reviewer"},
]

defaults = {
    "agent_states":  {a["key"]: "pending" for a in AGENTS},
    "logs":          [],
    "final_report":  "",
    "saved_paths":   {},
    "running":       False,
    "done":          False,
    "error":         None,
    "pipeline_result": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────
#  Helper: render agent cards
# ─────────────────────────────────────────────────────────────────
STATUS_LABELS = {
    "pending":  "Waiting",
    "running":  "Running…",
    "complete": "Complete",
    "error":    "Error",
}

def render_agent_cards():
    cards_html = '<div class="agent-grid">'
    for a in AGENTS:
        state  = st.session_state.agent_states.get(a["key"], "pending")
        label  = STATUS_LABELS.get(state, state)
        cards_html += f"""
        <div class="agent-card {state}">
          <span class="card-icon">{a['icon']}</span>
          <div class="card-label">Agent</div>
          <div class="card-name">{a['name']}</div>
          <div class="card-status">{label}</div>
        </div>"""
    cards_html += "</div>"
    return cards_html


# ─────────────────────────────────────────────────────────────────
#  Helper: render log panel
# ─────────────────────────────────────────────────────────────────
def render_log_panel():
    lines = st.session_state.logs[-40:]  # keep last 40 lines
    html_lines = []
    for line in lines:
        if line.startswith("✅") or line.startswith("🎉"):
            css = "success"
        elif line.startswith("⚠️") or line.startswith("🔑"):
            css = "warn"
        elif line.startswith("❌"):
            css = "error"
        else:
            css = ""
        safe_line = (line
                     .replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;"))
        # render **bold** in log
        safe_line = safe_line.replace("**", "<b>").replace("**", "</b>")
        html_lines.append(f'<div class="log-line {css}">{safe_line}</div>')
    return f'<div class="log-panel">{"".join(html_lines)}</div>'


# ─────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0 1.5rem 0; border-bottom: 1px solid #1a1a2e; margin-bottom: 1.5rem;">
      <div style="font-family: 'Playfair Display', serif; font-size: 1.5rem; font-weight: 900; color: #f0f0fc;">
        Research<span style="color:#f5b800;">Pulse</span>
      </div>
      <div style="font-size: 0.7rem; color: #444460; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px;">
        Multi-Agent Trend Research
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── API Key check ──────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("⚠️ ANTHROPIC_API_KEY not found.\nCreate a `.env` file or set the env var.")
    else:
        st.markdown('<div style="font-size:0.72rem;color:#22c55e;margin-bottom:1rem;">✅ API key detected</div>',
                    unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">Domain / Topic</div>', unsafe_allow_html=True)
    domain = st.text_input(
        label="domain",
        label_visibility="collapsed",
        value="",
        placeholder="e.g. AI Agents, Web3, Climate Tech…",
    )

    st.markdown('<div class="sidebar-label" style="margin-top:1rem;">Research Depth</div>',
                unsafe_allow_html=True)
    depth = st.selectbox(
        label="depth",
        label_visibility="collapsed",
        options=["Quick", "Standard", "Deep"],
        index=1,
        help="Quick: ~3 searches. Standard: ~6. Deep: ~10.",
    )

    st.markdown('<div class="sidebar-label" style="margin-top:1rem;">Output Folder</div>',
                unsafe_allow_html=True)
    output_folder = st.text_input(
        label="folder",
        label_visibility="collapsed",
        value=str(Path.home() / "research_pulse_reports"),
        help="Reports are saved here as .md and .html",
    )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    run_button = st.button(
        "▶  Run Pipeline",
        disabled=(not domain.strip() or st.session_state.running),
    )

    if st.session_state.done and st.session_state.saved_paths:
        st.markdown("<hr style='border-color:#1a1a2e;margin:1.5rem 0'>", unsafe_allow_html=True)
        st.markdown('<div class="sidebar-label">Last Report</div>', unsafe_allow_html=True)
        p = st.session_state.saved_paths
        st.code(p.get("md_path", ""), language=None)
        st.code(p.get("html_path", ""), language=None)

    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.65rem;color:#2e2e48;text-align:center;">'
        'Built with Claude · Research Pulse</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────
#  Main area — Header
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rp-header">
  <div class="rp-title">Research<span class="rp-accent">Pulse</span></div>
  <div class="rp-subtitle">AI-Powered Trend Research &amp; Report Generation</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Pipeline execution
# ─────────────────────────────────────────────────────────────────
if run_button and domain.strip():
    # Reset state
    st.session_state.agent_states  = {a["key"]: "pending" for a in AGENTS}
    st.session_state.logs          = ["🚀 Pipeline starting…"]
    st.session_state.final_report  = ""
    st.session_state.saved_paths   = {}
    st.session_state.running       = True
    st.session_state.done          = False
    st.session_state.error         = None


# ── Dynamic pipeline execution ─────────────────────────────────
if st.session_state.running and not st.session_state.done:

    from pipeline.orchestrator import run_pipeline

    cards_ph  = st.empty()
    log_ph    = st.empty()

    cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
    log_ph.markdown(render_log_panel(), unsafe_allow_html=True)

    AGENT_ORDER = [a["key"] for a in AGENTS]

    def callback(msg: str, agent_key: str):
        """Called by orchestrator for every progress update."""
        if msg:
            st.session_state.logs.append(msg)

        # State transitions
        if agent_key in AGENT_ORDER:
            # Mark current agent running
            current_idx = AGENT_ORDER.index(agent_key)
            for i, key in enumerate(AGENT_ORDER):
                if i < current_idx:
                    if st.session_state.agent_states[key] == "running":
                        st.session_state.agent_states[key] = "complete"
                elif i == current_idx:
                    if st.session_state.agent_states[key] == "pending":
                        st.session_state.agent_states[key] = "running"
                    if msg and msg.startswith("✅"):
                        st.session_state.agent_states[key] = "complete"
                    if msg and msg.startswith("❌"):
                        st.session_state.agent_states[key] = "error"

        # Re-render cards and log live
        cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
        log_ph.markdown(render_log_panel(), unsafe_allow_html=True)

    # ── Run pipeline (blocking — Streamlit runs this synchronously) ──
    result = run_pipeline(
        domain=domain.strip(),
        depth=depth,
        output_folder=output_folder.strip() or "reports",
        callback=callback,
    )

    # ── Mark all agents complete ──────────────────────────────────
    for key in AGENT_ORDER:
        if st.session_state.agent_states[key] == "running":
            st.session_state.agent_states[key] = "complete"

    st.session_state.final_report   = result.final_report
    st.session_state.saved_paths    = result.saved_paths
    st.session_state.error          = result.error
    st.session_state.running        = False
    st.session_state.done           = True
    st.session_state.pipeline_result = result

    # Final card + log render
    cards_ph.markdown(render_agent_cards(), unsafe_allow_html=True)
    log_ph.markdown(render_log_panel(), unsafe_allow_html=True)

    if not result.error:
        st.success("🎉 Report complete! See below.")
    else:
        st.error(f"Pipeline error: {result.error}")


# ─────────────────────────────────────────────────────────────────
#  Static display when not running
# ─────────────────────────────────────────────────────────────────
elif not st.session_state.running:
    st.markdown(render_agent_cards(), unsafe_allow_html=True)

    if st.session_state.logs:
        st.markdown(render_log_panel(), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="
            background:#0d0d1c;border:1px dashed #1a1a2e;border-radius:10px;
            padding:3rem;text-align:center;color:#333350;margin-bottom:2rem;
        ">
          <div style="font-size:2rem;margin-bottom:0.8rem;">🔬</div>
          <div style="font-family:'Playfair Display',serif;font-size:1.1rem;color:#444464;margin-bottom:0.5rem;">
            Enter a domain and run the pipeline
          </div>
          <div style="font-size:0.8rem;">
            Research → Patterns → Synthesis → Review → Report
          </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  Final Report Display
# ─────────────────────────────────────────────────────────────────
if st.session_state.final_report:
    st.markdown("---")
    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:1rem;">
      <span style="font-family:'Playfair Display',serif;font-size:1.3rem;color:#f0f0fc;font-weight:700;">
        Final Report
      </span>
      <span style="font-size:0.7rem;color:#f5b800;text-transform:uppercase;
                   letter-spacing:0.1em;background:#1a1400;padding:3px 8px;border-radius:4px;">
        Reviewed
      </span>
    </div>
    """, unsafe_allow_html=True)

    # Render markdown in styled container
    st.markdown(
        f'<div class="report-wrapper">{_md_to_html(st.session_state.final_report)}</div>',
        unsafe_allow_html=True,
    )

    # ── Download buttons ──────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.download_button(
            label="📥 Download .md",
            data=st.session_state.final_report,
            file_name=f"report_{domain[:30].replace(' ','_')}.md",
            mime="text/markdown",
        )
    with col2:
        if st.session_state.saved_paths.get("html_path"):
            try:
                with open(st.session_state.saved_paths["html_path"], "r") as f:
                    html_data = f.read()
                st.download_button(
                    label="📄 Download .html",
                    data=html_data,
                    file_name=f"report_{domain[:30].replace(' ','_')}.html",
                    mime="text/html",
                )
            except Exception:
                pass

    if st.session_state.saved_paths:
        st.markdown(
            f'<div style="font-size:0.72rem;color:#444460;margin-top:0.5rem;">'
            f'📁 Saved to: <code style="color:#666688">{st.session_state.saved_paths.get("folder","")}</code>'
            f'</div>',
            unsafe_allow_html=True,
        )