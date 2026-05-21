"""Empaquetado de contexto transaccional para agentes IA (v0.2)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from services.agente_ejecuciones_service import parse_payload_json


def empaquetar_contexto_alerta(row) -> dict[str, Any]:
    """Arma JSON de contexto a partir de una fila AgenteEjecucion (alerta operativa)."""
    payload = parse_payload_json(row.payload_json)
    codigo = (row.codigo or '').strip()
    base = {
        'alerta_id': row.id,
        'codigo': codigo,
        'severidad': row.severidad,
        'titulo_v01': row.titulo,
        'cuerpo_v01': row.cuerpo,
        'payload': payload,
    }
    if codigo == 'vale_pendiente_horas':
        base['historial'] = _historial_vale(payload.get('venta_id') or row.venta_id)
    elif codigo == 'caja_descuadre':
        base['historial'] = _historial_caja(payload.get('caja_id') or row.caja_id)
    else:
        base['historial'] = {}
    return base


def _historial_vale(venta_id: int | None) -> dict[str, Any]:
    if not venta_id:
        return {}
    from app import DetalleVenta, Producto, Venta

    v = Venta.query.get(int(venta_id))
    if not v:
        return {'error': 'venta_no_encontrada'}
    lineas = []
    dets = DetalleVenta.query.filter_by(id_venta=v.id).limit(20).all()
    for d in dets:
        p = Producto.query.get(d.id_producto) if d.id_producto else None
        lineas.append({
            'producto': (p.nombre if p else '?')[:80],
            'cantidad': float(d.cantidad or 0),
            'subtotal': int(round(float(d.subtotal or 0))),
        })
    usuario = (v.usuario or '').strip()
    recientes = []
    if usuario:
        desde = datetime.now() - timedelta(days=21)
        otras = (
            Venta.query.filter(
                Venta.usuario == usuario,
                Venta.id != v.id,
                Venta.fecha >= desde,
            )
            .order_by(Venta.fecha.desc())
            .limit(8)
            .all()
        )
        for ov in otras:
            recientes.append({
                'id': ov.id,
                'estado': ov.estado,
                'monto_clp': int(round(float(ov.monto_total or 0))),
                'fecha': ov.fecha.isoformat() if ov.fecha else None,
            })
    return {
        'venta': {
            'id': v.id,
            'estado': v.estado,
            'usuario': usuario,
            'monto_clp': int(round(float(v.monto_total or 0))),
            'punto_retiro': v.punto_retiro,
            'fecha': v.fecha.isoformat() if v.fecha else None,
            'horas_pendiente': None,
        },
        'lineas': lineas,
        'ventas_recientes_mismo_usuario': recientes,
    }


def _historial_caja(caja_id: int | None) -> dict[str, Any]:
    if not caja_id:
        return {}
    from app import Caja, MovimientoCaja, db

    c = Caja.query.get(int(caja_id))
    if not c:
        return {'error': 'caja_no_encontrada'}
    movs = (
        MovimientoCaja.query.filter_by(caja_id=c.id)
        .order_by(MovimientoCaja.fecha.desc())
        .limit(12)
        .all()
    )
    resumen_movs = [
        {
            'tipo': m.tipo,
            'concepto': (m.concepto or '')[:60],
            'monto_clp': int(round(float(m.monto or 0))),
        }
        for m in movs
    ]
    usuario = (c.usuario_apertura or c.usuario_cierre or '').strip()
    cierres_previos = []
    if usuario:
        desde = datetime.now() - timedelta(days=45)
        prev = (
            Caja.query.filter(
                Caja.estado == 'Cerrada',
                Caja.id != c.id,
                Caja.fecha_cierre.isnot(None),
                Caja.fecha_cierre >= desde,
            )
            .filter(
                db.or_(
                    Caja.usuario_apertura == usuario,
                    Caja.usuario_cierre == usuario,
                ),
            )
            .order_by(Caja.fecha_cierre.desc())
            .limit(6)
            .all()
        )
        for pc in prev:
            cierres_previos.append({
                'id': pc.id,
                'diferencia_clp': int(round(float(pc.diferencia_cierre or 0))),
                'fecha_cierre': pc.fecha_cierre.isoformat() if pc.fecha_cierre else None,
            })
    return {
        'caja': {
            'id': c.id,
            'estado': c.estado,
            'usuario_apertura': c.usuario_apertura,
            'usuario_cierre': c.usuario_cierre,
            'diferencia_clp': int(round(float(c.diferencia_cierre or 0))),
            'monto_contado': int(round(float(c.monto_contado_cierre or 0))) if c.monto_contado_cierre else None,
            'monto_teorico': int(round(float(c.monto_teorico_cierre or 0))) if c.monto_teorico_cierre else None,
            'fecha_cierre': c.fecha_cierre.isoformat() if c.fecha_cierre else None,
        },
        'movimientos_recientes': resumen_movs,
        'cierres_previos_mismo_usuario': cierres_previos,
    }


def contexto_a_texto_prompt(ctx: dict[str, Any]) -> str:
    """Serializa contexto a texto compacto para el LLM."""
    import json

    return json.dumps(ctx, ensure_ascii=False, indent=0)[:14000]
