"""Centro de Mandos Global Multi-Cliente — LhexIA VERTEX (cascarón Fase V3)."""

from __future__ import annotations



import os

from datetime import datetime

from typing import Any, Callable



from services.owner_dashboard_service import (

    _estado_a_status,

    _fmt_hace,

    _status_global,

    construir_owner_dashboard,

    kpis_ventas_hoy,

)

from services.vertex_pildora_contract import (

    AGENTE_VERTEX_HUB,

    PILDORA_VERSION,

    TENANT_EASY,

    TENANT_SANTO_DOMINGO,

    TENANT_SODIMAC,

    asegurar_pildoras_demo_red,

    listar_filas_feed_maestro,

    pildora_from_row,

)



SCOPE_GLOBAL_MAESTRO = 'global_maestro'



_MODULO_GUARDIAN = 'vertex_guardian'

_MODULO_OPERADOR = 'vertex_operador'

_MODULO_LOGISTICA = 'vertex_logistica'

_MODULO_INVENTARIO = 'vertex_inventario'



_SEV_TO_SEM = {'critical': 'rojo', 'warning': 'amarillo', 'info': 'verde'}

_DOMINIO_KEY = {

    'caja': 'caja',

    'inventario': 'inventario',

    'credito': 'credito',

    'compras': 'compras',

    'logistica': 'compras',

}





def usuario_es_vertex_maestro(usuario=None) -> bool:

    """

    Dueño LhexIA / plataforma: `gestionar_usuarios` + lista opcional

    `LHEXIA_VERTEX_MAESTRO_USERS` (usuarios separados por coma).

    """

    if usuario is None:

        return os.getenv('OWNER_GUARDIAN_DEV_MOCK', '').strip() == '1'



    from app import usuario_obj_tiene_permiso



    if not usuario_obj_tiene_permiso(usuario, 'gestionar_usuarios'):

        return False



    restrict = (os.getenv('LHEXIA_VERTEX_MAESTRO_USERS') or '').strip()

    if not restrict:

        return True



    allowed = {x.strip().lower() for x in restrict.split(',') if x.strip()}

    for attr in ('nombre_usuario', 'email', 'nombre'):

        val = (getattr(usuario, attr, None) or '').strip().lower()

        if val and val in allowed:

            return True

    return False





def _nombre_cliente_sd() -> str:

    return (

        os.getenv('LHEXIA_CLIENTE_SD_NOMBRE')

        or os.getenv('OWNER_GUARDIAN_SUCURSAL_LABEL')

        or 'Ferretería Santo Domingo'

    ).strip()





def _default_sd_tenant() -> dict[str, str]:

    return {

        'tenant_id': TENANT_SANTO_DOMINGO,

        'tenant_slug': 'santo-domingo',

        'cliente_nombre': _nombre_cliente_sd(),

    }





def _aplicar_pildoras_a_semaforos(

    sem: dict[str, str],

    pildoras: list[dict[str, Any]],

) -> dict[str, str]:

    rank = {'rojo': 3, 'amarillo': 2, 'verde': 1}

    out = dict(sem)

    for pill in pildoras:

        dom = pill.get('semaforo_dominio')

        if not dom:

            continue

        key = _DOMINIO_KEY.get(dom, dom)

        if key not in out:

            continue

        nuevo = _SEV_TO_SEM.get((pill.get('severidad') or 'info').lower(), 'verde')

        if rank.get(nuevo, 0) > rank.get(out[key], 0):

            out[key] = nuevo

    return out





def _estado_global_desde_semaforos(sem: dict[str, str]) -> str:

    st = _status_global(

        _estado_a_status(sem.get('caja', 'verde')),

        _estado_a_status(sem.get('inventario', 'verde')),

        _estado_a_status(sem.get('credito', 'verde')),

        _estado_a_status(sem.get('compras', 'verde')),

    )

    return {'red': 'rojo', 'amber': 'amarillo', 'green': 'verde'}.get(st, 'verde')





def _cliente_plantilla_mock(

    *,

    tenant_id: str,

    tenant_slug: str,

    nombre: str,

    vertical: str,

    semaforos_base: dict[str, str],

    modulos: list[str],

    agentes: list[str],

    kpis: dict[str, Any],

    mensaje: str,

    pildoras: list[dict[str, Any]],

) -> dict[str, Any]:

    sem = _aplicar_pildoras_a_semaforos(semaforos_base, pildoras)

    return {

        'id': tenant_id,

        'nombre': nombre,

        'tenant_id': tenant_id,

        'tenant_slug': tenant_slug,

        'pais': 'CL',

        'vertical': vertical,

        'fuente_datos': 'mock',

        'estado_global': _estado_global_desde_semaforos(sem),

        'semaforos': sem,

        'modulos_contratados': modulos,

        'agentes_activos': agentes,

        'kpis': kpis,

        'mensaje_resumen': mensaje,

        'pildoras_activas': len([p for p in pildoras if p.get('severidad') in ('critical', 'warning')]),

    }





def _clientes_mock(*, pildoras_por_tenant: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:

    sod_pills = pildoras_por_tenant.get(TENANT_SODIMAC, [])

    easy_pills = pildoras_por_tenant.get(TENANT_EASY, [])

    return [

        _cliente_plantilla_mock(

            tenant_id=TENANT_SODIMAC,

            tenant_slug='sodimac-piloto',

            nombre='Sodimac Piloto',

            vertical='retail',

            semaforos_base={

                'caja': 'verde',

                'inventario': 'amarillo',

                'credito': 'verde',

                'compras': 'amarillo',

            },

            modulos=[_MODULO_GUARDIAN, _MODULO_OPERADOR, _MODULO_LOGISTICA],

            agentes=['guardian', 'operador', 'logistica'],

            kpis={

                'ventas_hoy_clp': 18420000,

                'ventas_hoy_fmt': '$18.420.000',

                'transacciones_hoy': 412,

                'sucursales_activas': 4,

            },

            mensaje='Piloto retail — red neuronal con píldoras persistidas.',

            pildoras=sod_pills,

        ),

        _cliente_plantilla_mock(

            tenant_id=TENANT_EASY,

            tenant_slug='easy-demo',

            nombre='Easy Demo',

            vertical='retail',

            semaforos_base={

                'caja': 'verde',

                'inventario': 'verde',

                'credito': 'verde',

                'compras': 'verde',

            },

            modulos=[_MODULO_GUARDIAN, _MODULO_INVENTARIO],

            agentes=['guardian', 'inventario'],

            kpis={

                'ventas_hoy_clp': 9200000,

                'ventas_hoy_fmt': '$9.200.000',

                'transacciones_hoy': 198,

                'sucursales_activas': 2,

            },

            mensaje='Demo estable — eventos Guardián en feed global.',

            pildoras=easy_pills,

        ),

    ]





def _cliente_santo_domingo_live(*, calcular_ctx_caja: Callable, usuario=None) -> dict[str, Any]:

    """Cliente #1: semáforos y KPIs desde BD actual (Guardián v3)."""

    dash = construir_owner_dashboard(

        calcular_ctx_caja=calcular_ctx_caja,

        usuario=usuario,

    )

    tc = dash.get('tarjeta_caja') or {}

    ti = dash.get('tarjeta_inventario') or {}

    tcr = dash.get('tarjeta_credito') or {}

    tco = dash.get('tarjeta_compras') or {}

    cons = dash.get('consolidado') or {}



    sem = {

        'caja': tc.get('estado', 'verde'),

        'inventario': ti.get('estado', 'verde'),

        'credito': tcr.get('estado', 'verde'),

        'compras': tco.get('estado', 'verde'),

    }

    estado_global = _estado_global_desde_semaforos(sem)



    modulos = [_MODULO_GUARDIAN, _MODULO_OPERADOR]

    if sem['inventario'] in ('amarillo', 'rojo'):

        modulos.append(_MODULO_INVENTARIO)



    return {

        'id': TENANT_SANTO_DOMINGO,

        'nombre': _nombre_cliente_sd(),

        'tenant_id': TENANT_SANTO_DOMINGO,

        'tenant_slug': 'santo-domingo',

        'pais': 'CL',

        'vertical': 'ferreteria',

        'fuente_datos': 'live',

        'estado_global': estado_global,

        'semaforos': sem,

        'modulos_contratados': modulos,

        'agentes_activos': ['guardian', 'operador'],

        'kpis': {

            'ventas_hoy_clp': cons.get('ventas_hoy_clp', 0),

            'ventas_hoy_fmt': cons.get('ventas_hoy_fmt', '$0'),

            'transacciones_hoy': cons.get('transacciones_hoy', 0),

            'descuadre_acumulado_fmt': cons.get('descuadre_acumulado_fmt'),

            'alertas_operador': dash.get('meta', {}).get('alertas_abiertas', 0),

        },

        'mensaje_resumen': (dash.get('mensaje_ia') or '')[:200],

        'guardian_perfil': dash.get('perfil'),

    }





def _feed_item_desde_fila(row, *, default_tenant: dict[str, str] | None = None) -> dict[str, Any]:

    pill = pildora_from_row(row, default_tenant=default_tenant or _default_sd_tenant())

    tenant_id = pill.get('tenant_id', TENANT_SANTO_DOMINGO)

    modo = pill.get('modo', 'live')

    fuente = 'live' if modo == 'live' else 'mock'

    ts = pill.get('occurred_at') or ''

    try:

        dt = datetime.fromisoformat(ts) if ts else (row.updated_at or row.created_at)

    except ValueError:

        dt = row.updated_at or row.created_at



    nav = pill.get('nav_href') or '#'

    if modo == 'mock':

        nav = '#'



    return {

        'id': f'{tenant_id}-{row.id}',

        'registro_id': row.id,

        'tipo': 'alerta',

        'cliente_id': tenant_id,

        'cliente_nombre': pill.get('cliente_nombre', ''),

        'agente': pill.get('agente_nombre') or row.agente_nombre or 'operador',

        'agente_producto': pill.get('agente_producto', _MODULO_OPERADOR),

        'severidad': (pill.get('severidad') or 'info').lower(),

        'codigo': pill.get('codigo', ''),

        'titulo': (pill.get('titulo') or row.titulo or '')[:120],

        'hace': _fmt_hace(dt),

        'timestamp': dt.isoformat(timespec='seconds') if dt else ts,

        'estado': row.estado,

        'nav_href': nav,

        'fuente_datos': fuente,

        'pildora': pill,

    }





def _feed_preview_global(*, limite: int = 5) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:

    """Feed desde `agente_ejecuciones` (píldoras v1.0 + alertas SD envueltas)."""

    pildoras_por_tenant: dict[str, list[dict[str, Any]]] = {

        TENANT_SANTO_DOMINGO: [],

        TENANT_SODIMAC: [],

        TENANT_EASY: [],

    }

    items: list[dict[str, Any]] = []



    for row in listar_filas_feed_maestro(limite=limite * 4):

        item = _feed_item_desde_fila(row)

        items.append(item)

        tid = item.get('cliente_id')

        if tid in pildoras_por_tenant:

            pildoras_por_tenant[tid].append(item['pildora'])



    sev_rank = {'critical': 0, 'warning': 1, 'info': 2}



    def sort_key(it: dict) -> tuple:

        return (sev_rank.get(it.get('severidad', 'info'), 9), it.get('timestamp') or '')



    items.sort(key=sort_key)

    return items[:limite], pildoras_por_tenant





def _grafo_agentes(clientes: list[dict[str, Any]]) -> dict[str, Any]:

    """Mapa de interconexión agentes ↔ clientes (visualización front)."""

    nodos: list[dict[str, Any]] = [

        {

            'id': 'vertex_hub',

            'tipo': 'hub',

            'label': 'VERTEX Hub',

            'sub': 'Plataforma LhexIA',

        },

    ]

    aristas: list[dict[str, Any]] = []



    agente_labels = {

        'guardian': 'Guardián',

        'operador': 'Operador',

        'logistica': 'Logística',

        'inventario': 'Inventario',

    }



    for cli in clientes:

        cid = cli['id']

        nodos.append({

            'id': f'cliente_{cid}',

            'tipo': 'cliente',

            'label': cli.get('nombre', cid),

            'estado_global': cli.get('estado_global', 'verde'),

            'fuente_datos': cli.get('fuente_datos', 'mock'),

        })

        aristas.append({

            'from': 'vertex_hub',

            'to': f'cliente_{cid}',

            'tipo': 'tenant',

            'estado': cli.get('estado_global', 'verde'),

        })



        for ag in cli.get('agentes_activos') or []:

            nid = f'{cid}_{ag}'

            nodos.append({

                'id': nid,

                'tipo': 'agente',

                'label': agente_labels.get(ag, ag.title()),

                'cliente_id': cid,

                'agente': ag,

            })

            aristas.append({

                'from': f'cliente_{cid}',

                'to': nid,

                'tipo': 'contrato',

                'estado': 'activo',

            })

            aristas.append({

                'from': nid,

                'to': 'vertex_hub',

                'tipo': 'telemetria',

                'estado': 'sync',

            })



    return {'nodos': nodos, 'aristas': aristas}





def _resumen_red(clientes: list[dict[str, Any]], *, pildoras_sembradas: int = 0) -> dict[str, Any]:

    kpis = kpis_ventas_hoy()

    live = [c for c in clientes if c.get('fuente_datos') == 'live']

    mock = [c for c in clientes if c.get('fuente_datos') == 'mock']

    rojos = sum(1 for c in clientes if c.get('estado_global') == 'rojo')

    amarillos = sum(1 for c in clientes if c.get('estado_global') == 'amarillo')

    eventos_red = sum(c.get('pildoras_activas', 0) for c in mock)

    return {

        'clientes_total': len(clientes),

        'clientes_live': len(live),

        'clientes_mock': len(mock),

        'alertas_rojo': rojos,

        'alertas_amarillo': amarillos,

        'eventos_red_neuronal': eventos_red,

        'pildoras_demo_sembradas': pildoras_sembradas,

        'ventas_hoy_red_live_fmt': (live[0].get('kpis') or {}).get('ventas_hoy_fmt')

        if live

        else kpis.get('ventas_hoy_fmt', '$0'),

    }





def construir_dashboard_global_maestro(

    *,

    calcular_ctx_caja: Callable,

    usuario=None,

) -> dict[str, Any]:

    """Payload `data` cuando `?scope=global_maestro` en API Guardián v3."""

    pildoras_nuevas = asegurar_pildoras_demo_red()

    sd = _cliente_santo_domingo_live(calcular_ctx_caja=calcular_ctx_caja, usuario=usuario)

    feed, pildoras_por_tenant = _feed_preview_global(limite=5)

    clientes = [sd] + _clientes_mock(pildoras_por_tenant=pildoras_por_tenant)

    grafo = _grafo_agentes(clientes)

    resumen = _resumen_red(clientes, pildoras_sembradas=pildoras_nuevas)



    nombre_maestro = ''

    if usuario:

        nombre_maestro = (

            getattr(usuario, 'nombre', None)

            or getattr(usuario, 'nombre_usuario', None)

            or ''

        ).strip()



    return {

        'version': 'guardian_v3',

        'scope': SCOPE_GLOBAL_MAESTRO,

        'ecosystem': 'lhexia_vertex',

        'panel': 'vertex_control_center',

        'saludo': f'Centro de Mandos VERTEX — {nombre_maestro or "Maestro"}',

        'clientes': clientes,

        'feed_preview_global': feed,

        'grafo_agentes': grafo,

        'resumen_red': resumen,

        'meta': {

            'version': 'guardian_v3',

            'scope': SCOPE_GLOBAL_MAESTRO,

            'ecosystem': 'lhexia_vertex',

            'vertex_pildora_version': PILDORA_VERSION,

            'generado_en': datetime.now().isoformat(timespec='seconds'),

            'poll_recomendado_ms': 45000,

            'clientes_mock_ids': [TENANT_SODIMAC, TENANT_EASY],

            'cliente_live_id': TENANT_SANTO_DOMINGO,

            'agente_red_hub': AGENTE_VERTEX_HUB,

            'modo_ingesta_sd1': 'pull+push_pildora',

        },

    }


