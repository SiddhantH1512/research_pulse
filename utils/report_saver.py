"""
utils/report_saver.py
──────────────────────
Saves the final report to the specified local folder.
Produces two files:
  - report_<domain>_<timestamp>.md         (markdown)
  - report_<domain>_<timestamp>_publish.html  (Substack / Medium ready)
"""

import re
from datetime import datetime
from pathlib import Path


# ── Publish-ready HTML template ───────────────────────────────────
# Clean light theme · 680px reading width matches Substack & Medium
# No tooling branding, no timestamps, no instructions box.
# Upload directly to Medium or open in browser → select all → paste into Substack.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;500;600&display=swap');

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #ffffff;
      color: #1a1a2e;
      font-family: 'Lora', Georgia, serif;
      font-size: 19px;
      line-height: 1.8;
      padding: 4rem 1.5rem 6rem;
    }}

    .container {{
      max-width: 680px;
      margin: 0 auto;
    }}

    /* ── Byline ─────────────────────────────────────────────────── */
    .byline {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 2.5rem;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      color: #888;
    }}
    .byline-author {{
      font-weight: 600;
      color: #444;
    }}

    /* ── Headings ───────────────────────────────────────────────── */
    h1 {{
      font-family: 'Lora', Georgia, serif;
      font-size: 2.6rem;
      font-weight: 600;
      line-height: 1.2;
      color: #0f0f1a;
      margin-bottom: 1.2rem;
      letter-spacing: -0.01em;
    }}
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

    /* ── Body ───────────────────────────────────────────────────── */
    p {{ margin-bottom: 1.4rem; }}

    ul, ol {{ margin: 0.5rem 0 1.4rem 1.8rem; }}
    li      {{ margin-bottom: 0.5rem; }}

    strong {{ font-weight: 600; color: #0f0f1a; }}
    em     {{ font-style: italic; color: #444; }}

    blockquote {{
      border-left: 3px solid #d0d0e8;
      padding: 0.6rem 0 0.6rem 1.4rem;
      margin: 1.8rem 0;
      font-style: italic;
      color: #555;
      font-size: 1.05rem;
    }}

    hr {{
      border: none;
      border-top: 1px solid #e8e8f0;
      margin: 2.5rem 0;
    }}

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
      font-size: 13px;
      color: #aaa;
      text-align: center;
      font-style: italic;
    }}
  </style>
</head>
<body>
  <div class="container">

    {byline_html}

    {body}

    <div class="footer">Thank you for reading.</div>
  </div>
</body>
</html>"""


def _build_byline(author_name: str, domain: str) -> str:
    """Build the byline HTML. Shows author name if provided, otherwise just topic."""
    if author_name.strip():
        return (
            f'<div class="byline">'
            f'<span class="byline-author">{author_name.strip()}</span>'
            f'<span>·</span>'
            f'<span>{domain}</span>'
            f'</div>'
        )
    return f'<div class="byline"><span>{domain}</span></div>'


def _md_to_html_body(markdown_text: str) -> str:
    """Convert markdown to HTML body content."""
    try:
        import markdown2
        return markdown2.markdown(
            markdown_text,
            extras=["fenced-code-blocks", "tables", "header-ids", "strike"],
        )
    except ImportError:
        html = markdown_text
        html = re.sub(r"^## (.+)$",  r"<h2>\1</h2>",  html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>",  html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         html)
        html = "\n".join(
            f"<p>{line}</p>" if line.strip() and not line.startswith("<") else line
            for line in html.splitlines()
        )
        return html


def save_report(
    report_markdown: str,
    domain: str,
    md_folder: str,
    html_folder: str,
    author_name: str = "",
    research_data: dict | None = None,
) -> dict[str, str]:
    """
    Save the report. Markdown and HTML go to separate folders.

    Returns dict with md_path, html_path, md_folder, html_folder, base_name.
    """
    md_dir   = Path(md_folder).expanduser().resolve()
    html_dir = Path(html_folder).expanduser().resolve()
    md_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_domain = re.sub(r"[^\w\-]", "_", domain.lower())[:40]
    base_name = f"report_{safe_domain}_{ts}"

    # ── Markdown (Obsidian-friendly, no branding) ─────────────────
    md_path = md_dir / f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_markdown)

    # ── Publish-ready HTML ────────────────────────────────────────
    html_body  = _md_to_html_body(report_markdown)
    title_match = re.search(r"^##?\s+(.+)$", report_markdown, re.MULTILINE)
    title = title_match.group(1) if title_match else f"Research Report: {domain}"

    html_content = HTML_TEMPLATE.format(
        title=title,
        byline_html=_build_byline(author_name, domain),
        body=html_body,
    )

    html_path = html_dir / f"{base_name}_publish.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "md_path":     str(md_path),
        "html_path":   str(html_path),
        "md_folder":   str(md_dir),
        "html_folder": str(html_dir),
        "base_name":   base_name,
    }