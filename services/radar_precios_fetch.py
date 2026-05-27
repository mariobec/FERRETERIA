"""Fetch y extracción de catálogos desde URLs públicas (Radar Precios)."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import certifi
import requests
import urllib3

_log = logging.getLogger(__name__)

# Sitios con cadena SSL incompleta (común en retail CL). Ampliar por env sin tocar código.
_DEFAULT_SSL_RELAXED = 'electrocom.cl,www.electrocom.cl'
_DEFAULT_PLAYWRIGHT_HOSTS = 'imperial.cl,www.imperial.cl'


def _ssl_relaxed_hosts() -> frozenset[str]:
    raw = (os.getenv('RADAR_FETCH_SSL_RELAXED_HOSTS') or _DEFAULT_SSL_RELAXED).strip()
    return frozenset(h.strip().lower() for h in raw.split(',') if h.strip())


def _host_en_lista_relajada(hostname: str, relaxed: frozenset[str]) -> bool:
    h = (hostname or '').lower()
    if not h:
        return False
    if h in relaxed:
        return True
    return any(h == rh or h.endswith('.' + rh) for rh in relaxed)


def _resolve_ssl_verify(url: str) -> bool | str:
    """
    verify para requests.get:
    - certifi por defecto (Windows/local)
    - False solo en hosts listados o si RADAR_FETCH_SSL_VERIFY=0
    """
    flag = (os.getenv('RADAR_FETCH_SSL_VERIFY') or '1').strip().lower()
    if flag in ('0', 'false', 'no', 'off'):
        return False
    host = (urlparse(url).hostname or '').lower()
    if _host_en_lista_relajada(host, _ssl_relaxed_hosts()):
        return False
    return certifi.where()

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


def _playwright_hosts() -> frozenset[str]:
    raw = (os.getenv('RADAR_FETCH_PLAYWRIGHT_HOSTS') or _DEFAULT_PLAYWRIGHT_HOSTS).strip()
    return frozenset(h.strip().lower() for h in raw.split(',') if h.strip())


def _host_usa_playwright(hostname: str) -> bool:
    h = (hostname or '').lower()
    if not h:
        return False
    relaxed = _playwright_hosts()
    if h in relaxed:
        return True
    return any(h == rh or h.endswith('.' + rh) for rh in relaxed)


def playwright_disponible() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


_chromium_ok_cache: bool | None = None


def playwright_chromium_listo() -> bool:
    """Paquete playwright + navegador Chromium instalado (playwright install chromium)."""
    global _chromium_ok_cache
    if _chromium_ok_cache is not None:
        return _chromium_ok_cache
    _ensure_playwright_browsers_path()
    if not playwright_disponible():
        _chromium_ok_cache = False
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        _chromium_ok_cache = True
    except Exception as ex:
        _log.debug('playwright chromium no listo: %s', ex)
        _chromium_ok_cache = False
    return _chromium_ok_cache


def _ensure_playwright_browsers_path() -> None:
    """Usa Chromium instalado en %LOCALAPPDATA%\\ms-playwright si no hay env."""
    if (os.getenv('PLAYWRIGHT_BROWSERS_PATH') or '').strip():
        return
    default = Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'
    if default.is_dir():
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(default)


def fetch_playwright_html(url: str) -> dict[str, Any]:
    """
    Renderiza la página con Chromium (catálogos SPA: Imperial, etc.).
  Requiere: pip install playwright && playwright install chromium
    """
    _ensure_playwright_browsers_path()
    if not playwright_disponible():
        return {
            'ok': False,
            'error': 'playwright_no_instalado',
            'html': '',
            'hint': 'pip install playwright && playwright install chromium',
        }
    url = validar_url_publica(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            'ok': False,
            'error': 'playwright_no_instalado',
            'html': '',
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale='es-CL',
                user_agent=_USER_AGENT,
                viewport={'width': 1400, 'height': 900},
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=90000)
                try:
                    page.wait_for_load_state('networkidle', timeout=45000)
                except Exception:
                    pass
                for sel in (
                    'a[href*="/product/"]',
                    'a[href*="/p/"]',
                    '[data-product-id]',
                    '[class*="product" i]',
                    '.product-tile',
                    '.product-item',
                    '[class*="price" i]',
                    'img[alt*="product" i]',
                ):
                    try:
                        page.wait_for_selector(sel, timeout=15000)
                        break
                    except Exception:
                        continue
                time.sleep(3)
                for _ in range(8):
                    page.evaluate(
                        'window.scrollBy(0, Math.max(500, window.innerHeight * 0.85))'
                    )
                    time.sleep(0.7)
                html = page.content()
                if len(html.encode('utf-8', errors='ignore')) > _MAX_HTML_BYTES:
                    html = html[:_MAX_HTML_BYTES]
                return {
                    'ok': True,
                    'html': html,
                    'url_final': page.url,
                    'titulo': page.title() or _extraer_titulo(html),
                    'fuente': 'playwright',
                }
            finally:
                context.close()
                browser.close()
    except Exception as ex:
        _log.warning('playwright fetch %s: %s', url, ex)
        return {'ok': False, 'error': f'playwright: {ex}', 'html': ''}


def _fetch_public_html_requests(url: str) -> dict[str, Any]:
    """Descarga HTML estático (sin render JS)."""
    url = validar_url_publica(url)
    headers = {
        'User-Agent': _USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-CL,es;q=0.9',
    }
    verify = _resolve_ssl_verify(url)
    if verify is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=_FETCH_TIMEOUT,
            allow_redirects=True,
            verify=verify,
        )
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == 'iso-8859-1':
            r.encoding = r.apparent_encoding or 'utf-8'
        html = r.text
        if len(html.encode('utf-8', errors='ignore')) > _MAX_HTML_BYTES:
            html = html[:_MAX_HTML_BYTES]
        out = {
            'ok': True,
            'html': html,
            'url_final': r.url,
            'titulo': _extraer_titulo(html),
            'status_code': r.status_code,
        }
        if verify is False:
            out['ssl_relaxed'] = True
        return out
    except requests.Timeout:
        return {'ok': False, 'error': 'timeout_descarga', 'html': ''}
    except requests.exceptions.SSLError as ex:
        host = (urlparse(url).hostname or '')
        return {
            'ok': False,
            'error': (
                f'ssl_certificado: {host or url} — verifique RADAR_FETCH_SSL_RELAXED_HOSTS '
                f'o el certificado del sitio. ({ex})'
            ),
            'html': '',
        }
    except requests.RequestException as ex:
        return {'ok': False, 'error': f'descarga: {ex}', 'html': ''}


def fetch_public_html(url: str) -> dict[str, Any]:
    """Descarga HTML; usa Playwright en hosts SPA (Imperial) o si el HTML viene vacío."""
    url = validar_url_publica(url)
    host = (urlparse(url).hostname or '').lower()

    if _host_usa_playwright(host):
        paso = fetch_playwright_html(url)
        if paso.get('ok'):
            prods, _ = extraer_productos_de_html(paso.get('html') or '', url)
            if prods:
                return paso
            return {
                'ok': False,
                'error': 'playwright_sin_productos',
                'html': paso.get('html') or '',
                'hint': (
                    'Playwright abrió la página pero no se detectaron fichas. '
                    'Pruebe otra URL de categoría o espere más tiempo de carga.'
                ),
            }
        return {
            'ok': False,
            'error': paso.get('error') or 'playwright_fallo',
            'html': '',
            'hint': paso.get('hint')
            or 'pip install playwright && playwright install chromium',
        }

    req = _fetch_public_html_requests(url)
    if not req.get('ok'):
        return req

    prods, _ = extraer_productos_de_html(req.get('html') or '', url)
    if len(prods) < 3 and playwright_disponible():
        paso = fetch_playwright_html(url)
        if paso.get('ok'):
            prods2, _ = extraer_productos_de_html(paso.get('html') or '', url)
            if len(prods2) > len(prods):
                paso['fuente'] = 'playwright_fallback'
                return paso
    return req


def mensaje_error_radar(codigo: str, url: str = '') -> str:
    """Texto legible para errores SSE/UI."""
    host = (urlparse(url or '').hostname or '').lower()
    mapa = {
        'sin_productos_en_pagina': (
            'No se detectaron productos en la página descargada. '
            'Sitios como Imperial.cl cargan el catálogo con JavaScript: '
            'instale Playwright (pip install playwright && playwright install chromium) '
            'o pruebe una URL de listado que muestre precios sin login.'
        ),
        'playwright_no_instalado': (
            'Este sitio requiere Playwright para ver el catálogo renderizado. '
            'En la terminal del ERP (misma Python que Flask): '
            'pip install playwright && playwright install chromium — luego reinicie Flask.'
        ),
        'playwright_fallo': (
            'No se pudo abrir Chromium (Playwright). Ejecute: playwright install chromium'
        ),
        'playwright_sin_productos': (
            'La página cargó en Playwright pero no se vieron productos. '
            'Verifique la URL de categoría o aumente el tiempo de espera.'
        ),
        'timeout_descarga': 'La descarga tardó demasiado. Intente de nuevo.',
    }
    if codigo == 'sin_productos_en_pagina' and _host_usa_playwright(host):
        return mapa['sin_productos_en_pagina']
    return mapa.get(codigo, codigo or 'error_desconocido')


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


def _imperial_attr_val(attrs: dict[str, Any], key: str) -> str:
    val = attrs.get(key)
    if isinstance(val, list) and val:
        return str(val[0]).strip()
    if val is not None:
        return str(val).strip()
    return ''


def _imperial_precio_clp(raw: str) -> int:
    if not raw:
        return 0
    try:
        v = int(round(float(raw.replace(',', '.'))))
        return v if 0 < v <= 50_000_000 else 0
    except (TypeError, ValueError):
        return _precio_entero_clp(raw)


def parse_imperial_occ_state(html: str) -> list[dict[str, Any]]:
    """Oracle Commerce Cloud — window.state en imperial.cl (searchRepository.records)."""
    m = re.search(
        r'window\.state\s*=\s*JSON\.parse\(decodeURI\("([^"]+)"\)\)',
        html,
    )
    if not m:
        return []
    try:
        data = json.loads(unquote(m.group(1)))
    except (json.JSONDecodeError, ValueError) as ex:
        _log.debug('imperial state json: %s', ex)
        return []

    items: list[dict[str, Any]] = []
    pages = (data.get('searchRepository') or {}).get('pages') or {}
    if not isinstance(pages, dict):
        return []

    for page in pages.values():
        if not isinstance(page, dict):
            continue
        results = page.get('results')
        if not isinstance(results, dict):
            continue
        records = results.get('records')
        if not isinstance(records, list):
            continue
        for rec in records:
            if not isinstance(rec, dict):
                continue
            attrs = rec.get('attributes')
            if not isinstance(attrs, dict):
                continue
            nombre = _imperial_attr_val(attrs, 'product.displayName')
            sku = (
                _imperial_attr_val(attrs, 'sku.repositoryId')
                or _imperial_attr_val(attrs, 'product.repositoryId')
                or _imperial_attr_val(attrs, 'sku.listingId')
            )
            precio_raw = (
                _imperial_attr_val(attrs, 'sku.activePrice')
                or _imperial_attr_val(attrs, 'sku.listPrice')
                or _imperial_attr_val(attrs, 'sku.maxActivePrice')
            )
            precio = _imperial_precio_clp(precio_raw)
            it = _item(sku, nombre, precio)
            if it and it['precio'] > 0 and nombre:
                items.append(it)

    return _dedupe_items(items)


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

    host = (urlparse(url or '').hostname or '').lower()
    if 'imperial.cl' in host:
        imp = parse_imperial_occ_state(html)
        if imp:
            return imp, 'imperial_occ'

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
