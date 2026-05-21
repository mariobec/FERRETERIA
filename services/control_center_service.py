"""Contexto del LhexIA Control Center (Plataforma Madre — Etapa 2)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from sqlalchemy import inspect

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    TIPO_BORRADOR,
    contar_alertas_abiertas,
    contar_hitl_pendientes,
    listar_alertas_operativas,
    metricas_telemetria_30d,
    ultimo_borrador_hitl,
)


def _models():
    from app import Caja, Venta, db

    return Caja, Venta, db


def _tabla_existe(nombre: str) -> bool:
    _, _, db = _models()
    try:
        return nombre in inspect(db.engine).get_table_names()
    except Exception:
        return False


def _fmt_clp(valor: int | float | None) -> str:
    n = int(round(float(valor or 0)))
    sign = '+' if n > 0 else ''
    return f'{sign}${abs(n):,}'.replace(',', '.')


def _etiqueta_caja(caja, indice: int) -> str:
    usuario = (caja.usuario_apertura or '').strip()
    if usuario.startswith('SEED-ARQUEO'):
        usuario = usuario.replace('SEED-ARQUEO', '').strip(' |') or 'Demo'
    sucursal = (os.getenv('CONTROL_CENTER_SUCURSAL_LABEL') or '').strip()
    if indice == 1:
        if sucursal:
            return f'Caja {indice:02d} — {sucursal}'
        return f'Caja {indice:02d} — Casa Matriz'
    if indice == 2:
        return f'Caja {indice:02d} — Sucursal SD-1'
    return f'Caja #{caja.id}'


def _tarjeta_caja(caja, indice: int, *, calcular_ctx) -> dict:
    estado = (caja.estado or '').strip()
    diff = int(round(float(caja.diferencia_cierre or 0)))
    teorico = None
    if estado == 'Abierta':
        try:
            ctx = calcular_ctx(caja)
            teorico = int(round(float(ctx.get('monto_teorico') or 0)))
        except Exception:
            teorico = int(round(float(caja.monto_teorico_cierre or 0)))
    alerta = None
    if estado == 'Cerrada' and diff != 0:
        alerta = 'danger' if diff < 0 else 'warning'
    elif estado == 'Abierta':
        alerta = 'success'
    return {
        'id': caja.id,
        'titulo': _etiqueta_caja(caja, indice),
        'estado': estado,
        'estado_label': 'ABIERTO' if estado == 'Abierta' else 'CERRADA',
        'teorico_clp': teorico,
        'teorico_fmt': _fmt_clp(teorico) if teorico is not None else None,
        'diferencia_clp': diff if estado == 'Cerrada' else None,
        'diferencia_fmt': _fmt_clp(diff) if estado == 'Cerrada' and diff != 0 else None,
        'alerta': alerta,
        'operador': (caja.usuario_apertura or '—')[:48],
    }


def obtener_tarjetas_sucursales(*, calcular_ctx, limite_cerradas: int = 2) -> dict:
    Caja, _, _ = _models()
    abiertas = (
        Caja.query.filter_by(estado='Abierta')
        .order_by(Caja.id.desc())
        .limit(3)
        .all()
    )
    cerradas = (
        Caja.query.filter_by(estado='Cerrada')
        .order_by(Caja.fecha_cierre.desc().nullslast(), Caja.id.desc())
        .limit(limite_cerradas)
        .all()
    )
    tarjetas = []
    idx = 1
    for c in abiertas:
        tarjetas.append(_tarjeta_caja(c, idx, calcular_ctx=calcular_ctx))
        idx += 1
    for c in cerradas:
        if len(tarjetas) >= 3:
            break
        tarjetas.append(_tarjeta_caja(c, idx, calcular_ctx=calcular_ctx))
        idx += 1

    descuadres = [
        int(round(float(c.diferencia_cierre or 0)))
        for c in Caja.query.filter_by(estado='Cerrada').all()
        if abs(float(c.diferencia_cierre or 0)) >= 1
    ]
    total_descuadre = sum(descuadres)
    alerta_global = None
    if any(d < 0 for d in descuadres):
        alerta_global = 'danger'
    elif total_descuadre != 0:
        alerta_global = 'warning'

    return {
        'tarjetas': tarjetas,
        'alerta_global_clp': total_descuadre,
        'alerta_global_fmt': _fmt_clp(total_descuadre),
        'alerta_global_tipo': alerta_global or ('ok' if not descuadres else 'warning'),
        'cajas_con_descuadre': len(descuadres),
        'alertas_operador_abiertas': contar_alertas_abiertas(),
    }


def obtener_salud_tributaria() -> dict:
    Caja, Venta, _ = _models()
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy, datetime.min.time())
    ventas_fe = Venta.query.filter(
        Venta.dte_estado.isnot(None),
        Venta.fecha >= inicio,
    )
    emitidas = int(ventas_fe.count() or 0)
    sincronizadas = int(
        ventas_fe.filter(
            Venta.dte_estado.in_(('ENVIADO', 'ACEPTADO', 'ACEPTADA', 'OK'))
        ).count()
        or 0
    )
    pendientes = max(0, emitidas - sincronizadas)
    pendientes_envio = int(
        ventas_fe.filter(
            Venta.dte_estado.in_(
                ('PENDIENTE_ENVIO', 'PENDIENTE', 'ERROR', 'RECHAZADO', 'RECHAZADA')
            )
        ).count()
        or 0
    )
    pct = int(round(100 * sincronizadas / emitidas)) if emitidas else 100
    pct_emit = min(100, max(8, pct if emitidas else 100))
    pct_sync = min(100, max(5, int(round(100 * sincronizadas / emitidas)) if emitidas else 0))

    for caja in Caja.query.filter(Caja.estado == 'Cerrada').order_by(Caja.id.desc()).limit(5):
        be = int(caja.boletas_emitidas_qty or 0)
        if be > emitidas:
            emitidas = be
            sincronizadas = int(caja.boletas_sincronizadas_qty or 0)
            pendientes = max(0, emitidas - sincronizadas)
            pct_emit = 100
            pct_sync = int(round(100 * sincronizadas / emitidas)) if emitidas else 0

    form_estado = (
        os.getenv('CONTROL_CENTER_FORM_3230')
        or 'RECEPCIONADA — Asignada a Fabiola Ruiz'
    ).strip()
    municipio = (os.getenv('CONTROL_CENTER_MUNICIPIO') or 'Maullín').strip()

    return {
        'municipio': municipio,
        'boletas_emitidas': emitidas,
        'boletas_sii': sincronizadas,
        'boletas_pendientes': pendientes,
        'pendientes_envio': pendientes_envio or pendientes,
        'pct_emitidas_bar': pct_emit,
        'pct_sii_bar': pct_sync,
        'form_3230_estado': form_estado,
        'url_sincronizar': '/admin/facturacion/cola',
    }


def _alerta_a_dict(row) -> dict:
    payload = {}
    if row.payload_json:
        try:
            payload = json.loads(row.payload_json)
        except Exception:
            payload = {}
    sev = (row.severidad or 'info').lower()
    badge = 'secondary'
    if sev == 'warning':
        badge = 'warning'
    elif sev == 'critical':
        badge = 'danger'
    return {
        'id': row.id,
        'titulo': row.titulo,
        'cuerpo': (row.cuerpo or '')[:280],
        'codigo': row.codigo,
        'estado': row.estado,
        'severidad': sev,
        'badge': badge,
        'created_at': row.created_at,
        'venta_id': row.venta_id,
        'caja_id': row.caja_id,
        'payload': payload,
    }


def obtener_panel_operador(*, limite: int = 12) -> dict:
    if not _tabla_existe('agente_ejecuciones'):
        return {
            'tabla_ok': False,
            'alertas': [],
            'abiertas': 0,
        }
    alertas = [_alerta_a_dict(r) for r in listar_alertas_operativas(limite=limite)]
    return {
        'tabla_ok': True,
        'alertas': alertas,
        'abiertas': contar_alertas_abiertas(),
    }


def obtener_telemetria_ia() -> dict:
    if not _tabla_existe('agente_ejecuciones'):
        return {
            'modo_demo': True,
            'pendientes_aprobacion': 0,
            'agente_nombre': '—',
            'contenido_titulo': 'Ejecute migración agente_ejecuciones',
            'costo_usd': 0,
            'tokens': 0,
            'url_bandeja': '/admin/control-center',
            'metricas_agentes': [],
        }

    pendientes = contar_hitl_pendientes()
    ultimo = ultimo_borrador_hitl()
    metricas = metricas_telemetria_30d()

    if ultimo:
        return {
            'modo_demo': False,
            'pendientes_aprobacion': pendientes,
            'agente_nombre': ultimo.agente_nombre or 'comercial',
            'contenido_titulo': ultimo.titulo or '—',
            'costo_usd': float(ultimo.costo_api_usd or 0),
            'tokens': int(ultimo.tokens_total or 0),
            'url_bandeja': '/admin/control-center',
            'metricas_agentes': metricas,
        }

    return {
        'modo_demo': False,
        'pendientes_aprobacion': pendientes,
        'agente_nombre': 'LhexIA Operador',
        'contenido_titulo': 'Sin borradores HITL — alertas operativas activas arriba',
        'costo_usd': 0,
        'tokens': 0,
        'url_bandeja': '/admin/control-center',
        'metricas_agentes': metricas,
    }


def construir_contexto_control_center(*, calcular_ctx) -> dict:
    sucursales = obtener_tarjetas_sucursales(calcular_ctx=calcular_ctx)
    tributaria = obtener_salud_tributaria()
    operador = obtener_panel_operador()
    ia = obtener_telemetria_ia()
    return {
        'sucursales': sucursales,
        'tributaria': tributaria,
        'operador': operador,
        'ia': ia,
        'actualizado': datetime.now(),
    }
