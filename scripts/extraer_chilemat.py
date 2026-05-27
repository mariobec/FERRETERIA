#!/usr/bin/env python3
"""Extrae listado Chilemat (VTEX) con Playwright + parser nativo."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._chilemat_listado import (  # noqa: E402
    DEFAULT_URL,
    fetch_html,
    parse_chilemat_listado,
)


def export_csv(productos: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(
            f,
            fieldnames=['codigo_interno', 'descripcion_producto', 'precio', 'url'],
            extrasaction='ignore',
        )
        w.writeheader()
        for p in sorted(productos, key=lambda x: x.get('codigo_interno', '')):
            w.writerow(p)


def main() -> int:
    ap = argparse.ArgumentParser(description='Extractor Chilemat (categoría VTEX)')
    ap.add_argument('--url', default=DEFAULT_URL)
    ap.add_argument('--html-guardado', type=Path, default=None)
    ap.add_argument(
        '--salida-json',
        type=Path,
        default=ROOT / 'respaldos' / 'chilemat_bano_cocina.json',
    )
    ap.add_argument(
        '--salida-csv',
        type=Path,
        default=ROOT / 'respaldos' / 'chilemat_bano_cocina.csv',
    )
    args = ap.parse_args()

    if args.html_guardado and args.html_guardado.is_file():
        html = args.html_guardado.read_text(encoding='utf-8')
        fuente = 'html_guardado'
    else:
        html = fetch_html(args.url.strip())
        fuente = 'playwright_chilemat'
        dbg = ROOT / 'respaldos' / 'debug_extractor_proveedor' / 'chilemat_bano_cocina.html'
        dbg.parent.mkdir(parents=True, exist_ok=True)
        dbg.write_text(html, encoding='utf-8')

    productos = parse_chilemat_listado(html)
    out = {
        'ok': bool(productos),
        'url': args.url.strip(),
        'fuente': fuente,
        'total': len(productos),
        'productos': productos,
    }
    args.salida_json.parent.mkdir(parents=True, exist_ok=True)
    args.salida_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    export_csv(productos, args.salida_csv)
    print(json.dumps({
        'ok': out['ok'],
        'total': out['total'],
        'json': str(args.salida_json),
        'csv': str(args.salida_csv),
    }, ensure_ascii=False, indent=2))
    return 0 if productos else 1


if __name__ == '__main__':
    raise SystemExit(main())
