#!/usr/bin/env python3
"""Exporta docs/ERP_MAESTRO.md a PDF (wkhtmltopdf + pdfkit)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / 'docs' / 'ERP_MAESTRO.md'
OUT_DIR = ROOT / 'docs' / 'export'
OUT_PDF = OUT_DIR / 'ERP_MAESTRO.pdf'


def _wkhtml_path() -> str:
    env = (os.getenv('WKHTMLTOPDF_PATH') or '').strip()
    if env and Path(env).is_file():
        return env
    found = shutil.which('wkhtmltopdf')
    if found:
        return found
    win_default = Path(r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
    if win_default.is_file():
        return str(win_default)
    raise SystemExit(
        'wkhtmltopdf no encontrado. Instale desde https://wkhtmltopdf.org '
        'o defina WKHTMLTOPDF_PATH.'
    )


def _html_shell(body: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es-CL">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    @page {{ margin: 18mm 14mm 20mm 14mm; }}
    body {{
      font-family: "Segoe UI", Roboto, Arial, sans-serif;
      font-size: 10.5pt;
      line-height: 1.45;
      color: #111827;
      max-width: 100%;
    }}
    h1 {{ color: #f37021; font-size: 20pt; border-bottom: 2px solid #f37021; padding-bottom: 6px; }}
    h2 {{ color: #0f172a; font-size: 14pt; margin-top: 1.2em; page-break-after: avoid; }}
    h3 {{ font-size: 11.5pt; color: #334155; page-break-after: avoid; }}
    h4 {{ font-size: 10.5pt; }}
    table {{ border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: 9pt; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 5px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; font-weight: 700; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
    code {{ background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }}
    pre {{
      background: #0f172a;
      color: #e2e8f0;
      padding: 10px 12px;
      border-radius: 6px;
      font-size: 8pt;
      white-space: pre-wrap;
      word-wrap: break-word;
      page-break-inside: avoid;
    }}
    pre code {{ background: transparent; color: inherit; padding: 0; }}
    blockquote {{
      border-left: 4px solid #f37021;
      margin: 0.8em 0;
      padding: 0.4em 12px;
      color: #475569;
      background: #fff7ed;
    }}
    a {{ color: #0369a1; text-decoration: none; }}
    hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.2em 0; }}
    .cover {{
      text-align: center;
      padding: 3em 1em 2em;
      page-break-after: always;
    }}
    .cover h1 {{ border: none; font-size: 26pt; }}
    .cover p {{ color: #64748b; font-size: 11pt; }}
    .mermaid-note {{
      font-size: 8.5pt;
      color: #64748b;
      font-style: italic;
    }}
  </style>
</head>
<body>
  <div class="cover">
    <h1>LhexIA ERP</h1>
    <p><strong>Documento Maestro</strong> — Especificación funcional y mapa técnico</p>
    <p>www.lhexia.cl · Generado desde ERP_MAESTRO.md</p>
  </div>
  {body}
</body>
</html>"""


def main() -> None:
    if not MD_PATH.is_file():
        raise SystemExit(f'No existe {MD_PATH}')

    import markdown
    import pdfkit

    raw = MD_PATH.read_text(encoding='utf-8')
    # Mermaid: nota para lectores PDF
    raw = raw.replace('```mermaid', '```\n<!-- diagrama mermaid — ver version MD -->\n```')

    body = markdown.markdown(
        raw,
        extensions=['tables', 'fenced_code', 'toc', 'nl2br'],
        extension_configs={'toc': {'permalink': False, 'toc_depth': 3}},
    )

    html = _html_shell(body, 'ERP LhexIA — Documento Maestro')
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    wk = _wkhtml_path()
    config = pdfkit.configuration(wkhtmltopdf=wk)
    options = {
        'encoding': 'UTF-8',
        'enable-local-file-access': None,
        'print-media-type': None,
        'footer-center': '[page] / [topage]',
        'footer-font-size': '8',
        'footer-spacing': '4',
        'quiet': '',
    }

    pdfkit.from_string(html, str(OUT_PDF), options=options, configuration=config)
    print(f'PDF generado: {OUT_PDF}')
    print(f'Tamano: {OUT_PDF.stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    main()
