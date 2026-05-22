#!/usr/bin/env python3
"""
Estado operativo SD-1 para piso — resumen del día (una pantalla).

Uso:
  python scripts/sd1_estado_piso.py

Requiere DATABASE_URL local/QA (misma BD que el ERP en piso si apunta a Neon).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _fmt_clp(n: int | float) -> str:
    return f'${int(round(float(n or 0))):,}'.replace(',', '.')


def main() -> int:
    import app as m

    hoy = datetime.now().date()
    d0 = datetime.combine(hoy, datetime.min.time())
    d1 = datetime.combine(hoy + timedelta(days=1), datetime.min.time())

    with m.app.app_context():
        lines: list[str] = []
        lines.append('=== SD-1 Estado piso ===')
        lines.append(f'Fecha local: {hoy.isoformat()}\n')

        # Enrolamiento infra
        enrol_ok = m._tablas_enrolamiento_existen() if hasattr(m, '_tablas_enrolamiento_existen') else False
        lines.append(f'Tablas enrolamiento: {"OK" if enrol_ok else "FALTAN (sql/2026_05_06_enrolamiento_inventario.sql)"}')

        agente_ok = False
        if hasattr(m, '_asegurar_tabla_agente_ejecuciones'):
            agente_ok = m._asegurar_tabla_agente_ejecuciones()
        lines.append(f'Tabla agente_ejecuciones: {"OK" if agente_ok else "no"}\n')

        # Almacenes + sesiones enrolamiento
        lines.append('--- Almacenes activos (toma física) ---')
        almacenes = m.Almacen.query.filter_by(activo=True).order_by(m.Almacen.id).all()
        if not almacenes:
            lines.append('  (ninguno activo)')
        for a in almacenes:
            sesiones_txt = 'sin tabla enrolamiento'
            if enrol_ok:
                sesiones = (
                    m.EnrolamientoTomaSesion.query.filter_by(id_almacen=a.id)
                    .order_by(m.EnrolamientoTomaSesion.iniciado_at.desc())
                    .limit(3)
                    .all()
                )
                if not sesiones:
                    sesiones_txt = 'sin sesiones aún'
                else:
                    partes = []
                    for s in sesiones:
                        n_lin = s.lineas.count()
                        when = (s.iniciado_at or datetime.now()).strftime('%d/%m %H:%M')
                        partes.append(f'sesión #{s.id} ({n_lin} SKU, {when})')
                    sesiones_txt = '; '.join(partes)
            lines.append(f'  [{a.id}] {a.codigo} - {a.nombre}')
            lines.append(f'       Enrolamiento: {sesiones_txt}')

        # Caja
        lines.append('\n--- Caja ---')
        caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
        if caja:
            lines.append(
                f'  ABIERTA #{caja.id} - {caja.usuario_apertura or "?"} '
                f'(apertura {caja.fecha_apertura})'
            )
        else:
            lines.append('  Sin caja abierta - abrir en /abrir_caja antes de POS/cobro')

        cierres_hoy = m.Caja.query.filter(
            m.Caja.estado == 'Cerrada',
            m.Caja.fecha_cierre >= d0,
            m.Caja.fecha_cierre < d1,
        ).count()
        lines.append(f'  Cierres de caja hoy: {cierres_hoy}')

        # Ventas hoy
        lines.append('\n--- Ventas hoy ---')
        try:
            from services.owner_dashboard_service import kpis_ventas_hoy

            k = kpis_ventas_hoy()
            lines.append(f'  Total Pagado+Pendiente: {_fmt_clp(k.get("ventas_hoy_clp"))}')
            lines.append(f'  Transacciones: {k.get("transacciones_hoy", 0)}')
        except Exception as ex:
            lines.append(f'  (no se pudo calcular KPI: {ex})')

        pend = m.Venta.query.filter(
            m.Venta.estado == 'Pendiente',
            m.Venta.fecha >= d0,
            m.Venta.fecha < d1,
        ).count()
        pag = m.Venta.query.filter(
            m.Venta.estado == 'Pagado',
            m.Venta.fecha >= d0,
            m.Venta.fecha < d1,
        ).count()
        lines.append(f'  Vales Pendiente hoy: {pend} | Pagado hoy: {pag}')

        # Guardián / operador
        if agente_ok:
            from services.agente_ejecuciones_service import contar_alertas_abiertas

            abiertas = contar_alertas_abiertas()
            lines.append(f'\n--- Agente Operador ---\n  Alertas abiertas: {abiertas}')

        lines.append('\n--- Siguiente paso (plan D1) ---')
        if not caja:
            lines.append('  1. Abrir caja (/abrir_caja)')
        if almacenes:
            primero = almacenes[0]
            lines.append(
                f'  2. Enrolamiento almacen [{primero.id}] {primero.nombre} - /inventario/enrolamiento'
            )
        lines.append('  3. Revisar /inventario/salud')
        lines.append('  4. Piloto vale -> cobro (ver SD1_DIA1_PISO.md)')

        print('\n'.join(lines))
        return 0


if __name__ == '__main__':
    sys.exit(main())
