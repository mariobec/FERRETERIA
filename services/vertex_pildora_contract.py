"""Contrato píldora VERTEX Master Core v1.0 — payload y semillas demo red."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    EST_ALERTA_CERRADA,
    TIPO_ALERTA,
    asegurar_tabla,
    crear_registro,
    existe_dedupe_registrada,
    parse_payload_json,
)

PILDORA_VERSION = '1.0'

TENANT_SANTO_DOMINGO = 'santo_domingo'
TENANT_SODIMAC = 'sodimac_piloto'
TENANT_EASY = 'easy_demo'

AGENTE_VERTEX_HUB = 'vertex_hub'

_MODULO_GUARDIAN = 'vertex_guardian'
_MODULO_OPERADOR = 'vertex_operador'
_MODULO_LOGISTICA = 'vertex_logistica'
_MODULO_INVENTARIO = 'vertex_inventario'
_MODULO_MENTOR = 'vertex_mentor'

_CODIGO_A_PRODUCTO = {
    'caja_descuadre': _MODULO_GUARDIAN,
    'caja_dia_anterior': _MODULO_GUARDIAN,
    'caja_ok': _MODULO_GUARDIAN,
    'sku_quiebre': _MODULO_OPERADOR,
    'stock_bajo': _MODULO_INVENTARIO,
    'traslado_retrasado': _MODULO_LOGISTICA,
    'mentor_guia_nota_credito': _MODULO_MENTOR,
    'mentor_capacitacion': _MODULO_MENTOR,
    'mentor_consulta_proceso': _MODULO_MENTOR,
    'mentor_consulta_academy': _MODULO_MENTOR,
    'mentor_caja_dia_anterior': _MODULO_MENTOR,
}


def build_pildora(
    *,
    tenant_id: str,
    tenant_slug: str,
    cliente_nombre: str,
    agente_producto: str,
    codigo: str,
    severidad: str,
    titulo: str,
    modo: str,
    origen: str,
    occurred_at: datetime | None = None,
    agente_nombre: str | None = None,
    mensaje_corto: str | None = None,
    semaforo_dominio: str | None = None,
    kpi_snapshot: dict[str, Any] | None = None,
    nav_href: str | None = None,
    registro_id: int | None = None,
) -> dict[str, Any]:
    """Construye payload oficial vertex_pildora v1.0."""
    pill: dict[str, Any] = {
        'vertex_pildora_version': PILDORA_VERSION,
        'tenant_id': tenant_id,
        'tenant_slug': tenant_slug,
        'cliente_nombre': cliente_nombre,
        'agente_producto': agente_producto,
        'codigo': codigo,
        'severidad': severidad,
        'titulo': (titulo or '')[:255],
        'modo': modo,
        'origen': origen,
        'occurred_at': (occurred_at or datetime.now()).isoformat(timespec='seconds'),
    }
    if agente_nombre:
        pill['agente_nombre'] = agente_nombre
    if mensaje_corto:
        pill['mensaje_corto'] = mensaje_corto[:500]
    if semaforo_dominio:
        pill['semaforo_dominio'] = semaforo_dominio
    if kpi_snapshot:
        pill['kpi_snapshot'] = kpi_snapshot
    if nav_href:
        pill['nav_href'] = nav_href
    if registro_id is not None:
        pill['registro_id'] = registro_id
    return pill


def pildora_from_row(row, *, default_tenant: dict[str, str] | None = None) -> dict[str, Any]:
    """Lee o envuelve una fila `agente_ejecuciones` como píldora v1.0."""
    payload = parse_payload_json(row.payload_json)
    if payload.get('vertex_pildora_version') == PILDORA_VERSION and payload.get('tenant_id'):
        out = dict(payload)
        if row.id and 'registro_id' not in out:
            out['registro_id'] = row.id
        return out

    default = default_tenant or {
        'tenant_id': TENANT_SANTO_DOMINGO,
        'tenant_slug': 'santo-domingo',
        'cliente_nombre': 'Ferretería Santo Domingo',
    }
    codigo = row.codigo or 'alerta_operativa'
    agente_producto = _CODIGO_A_PRODUCTO.get(codigo, _MODULO_OPERADOR)
    if (row.agente_nombre or '') == AGENTE_VERTEX_HUB:
        agente_producto = payload.get('agente_producto') or agente_producto

    dominio = 'caja' if 'caja' in codigo else None
    nav = '/admin/control-center'
    venta_id = row.venta_id or payload.get('venta_id')
    if venta_id:
        nav = f'/editar_venta/{venta_id}'

    return build_pildora(
        tenant_id=default['tenant_id'],
        tenant_slug=default['tenant_slug'],
        cliente_nombre=default['cliente_nombre'],
        agente_producto=agente_producto,
        agente_nombre=row.agente_nombre,
        codigo=codigo,
        severidad=(row.severidad or 'info').lower(),
        titulo=row.titulo or 'Alerta operativa',
        mensaje_corto=(row.cuerpo or '')[:500] or None,
        modo='live',
        origen='pull_sd1',
        occurred_at=row.updated_at or row.created_at,
        semaforo_dominio=dominio,
        nav_href=nav,
        registro_id=row.id,
    )


def _demo_specs() -> list[dict[str, Any]]:
    ahora = datetime.now()
    return [
        {
            'dedupe_key': f'vertex:maestro:{TENANT_SODIMAC}:traslado_retrasado',
            'estado': EST_ALERTA_ABIERTA,
            'minutes_ago': 12,
            'pill': build_pildora(
                tenant_id=TENANT_SODIMAC,
                tenant_slug='sodimac-piloto',
                cliente_nombre='Sodimac Piloto',
                agente_producto=_MODULO_LOGISTICA,
                agente_nombre=AGENTE_VERTEX_HUB,
                codigo='traslado_retrasado',
                severidad='warning',
                titulo='Traslado bodega norte +45 min vs SLA',
                mensaje_corto='VERTEX Hub — simulación red logística piloto.',
                modo='mock',
                origen='push_agente',
                occurred_at=ahora - timedelta(minutes=12),
                semaforo_dominio='logistica',
                kpi_snapshot={'ventas_hoy_clp': 18420000, 'sucursales_activas': 4},
            ),
        },
        {
            'dedupe_key': f'vertex:maestro:{TENANT_SODIMAC}:sku_quiebre',
            'estado': EST_ALERTA_ABIERTA,
            'minutes_ago': 41,
            'pill': build_pildora(
                tenant_id=TENANT_SODIMAC,
                tenant_slug='sodimac-piloto',
                cliente_nombre='Sodimac Piloto',
                agente_producto=_MODULO_OPERADOR,
                agente_nombre=AGENTE_VERTEX_HUB,
                codigo='sku_quiebre',
                severidad='critical',
                titulo='SKU 88421 — quiebre proyectado 3 días (piloto)',
                mensaje_corto='Operador remoto — demo Chilemat.',
                modo='mock',
                origen='push_agente',
                occurred_at=ahora - timedelta(minutes=41),
                semaforo_dominio='inventario',
                kpi_snapshot={'ventas_hoy_clp': 18420000},
            ),
        },
        {
            'dedupe_key': f'vertex:maestro:{TENANT_SANTO_DOMINGO}:mentor_nota_credito',
            'estado': EST_ALERTA_ABIERTA,
            'minutes_ago': 18,
            'pill': build_pildora(
                tenant_id=TENANT_SANTO_DOMINGO,
                tenant_slug='santo-domingo',
                cliente_nombre='Ferretería Santo Domingo',
                agente_producto=_MODULO_MENTOR,
                agente_nombre='mentor',
                codigo='mentor_guia_nota_credito',
                severidad='info',
                titulo='Mentor: guía nota de crédito — 3 vendedoras consultaron hoy',
                mensaje_corto=(
                    'Paso a paso: localizar venta pagada → Caja → Cambios/devoluciones → '
                    'emitir NC según política de la tienda.'
                ),
                modo='mock',
                origen='push_agente',
                occurred_at=ahora - timedelta(minutes=18),
                semaforo_dominio='caja',
                nav_href='/caja/cambios',
            ),
        },
        {
            'dedupe_key': f'vertex:maestro:{TENANT_SODIMAC}:mentor_capacitacion',
            'estado': EST_ALERTA_ABIERTA,
            'minutes_ago': 33,
            'pill': build_pildora(
                tenant_id=TENANT_SODIMAC,
                tenant_slug='sodimac-piloto',
                cliente_nombre='Sodimac Piloto',
                agente_producto=_MODULO_MENTOR,
                agente_nombre='mentor',
                codigo='mentor_capacitacion',
                severidad='info',
                titulo='Mentor piloto: onboarding cajera — vale pendiente y cobro',
                mensaje_corto='Checklist interactivo para vendedora sin experiencia en POS.',
                modo='mock',
                origen='push_agente',
                occurred_at=ahora - timedelta(minutes=33),
                semaforo_dominio='caja',
                nav_href='/punto_venta',
            ),
        },
        {
            'dedupe_key': f'vertex:maestro:{TENANT_EASY}:caja_ok',
            'estado': EST_ALERTA_CERRADA,
            'minutes_ago': 28,
            'pill': build_pildora(
                tenant_id=TENANT_EASY,
                tenant_slug='easy-demo',
                cliente_nombre='Easy Demo',
                agente_producto=_MODULO_GUARDIAN,
                agente_nombre=AGENTE_VERTEX_HUB,
                codigo='caja_ok',
                severidad='info',
                titulo='Arqueo ciego OK — sucursal demo Las Condes',
                mensaje_corto='Guardián demo — sin desvíos.',
                modo='mock',
                origen='push_agente',
                occurred_at=ahora - timedelta(minutes=28),
                semaforo_dominio='caja',
                kpi_snapshot={'ventas_hoy_clp': 9200000, 'sucursales_activas': 2},
            ),
        },
    ]


def asegurar_pildoras_demo_red() -> int:
    """
    Persiste píldoras mock Sodimac/Easy en `agente_ejecuciones` (idempotente por dedupe_key).
    Retorna cantidad de filas creadas en esta llamada.
    """
    if not asegurar_tabla():
        return 0
    creadas = 0
    for spec in _demo_specs():
        if existe_dedupe_registrada(spec['dedupe_key']):
            continue
        pill = spec['pill']
        rid = crear_registro(
            agente_nombre=AGENTE_VERTEX_HUB,
            tipo=TIPO_ALERTA,
            estado=spec['estado'],
            titulo=pill['titulo'],
            cuerpo=pill.get('mensaje_corto'),
            severidad=pill['severidad'],
            codigo=pill['codigo'],
            dedupe_key=spec['dedupe_key'],
            payload=pill,
        )
        if rid:
            creadas += 1
    return creadas


def listar_filas_feed_maestro(*, limite: int = 20) -> list:
    """Filas recientes aptas para feed global (píldora explícita, alertas SD, telemetría Academy)."""
    from services.agente_ejecuciones_service import TIPO_LOG, listar_alertas_operativas

    AgenteEjecucion = None
    try:
        from app import AgenteEjecucion as _AE
        AgenteEjecucion = _AE
    except Exception:
        pass

    rows = listar_alertas_operativas(limite=max(limite * 3, 30), solo_abiertas=False)
    mentor_logs: list = []
    if AgenteEjecucion and asegurar_tabla():
        mentor_logs = (
            AgenteEjecucion.query.filter_by(agente_nombre='mentor', tipo=TIPO_LOG)
            .order_by(AgenteEjecucion.created_at.desc())
            .limit(max(limite, 10))
            .all()
        )
    merged = list(mentor_logs) + list(rows)
    merged.sort(key=lambda r: r.created_at or datetime.min, reverse=True)
    seen_ids: set[int] = set()
    deduped: list = []
    for row in merged:
        if row.id in seen_ids:
            continue
        seen_ids.add(row.id)
        deduped.append(row)

    out = []
    for row in deduped:
        payload = parse_payload_json(row.payload_json)
        if payload.get('vertex_pildora_version') == PILDORA_VERSION:
            out.append(row)
            continue
        if row.agente_nombre in ('operador', 'guardian', 'mentor', AGENTE_VERTEX_HUB):
            if payload.get('vertex_pildora_version') == PILDORA_VERSION and row.agente_nombre == 'mentor':
                out.append(row)
                continue
            if payload.get('tenant_id') in (TENANT_SODIMAC, TENANT_EASY):
                out.append(row)
                continue
            if not payload.get('tenant_id') or payload.get('tenant_id') == TENANT_SANTO_DOMINGO:
                out.append(row)
    return out[:limite]
