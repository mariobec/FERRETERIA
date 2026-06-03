"""
Vacía la cola de plataforma bodega (marca preparación CERRADO).
Uso DEV/QA: python scripts/vaciar_cola_bodega.py
         python scripts/vaciar_cola_bodega.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description='Cerrar vales en cola bodega (plataforma retiro).')
    parser.add_argument('--dry-run', action='store_true', help='Solo listar, no guardar')
    parser.add_argument('--ids', type=str, default='', help='Solo estos IDs separados por coma (ej. 533,3061)')
    args = parser.parse_args()

    from app import Venta, _sql_filtro_venta_cola_bodega, app, db
    from services.audit_service import audit_log

    filtro_ids = None
    if args.ids.strip():
        filtro_ids = [int(x.strip()) for x in args.ids.split(',') if x.strip().isdigit()]

    with app.app_context():
        q = Venta.query.filter(
            Venta.estado == 'Pagado',
            _sql_filtro_venta_cola_bodega(),
            Venta.bodega_preparacion_estado.isnot(None),
            Venta.bodega_preparacion_estado != 'CERRADO',
        )
        if filtro_ids:
            q = q.filter(Venta.id.in_(filtro_ids))
        vales = q.order_by(Venta.id.asc()).all()

        if not vales:
            print('Cola bodega: 0 vales activos.')
            return 0

        print(f'Cola bodega: {len(vales)} vale(s)')
        for v in vales:
            cli = (v.cliente.nombre if v.cliente else '—') if hasattr(v, 'cliente') else '—'
            print(
                f"  #{v.id}  estado_prep={v.bodega_preparacion_estado!r}  "
                f"total=${int(v.monto_total or 0)}  cliente={cli!r}"
            )

        if args.dry_run:
            print('(dry-run: no se modificó nada)')
            return 0

        ahora = datetime.now()
        for v in vales:
            antes = (v.bodega_preparacion_estado or '').strip()
            v.bodega_preparacion_estado = 'CERRADO'
            v.bodega_preparacion_cerrado_at = ahora
            audit_log(
                'bodega_cola_cerrada_script',
                'venta',
                v.id,
                usuario='script:vaciar_cola_bodega',
                datos_antes={'bodega_preparacion_estado': antes},
                datos_despues={'bodega_preparacion_estado': 'CERRADO', 'motivo': 'limpieza_manual'},
            )
        db.session.commit()
        print(f'OK: {len(vales)} vale(s) marcados CERRADO (salen de la cola).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
