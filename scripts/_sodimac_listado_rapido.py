"""Listado Sodimac categoría — sin Ollama, parser HTML."""
from __future__ import annotations

import json
import re
import sys
import time
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = 'https://www.sodimac.cl/sodimac-cl/buscar?Ntt=maquina%20de%20soldar'


def parse_html(html: str) -> list[dict]:
    items = []
    seen = set()
    # Patrón grid + cards popularity
    for m in re.finditer(
        r'/articulo/(\d+)/[^"]*"[^>]*>[\s\S]{0,8000}?<h3[^>]*>([^<]+)</h3>[\s\S]{0,4000}?'
        r'(?:OUPrice|Price)[^>]*>\s*\$([\d.]+)',
        html,
        flags=re.I,
    ):
        cod, desc, pr = m.group(1), m.group(2).strip(), m.group(3)
        if cod in seen:
            continue
        seen.add(cod)
        items.append({
            'codigo_interno': cod,
            'descripcion_producto': desc,
            'precio': int(re.sub(r'[^0-9]', '', pr)),
        })
    if items:
        return items
    # Fallback: solo id + precio en href cercano
    for m in re.finditer(r'href="[^"]*/articulo/(\d+)/[^"]*"', html):
        cod = m.group(1)
        if cod in seen:
            continue
        chunk = html[m.start() : m.start() + 12000]
        mn = re.search(r'<h3[^>]*>([^<]+)</h3>', chunk)
        mp = re.search(r'\$([\d.]+)', chunk)
        if mn and mp:
            seen.add(cod)
            items.append({
                'codigo_interno': cod,
                'descripcion_producto': mn.group(1).strip(),
                'precio': int(re.sub(r'[^0-9]', '', mp.group(1))),
            })
    return items


def parse_search_json(html: str) -> list[dict]:
    """Extrae productos del JSON embebido en /buscar (Sodimac/Falabella)."""
    items: list[dict] = []
    seen: set[str] = set()
    bloques = re.split(r'(?="productId":")', html)
    for bloque in bloques[1:]:
        mp = re.search(r'"productId":"(\d+)"', bloque)
        mn = re.search(r'"displayName":"([^"]+)"', bloque)
        if not mp or not mn:
            continue
        cod = mp.group(1)
        if cod in seen:
            continue
        mpr = re.search(
            r'"type":"(?:internetPrice|eventPrice|normalPrice)"[^}]*"price":\["([\d.]+)"\]',
            bloque,
        )
        if not mpr:
            mpr = re.search(r'"price":\["([\d.]+)"\]', bloque)
        if not mpr:
            continue
        seen.add(cod)
        items.append({
            'codigo_interno': cod,
            'descripcion_producto': mn.group(1).strip(),
            'precio': int(re.sub(r'[^0-9]', '', mpr.group(1))),
        })
    return items


def parse_search_cards(html: str) -> list[dict]:
    """Parser para tarjetas de /buscar (pod + layout Sodimac)."""
    found = parse_search_json(html)
    if found:
        return found
    items: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'href="([^"]*/articulo/(\d+)/[^"]*)"', html):
        href, cod = m.group(1), m.group(2)
        if cod in seen:
            continue
        chunk = html[m.start() : m.start() + 15000]
        mn = re.search(
            r'(?:ProductName|product-name|pod-headline)[^>]*>[\s\S]{0,200}?<h\d[^>]*>([^<]+)</h\d>',
            chunk,
            re.I,
        ) or re.search(r'<h3[^>]*>([^<]+)</h3>', chunk)
        mp = re.search(
            r'(?:OUPrice|normalPrice|Price)[^>]*>\s*\$?\s*([\d.]+)',
            chunk,
            re.I,
        ) or re.search(r'\$\s*([\d]{2,3}\.[\d]{3})', chunk)
        if not mn or not mp:
            continue
        seen.add(cod)
        items.append({
            'codigo_interno': cod,
            'descripcion_producto': re.sub(r'\s+', ' ', mn.group(1)).strip(),
            'precio': int(re.sub(r'[^0-9]', '', mp.group(1))),
            'url': href if href.startswith('http') else f'https://www.sodimac.cl{href}',
        })
    return items


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=DEFAULT_URL)
    args = ap.parse_args()
    url = args.url.strip()

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
        for frac in (0.35, 0.7, 1.0):
            page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {frac})')
            time.sleep(1.2 + random.uniform(0.2, 0.8))
        html = page.content()
        browser.close()

    productos = parse_search_cards(html) or parse_html(html)
    out = {
        'ok': True,
        'url': url,
        'fuente': 'playwright_busqueda_sodimac',
        'total': len(productos),
        'productos': productos[:80],
    }
    path = ROOT / 'respaldos/sodimac_extraccion_run.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'respaldos/debug_extractor_proveedor/pagina_buscar.html').write_text(
        html, encoding='utf-8'
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if productos else 1


if __name__ == '__main__':
    raise SystemExit(main())
