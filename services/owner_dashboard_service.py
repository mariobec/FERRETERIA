"""Dashboard semáforo PWA dueño — consolida Operador + caja + stock (sin duplicar agentes)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    asegurar_tabla,
    contar_alertas_abiertas,
    parse_payload_json,
)
from services.control_center_service import obtener_tarjetas_sucursales

_CODIGOS_CAJA = ('caja_descuadre', 'caja_dia_anterior')


def _fmt_hace(dt: datetime | None) -> str:
    if not dt:
        return '—'
    mins = max(0, int((datetime.now() - dt).total_seconds() // 60))
    if mins < 1:
        return 'Ahora'
    if mins < 60:
        return f'Hace {mins} min'
    horas = mins // 60
    return f'Hace {horas} h' if horas < 48 else dt.strftime('%d/%m %H:%M')


def _severidad_a_estado(sev: str | None) -> str:
    s = (sev or '').lower()
    if s == 'critical':
        return 'rojo'
    if s == 'warning':
        return 'amarillo'
    return 'verde'


def _tipo_accion(codigo: str | None) -> str | None:
    c = (codigo or '').lower()
    if c in _CODIGOS_CAJA + ('vale_pendiente_horas',):
        return 'llamada_supervisor'
    return None


def _tarjeta_desde_alerta(row, *, dominio: str) -> dict[str, Any]:
    payload = parse_payload_json(row.payload_json)
    mensaje = (row.cuerpo or '').strip()
    if payload.get('enriquecido_semantico'):
        mensaje = mensaje or (payload.get('cuerpo_base_v01') or '')
    estado = _severidad_a_estado(row.severidad)
    codigo = row.codigo or ''
    return {
        'estado': estado,
        'titulo': (row.titulo or f'Alerta {dominio}')[:80],
        'mensaje': (mensaje[:500] if mensaje else 'Revise en Control Center.'),
        'timestamp': _fmt_hace(row.updated_at or row.created_at),
        'accion_requerida': estado in ('rojo', 'amarillo'),
        'tipo_accion': _tipo_accion(codigo),
        'alerta_id': row.id,
        'codigo': codigo,
        'caja_id': row.caja_id,
        'venta_id': row.venta_id,
    }


def _mejor_alerta_caja():
    from app import AgenteEjecucion

    if not asegurar_tabla():
        return None
    base = AgenteEjecucion.query.filter_by(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
    ).filter(AgenteEjecucion.codigo.in_(_CODIGOS_CAJA))
    crit = (
        base.filter(AgenteEjecucion.severidad == 'critical')
        .order_by(AgenteEjecucion.created_at.desc())
        .first()
    )
    if crit:
        return crit
    return base.order_by(AgenteEjecucion.created_at.desc()).first()


def _tarjeta_caja(*, calcular_ctx_caja: Callable) -> dict[str, Any]:
    row = _mejor_alerta_caja()
    if row:
        return _tarjeta_desde_alerta(row, dominio='caja')

    bloque = obtener_tarjetas_sucursales(calcular_ctx=calcular_ctx_caja)
    tipo_global = bloque.get('alerta_global_tipo')
    if tipo_global == 'danger':
        return {
            'estado': 'rojo',
            'titulo': 'Caja: descuadre detectado',
            'mensaje': (
                f"{bloque.get('cajas_con_descuadre', 0)} cierre(s) con diferencia. "
                f"Total {bloque.get('alerta_global_fmt', '')}."
            ),
            'timestamp': 'Ahora',
            'accion_requerida': True,
            'tipo_accion': 'llamada_supervisor',
        }
    if tipo_global == 'warning':
        return {
            'estado': 'amarillo',
            'titulo': 'Caja: revisar arqueos',
            'mensaje': (
                f"{bloque.get('cajas_con_descuadre', 0)} cierre(s) con diferencia menor. "
                f"Total {bloque.get('alerta_global_fmt', '')}."
            ),
            'timestamp': 'Ahora',
            'accion_requerida': True,
            'tipo_accion': 'llamada_supervisor',
        }

    from app import Caja

    caja_abierta = Caja.query.filter_by(estado='Abierta').order_by(Caja.id.desc()).first()
    if caja_abierta and caja_abierta.fecha_apertura:
        if caja_abierta.fecha_apertura.date() < datetime.now().date():
            return {
                'estado': 'amarillo',
                'titulo': f'Caja #{caja_abierta.id} abierta',
                'mensaje': (
                    'Caja de día anterior sin cerrar. Debe cerrarse antes de seguir en POS.'
                ),
                'timestamp': _fmt_hace(caja_abierta.fecha_apertura),
                'accion_requerida': True,
                'tipo_accion': 'llamada_supervisor',
                'caja_id': caja_abierta.id,
            }

    return {
        'estado': 'verde',
        'titulo': 'Caja: OK',
        'mensaje': 'Sin descuadres ni alertas del Operador.',
        'timestamp': 'Ahora',
        'accion_requerida': False,
        'tipo_accion': None,
    }


def _tarjeta_inventario() -> dict[str, Any]:
    from app import Producto

    bajo = Producto.query.filter(Producto.stock < 5, Producto.activo.is_(True)).count()
    if bajo >= 15:
        estado, titulo = 'rojo', 'Inventario: crítico'
    elif bajo >= 5:
        estado, titulo = 'amarillo', 'Inventario: atención'
    else:
        estado, titulo = 'verde', 'Inventario: OK'

    sucursal = (os.getenv('OWNER_PWA_SUCURSAL_LABEL') or 'SD-1').strip()
    return {
        'estado': estado,
        'titulo': titulo,
        'mensaje': f'{bajo} SKU bajo mínimo (<5 u). Sucursal {sucursal}.',
        'timestamp': 'Ahora',
        'accion_requerida': estado != 'verde',
        'tipo_accion': 'llamada_supervisor' if estado == 'rojo' else None,
        'skus_bajo_minimo': int(bajo),
    }


def construir_owner_dashboard(*, calcular_ctx_caja: Callable) -> dict[str, Any]:
    """Payload `data` para GET /api/v1/owner/dashboard."""
    return {
        'tarjeta_caja': _tarjeta_caja(calcular_ctx_caja=calcular_ctx_caja),
        'tarjeta_inventario': _tarjeta_inventario(),
        'meta': {
            'alertas_abiertas': contar_alertas_abiertas(),
            'supervisor_telefono': (
                os.getenv('OWNER_SUPERVISOR_TELEFONO')
                or os.getenv('OWNER_SUPERVISOR_TEL')
                or ''
            ).strip(),
            'generado_en': datetime.now().isoformat(timespec='seconds'),
        },
    }
