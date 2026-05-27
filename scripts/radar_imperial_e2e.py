"""Verificación end-to-end Imperial + Playwright para Radar."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    'PLAYWRIGHT_BROWSERS_PATH',
    str(Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'),
)

from services.radar_precios_fetch import (
    extraer_productos_de_html,
    fetch_public_html,
    playwright_chromium_listo,
)

URL = 'https://www.imperial.cl/herramientas-inalambricas/category/000300020076'


def main():
    print('Chromium listo:', playwright_chromium_listo())
    paso = fetch_public_html(URL)
    print('fetch ok:', paso.get('ok'), 'fuente:', paso.get('fuente'), 'error:', paso.get('error'))
    if not paso.get('ok'):
        return 1
    prods, parser = extraer_productos_de_html(paso['html'], URL)
    print('parser:', parser, 'productos:', len(prods))
    for p in prods[:5]:
        print(' -', p.get('codigo_interno'), p.get('descripcion_producto')[:50], p.get('precio'))
    return 0 if len(prods) >= 10 else 1


if __name__ == '__main__':
    raise SystemExit(main())
