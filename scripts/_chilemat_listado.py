"""Parser listados Chilemat (VTEX IO)."""
from __future__ import annotations

import json
import re
import time
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = 'https://www.chilemat.com/bano-y-cocina'


def _precio_vtex_product(p: dict) -> int:
    pr = p.get('priceRange') or {}
    if isinstance(pr, dict):
        selling = pr.get('sellingPrice') or {}
        if isinstance(selling, dict):
            low = selling.get('lowPrice')
            if low is not None:
                return int(round(float(low)))
        low = pr.get('lowPrice')
        if low is not None:
            return int(round(float(low)))
    items = p.get('items') or []
    if items and isinstance(items[0], dict):
        sellers = (items[0].get('sellers') or [])
        if sellers and isinstance(sellers[0], dict):
            offer = sellers[0].get('commertialOffer') or {}
            price = offer.get('Price') or offer.get('price')
            if price is not None:
                return int(round(float(price)))
    for pat in (
        r'"Price"\s*:\s*([\d.]+)',
        r'"price"\s*:\s*([\d.]+)',
    ):
        chunk = json.dumps(p, ensure_ascii=False)
        m = re.search(pat, chunk)
        if m:
            return int(re.sub(r'[^0-9]', '', m.group(1)) or 0)
    return 0


def parse_vtex_runtime_products(html: str) -> list[dict]:
    """Extrae productos del JSON de hidratación VTEX (bloques Product:sp-*)."""
    items: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<script[^>]*>\s*(\{"Product:sp-[^<]+)\s*</script>',
        html,
        flags=re.I,
    ):
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for key, p in data.items():
            if not key.startswith('Product:') or not isinstance(p, dict):
                continue
            cod = str(p.get('productId') or '').strip()
            desc = str(p.get('productName') or p.get('name') or '').strip()
            if not cod or not desc or cod in seen:
                continue
            seen.add(cod)
            link = str(p.get('link') or '').strip()
            url = f'https://www.chilemat.com{link}' if link.startswith('/') else link
            items.append({
                'codigo_interno': cod,
                'descripcion_producto': desc,
                'precio': _precio_vtex_product(p),
                'url': url or None,
            })
        if items:
            return items
    return items


def parse_ld_json_products(html: str) -> list[dict]:
    """Fallback: schema.org ItemList en la página."""
    items: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        elements = []
        if data.get('@type') == 'ItemList':
            elements = data.get('itemListElement') or []
        elif isinstance(data, list):
            for block in data:
                if isinstance(block, dict) and block.get('@type') == 'ItemList':
                    elements.extend(block.get('itemListElement') or [])
        for el in elements:
            if not isinstance(el, dict):
                continue
            prod = el.get('item') or el
            if not isinstance(prod, dict) or prod.get('@type') != 'Product':
                continue
            pid = str(prod.get('sku') or prod.get('mpn') or '').strip()
            desc = str(prod.get('name') or '').strip()
            offers = prod.get('offers') or {}
            low = offers.get('lowPrice') if isinstance(offers, dict) else None
            precio = int(round(float(low))) if low is not None else 0
            if not pid or not desc or pid in seen:
                continue
            seen.add(pid)
            items.append({
                'codigo_interno': pid,
                'descripcion_producto': desc,
                'precio': precio,
                'url': str(prod.get('@id') or prod.get('url') or '').strip() or None,
            })
    return items


def parse_chilemat_listado(html: str) -> list[dict]:
    found = parse_vtex_runtime_products(html)
    if found:
        return found
    return parse_ld_json_products(html)


def scroll_page_lazy(page, *, step_px: int = 1000, wait_sec: float = 0.8) -> None:
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


def fetch_html(url: str) -> str:
    from playwright.sync_api import sync_playwright

    time.sleep(2 + random.uniform(0.2, 1.0))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale='es-CL', viewport={'width': 1400, 'height': 900})
        page.goto(url, wait_until='domcontentloaded', timeout=120000)
        try:
            page.wait_for_selector(
                '.vtex-product-summary-2-x-container, a[href*="/p"]',
                timeout=60000,
            )
        except Exception:
            pass
        try:
            page.wait_for_load_state('networkidle', timeout=45000)
        except Exception:
            pass
        time.sleep(4 + random.uniform(0.5, 2.0))
        scroll_page_lazy(page)
        html = page.content()
        browser.close()
    return html
