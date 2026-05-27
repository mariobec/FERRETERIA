"""Fetch y extracción de catálogos desde URLs públicas (Radar Precios)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests

_log = logging.getLogger(__name__)

_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
_MAX_HTML_BYTES = 2_500_000
_FETCH_TIMEOUT = 45


def validar_url_publica(url: str) -> str:
    u = (url or '').strip()
    if not u:
        raise ValueError('Ingrese una URL válida.')
    parsed = urlparse(u)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('La URL debe comenzar con http:// o https://')
    if not parsed.netloc:
        raise ValueError('URL incompleta.')
    blocked = ('localhost', '127.0.0.1', '0.0.0.0', '::1')
    host = (parsed.hostname or '').lower()
    if host in blocked or host.endswith('.local'):
        raise ValueError('No se permiten URLs locales.')
    return u


def fetch_public_html(url: str) -> dict[str, Any]:
    """Descarga HTML de una página pública."""
    url = validar_url_publica(url)
    headers = {
        'User-Agent': _USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-CL,es;q=0.9',
    }
    try:
        r = requests.get(url, headers=headers, timeout=_FETCH_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == 'iso-8859-1':
            r.encoding = r.apparent_encoding or 'utf-8'
        html = r.text
        if len(html.encode('utf-8', errors='ignore')) > _MAX_HTML_BYTES:
            html = html[:_MAX_HTML_BYTES]
        return {
            'ok': True,
            'html': html,
            'url_final': r.url,
            'titulo': _extraer_titulo(html),
            'status_code': r.status_code,
        }
    except requests.Timeout:
        return {'ok': False, 'error': 'timeout_descarga', 'html': ''}
    except requests.RequestException as ex:
        return {'ok': False, 'error': f'descarga: {ex}', 'html': ''}


def _extraer_titulo(html: str) -> str:
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    return (m.group(1).strip()[:200] if m else '')


def _limpiar_html(html: str) -> str:
    html = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    html = re.sub(r'<style[\s\S]*?</style>', ' ', html, flags=re.I)
    html = re.sub(r'<!--[\s\S]*?-->', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html


def _precio_entero_clp(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        v = int(raw)
        return v if v > 0 else 0
    s = re.sub(r'[^\d]', '', str(raw))
    if not s:
        return 0
    v = int(s)
    if v > 50_000_000:
        return 0
    return v


def _item(codigo: str, desc: str, precio: int) -> dict[str, Any] | None:
    codigo = (codigo or '').strip()[:64]
    desc = (desc or '').strip()[:500]
    if not desc and not codigo:
        return None
    if not codigo:
        codigo = re.sub(r'[^a-zA-Z0-9_-]', '-', desc[:32])[:32] or 'WEB'
    return {
        'codigo_interno': codigo,
        'descripcion_producto': desc or codigo,
        'precio': _precio_entero_clp(precio),
    }


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        key = f"{it.get('codigo_interno')}|{it.get('descripcion_producto', '')[:40]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def parse_json_ld_products(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        html,
        re.I,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        bloques = data if isinstance(data, list) else [data]
        for bloque in bloques:
            if not isinstance(bloque, dict):
                continue
            tipo = bloque.get('@type') or ''
            if isinstance(tipo, list):
                tipo = tipo[0] if tipo else ''
            if str(tipo).lower() == 'product':
                _agregar_producto_ld(bloque, items)
            elif str(tipo).lower() == 'itemlist':
                for el in bloque.get('itemListElement') or []:
                    if isinstance(el, dict):
                        prod = el.get('item') if isinstance(el.get('item'), dict) else el
                        if isinstance(prod, dict):
                            _agregar_producto_ld(prod, items)
    return items


def _agregar_producto_ld(prod: dict, items: list[dict[str, Any]]) -> None:
    nombre = str(prod.get('name') or prod.get('description') or '').strip()
    sku = str(prod.get('sku') or prod.get('productID') or prod.get('mpn') or '').strip()
    precio = 0
    offers = prod.get('offers')
    if isinstance(offers, dict):
        precio = _precio_entero_clp(offers.get('price') or offers.get('lowPrice'))
    elif isinstance(offers, list) and offers:
        o0 = offers[0]
        if isinstance(o0, dict):
            precio = _precio_entero_clp(o0.get('price') or o0.get('lowPrice'))
    it = _item(sku, nombre, precio)
    if it:
        items.append(it)


def parse_embedded_json_products(html: str) -> list[dict[str, Any]]:
    """Next.js, window.__STATE__, arrays con name+price."""
    items: list[dict[str, Any]] = []
    try:
        from scripts._sodimac_listado_rapido import parse_next_data_json, parse_search_cards

        items.extend(parse_next_data_json(html))
        if not items:
            items.extend(parse_search_cards(html))
    except Exception as ex:
        _log.debug('parser sodimac embebido: %s', ex)

    for pattern in (
        r'__NEXT_DATA__[^>]*>(.*?)</script>',
        r'window\.__PRELOADED_STATE__\s*=\s*({[\s\S]*?});',
        r'window\.__INITIAL_STATE__\s*=\s*({[\s\S]*?});',
    ):
        for m in re.finditer(pattern, html, re.I | re.S):
            raw = m.group(1).strip()
            if raw.startswith('{'):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                items.extend(_walk_json_productos(data, depth=0))
    return items


def _walk_json_productos(obj: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 12:
        return []
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        keys = {k.lower() for k in obj.keys()}
        name = obj.get('displayName') or obj.get('name') or obj.get('title') or obj.get('productName')
        sku = obj.get('productId') or obj.get('sku') or obj.get('id') or obj.get('code')
        precio = None
        if 'price' in keys:
            pr = obj.get('price')
            if isinstance(pr, dict):
                precio = pr.get('currentPrice') or pr.get('price') or pr.get('value')
            else:
                precio = pr
        if precio is None and 'currentprice' in keys:
            precio = obj.get('currentPrice')
        if precio is None and 'precio' in keys:
            precio = obj.get('precio')
        if name and (sku or precio):
            it = _item(str(sku or ''), str(name), precio or 0)
            if it and it['precio'] > 0:
                found.append(it)
        for v in obj.values():
            found.extend(_walk_json_productos(v, depth + 1))
    elif isinstance(obj, list):
        for el in obj[:400]:
            found.extend(_walk_json_productos(el, depth + 1))
    return found


def parse_html_heuristic(html: str) -> list[dict[str, Any]]:
    """Patrones DOM/regex para listados genéricos."""
    items: list[dict[str, Any]] = []
    html_clean = _limpiar_html(html)

    for m in re.finditer(
        r'data-(?:product-)?(?:id|sku)=["\']([^"\']+)["\'][^>]{0,400}?'
        r'(?:data-(?:price|precio)=["\'](\d+)["\']|(?:\$|CLP)\s*([\d\.]+))',
        html_clean,
        re.I,
    ):
        it = _item(m.group(1), m.group(1), m.group(2) or m.group(3))
        if it:
            items.append(it)

    for m in re.finditer(
        r'(?:class|itemtype)=[^>]*product[^>]*>[\s\S]{0,800}?'
        r'<h[1-4][^>]*>([^<]{4,120})</h[1-4]>[\s\S]{0,400}?'
        r'(?:\$|CLP)\s*([\d\.\,]+)',
        html_clean,
        re.I,
    ):
        it = _item('', m.group(1), m.group(2))
        if it:
            items.append(it)

    for m in re.finditer(
        r'"(?:name|title|displayName)"\s*:\s*"([^"]{4,120})"[\s\S]{0,120}?'
        r'"(?:price|precio|currentPrice)"\s*:\s*"?([\d\.]+)"?',
        html_clean,
        re.I,
    ):
        it = _item('', m.group(1), m.group(2))
        if it and it['precio'] > 0:
            items.append(it)

    return _dedupe_items(items)


def extraer_productos_de_html(html: str, url: str = '') -> tuple[list[dict[str, Any]], str]:
    """
    Pipeline de parsers nativos (sin IA).
    Retorna (productos, fuente_parser).
    """
    if not html:
        return [], 'vacio'
    items: list[dict[str, Any]] = []
    fuentes: list[str] = []

    for parser_fn, nombre in (
        (parse_json_ld_products, 'json_ld'),
        (parse_embedded_json_products, 'json_embebido'),
        (parse_html_heuristic, 'heuristica_html'),
    ):
        try:
            chunk = parser_fn(html)
            if chunk:
                items.extend(chunk)
                fuentes.append(nombre)
        except Exception as ex:
            _log.debug('parser %s: %s', nombre, ex)

    items = _dedupe_items(items)
    return items, '+'.join(fuentes) if fuentes else 'ninguno'


def recortar_html_para_ollama(html: str, max_chars: int = 55000) -> str:
    max_chars = max(5000, min(max_chars, 110000))
    html = _limpiar_html(html)
    if len(html) <= max_chars:
        return html
    return html[:max_chars] + '\n<!-- recortado -->'


def extraer_candidatos_texto_crudo(html: str, *, max_items: int = 120) -> list[str]:
    """
    Fragmentos de texto (fichas ruidosas) para normalización item-a-item con Ollama.
    Complementa parsers estructurados cuando el HTML es irregular.
    """
    if not html:
        return []
    max_items = max(5, min(max_items, 200))
    candidatos: list[str] = []
    seen: set[str] = set()

    def _push(txt: str) -> None:
        t = re.sub(r'\s+', ' ', (txt or '').strip())
        if len(t) < 12 or len(t) > 900:
            return
        key = t[:80].lower()
        if key in seen:
            return
        seen.add(key)
        candidatos.append(t)

    html_clean = _limpiar_html(html)
    for m in re.finditer(
        r'(?:class|itemtype|data-testid)=[^>]*(?:product|articulo|item)[^>]*>[\s\S]{0,1200}?(?:\$|CLP)\s*[\d\.\,]+',
        html_clean,
        re.I,
    ):
        _push(re.sub(r'<[^>]+>', ' ', m.group(0)))

    for m in re.finditer(
        r'<(?:h[1-4]|p|span|div)[^>]*>([^<]{8,180})</(?:h[1-4]|p|span|div)>[\s\S]{0,350}?(?:\$|CLP)\s*([\d\.\,]+)',
        html_clean,
        re.I,
    ):
        _push(f'{m.group(1).strip()} ${m.group(2)}')

    for it in parse_json_ld_products(html)[:max_items]:
        _push(
            f"SKU {it.get('codigo_interno', '')} {it.get('descripcion_producto', '')} "
            f"${it.get('precio', 0)}"
        )

    return candidatos[:max_items]
