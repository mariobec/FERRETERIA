#!/usr/bin/env python3
"""Extrae listado Sodimac desde URL /buscar (Playwright + JSON embebido)."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._sodimac_listado_rapido import (  # noqa: E402
    DEFAULT_URL,
    parse_search_cards,
    scroll_page_lazy,
)


def fetch_html(url: str) -> str:
    from playwright.sync_api import sync_playwright

    time.sleep(2 + random.uniform(0.2, 1.0))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale='es-CL', viewport={'width': 1400, 'height': 900})
        page.goto(url, wait_until='domcontentloaded', timeout=120000)
        try:
            page.wait_for_selector('a[href*="/articulo/"]', timeout=45000)
        except Exception:
            pass
        time.sleep(3 + random.uniform(0.5, 1.5))
        scroll_page_lazy(page)
        html = page.content()
        browser.close()
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=DEFAULT_URL)
    ap.add_argument(
        '--html-guardado',
        type=Path,
        default=None,
        help='Usar HTML ya descargado (sin Playwright)',
    )
    ap.add_argument(
        '--salida',
        type=Path,
        default=ROOT / 'respaldos' / 'sodimac_buscar_maquina_soldar.json',
    )
    args = ap.parse_args()

    if args.html_guardado and args.html_guardado.is_file():
        html = args.html_guardado.read_text(encoding='utf-8')
        fuente = 'html_guardado'
    else:
        html = fetch_html(args.url.strip())
        fuente = 'playwright_busqueda'
        dbg = ROOT / 'respaldos/debug_extractor_proveedor/pagina_buscar.html'
        dbg.parent.mkdir(parents=True, exist_ok=True)
        dbg.write_text(html, encoding='utf-8')

    productos = parse_search_cards(html)
    out = {
        'ok': bool(productos),
        'url': args.url.strip(),
        'fuente': fuente,
        'total': len(productos),
        'productos': productos,
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if productos else 1


if __name__ == '__main__':
    raise SystemExit(main())
