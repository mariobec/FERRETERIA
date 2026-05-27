#!/usr/bin/env python3
"""Extrae catálogo Sodimac /buscar con paginación (Playwright + JSON embebido)."""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._sodimac_listado_rapido import (  # noqa: E402
    DEFAULT_URL,
    pagination_from_next_data,
    parse_search_cards,
)
from scripts.extraer_sodimac_buscar import fetch_html  # noqa: E402


def build_page_url(base_url: str, page: int) -> str:
    """Arma URL de búsqueda Sodimac para página N (1-based). Validado: &page=N."""
    if page <= 1:
        return base_url.strip()
    parsed = urlparse(base_url.strip())
    q = parse_qs(parsed.query, keep_blank_values=True)
    q.pop('offset', None)
    q['page'] = [str(page)]
    new_query = urlencode({k: v[0] for k, v in q.items()})
    return urlunparse(parsed._replace(query=new_query))


def merge_productos(acum: dict[str, dict], nuevos: list[dict]) -> int:
    n = 0
    for p in nuevos:
        cod = str(p.get('codigo_interno') or '').strip()
        if not cod:
            continue
        if cod not in acum:
            acum[cod] = {
                'codigo_interno': cod,
                'descripcion_producto': (p.get('descripcion_producto') or '').strip(),
                'precio': int(p.get('precio') or 0),
            }
            n += 1
        else:
            # Mantener precio más reciente si cambió
            acum[cod]['precio'] = int(p.get('precio') or acum[cod]['precio'])
    return n


def detect_total_paginas(html: str, default_max: int = 17) -> int | None:
    """Intenta leer total de páginas del JSON/HTML embebido."""
    pag = pagination_from_next_data(html)
    if pag:
        total = int(pag.get('count') or pag.get('totalResults') or 0)
        per = int(pag.get('perPage') or pag.get('totalPerPage') or 48) or 48
        if total > 0:
            return min(default_max, max(1, (total + per - 1) // per))
    for pat in (
        r'"totalPages"\s*:\s*(\d+)',
        r'"numberOfPages"\s*:\s*(\d+)',
        r'"pageCount"\s*:\s*(\d+)',
    ):
        m = re.search(pat, html)
        if m:
            return max(1, int(m.group(1)))
    m = re.search(r'"totalResults"\s*:\s*(\d+)', html)
    if m:
        total = int(m.group(1))
        per = 48
        return min(default_max, max(1, (total + per - 1) // per))
    return None


def export_csv(productos: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(
            f,
            fieldnames=['codigo_interno', 'descripcion_producto', 'precio'],
            extrasaction='ignore',
        )
        w.writeheader()
        for p in sorted(productos, key=lambda x: x.get('codigo_interno', '')):
            w.writerow({
                'codigo_interno': p['codigo_interno'],
                'descripcion_producto': p['descripcion_producto'],
                'precio': p['precio'],
            })


def main() -> int:
    ap = argparse.ArgumentParser(description='Extractor Sodimac /buscar paginado')
    ap.add_argument('--url', default=DEFAULT_URL)
    ap.add_argument('--pagina-inicio', type=int, default=1)
    ap.add_argument('--pagina-fin', type=int, default=17)
    ap.add_argument('--pausa-seg', type=float, default=2.0, help='Pausa base entre páginas')
    ap.add_argument(
        '--salida-json',
        type=Path,
        default=ROOT / 'respaldos' / 'sodimac_buscar_maquina_soldar.json',
    )
    ap.add_argument(
        '--salida-csv',
        type=Path,
        default=ROOT / 'respaldos' / 'sodimac_buscar_maquina_soldar.csv',
    )
    ap.add_argument('--solo-pagina', type=int, default=0, help='Si >0, solo esa página')
    args = ap.parse_args()

    base_url = args.url.strip()
    p_ini = max(1, args.pagina_inicio)
    p_fin = max(p_ini, args.pagina_fin)
    if args.solo_pagina > 0:
        p_ini = p_fin = args.solo_pagina

    acum: dict[str, dict] = {}
    paginas_ok: list[int] = []
    paginas_vacias: list[int] = []
    errores: list[str] = []
    total_esperado_paginas: int | None = None

    for num in range(p_ini, p_fin + 1):
        url = build_page_url(base_url, num)
        print(f'[pagina {num}] {url}', flush=True)
        try:
            html = fetch_html(url)
        except Exception as ex:
            errores.append(f'pagina {num}: {ex}')
            print(f'  ERROR: {ex}', flush=True)
            continue

        if num == p_ini:
            total_esperado_paginas = detect_total_paginas(html)
            if total_esperado_paginas and total_esperado_paginas < p_fin:
                print(f'  total paginas detectado en HTML: {total_esperado_paginas}', flush=True)
                p_fin = min(p_fin, total_esperado_paginas)

        dbg = ROOT / 'respaldos' / 'debug_extractor_proveedor' / f'pagina_buscar_{num:02d}.html'
        dbg.parent.mkdir(parents=True, exist_ok=True)
        dbg.write_text(html, encoding='utf-8')

        batch = parse_search_cards(html)
        nuevos = merge_productos(acum, batch)
        print(f'  parseados={len(batch)} nuevos={nuevos} acumulado={len(acum)}', flush=True)
        if batch:
            paginas_ok.append(num)
        else:
            paginas_vacias.append(num)
            if num > p_ini and len(paginas_vacias) >= 2:
                print('  dos páginas vacías seguidas → fin anticipado', flush=True)
                break

        if num < p_fin:
            time.sleep(args.pausa_seg + random.uniform(0.2, 1.0))

    productos = list(acum.values())
    out = {
        'ok': len(productos) > 0,
        'url_base': base_url,
        'fuente': 'playwright_busqueda_paginado',
        'paginas_ok': paginas_ok,
        'paginas_vacias': paginas_vacias,
        'paginas_detectadas': total_esperado_paginas,
        'total_unicos': len(productos),
        'errores': errores,
        'productos': productos,
    }
    args.salida_json.parent.mkdir(parents=True, exist_ok=True)
    args.salida_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    export_csv(productos, args.salida_csv)
    print(json.dumps({
        'ok': out['ok'],
        'total_unicos': out['total_unicos'],
        'paginas_ok': len(paginas_ok),
        'json': str(args.salida_json),
        'csv': str(args.salida_csv),
    }, ensure_ascii=False, indent=2))
    return 0 if productos else 1


if __name__ == '__main__':
    raise SystemExit(main())
