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

_PRICE_TYPES = ('internetPrice', 'eventPrice', 'normalPrice')


def scroll_page_lazy(page, *, step_px: int = 1000, wait_sec: float = 0.8) -> None:
    """Desplazamiento incremental para activar lazy loading antes de capturar HTML."""
    last_height = page.evaluate('document.body.scrollHeight')
    while True:
        page.evaluate(f'window.scrollBy(0, {step_px});')
        time.sleep(wait_sec)
        new_height = page.evaluate('document.body.scrollHeight')
        if new_height == last_height:
            page.evaluate('window.scrollBy(0, 500);')
            time.sleep(1.5)
            if page.evaluate('document.body.scrollHeight') == last_height:
                break
        last_height = new_height


def _precio_desde_next_product(p: dict) -> int:
    prices = p.get('price')
    if isinstance(prices, dict):
        raw = prices.get('currentPrice') or prices.get('price') or 0
        return int(re.sub(r'[^0-9]', '', str(raw)) or 0)
    entries = p.get('prices')
    if not isinstance(entries, list):
        return 0
    by_type = {e.get('type'): e for e in entries if isinstance(e, dict) and e.get('type')}
    for tipo in _PRICE_TYPES:
        entry = by_type.get(tipo)
        if not entry:
            continue
        vals = entry.get('price')
        if isinstance(vals, list) and vals:
            return int(re.sub(r'[^0-9]', '', str(vals[0])) or 0)
        if vals:
            return int(re.sub(r'[^0-9]', '', str(vals)) or 0)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        vals = entry.get('price')
        if isinstance(vals, list) and vals:
            return int(re.sub(r'[^0-9]', '', str(vals[0])) or 0)
    return 0


def parse_next_data_json(html: str) -> list[dict]:
    """Catálogo desde __NEXT_DATA__ (Next.js) sin depender del DOM renderizado."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    pp = (data.get('props') or {}).get('pageProps') or {}
    products_list = pp.get('results')
    if not isinstance(products_list, list) or not products_list:
        sr = pp.get('searchResults')
        if isinstance(sr, dict):
            products_list = sr.get('products') or []
        elif isinstance(sr, list):
            products_list = sr

    items: list[dict] = []
    seen: set[str] = set()
    for p in products_list or []:
        if not isinstance(p, dict):
            continue
        cod = str(p.get('productId') or p.get('id') or '').strip()
        desc = str(p.get('displayName') or p.get('name') or '').strip()
        if not cod or not desc or cod in seen:
            continue
        seen.add(cod)
        items.append({
            'codigo_interno': cod,
            'descripcion_producto': desc,
            'precio': _precio_desde_next_product(p),
        })
    return items


def pagination_from_next_data(html: str) -> dict | None:
    """Lee bloque pagination de __NEXT_DATA__ (count, perPage, currentPage)."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    pag = (data.get('props') or {}).get('pageProps') or {}
    pag = pag.get('pagination')
    return pag if isinstance(pag, dict) else None


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
    found = parse_next_data_json(html)
    if found:
        return found
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
        scroll_page_lazy(page)
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
