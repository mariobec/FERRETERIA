#!/usr/bin/env python3
"""
Sincroniza catálogo Chilemat (VTEX) y relaciones para cross-sell POS.

Uso (desde raíz del repo):
  python scripts/sync_chilemat_catalogo.py
  python scripts/sync_chilemat_catalogo.py --solo-categorias
  python scripts/sync_chilemat_catalogo.py --max-productos 200 --sin-historico
  python scripts/sync_chilemat_catalogo.py --solo-relaciones-vtex --max-anclas 50

Requiere DATABASE_URL local/QA (no producción sin ALLOW_TESTS_ON_REMOTE).

Checkpoint git (antes de desplegar):
  git tag -a checkpoint/chilemat-relaciones-2026-05-26 -m "Antes sync Chilemat"
  git checkout checkpoint/chilemat-relaciones-2026-05-26   # revertir código

Revertir solo tablas nuevas (PostgreSQL QA):
  TRUNCATE producto_relacion, chilemat_vtex_producto, chilemat_categoria;
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description='Sync Chilemat → staging + producto_relacion')
    ap.add_argument('--solo-categorias', action='store_true')
    ap.add_argument('--solo-productos', action='store_true')
    ap.add_argument('--solo-relaciones-vtex', action='store_true')
    ap.add_argument('--solo-historico', action='store_true')
    ap.add_argument('--sin-historico', action='store_true')
    ap.add_argument('--sin-vtex', action='store_true')
    ap.add_argument('--max-productos', type=int, default=0, help='0 = todos (~4891)')
    ap.add_argument('--max-anclas', type=int, default=0, help='0 = todas las anclas vinculadas ERP')
    ap.add_argument(
        '--solo-faltantes',
        action='store_true',
        help='Solo categorías/productos que aún no están en BD (sync incremental)',
    )
    args = ap.parse_args()

    from app import app

    with app.app_context():
        from services.chilemat_catalogo_service import (
            sync_all,
            sync_categorias,
            sync_productos_vtex,
            sync_relaciones_chilemat_vtex,
            sync_relaciones_historico_ventas,
        )

        max_p = args.max_productos if args.max_productos > 0 else None
        max_a = args.max_anclas if args.max_anclas > 0 else None

        solo_f = bool(args.solo_faltantes)

        if args.solo_categorias:
            out = {'categorias': sync_categorias(solo_faltantes=solo_f)}
        elif args.solo_productos:
            out = {'productos': sync_productos_vtex(max_productos=max_p, solo_faltantes=solo_f)}
        elif solo_f and not args.solo_relaciones_vtex and not args.solo_historico:
            out = {
                'categorias': sync_categorias(solo_faltantes=True),
                'productos': sync_productos_vtex(max_productos=max_p, solo_faltantes=True),
            }
        elif args.solo_relaciones_vtex:
            out = {'relaciones_vtex': sync_relaciones_chilemat_vtex(max_anclas=max_a)}
        elif args.solo_historico:
            out = {'relaciones_historico': sync_relaciones_historico_ventas()}
        else:
            out = sync_all(
                categorias=True,
                productos=True,
                relaciones_vtex=not args.sin_vtex,
                relaciones_historico=not args.sin_historico,
                max_productos=max_p,
                max_anclas_vtex=max_a,
                solo_faltantes=solo_f,
            )

        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
