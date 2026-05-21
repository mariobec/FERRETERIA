"""LhexIA Operador v0.1 — reglas SQL sin GPU (PLAT-2.1)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    crear_registro,
    existe_dedupe_abierta,
)


def _umbral_vale_horas() -> float:
    try:
        return float((os.getenv('AGENTE_VALE_HORAS_UMBRAL') or '3').strip() or '3')
    except ValueError:
        return 3.0


def _umbral_descuadre_clp() -> int:
    try:
        return int(round(float((os.getenv('AGENTE_CIERRE_DIF_UMBRAL_CLP') or '5000').strip() or '5000')))
    except ValueError:
        return 5000


def _fmt_clp(n: int) -> str:
    sign = '+' if n > 0 else ''
    return f'{sign}${abs(int(n)):,}'.replace(',', '.')


def escanear_y_registrar_alertas() -> dict:
    """
    Ejecuta reglas de solo lectura sobre ventas/cajas.
    Retorna resumen {creadas, omitidas, vale_pendientes, cajas_descuadre}.
    """
    from app import Caja, Venta, db

    from services.agente_ejecuciones_service import asegurar_tabla

    if not asegurar_tabla():
        return {'ok': False, 'motivo': 'tabla_agente_ejecuciones_no_disponible'}

    ahora = datetime.now()
    umbral_h = _umbral_vale_horas()
    umbral_clp = _umbral_descuadre_clp()
    creadas = 0
    omitidas = 0
    detalle: list[str] = []

    # --- Vales pendientes sin cobrar ---
    corte = ahora - timedelta(hours=umbral_h)
    vales = (
        Venta.query.filter(
            Venta.estado == 'Pendiente',
            Venta.fecha.isnot(None),
            Venta.fecha < corte,
        )
        .order_by(Venta.fecha.asc())
        .limit(200)
        .all()
    )
    for v in vales:
        horas = (ahora - (v.fecha or ahora)).total_seconds() / 3600.0
        dedupe = f'operador:vale_pendiente:{v.id}'
        if existe_dedupe_abierta(dedupe):
            omitidas += 1
            continue
        monto = int(round(float(v.monto_total or 0)))
        sev = 'critical' if horas >= umbral_h * 2 else 'warning'
        titulo = f'Vale #{v.id} pendiente {horas:.1f} h'
        cuerpo = (
            f'Vale en estado Pendiente desde {v.fecha.strftime("%d-%m-%Y %H:%M") if v.fecha else "—"}. '
            f'Monto ${monto:,}. Operador: {v.usuario or "—"}.'.replace(',', '.')
        )
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=titulo[:255],
            cuerpo=cuerpo,
            severidad=sev,
            codigo='vale_pendiente_horas',
            dedupe_key=dedupe,
            payload={'venta_id': v.id, 'horas': round(horas, 2), 'monto_clp': monto},
            venta_id=v.id,
        )
        if rid:
            creadas += 1
            detalle.append(titulo)
        else:
            omitidas += 1

    # --- Cajas cerradas con descuadre ---
    desde_caja = ahora - timedelta(days=14)
    cajas = (
        Caja.query.filter(
            Caja.estado == 'Cerrada',
            Caja.fecha_cierre.isnot(None),
            Caja.fecha_cierre >= desde_caja,
        )
        .order_by(Caja.fecha_cierre.desc())
        .limit(100)
        .all()
    )
    for c in cajas:
        diff = int(round(float(c.diferencia_cierre or 0)))
        if abs(diff) < max(1, umbral_clp):
            continue
        dedupe = f'operador:caja_descuadre:{c.id}'
        if existe_dedupe_abierta(dedupe):
            omitidas += 1
            continue
        sev = 'critical' if diff < 0 else 'warning'
        titulo = f'Caja #{c.id} descuadre {_fmt_clp(diff)} CLP'
        cuerpo = (
            f'Cierre {c.fecha_cierre.strftime("%d-%m-%Y %H:%M") if c.fecha_cierre else "—"}. '
            f'Apertura: {c.usuario_apertura or "—"}. Diferencia arqueo ciego.'
        )
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=titulo[:255],
            cuerpo=cuerpo,
            severidad=sev,
            codigo='caja_descuadre',
            dedupe_key=dedupe,
            payload={'caja_id': c.id, 'diferencia_clp': diff},
            caja_id=c.id,
        )
        if rid:
            creadas += 1
            detalle.append(titulo)
        else:
            omitidas += 1

    return {
        'ok': True,
        'creadas': creadas,
        'omitidas': omitidas,
        'vales_revisados': len(vales),
        'cajas_revisadas': len(cajas),
        'detalle': detalle[:20],
    }
