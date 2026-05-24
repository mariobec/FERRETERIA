"""Agente Mentor (vertex_mentor) — contexto POS/caja y telemetría LhexIA Academy."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from services.agente_ejecuciones_service import EST_LOG_EJECUTADO, TIPO_LOG, registrar_ejecucion_mentor
from services.vertex_pildora_contract import (
    TENANT_SANTO_DOMINGO,
    _MODULO_MENTOR,
    build_pildora,
    parse_payload_json,
)

# Píldoras contextuales (dedupe_key maestro)
PILDORA_NOTA_CREDITO = f'vertex:maestro:{TENANT_SANTO_DOMINGO}:mentor_nota_credito'
PILDORA_CAJA_DIA_ANTERIOR = f'vertex:maestro:{TENANT_SANTO_DOMINGO}:mentor_caja_dia_anterior'
PILDORA_CAPACITACION_POS = f'vertex:maestro:{TENANT_SANTO_DOMINGO}:mentor_capacitacion'

# Biblioteca virtual — guías interactivas (dedupe_key = componente)
ACADEMY_GUIDES: list[dict[str, Any]] = [
    {
        'dedupe_key': 'academy:pos:emitir_vale',
        'titulo': 'Emitir un vale en POS',
        'contextos': ('pos',),
        'pasos': [
            'Buscar producto por nombre o código de barra.',
            'Ajustar cantidades y revisar alertas de stock.',
            'Identificar cliente o usar cliente final.',
            'Pulsar Emitir vale — el cobro lo hace caja.',
        ],
        'ancla_ayuda': '/academy#academy-pos',
    },
    {
        'dedupe_key': 'academy:caja:cobrar_vale',
        'titulo': 'Cobrar vales pendientes',
        'contextos': ('caja', 'pos'),
        'pasos': [
            'Abrir Vales pendientes.',
            'Seleccionar vale de la cola.',
            'Elegir método de pago y confirmar cobro.',
            'Entregar vuelto si corresponde.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
    {
        'dedupe_key': 'academy:caja:cambios_devoluciones',
        'titulo': 'Cambios y devoluciones',
        'contextos': ('cambios_devoluciones',),
        'pasos': [
            'Localizar venta pagada en Caja → Cambios.',
            'Seleccionar ítems y motivo de devolución.',
            'Emitir nota de crédito según política de la tienda.',
            'Verificar saldo a favor o reintegro en caja.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
    {
        'dedupe_key': 'academy:caja:caja_dia_anterior',
        'titulo': 'Regularizar caja del día anterior',
        'contextos': ('caja_dia_anterior', 'caja', 'cerrar_caja'),
        'pasos': [
            'Ir a Cerrar caja de la apertura pendiente.',
            'Cuadrar efectivo y tarjetas declaradas.',
            'Resolver vales pendientes si los hay.',
            'Abrir caja nueva para el turno actual.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
    {
        'dedupe_key': 'academy:caja:abrir_cerrar',
        'titulo': 'Abrir y cerrar caja',
        'contextos': ('caja', 'cerrar_caja', 'abrir_caja'),
        'pasos': [
            'Abrir caja con monto inicial real al iniciar turno.',
            'Registrar movimientos extraordinarios con motivo.',
            'Al cierre, contar gaveta y declarar montos.',
            'Agregar observación si hay descuadre.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
    {
        'dedupe_key': 'academy:caja:apertura_turno',
        'titulo': 'Apertura de caja (inicio de turno)',
        'contextos': ('abrir_caja',),
        'pasos': [
            'Contar el efectivo real en gaveta antes de declarar.',
            'Ingresar saldo inicial en pesos chilenos (puede usar punto de miles).',
            'Confirmar apertura — solo después podrá cobrar vales en caja.',
            'Si el POS está bloqueado, verifique que no quede caja del día anterior abierta.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
    {
        'dedupe_key': 'academy:caja:movimiento_extra',
        'titulo': 'Movimientos de ingreso y egreso',
        'contextos': ('movimiento_caja', 'caja'),
        'pasos': [
            'Elegir tipo: Ingreso (entra dinero) o Egreso (sale dinero).',
            'Describir concepto claro (ej. compra insumos, retiro autorizado).',
            'En egreso, indicar responsable del retiro.',
            'Guardar y verificar en el historial del turno.',
        ],
        'ancla_ayuda': '/academy#academy-caja',
    },
]


def _normalizar_path(url: str | None) -> str:
    raw = (url or '').strip()
    if not raw:
        return ''
    if raw.startswith('http'):
        return (urlparse(raw).path or '').lower()
    return raw.split('?')[0].lower()


def detectar_contexto_pantalla(url: str | None) -> str:
    """Inferir contexto operativo desde la URL del piso."""
    path = _normalizar_path(url)
    if any(x in path for x in ('/caja/cambios', 'caja_cambios', '/cambios')):
        return 'cambios_devoluciones'
    if any(x in path for x in ('/caja/vales', 'caja_pendientes', '/caja/pendientes')):
        return 'caja'
    if any(x in path for x in ('/cerrar_caja', '/caja/cerrar', 'cerrar_caja')):
        return 'cerrar_caja'
    if any(x in path for x in ('/abrir_caja', 'abrir_caja')):
        return 'abrir_caja'
    if any(x in path for x in ('/movimiento_caja', 'movimiento_caja')):
        return 'movimiento_caja'
    if any(x in path for x in ('/punto_venta', '/pos')):
        return 'pos'
    return 'general'


def _caja_dia_anterior_abierta() -> tuple[bool, int | None]:
    from app import Caja, obtener_caja_activa

    caja = obtener_caja_activa()
    if not caja or not caja.fecha_apertura:
        return False, None
    if caja.fecha_apertura.date() < datetime.now().date():
        return True, caja.id
    return False, caja.id


def _pildora_nota_credito() -> dict[str, Any]:
    return build_pildora(
        tenant_id=TENANT_SANTO_DOMINGO,
        tenant_slug='santo-domingo',
        cliente_nombre='Ferretería Santo Domingo',
        agente_producto=_MODULO_MENTOR,
        agente_nombre='mentor',
        codigo='mentor_guia_nota_credito',
        severidad='info',
        titulo='Mentor: guía nota de crédito y devoluciones',
        mensaje_corto=(
            'Paso a paso: localizar venta pagada → Caja → Cambios/devoluciones → '
            'emitir NC según política de la tienda.'
        ),
        modo='live',
        origen='academy_contexto',
        semaforo_dominio='caja',
        nav_href='/caja/cambios',
        kpi_snapshot={'pildora_dedupe_key': PILDORA_NOTA_CREDITO},
    )


def _pildora_caja_dia_anterior(caja_id: int | None) -> dict[str, Any]:
    return build_pildora(
        tenant_id=TENANT_SANTO_DOMINGO,
        tenant_slug='santo-domingo',
        cliente_nombre='Ferretería Santo Domingo',
        agente_producto=_MODULO_MENTOR,
        agente_nombre='mentor',
        codigo='mentor_caja_dia_anterior',
        severidad='warning',
        titulo='Mentor: caja del día anterior sin cerrar',
        mensaje_corto=(
            'El POS puede estar bloqueado. Cierre la caja pendiente, resuelva vales abiertos '
            'y abra turno nuevo antes de vender.'
        ),
        modo='live',
        origen='academy_contexto',
        semaforo_dominio='caja',
        nav_href='/cerrar_caja',
        kpi_snapshot={'pildora_dedupe_key': PILDORA_CAJA_DIA_ANTERIOR, 'caja_id': caja_id},
    )


def _pildora_capacitacion_pos() -> dict[str, Any]:
    return build_pildora(
        tenant_id=TENANT_SANTO_DOMINGO,
        tenant_slug='santo-domingo',
        cliente_nombre='Ferretería Santo Domingo',
        agente_producto=_MODULO_MENTOR,
        agente_nombre='mentor',
        codigo='mentor_capacitacion',
        severidad='info',
        titulo='Mentor: checklist vale y cobro en mostrador',
        mensaje_corto='Guía interactiva: buscar producto, emitir vale y derivar a caja para cobro.',
        modo='live',
        origen='academy_contexto',
        semaforo_dominio='caja',
        nav_href='/punto_venta',
        kpi_snapshot={'pildora_dedupe_key': PILDORA_CAPACITACION_POS},
    )


def resolver_pildora_prioritaria(contexto: str, *, caja_dia_anterior: bool) -> dict[str, Any] | None:
    if contexto == 'cambios_devoluciones':
        return _pildora_nota_credito()
    if caja_dia_anterior:
        _, caja_id = _caja_dia_anterior_abierta()
        return _pildora_caja_dia_anterior(caja_id)
    if contexto == 'cerrar_caja':
        return build_pildora(
            tenant_id=TENANT_SANTO_DOMINGO,
            tenant_slug='santo-domingo',
            cliente_nombre='Ferretería Santo Domingo',
            agente_producto=_MODULO_MENTOR,
            agente_nombre='mentor',
            codigo='mentor_consulta_academy',
            severidad='info',
            titulo='Mentor: cierre de turno paso a paso',
            mensaje_corto='Cuente efectivo y vouchers, declare montos y confirme cierre. Revise vales pendientes antes.',
            modo='live',
            origen='academy_contexto',
            semaforo_dominio='caja',
            nav_href='/cerrar_caja',
        )
    if contexto == 'abrir_caja':
        return build_pildora(
            tenant_id=TENANT_SANTO_DOMINGO,
            tenant_slug='santo-domingo',
            cliente_nombre='Ferretería Santo Domingo',
            agente_producto=_MODULO_MENTOR,
            agente_nombre='mentor',
            codigo='mentor_apertura_caja',
            severidad='info',
            titulo='Mentor: apertura de caja',
            mensaje_corto='Declare el efectivo real en gaveta para iniciar el turno y habilitar cobros.',
            modo='live',
            origen='academy_contexto',
            semaforo_dominio='caja',
            nav_href='/abrir_caja',
            kpi_snapshot={'dedupe_key': 'academy:caja:apertura_turno'},
        )
    if contexto == 'movimiento_caja':
        return build_pildora(
            tenant_id=TENANT_SANTO_DOMINGO,
            tenant_slug='santo-domingo',
            cliente_nombre='Ferretería Santo Domingo',
            agente_producto=_MODULO_MENTOR,
            agente_nombre='mentor',
            codigo='mentor_movimiento_caja',
            severidad='info',
            titulo='Mentor: movimientos de caja',
            mensaje_corto='Registre ingresos y egresos con concepto; en egresos indique responsable del retiro.',
            modo='live',
            origen='academy_contexto',
            semaforo_dominio='caja',
            nav_href='/movimiento_caja',
            kpi_snapshot={'dedupe_key': 'academy:caja:movimiento_extra'},
        )
    if contexto == 'pos':
        return _pildora_capacitacion_pos()
    return None


def listar_guias_biblioteca(contexto: str, *, caja_dia_anterior: bool) -> list[dict[str, Any]]:
    ctx_extra = ('caja_dia_anterior',) if caja_dia_anterior else ()
    out: list[dict[str, Any]] = []
    for g in ACADEMY_GUIDES:
        ctxs = tuple(g.get('contextos') or ())
        if contexto in ctxs or any(c in ctxs for c in ctx_extra):
            out.append(
                {
                    'dedupe_key': g['dedupe_key'],
                    'titulo': g['titulo'],
                    'pasos': list(g.get('pasos') or []),
                    'ancla_ayuda': g.get('ancla_ayuda'),
                }
            )
    if not out:
        out = [
            {
                'dedupe_key': g['dedupe_key'],
                'titulo': g['titulo'],
                'pasos': list(g.get('pasos') or []),
                'ancla_ayuda': g.get('ancla_ayuda'),
            }
            for g in ACADEMY_GUIDES[:3]
        ]
    return out


def construir_contexto_mentor(*, url: str | None) -> dict[str, Any]:
    from services.academy_service import construir_contexto_mentor_db

    return construir_contexto_mentor_db(url=url)


def registrar_consulta_academy(
    *,
    usuario_id: int,
    usuario_nombre: str,
    dedupe_key: str,
    accion: str = 'expandir',
    url: str | None = None,
) -> dict[str, Any]:
    """Registra telemetría de guía consultada (feed VERTEX + mapa cognitivo)."""
    from services.academy_service import registrar_lectura_academy

    return registrar_lectura_academy(
        usuario_id=usuario_id,
        usuario_nombre=usuario_nombre,
        dedupe_key=dedupe_key,
        accion=accion,
        url=url,
    )


def fila_es_telemetria_academy(row) -> bool:
    if (row.agente_nombre or '') != 'mentor' or row.tipo != TIPO_LOG:
        return False
    if row.estado != EST_LOG_EJECUTADO:
        return False
    payload = parse_payload_json(row.payload_json)
    return payload.get('vertex_pildora_version') == '1.0' or payload.get('origen') == 'academy_sidebar'
