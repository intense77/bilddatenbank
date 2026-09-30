#!/usr/bin/env python3
"""
Generiert aus allen Markdown-Dokumentationen eigenständige, druckfertige
und responsive HTML-Dateien für die Weitergabe und das Offline-Webinterface.
"""

import re
import shutil
from pathlib import Path
import markdown

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"

DOCS = [
    {
        "md": "README.md",
        "html": "README.html",
        "title": "Übersicht & Architektur — Lokales Bildarchiv-Suchsystem",
        "badge": "Archivsystem • Übersicht",
    },
    {
        "md": "anleitung.md",
        "html": "anleitung.html",
        "title": "Bedienungsanleitung — Lokales Bildarchiv-Suchsystem",
        "badge": "Handbuch • Praxisleitfaden",
    },
    {
        "md": "datenschutz.md",
        "html": "datenschutz.html",
        "title": "Datenschutzkonzept & DSGVO-Hinweise — Bildarchiv",
        "badge": "Recht • DSGVO Art. 9 & 17",
    },
    {
        "md": "lizenzen.md",
        "html": "lizenzen.html",
        "title": "Lizenzübersicht & Drittanbieter — Bildarchiv",
        "badge": "Recht • Open Source Lizenzen",
    },
    {
        "md": "todo.md",
        "html": "todo.html",
        "title": "Roadmap & Offene Aufgaben — Bildarchiv",
        "badge": "Entwicklung • Backlog & Roadmap",
    },
]

NAV_ITEMS = [
    ("README.html", "Übersicht"),
    ("anleitung.html", "Anleitung"),
    ("datenschutz.html", "Datenschutz & DSGVO"),
    ("lizenzen.html", "Lizenzen"),
    ("todo.html", "Roadmap"),
    ("/", "← Zurück zur Bildersuche"),
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--font-sans);
      color: #1e293b;
      background: #f8fafc;
      line-height: 1.65;
      padding: 2.5rem 1rem;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      padding: 3rem 3.5rem;
      border-radius: 16px;
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.04);
      border: 1px solid #e2e8f0;
    }}
    .doc-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      padding-bottom: 1.25rem;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid #f1f5f9;
      font-size: 0.82rem;
    }}
    .doc-nav a {{
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      background: #f1f5f9;
      color: #475569;
      text-decoration: none;
      font-weight: 500;
      transition: all 0.15s;
    }}
    .doc-nav a:hover {{
      background: #e2e8f0;
      color: #0f172a;
    }}
    .doc-nav a.active {{
      background: #f59e0b;
      color: #0f172a;
      font-weight: 600;
    }}
    .doc-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 1rem;
      margin-bottom: 2rem;
    }}
    .badge {{
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.3rem 0.75rem;
      border-radius: 9999px;
      background: #fef3c7;
      color: #92400e;
      border: 1px solid #fde68a;
    }}
    .print-btn {{
      font-size: 0.85rem;
      padding: 0.4rem 0.85rem;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      background: #ffffff;
      color: #334155;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s;
    }}
    .print-btn:hover {{
      background: #f8fafc;
      border-color: #94a3b8;
    }}
    h1 {{ font-size: 2rem; font-weight: 700; color: #0f172a; margin-bottom: 1rem; letter-spacing: -0.02em; line-height: 1.25; }}
    h2 {{ font-size: 1.35rem; font-weight: 600; color: #1e293b; margin-top: 2rem; margin-bottom: 0.85rem; padding-bottom: 0.4rem; border-bottom: 1px solid #f1f5f9; }}
    h3 {{ font-size: 1.12rem; font-weight: 600; color: #334155; margin-top: 1.5rem; margin-bottom: 0.6rem; }}
    p {{ margin-bottom: 1rem; }}
    ul, ol {{ margin-bottom: 1.25rem; padding-left: 1.5rem; }}
    li {{ margin-bottom: 0.35rem; }}
    code {{
      font-family: var(--font-mono);
      font-size: 0.88em;
      background: #f1f5f9;
      color: #0f172a;
      padding: 0.15em 0.35em;
      border-radius: 4px;
    }}
    pre {{
      background: #0f172a;
      color: #f8fafc;
      padding: 1.2rem 1.4rem;
      border-radius: 10px;
      overflow-x: auto;
      margin-bottom: 1.25rem;
    }}
    pre code {{
      background: transparent;
      color: inherit;
      padding: 0;
      font-size: 0.85rem;
      line-height: 1.5;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
      margin-bottom: 1.5rem;
      font-size: 0.92rem;
    }}
    th, td {{
      padding: 0.65rem 0.9rem;
      border: 1px solid #e2e8f0;
      text-align: left;
    }}
    th {{
      background: #f8fafc;
      font-weight: 600;
      color: #334155;
    }}
    tr:nth-child(even) {{ background: #fafafa; }}
    blockquote {{
      border-left: 4px solid #f59e0b;
      background: #fffbeb;
      padding: 0.85rem 1.15rem;
      margin: 1.25rem 0;
      border-radius: 0 8px 8px 0;
      font-size: 0.92rem;
      color: #78350f;
    }}
    hr {{
      border: 0;
      height: 1px;
      background: #e2e8f0;
      margin: 2rem 0;
    }}
    a {{
      color: #2563eb;
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}
    footer {{
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid #e2e8f0;
      font-size: 0.82rem;
      color: #64748b;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    @media print {{
      body {{ background: #ffffff; padding: 0; }}
      .container {{ border: none; box-shadow: none; padding: 0; max-width: 100%; }}
      .doc-nav, .doc-header button, footer {{ display: none; }}
      pre, code {{ background: #f8fafc !important; color: #000000 !important; border: 1px solid #cbd5e1; }}
    }}
    @media (max-width: 640px) {{
      .container {{ padding: 1.5rem; }}
      h1 {{ font-size: 1.5rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <nav class="doc-nav">
      {nav_links}
    </nav>
    <div class="doc-header">
      <span class="badge">{badge}</span>
      <button class="print-btn" onclick="window.print()">Drucken / Als PDF speichern</button>
    </div>
    <article>
{content}
    </article>
    <footer>
      <span>Historisches Bildarchiv &bull; Stand: Oktober 2026</span>
      <span>100 % Lokale KI &bull; Datensparsamkeit nach DSGVO</span>
    </footer>
  </div>
</body>
</html>
"""


def build_nav_links(current_html: str) -> str:
    links = []
    for href, label in NAV_ITEMS:
        is_active = (href == current_html)
        active_cls = ' class="active"' if is_active else ''
        links.append(f'<a href="{href}"{active_cls}>{label}</a>')
    return "\n      ".join(links)


def convert_admonitions(md_text: str) -> str:
    """Wandelt GitHub Callouts (> [!NOTE], > [!TIP]) in saubere HTML Blockquotes um."""
    def repl_note(m):
        return f"> **Hinweis:** {m.group(1)}"
    def repl_tip(m):
        return f"> **Tipp:** {m.group(1)}"
    def repl_warn(m):
        return f"> **Wichtig:** {m.group(1)}"

    text = re.sub(r">\s*\[!NOTE\]\s*(.*)", repl_note, md_text)
    text = re.sub(r">\s*\[!TIP\]\s*(.*)", repl_tip, md_text)
    text = re.sub(r">\s*\[!IMPORTANT\]\s*(.*)", repl_warn, text)
    text = re.sub(r">\s*\[!WARNING\]\s*(.*)", repl_warn, text)
    return text


def main():
    print("Starte Generierung der HTML-Dokumentation...")
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    md_parser = markdown.Markdown(
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "toc",
            "nl2br",
            "sane_lists",
        ]
    )

    for item in DOCS:
        md_path = ROOT_DIR / item["md"]
        if not md_path.exists():
            print(f"WARNUNG: {md_path} nicht gefunden, überspringe.")
            continue

        raw_md = md_path.read_text(encoding="utf-8")
        clean_md = convert_admonitions(raw_md)

        md_parser.reset()
        html_content = md_parser.convert(clean_md)

        # Links zu .md Dateien in .html umschreiben
        for d in DOCS:
            html_content = html_content.replace(f'href="{d["md"]}"', f'href="{d["html"]}"')
            html_content = html_content.replace(f'href="./{d["md"]}"', f'href="{d["html"]}"')

        rendered_html = HTML_TEMPLATE.format(
            title=item["title"],
            badge=item["badge"],
            nav_links=build_nav_links(item["html"]),
            content=html_content,
        )

        # 1. Im Root speichern
        out_root = ROOT_DIR / item["html"]
        out_root.write_text(rendered_html, encoding="utf-8")

        # 2. Im static/-Ordner speichern (für Auslieferung via Webserver)
        out_static = STATIC_DIR / item["html"]
        out_static.write_text(rendered_html, encoding="utf-8")

        print(f"✓ Erstellt: {item['html']} (Root & static/)")

    print("\nAlle HTML-Dokumente erfolgreich generiert!")


if __name__ == "__main__":
    main()
