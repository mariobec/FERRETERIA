#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reasigna folios del CAF real a ventas boleta (39) en PENDIENTE_ENVIO con numeracion mock.

Actualiza ventas.nro_documento, ventas.caf_id y cafs.usado_hasta.
No regenera XML: use Reintentar en /admin/facturacion/cola o reintentar_emision_fe_venta.

Uso:
    python scripts/recorrelativizar_cola.py --dry-run
    python scripts/recorrelativizar_cola.py --caf-id 63
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DTE_TIPO_BOLETA = 39
ESTADO_PENDIENTE = 'PENDIENTE_ENVIO'


def _load_env() -> None:
    import app as m

    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception as ex:
        print('AVISO: no se pudo cargar .env:', ex)


def _folios_ocupados_otras_ventas(db_session, venta_model, venta_ids: set[int], r0: int, r1: int) -> set[int]:
    """Folios tipo 39 ya usados por ventas que NO estan en la cola a parchar."""
    q = (
        db_session.query(venta_model.nro_documento)
        .filter(
            venta_model.dte_tipo == DTE_TIPO_BOLETA,
            venta_model.nro_documento.isnot(None),
            venta_model.nro_documento >= r0,
            venta_model.nro_documento <= r1,
        )
    )
    if venta_ids:
        q = q.filter(~venta_model.id.in_(venta_ids))
    return {int(row[0]) for row in q.all() if row[0] is not None}


def main() -> int:
    ap = argparse.ArgumentParser(description='Recorrelativizar cola DTE boletas PENDIENTE_ENVIO')
    ap.add_argument('--caf-id', type=int, default=63, help='ID del CAF real en tabla cafs')
    ap.add_argument(
        '--folio-inicio',
        type=int,
        default=None,
        help='Primer folio a asignar (default: rango_desde del CAF, ej. 755002)',
    )
    ap.add_argument('--dry-run', action='store_true', help='Solo muestra cambios, no escribe en BD')
    args = ap.parse_args()

    _load_env()
    import app as m

    with m.app.app_context():
        m._asegurar_tabla_cafs_y_columnas_ventas_fe()

        caf = m.db.session.query(m.Caf).filter(m.Caf.id == int(args.caf_id)).first()
        if not caf:
            print(f'ERROR: no existe CAF id={args.caf_id}')
            return 2
        if int(caf.tipo_dte) != DTE_TIPO_BOLETA:
            print(f'ERROR: CAF id={caf.id} no es tipo 39 (es {caf.tipo_dte})')
            return 2

        r0 = int(caf.rango_desde)
        r1 = int(caf.rango_hasta)
        folio_cursor = int(args.folio_inicio) if args.folio_inicio is not None else r0
        if folio_cursor < r0:
            print(f'ERROR: folio_inicio {folio_cursor} menor que rango_desde {r0}')
            return 2

        pendientes = (
            m.db.session.query(m.Venta)
            .filter(
                m.Venta.dte_tipo == DTE_TIPO_BOLETA,
                m.Venta.dte_estado == ESTADO_PENDIENTE,
            )
            .order_by(m.Venta.id.asc())
            .all()
        )

        if not pendientes:
            print('No hay ventas con dte_tipo=39 y dte_estado=PENDIENTE_ENVIO.')
            return 0

        ids_parchar = {int(v.id) for v in pendientes}
        ocupados = _folios_ocupados_otras_ventas(
            m.db.session, m.Venta, ids_parchar, r0, r1
        )

        print('=== Recorrelativizar cola DTE ===')
        print(f'  CAF id={caf.id}  rango {r0}-{r1}  usado_hasta actual={caf.usado_hasta}')
        print(f'  Ventas pendientes: {len(pendientes)}')
        print(f'  Folio inicial:     {folio_cursor}')
        if ocupados:
            print(f'  Folios ya usados (otras ventas): {sorted(ocupados)[:20]}'
                  + (' ...' if len(ocupados) > 20 else ''))

        cambios: list[tuple[int, int | None, int, int]] = []
        ultimo_asignado: int | None = None

        for v in pendientes:
            while folio_cursor in ocupados:
                folio_cursor += 1
            if folio_cursor > r1:
                print(f'ERROR: sin folios en CAF para venta #{v.id} (se agoto en {r1})')
                return 2

            viejo = getattr(v, 'nro_documento', None)
            viejo_caf = getattr(v, 'caf_id', None)
            nuevo = int(folio_cursor)
            cambios.append((int(v.id), viejo, nuevo, int(viejo_caf or 0)))
            ultimo_asignado = nuevo
            ocupados.add(nuevo)
            folio_cursor += 1

        print('\n  id_venta | folio_viejo -> folio_nuevo | caf_id ->', caf.id)
        for vid, viejo, nuevo, vcaf in cambios:
            print(f'  #{vid:6d} | {viejo!s:>9} -> {nuevo} | {vcaf} -> {caf.id}')

        if ultimo_asignado is None:
            return 0

        nuevo_usado = max(int(caf.usado_hasta or 0), int(ultimo_asignado))
        print(f'\n  cafs.usado_hasta: {caf.usado_hasta} -> {nuevo_usado}')

        if args.dry_run:
            print('\n[DRY-RUN] No se escribio en la base de datos.')
            return 0

        for v in pendientes:
            vid = int(v.id)
            nuevo = next(n for i, _, n, _ in cambios if i == vid)
            v.nro_documento = nuevo
            v.caf_id = int(caf.id)
            v.dte_tipo = DTE_TIPO_BOLETA

        caf.usado_hasta = nuevo_usado
        m.db.session.commit()
        print(f'\nOK: {len(cambios)} venta(s) actualizada(s).')
        print('Siguiente paso: Reintentar en /admin/facturacion/cola para regenerar XML con folio nuevo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
