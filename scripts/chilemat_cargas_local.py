#!/usr/bin/env python3
"""
Kit local Chilemat: borrado/carga masiva o selectiva.

Ver también pantalla ERP: Compras → Cargas Chilemat (/compras/chilemat/cargas)

Ejemplos:
  python scripts/chilemat_cargas_local.py --accion sync_staging
  python scripts/chilemat_cargas_local.py --accion reset_total --forzar
  python scripts/chilemat_cargas_local.py --accion borrar_productos --forzar --rubro "Pinturas"
  python scripts/chilemat_cargas_local.py --accion cargar_productos --rubro "Pinturas"
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
    from app import app
    from services import chilemat_cargas_service as svc

    ap = argparse.ArgumentParser(description='Cargas Chilemat local: masivo/selectivo')
    ap.add_argument('--accion', required=True, choices=list(svc.ACCIONES))
    ap.add_argument('--sin-sync', action='store_true', help='No llamar API Chilemat; usar staging actual')
    ap.add_argument('--solo-faltantes', action='store_true', help='Solo aplica para sync_staging')
    ap.add_argument('--max-productos', type=int, default=0, help='Solo aplica para sync_staging')
    ap.add_argument('--rubro', default='', help='Filtro por nombre rubro (categoria_path)')
    ap.add_argument('--rubro-vtex-id', type=int, default=0, help='Filtro por vtex_id de categoría')
    ap.add_argument('--q', default='', help='Filtro por nombre/ref/ean/vtex_id')
    ap.add_argument('--limit', type=int, default=0, help='Top N del set filtrado')
    ap.add_argument('--preview', action='store_true', help='No escribe; solo muestra conteos')
    ap.add_argument('--masivo', action='store_true', help='Para borrar_productos: TRUNCATE productos CASCADE')
    ap.add_argument('--forzar', action='store_true', help='Confirmación explícita para acciones destructivas')
    args = ap.parse_args()

    confirmacion = 'RESET TOTAL' if args.accion == 'reset_total' and args.forzar else ''

    with app.app_context():
        if args.accion in ('reset_total', 'reset_taxonomia') and not args.forzar:
            raise RuntimeError(f'{args.accion} requiere --forzar.')

        out = svc.ejecutar(
            accion=args.accion,
            sin_sync=bool(args.sin_sync),
            solo_faltantes_sync=bool(args.solo_faltantes),
            rubro=args.rubro,
            rubro_vtex_id=(args.rubro_vtex_id or None),
            q=args.q,
            limit=(args.limit if args.limit > 0 else None) or (
                args.max_productos if args.max_productos > 0 and args.accion == 'sync_staging' else None
            ),
            masivo=bool(args.masivo),
            forzar=bool(args.forzar),
            preview=bool(args.preview),
            confirmacion=confirmacion,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0 if out.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
