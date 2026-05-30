"""
utils/report_saver.py
──────────────────────
Saves the final report to the specified local folder.
Produces two files:
  - report_<domain>_<timestamp>.md   (markdown)
  - report_<domain>_<timestamp>.html (styled HTML for easy reading)
"""

import os
import re
from datetime import datetime
from pathlib import Path

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;500;600&display=swap');

    /* ── Reset ─────────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    /* ── Page ──────────────────────────────────────────────────── */
    body {{
      background: #ffffff;
      color: #1a1a2e;
      font-family: 'Lora', Georgia, serif;
      font-size: 19px;
      line-height: 1.8;
      padding: 4rem 1.5rem 6rem;
    }}

    /* ── Content width (matches Substack/Medium reading width) ─── */
    .container {{
      max-width: 680px;
      margin: 0 auto;
    }}

    /* ── Publication meta ───────────────────────────────────────── */
    .pub-meta {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 2.5rem;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      color: #888;
    }}
    .pub-badge {{
      background: #f0f0f8;
      color: #555;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    /* ── Title ──────────────────────────────────────────────────── */
    h1 {{
      font-family: 'Lora', Georgia, serif;
      font-size: 2.6rem;
      font-weight: 600;
      line-height: 1.2;
      color: #0f0f1a;
      margin-bottom: 1.2rem;
      letter-spacing: -0.01em;
    }}

    /* ── Section headings ───────────────────────────────────────── */
    h2 {{
      font-family: 'Inter', sans-serif;
      font-size: 1.15rem;
      font-weight: 600;
      color: #0f0f1a;
      margin: 2.8rem 0 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    h3 {{
      font-family: 'Lora', Georgia, serif;
      font-size: 1.25rem;
      font-weight: 600;
      color: #1a1a2e;
      margin: 1.8rem 0 0.5rem;
    }}

    /* ── Body text ──────────────────────────────────────────────── */
    p {{ margin-bottom: 1.4rem; }}

    /* ── Lists ──────────────────────────────────────────────────── */
    ul, ol {{
      margin: 0.5rem 0 1.4rem 1.8rem;
    }}
    li {{ margin-bottom: 0.5rem; }}

    /* ── Emphasis ───────────────────────────────────────────────── */
    strong {{ font-weight: 600; color: #0f0f1a; }}
    em     {{ font-style: italic; color: #444; }}

    /* ── Pull quote / blockquote ────────────────────────────────── */
    blockquote {{
      border-left: 3px solid #d0d0e8;
      padding: 0.6rem 0 0.6rem 1.4rem;
      margin: 1.8rem 0;
      font-style: italic;
      color: #555;
      font-size: 1.05rem;
    }}

    /* ── Section divider ────────────────────────────────────────── */
    hr {{
      border: none;
      border-top: 1px solid #e8e8f0;
      margin: 2.5rem 0;
    }}

    /* ── Inline code ────────────────────────────────────────────── */
    code {{
      background: #f4f4fb;
      padding: 0.15em 0.4em;
      border-radius: 3px;
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      font-size: 0.85em;
      color: #5555aa;
    }}

    /* ── Footer ─────────────────────────────────────────────────── */
    .footer {{
      margin-top: 5rem;
      padding-top: 1.5rem;
      border-top: 1px solid #e8e8f0;
      font-family: 'Inter', sans-serif;
      font-size: 12px;
      color: #aaa;
      text-align: center;
    }}

    /* ── How-to-publish note (strip before publishing) ──────────── */
    .publish-note {{
      background: #fffbea;
      border: 1px solid #f0d060;
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 2.5rem;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      color: #555;
      line-height: 1.6;
    }}
    .publish-note strong {{ color: #333; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">

    <!-- REMOVE THIS BOX BEFORE PUBLISHING -->
    <div class="publish-note">
      <strong>📋 Publishing instructions</strong><br>
      <strong>Substack:</strong> New Post → click ··· menu → Import → upload this file, or open in browser → select all → paste.<br>
      <strong>Medium:</strong> medium.com/new-story → Import a Story → upload this .html file directly.
    </div>

    <div class="pub-meta">
      <span class="pub-badge">Research Pulse</span>
      <span>{domain}</span>
      <span>·</span>
      <span>{timestamp}</span>
    </div>

    {body}

    <div class="footer">Research Pulse · Generated {timestamp}</div>
  </div>
</body>
</html>"""


def _md_to_html_body(markdown_text: str) -> str:
    """Convert markdown to HTML body content."""
    try:
        import markdown2
        return markdown2.markdown(
            markdown_text,
            extras=["fenced-code-blocks", "tables", "header-ids", "strike"],
        )
    except ImportError:
        # Very basic fallback if markdown2 isn't installed
        html = markdown_text
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        html = "\n".join(
            f"<p>{line}</p>" if line.strip() and not line.startswith("<") else line
            for line in html.splitlines()
        )
        return html


def save_report(
    report_markdown: str,
    domain: str,
    output_folder: str,
    research_data: dict | None = None,
) -> dict[str, str]:
    """
    Save the report to output_folder.

    Returns a dict with keys:
      md_path   — path to the markdown file
      html_path — path to the styled HTML file
    """
    # ── Prepare folder ────────────────────────────────────────────
    folder = Path(output_folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)

    # ── Build filename ─────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_domain = re.sub(r"[^\w\-]", "_", domain.lower())[:40]
    base_name = f"report_{safe_domain}_{ts}"

    # ── Save markdown ─────────────────────────────────────────────
    md_path = folder / f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"<!-- Research Pulse | {domain} | {datetime.now().isoformat()} -->\n\n")
        f.write(report_markdown)

    # ── Save HTML ─────────────────────────────────────────────────
    html_body = _md_to_html_body(report_markdown)
    title_match = re.search(r"^##?\s+(.+)$", report_markdown, re.MULTILINE)
    title = title_match.group(1) if title_match else f"Research Report: {domain}"

    html_content = HTML_TEMPLATE.format(
        title=title,
        domain=domain,
        timestamp=datetime.now().strftime("%B %d, %Y · %H:%M"),
        body=html_body,
    )

    html_path = folder / f"{base_name}_publish.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "md_path":   str(md_path),
        "html_path": str(html_path),
        "folder":    str(folder),
        "base_name": base_name,
    }