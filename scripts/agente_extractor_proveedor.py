#!/usr/bin/env python3
"""
LhexIA — Agente extractor de catálogo proveedor (Playwright + Ollama local).

Flujo:
  1. Login en portal externo (credenciales en .env.local).
  2. Extrae HTML de la página de listado de productos.
  3. Ollama estructura JSON: codigo_interno, descripcion_producto, precio.

Variables (.env.local — NO subir a Git):
  PROVEEDOR_URL          Base del sitio (default https://www.sodimac.cl)
  PROVEEDOR_USER         Usuario / email
  PROVEEDOR_PASS         Clave
  PROVEEDOR_CATALOGO_URL URL tras login con listado (obligatoria si no es la home)
  PROVEEDOR_DELAY_SEC    Pausa base entre pasos (default 2, + jitter aleatorio)
  PROVEEDOR_HTML_MAX_CHARS  Recorte HTML enviado a Ollama (default 55000)
  AGENTE_OLLAMA_ENABLED  1
  OLLAMA_*               Igual que Operador

Instalación (solo PC con navegador automatizado):
  pip install playwright
  playwright install chromium

Uso:
  cd <raíz repo>
  python scripts/agente_extractor_proveedor.py
  python scripts/agente_extractor_proveedor.py --headed --salida respaldos/sodimac_catalogo.json

Aviso legal: respetar términos del portal; uso interno ERP; delays para no saturar el servidor.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._agente_env import cargar_env_local  # noqa: E402

_log = logging.getLogger(__name__)

_PROMPT_SISTEMA = (
    'Eres un extractor de catálogo para un ERP de ferretería en Chile. '
    'Recibes HTML ruidoso de un listado de productos de proveedor. '
    'Devuelve ÚNICAMENTE un JSON válido: un array de objetos. '
    'Cada objeto debe tener exactamente estas claves: '
    '"codigo_interno" (string), "descripcion_producto" (string), "precio" (número entero CLP, sin puntos). '
    'Si no encuentras productos, devuelve []. No inventes SKUs ni precios.'
)


def _delay_paso() -> None:
    base = float((os.getenv('PROVEEDOR_DELAY_SEC') or '2').strip() or '2')
    jitter = random.uniform(0.3, 1.2)
    secs = max(1.0, base + jitter)
    _log.info('Espera %.1f s (anti-bloqueo)', secs)
    time.sleep(secs)


def _credenciales() -> tuple[str, str, str]:
    user = (os.getenv('PROVEEDOR_USER') or '').strip()
    pwd = (os.getenv('PROVEEDOR_PASS') or '').strip()
    base = (os.getenv('PROVEEDOR_URL') or 'https://www.sodimac.cl').strip().rstrip('/')
    if not user or not pwd:
        raise RuntimeError(
            'Faltan PROVEEDOR_USER y PROVEEDOR_PASS en .env.local (no uses credenciales en el código).'
        )
    return base, user, pwd


def _recortar_html(html: str) -> str:
    max_c = int((os.getenv('PROVEEDOR_HTML_MAX_CHARS') or '55000').strip() or '55000')
    max_c = max(5000, min(max_c, 110000))
    html = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    html = re.sub(r'<style[\s\S]*?</style>', ' ', html, flags=re.I)
    html = re.sub(r'\s+', ' ', html)
    if len(html) <= max_c:
        return html
    return html[:max_c] + '\n<!-- recortado -->'


def _extraer_json_desde_texto(texto: str) -> list[dict[str, Any]]:
    texto = (texto or '').strip()
    if not texto:
        return []
    bloques = re.findall(r'```(?:json)?\s*([\s\S]*?)```', texto, flags=re.I)
    candidatos = bloques + [texto]
    for raw in candidatos:
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'(\[[\s\S]*\])', raw)
            if not m:
                continue
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
        if isinstance(data, list):
            return _normalizar_items(data)
        if isinstance(data, dict) and isinstance(data.get('productos'), list):
            return _normalizar_items(data['productos'])
    return []


def _normalizar_items(items: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        codigo = str(
            it.get('codigo_interno')
            or it.get('codigo')
            or it.get('sku')
            or it.get('id')
            or ''
        ).strip()
        desc = str(
            it.get('descripcion_producto')
            or it.get('descripcion')
            or it.get('nombre')
            or ''
        ).strip()
        precio_raw = it.get('precio') or it.get('price') or it.get('precio_clp')
        try:
            if isinstance(precio_raw, str):
                precio_raw = re.sub(r'[^\d]', '', precio_raw)
            precio = int(precio_raw) if precio_raw not in (None, '') else 0
        except (TypeError, ValueError):
            precio = 0
        if not codigo and not desc:
            continue
        out.append(
            {
                'codigo_interno': codigo[:64],
                'descripcion_producto': desc[:500],
                'precio': precio,
            }
        )
    return out


def _ollama_estructurar(html: str) -> dict[str, Any]:
    from services.ollama_client import generar_chat, ollama_disponible

    if not ollama_disponible():
        return {'ok': False, 'productos': [], 'error': 'ollama_no_disponible'}
    html_rec = _recortar_html(html)
    user = (
        'Extrae el catálogo del siguiente HTML. '
        'Responde solo con el array JSON.\n\n'
        f'HTML:\n{html_rec}'
    )
    chat = generar_chat(system=_PROMPT_SISTEMA, user=user)
    if not chat.get('ok'):
        return {'ok': False, 'productos': [], 'error': chat.get('error') or 'ollama_error'}
    productos = _extraer_json_desde_texto(chat.get('texto') or '')
    return {
        'ok': True,
        'productos': productos,
        'tokens': int(chat.get('tokens_total') or 0),
        'modelo': chat.get('modelo'),
    }


def _click_si_existe(page, selectors: list[str], timeout_ms: int = 8000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                loc.click(timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def _fill_si_existe(page, selectors: list[str], value: str, timeout_ms: int = 10000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.fill(value, timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def extraer_html_playwright(
    *,
    headed: bool = False,
    catalogo_url: str | None = None,
    debug_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as ex:
        raise RuntimeError(
            'Instala Playwright: pip install playwright && playwright install chromium'
        ) from ex

    base, user, pwd = _credenciales()
    destino = (catalogo_url or os.getenv('PROVEEDOR_CATALOGO_URL') or '').strip() or base

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            locale='es-CL',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            viewport={'width': 1366, 'height': 900},
        )
        page = context.new_page()
        try:
            _log.info('Abriendo %s', base)
            page.goto(base, wait_until='domcontentloaded', timeout=90000)
            _delay_paso()

            # Sodimac / Falabella: botón ingreso
            _click_si_existe(
                page,
                [
                    'text=Inicia sesión',
                    'text=Iniciar sesión',
                    'text=Ingresar',
                    '[data-testid="testId-UserMenu"]',
                    'a[href*="login"]',
                    'button:has-text("Ingresar")',
                ],
            )
            _delay_paso()

            # Campos login (modal o redirect)
            _fill_si_existe(
                page,
                [
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[id*="email" i]',
                    'input[autocomplete="username"]',
                ],
                user,
            )
            _delay_paso()
            _fill_si_existe(
                page,
                [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[id*="password" i]',
                    'input[autocomplete="current-password"]',
                ],
                pwd,
            )
            _delay_paso()

            _click_si_existe(
                page,
                [
                    'button[type="submit"]',
                    'button:has-text("Ingresar")',
                    'button:has-text("Continuar")',
                    'text=Ingresar',
                ],
            )
            page.wait_for_load_state('networkidle', timeout=60000)
            _delay_paso()

            if destino != base:
                _log.info('Navegando al catálogo: %s', destino)
                page.goto(destino, wait_until='domcontentloaded', timeout=90000)
                page.wait_for_load_state('networkidle', timeout=60000)
                _delay_paso()

            # Intentar contenedor de productos; si no, body completo
            html = ''
            for sel in (
                '[data-testid*="product" i]',
                '.product-grid',
                '#product-results',
                'main',
                'body',
            ):
                try:
                    loc = page.locator(sel).first
                    if loc.count():
                        html = loc.inner_html(timeout=5000)
                        if len(html) > 500:
                            break
                except Exception:
                    continue
            if not html or len(html) < 500:
                html = page.content()

            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / 'pagina.html').write_text(html, encoding='utf-8')
                page.screenshot(path=str(debug_dir / 'pantalla.png'), full_page=True)

            return {
                'ok': True,
                'html': html,
                'url_final': page.url,
                'titulo': page.title(),
            }
        except Exception as ex:
            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(debug_dir / 'error.png'), full_page=True)
                except Exception:
                    pass
            return {'ok': False, 'error': str(ex), 'html': ''}
        finally:
            context.close()
            browser.close()


def ejecutar_extraccion(
    *,
    headed: bool = False,
    catalogo_url: str | None = None,
    salida: Path | None = None,
    debug_dir: Path | None = None,
) -> dict[str, Any]:
    paso1 = extraer_html_playwright(
        headed=headed,
        catalogo_url=catalogo_url,
        debug_dir=debug_dir,
    )
    if not paso1.get('ok'):
        return {'ok': False, 'fase': 'playwright', 'error': paso1.get('error'), 'productos': []}

    _delay_paso()
    paso2 = _ollama_estructurar(paso1.get('html') or '')
    productos = paso2.get('productos') or []
    if not paso2.get('ok') or not productos:
        try:
            from scripts._sodimac_listado_rapido import parse_search_cards

            productos = parse_search_cards(paso1.get('html') or '')
            if productos:
                paso2 = {'ok': True, 'productos': productos, 'fallback': 'json_embebido_sodimac'}
        except Exception as ex:
            _log.debug('fallback parser sodimac: %s', ex)
    if not productos:
        return {
            'ok': False,
            'fase': 'ollama' if not paso2.get('ok') else 'parser',
            'error': paso2.get('error') or 'sin_productos',
            'url_final': paso1.get('url_final'),
            'productos': [],
        }

    resultado = {
        'ok': True,
        'extraido_en': datetime.now(timezone.utc).isoformat(),
        'proveedor_url': os.getenv('PROVEEDOR_URL') or 'https://www.sodimac.cl',
        'url_final': paso1.get('url_final'),
        'titulo': paso1.get('titulo'),
        'total_productos': len(productos),
        'productos': productos,
        'parser': paso2.get('fallback') or ('ollama' if paso2.get('tokens') else 'ollama'),
        'ollama_tokens': paso2.get('tokens'),
        'ollama_modelo': paso2.get('modelo'),
    }

    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
        _log.info('Guardado: %s', salida)

    return resultado


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    cargar_env_local()
    os.environ.setdefault('AGENTE_OLLAMA_ENABLED', '1')

    ap = argparse.ArgumentParser(description='Extractor catálogo proveedor (Playwright + Ollama)')
    ap.add_argument('--headed', action='store_true', help='Mostrar navegador (depuración login)')
    ap.add_argument('--catalogo-url', default='', help='URL listado productos (o PROVEEDOR_CATALOGO_URL)')
    ap.add_argument(
        '--salida',
        type=Path,
        default=ROOT / 'respaldos' / 'catalogo_proveedor_extraido.json',
        help='JSON de salida',
    )
    ap.add_argument('--debug-dir', type=Path, default=None, help='Capturas HTML/PNG si falla')
    args = ap.parse_args()

    debug = args.debug_dir or (ROOT / 'respaldos' / 'debug_extractor_proveedor')
    res = ejecutar_extraccion(
        headed=args.headed,
        catalogo_url=(args.catalogo_url or '').strip() or None,
        salida=args.salida,
        debug_dir=debug,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
