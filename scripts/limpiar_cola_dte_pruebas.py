#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quita de la Cola DTE registros de prueba/seed (no borra ventas).

Criterios (cualquiera):
  - dte_track_id empieza con SEED
  - nro_documento >= 90000 (folios mock certificación)
  - PENDIENTE_ENVIO con dte_tipo 33 y folio < 1000 (sets de prueba locales)

Uso:
    python scripts/limpiar_cola_dte_pruebas.py --dry-run
    python scripts/limpiar_cola_dte_pruebas.py --aplicar
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _es_basura(venta) -> bool:
    from services.facturacion_electronica_service import DTE_ESTADO_PENDIENTE_ENVIO

    track = (getattr(venta, 'dte_track_id', None) or '').strip()
    if track.upper().startswith('SEED'):
        return True
    folio = getattr(venta, 'nro_documento', None)
    if folio is not None and int(folio) >= 90000:
        return True
    if (getattr(venta, 'dte_estado', None) or '') == DTE_ESTADO_PENDIENTE_ENVIO:
        if getattr(venta, 'dte_tipo', None) is None:
            return True
        if int(getattr(venta, 'dte_tipo', 0) or 0) == 33 and folio is not None and int(folio) < 1000:
            return True
    return False


def _limpiar_campos_dte(venta) -> None:
    venta.dte_estado = None
    venta.dte_tipo = None
    venta.nro_documento = None
    venta.caf_id = None
    venta.dte_track_id = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Solo listar (default si no --aplicar)')
    ap.add_argument('--aplicar', action='store_true', help='Escribir en BD')
    ap.add_argument(
        '--todo',
        action='store_true',
        help='Limpiar TODAS las ventas con dte_estado (incl. EXTERNO_MULTICAJA)',
    )
    args = ap.parse_args()
    if not args.aplicar:
        args.dry_run = True

    import app as m
    from services.facturacion_electronica_service import DTE_ESTADO_EXTERNO_BOLETA

    m._load_env_archivos(force_local_overwrite=True)
    with m.app.app_context():
        m._asegurar_tabla_cafs_y_columnas_ventas_fe()
        q = m.Venta.query.filter(m.Venta.dte_estado.isnot(None))
        if not args.todo:
            q = q.filter(m.Venta.dte_estado != DTE_ESTADO_EXTERNO_BOLETA)
        candidatas = q.order_by(m.Venta.id.desc()).all()
        basura = candidatas if args.todo else [v for v in candidatas if _es_basura(v)]
        print(f'En cola DTE (visible): {len(candidatas)} | Basura a limpiar: {len(basura)}')
        for v in basura[:30]:
            print(
                f"  #{v.id} estado={v.dte_estado} tipo={v.dte_tipo} "
                f"folio={v.nro_documento} track={v.dte_track_id}"
            )
        if len(basura) > 30:
            print(f'  ... y {len(basura) - 30} mas')

        if args.dry_run:
            print('\n[DRY-RUN] Use --aplicar para quitar estos registros de la cola.')
            return 0

        for v in basura:
            _limpiar_campos_dte(v)
        m.db.session.commit()
        print(f'\nOK: {len(basura)} venta(s) sin estado DTE (cola limpia).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
