"""Lhexia Guardián v3 — dashboard multiperfil + KPIs + feed + acciones."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    asegurar_tabla,
    contar_alertas_abiertas,
    cuerpo_alerta_para_ui,
    parse_payload_json,
)
from services.agente_ejecuciones_service import listar_alertas_operativas
from services.control_center_service import obtener_tarjetas_sucursales
from services.empresa_operacion_service import es_operacion_un_local, obtener_sucursales_red_n

_CODIGOS_CAJA = ('caja_descuadre', 'caja_dia_anterior')

# Rutas PWA (paths absolutos; el front resuelve mismo origen)
_URL_CONTROL_CENTER = '/admin/control-center'
_URL_ABASTECIMIENTO = '/ia/abastecimiento?dias=30&solo_alerta=1&from=owner'
_URL_CREDITOS = '/creditos'
_URL_ORDENES_COMPRA = '/compras/ordenes'

_ROLES_ALTA_GERENCIA = frozenset({
    'dueño', 'dueno', 'dono', 'gerencia', 'alta gerencia', 'alta_gerencia',
    'director', 'presidente', 'superadmin', 'super admin',
    'administrador', 'admin',
})
_ROLES_SUPERVISOR_SUCURSAL = frozenset({
    'supervisor', 'jefe tienda', 'jefe de tienda',
})


@dataclass(frozen=True)
class PerfilGuardian:
    codigo: str
    alcance: str
    saludo: str
    sucursal_label: str | None
    nombre_usuario: str


def _fmt_clp(valor: int | float | None) -> str:
    n = int(round(float(valor or 0)))
    sign = '+' if n > 0 else ''
    return f'{sign}${abs(n):,}'.replace(',', '.')


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


def _normalizar_rol(rol: str | None) -> str:
    return (rol or '').strip().lower()


def _sucursal_label_default() -> str:
    return (
        os.getenv('OWNER_GUARDIAN_SUCURSAL_LABEL')
        or os.getenv('CONTROL_CENTER_SUCURSAL_LABEL')
        or os.getenv('OWNER_PWA_SUCURSAL_LABEL')
        or 'Santo Domingo SD-1'
    ).strip()


def guardian_suprimir_alertas_stock() -> bool:
    """
    Piloto / demo: oculta semáforo INV y mensajes de quiebre por catálogo masivo en Neon.
    No afecta alertas Operador (caja/vales) en agente_ejecuciones.
    """
    return (os.getenv('OWNER_GUARDIAN_DEMO_LIMPIO') or '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )


def _caja_pertenece_sucursal(caja, sucursal_label: str) -> bool:
    """Heurística sucursal hasta modelo multi-sucursal en Caja."""
    label = (sucursal_label or '').strip().upper()
    if not label:
        return True
    u = (caja.usuario_apertura or '').upper()
    cierre = (caja.usuario_cierre or '').upper()
    blob = f'{u} {cierre}'
    tokens = [t for t in label.replace('—', '-').split() if len(t) >= 2]
    if any(t in blob for t in tokens):
        return True
    if 'SD-1' in label or 'SD1' in label:
        if 'SD-1' in blob or 'SD1' in blob or 'SANTO' in blob:
            return True
    ids_raw = (os.getenv('OWNER_GUARDIAN_CAJA_IDS_SD1') or '').strip()
    if ids_raw:
        ids = {x.strip() for x in ids_raw.split(',') if x.strip()}
        if str(caja.id) in ids:
            return True
    return False


def saludo_guardian_usuario(usuario) -> str:
    """Saludo visible en PWA y API (v2)."""
    perfil = detectar_perfil_guardian(usuario)
    return perfil.saludo


def detectar_perfil_guardian(usuario=None) -> PerfilGuardian:
    """
    Detecta perfil Guardián según rol Flask-Login.
    Sin usuario + OWNER_GUARDIAN_DEV_MOCK=1 → mock_dueno (desarrollo).
    """
    if usuario is None:
        if os.getenv('OWNER_GUARDIAN_DEV_MOCK', '').strip() == '1':
            return PerfilGuardian(
                codigo='mock_dueno',
                alcance='global',
                saludo='¡Hola, Don Mario!',
                sucursal_label=None,
                nombre_usuario='Mario (mock)',
            )
        return PerfilGuardian(
            codigo='anonimo',
            alcance='global',
            saludo='Centro de mando activo',
            sucursal_label=None,
            nombre_usuario='',
        )

    nombre = (getattr(usuario, 'nombre', None) or '').strip()
    primer = (nombre.split()[0] if nombre else '') or 'equipo'
    rol = _normalizar_rol(getattr(getattr(usuario, 'rol', None), 'nombre', None))

    if rol in _ROLES_ALTA_GERENCIA or any(
        k in rol for k in ('dueño', 'dueno', 'gerencia', 'director', 'presidente', 'alta')
    ):
        honor = 'Doña' if primer.lower().endswith('a') and len(primer) > 3 else 'Don'
        saludo = f'¡Hola, {honor} {primer}!' if primer != 'equipo' else '¡Hola!'
        return PerfilGuardian(
            codigo='alta_gerencia',
            alcance='global',
            saludo=saludo,
            sucursal_label=None,
            nombre_usuario=nombre or primer,
        )

    if 'supervisor' in rol or rol in _ROLES_SUPERVISOR_SUCURSAL:
        suc = _sucursal_label_default()
        return PerfilGuardian(
            codigo='supervisor',
            alcance='sucursal',
            saludo='Estimado Supervisor de Turno',
            sucursal_label=suc,
            nombre_usuario=nombre or primer,
        )

    honor = 'Doña' if primer.lower().endswith('a') and len(primer) > 3 else 'Don'
    return PerfilGuardian(
        codigo='alta_gerencia',
        alcance='global',
        saludo=f'¡Hola, {honor} {primer}!' if primer != 'equipo' else '¡Hola!',
        sucursal_label=None,
        nombre_usuario=nombre or primer,
    )


def _estado_a_status(estado: str | None) -> str:
    m = {
        'verde': 'green', 
        'rojo': 'red', 
        'amarillo': 'amber',
        'critico': 'red'
    }
    return m.get((estado or '').lower(), 'gray')


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
    mensaje = cuerpo_alerta_para_ui(row.cuerpo, payload)
    if not mensaje and payload.get('enriquecido_semantico'):
        mensaje = (payload.get('cuerpo_base_v01') or '').strip()[:500]
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


def _mejor_alerta_caja(*, sucursal_label: str | None = None):
    from app import AgenteEjecucion

    if not asegurar_tabla():
        return None
    base = AgenteEjecucion.query.filter_by(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
    ).filter(AgenteEjecucion.codigo.in_(_CODIGOS_CAJA))
    rows = base.order_by(AgenteEjecucion.created_at.desc()).limit(20).all()
    if sucursal_label:
        from app import Caja

        suc = sucursal_label
        filtradas = []
        for row in rows:
            if row.caja_id:
                caja = Caja.query.get(row.caja_id)
                if caja and _caja_pertenece_sucursal(caja, suc):
                    filtradas.append(row)
                    continue
            payload = parse_payload_json(row.payload_json)
            blob = f'{(row.titulo or "")} {(row.cuerpo or "")} {payload}'.upper()
            suc_u = suc.upper()
            if suc_u in blob or ('SD-1' in suc_u and 'SD' in blob):
                filtradas.append(row)
        if filtradas:
            crit = [r for r in filtradas if (r.severidad or '').lower() == 'critical']
            return crit[0] if crit else filtradas[0]
        return None
    crit = (
        base.filter(AgenteEjecucion.severidad == 'critical')
        .order_by(AgenteEjecucion.created_at.desc())
        .first()
    )
    if crit:
        return crit
    return base.order_by(AgenteEjecucion.created_at.desc()).first()


def _bloque_caja_por_alcance(*, calcular_ctx_caja: Callable, alcance: str, sucursal_label: str | None) -> dict:
    bloque = obtener_tarjetas_sucursales(calcular_ctx=calcular_ctx_caja)
    if alcance == 'global':
        return bloque

    from app import Caja

    suc = sucursal_label or _sucursal_label_default()
    cerradas = Caja.query.filter_by(estado='Cerrada').all()
    descuadres = []
    for c in cerradas:
        diff = int(round(float(c.diferencia_cierre or 0)))
        if abs(diff) < 1:
            continue
        if _caja_pertenece_sucursal(c, suc):
            descuadres.append(diff)

    total = sum(descuadres)
    alerta_global = None
    if any(d < 0 for d in descuadres):
        alerta_global = 'danger'
    elif total != 0:
        alerta_global = 'warning'

    tarjetas = [
        t for t in (bloque.get('tarjetas') or [])
        if suc.upper() in (t.get('titulo') or '').upper()
    ]
    if not tarjetas and bloque.get('tarjetas'):
        tarjetas = (bloque.get('tarjetas') or [])[:2]

    return {
        'tarjetas': tarjetas,
        'alerta_global_clp': total,
        'alerta_global_fmt': _fmt_clp(total),
        'alerta_global_tipo': alerta_global or ('ok' if not descuadres else 'warning'),
        'cajas_con_descuadre': len(descuadres),
        'alertas_operador_abiertas': contar_alertas_abiertas(),
        'sucursal_filtro': suc,
    }


def _tarjeta_caja(
    *,
    calcular_ctx_caja: Callable,
    perfil: PerfilGuardian,
) -> dict[str, Any]:
    sucursal = perfil.sucursal_label if perfil.alcance == 'sucursal' else None
    row = _mejor_alerta_caja(sucursal_label=sucursal)
    if row:
        tarjeta = _tarjeta_desde_alerta(row, dominio='caja')
        if perfil.alcance == 'sucursal' and perfil.sucursal_label:
            tarjeta['mensaje'] = (
                f"{tarjeta['mensaje']} · Ámbito: {perfil.sucursal_label}."
            )[:500]
        return tarjeta

    bloque = _bloque_caja_por_alcance(
        calcular_ctx_caja=calcular_ctx_caja,
        alcance=perfil.alcance,
        sucursal_label=perfil.sucursal_label,
    )
    tipo_global = bloque.get('alerta_global_tipo')

    if tipo_global == 'danger':
        msg = (
            f"{bloque.get('cajas_con_descuadre', 0)} cierre(s) con diferencia. "
            f"Total {bloque.get('alerta_global_fmt', '')}."
        )
        if perfil.alcance == 'global':
            msg = (
                f"Desfalco acumulado red {bloque.get('alerta_global_fmt', '')}. "
                f"{bloque.get('cajas_con_descuadre', 0)} cierre(s) con descuadre."
            )
        elif perfil.sucursal_label:
            msg = (
                f"{bloque.get('cajas_con_descuadre', 0)} cierre(s) en {perfil.sucursal_label}. "
                f"Diferencia {bloque.get('alerta_global_fmt', '')}."
            )
        return {
            'estado': 'rojo',
            'titulo': 'Alerta Crítica: Caja: descuadre detectado',
            'mensaje': msg,
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
                + (f" · {perfil.sucursal_label}" if perfil.sucursal_label else '')
            ),
            'timestamp': 'Ahora',
            'accion_requerida': True,
            'tipo_accion': 'llamada_supervisor',
        }

    from app import Caja

    q = Caja.query.filter_by(estado='Abierta').order_by(Caja.id.desc())
    caja_abierta = q.first()
    if caja_abierta and caja_abierta.fecha_apertura:
        if perfil.alcance == 'sucursal' and not _caja_pertenece_sucursal(caja_abierta, perfil.sucursal_label or ''):
            pass
        elif caja_abierta.fecha_apertura.date() < datetime.now().date():
            return {
                'estado': 'amarillo',
                'titulo': f'Caja #{caja_abierta.id} abierta',
                'mensaje': 'Caja de día anterior sin cerrar. Debe cerrarse antes de seguir en POS.',
                'timestamp': _fmt_hace(caja_abierta.fecha_apertura),
                'accion_requerida': True,
                'tipo_accion': 'llamada_supervisor',
                'caja_id': caja_abierta.id,
            }

    ok_msg = 'Sin descuadres ni alertas del Operador.'
    if perfil.sucursal_label:
        ok_msg = f'Sucursal {perfil.sucursal_label}: caja sin alertas activas.'
    return {
        'estado': 'verde',
        'titulo': 'Caja: OK',
        'mensaje': ok_msg,
        'timestamp': 'Ahora',
        'accion_requerida': False,
        'tipo_accion': None,
    }


def _tarjeta_inventario(*, perfil: PerfilGuardian) -> dict[str, Any]:
    from app import Producto

    if guardian_suprimir_alertas_stock():
        sucursal = perfil.sucursal_label or _sucursal_label_default()
        return {
            'estado': 'verde',
            'titulo': 'Inventario: OK',
            'mensaje': f'Vista piloto sin alertas de stock ({sucursal}).',
            'timestamp': 'Ahora',
            'accion_requerida': False,
            'tipo_accion': None,
            'skus_bajo_minimo': 0,
        }

    # Métricas de salud: Stock + Calidad de Datos
    total_activos = Producto.query.filter(Producto.activo.is_(True)).count()
    bajo = Producto.query.filter(Producto.stock < 5, Producto.activo.is_(True)).count()
    sin_cat = Producto.query.filter(Producto.activo.is_(True), (Producto.categoria == None) | (Producto.categoria == '')).count()
    sin_ub = Producto.query.filter(Producto.activo.is_(True), (Producto.ubicacion_pasillo == None) | (Producto.ubicacion_pasillo == '')).count()

    if bajo >= 15:
        estado, titulo = 'rojo', 'Inventario: crítico'
    elif bajo >= 5 or sin_cat > 0:
        estado, titulo = 'amarillo', 'Inventario: atención'
    else:
        estado, titulo = 'verde', 'Inventario: OK'

    sucursal = perfil.sucursal_label or _sucursal_label_default()
    if perfil.alcance == 'global':
        sucursal = (os.getenv('OWNER_PWA_SUCURSAL_LABEL') or 'todas las sucursales').strip()

    return {
        'estado': estado,
        'titulo': titulo,
        'mensaje': f'{bajo} bajo stock, {sin_cat} sin categoría. Ámbito: {sucursal}.',
        'timestamp': 'Ahora',
        'accion_requerida': estado != 'verde',
        'tipo_accion': 'llamada_supervisor' if estado == 'rojo' else None,
        'skus_bajo_minimo': int(bajo),
        'skus_sin_categoria': int(sin_cat),
        'skus_sin_ubicacion': int(sin_ub),
    }


def _rango_dia_calendario(dia) -> tuple:
    """Inicio inclusive y fin exclusive del día calendario (misma TZ que datetime.now())."""
    from datetime import datetime, timedelta

    inicio = datetime.combine(dia, datetime.min.time())
    return inicio, inicio + timedelta(days=1)


def _filtro_ventas_kpi_dia():
    """Vales emitidos o cobrados hoy: Pagado + Pendiente; excluye Abierta y Anulada."""
    from app import Venta

    return Venta.estado.in_(('Pagado', 'Pendiente'))


def kpis_ventas_hoy() -> dict[str, Any]:
    """
    Ventas del día para Guardián / gerencia.
    Usa rango datetime (no DATE SQL) y estados Pagado+Pendiente para alinear con POS.
    """
    from datetime import date, timedelta

    from app import Venta, db

    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    inicio_hoy, fin_hoy = _rango_dia_calendario(hoy)
    inicio_ayer, fin_ayer = _rango_dia_calendario(ayer)
    filtro_estado = _filtro_ventas_kpi_dia()

    ventas_hoy = (
        db.session.query(db.func.sum(Venta.monto_total))
        .filter(
            Venta.fecha >= inicio_hoy,
            Venta.fecha < fin_hoy,
            filtro_estado,
        )
        .scalar()
        or 0
    )
    ventas_ayer = (
        db.session.query(db.func.sum(Venta.monto_total))
        .filter(
            Venta.fecha >= inicio_ayer,
            Venta.fecha < fin_ayer,
            filtro_estado,
        )
        .scalar()
        or 0
    )
    var_pct = None
    if ventas_ayer:
        var_pct = round(
            ((float(ventas_hoy) - float(ventas_ayer)) / float(ventas_ayer)) * 100.0,
            1,
        )
    transacciones = Venta.query.filter(
        Venta.fecha >= inicio_hoy,
        Venta.fecha < fin_hoy,
        filtro_estado,
    ).count()
    return {
        'ventas_hoy_clp': int(round(float(ventas_hoy))),
        'ventas_hoy_fmt': _fmt_clp(ventas_hoy),
        'var_vs_ayer_pct': var_pct,
        'transacciones_hoy': int(transacciones),
    }


def _kpis_ventas_hoy() -> dict[str, Any]:
    """Alias interno."""
    return kpis_ventas_hoy()


def _tablas_orden_compra_existen() -> bool:
    from sqlalchemy import inspect

    from app import db

    try:
        names = inspect(db.engine).get_table_names()
        return 'ordenes_compra' in names and 'detalle_orden_compra' in names
    except Exception:
        return False


def _tarjeta_credito(*, perfil: PerfilGuardian) -> dict[str, Any]:
    from app import Cliente, db

    total = float(db.session.query(db.func.sum(Cliente.saldo_deudor)).scalar() or 0)
    morosos = Cliente.query.filter(Cliente.saldo_deudor > 0).count()
    umbral_rojo = float(os.getenv('OWNER_GUARDIAN_CARTERA_ROJO_CLP', '5000000'))
    umbral_amarillo = float(os.getenv('OWNER_GUARDIAN_CARTERA_AMARILLO_CLP', '1500000'))
    if total >= umbral_rojo:
        estado, titulo = 'rojo', 'Crédito: cartera crítica'
    elif total >= umbral_amarillo:
        estado, titulo = 'amarillo', 'Crédito: revisar cobranza'
    else:
        estado, titulo = 'verde', 'Crédito: OK'
    alcance = perfil.sucursal_label or 'red'
    if perfil.alcance != 'global':
        alcance = perfil.sucursal_label or 'su sucursal'
    return {
        'estado': estado,
        'titulo': titulo,
        'mensaje': (
            f'Cartera ${int(total):,}'.replace(',', '.')
            + f' por cobrar · {morosos} cliente(s) con saldo. Ámbito: {alcance}.'
        ),
        'timestamp': 'Ahora',
        'accion_requerida': estado != 'verde',
        'tipo_accion': 'llamada_supervisor' if estado == 'rojo' else None,
        'cartera_clp': int(round(total)),
        'clientes_con_saldo': int(morosos),
    }


def _tarjeta_compras(*, perfil: PerfilGuardian) -> dict[str, Any]:
    oc_pendientes = 0
    if _tablas_orden_compra_existen():
        from app import OrdenCompra

        oc_estados = ('Borrador', 'Enviada', 'Parcial')
        oc_pendientes = OrdenCompra.query.filter(OrdenCompra.estado.in_(oc_estados)).count()
    if oc_pendientes >= 8:
        estado, titulo = 'rojo', 'Compras: OC urgentes'
    elif oc_pendientes >= 3:
        estado, titulo = 'amarillo', 'Compras: OC pendientes'
    else:
        estado, titulo = 'verde', 'Compras: OK'
    return {
        'estado': estado,
        'titulo': titulo,
        'mensaje': f'{oc_pendientes} orden(es) de compra pendientes de cierre.',
        'timestamp': 'Ahora',
        'accion_requerida': estado != 'verde',
        'tipo_accion': None,
        'oc_pendientes': int(oc_pendientes),
    }


def _acciones_para_tarjeta(
    dominio: str,
    tarjeta: dict[str, Any],
    *,
    telefono: str,
) -> list[dict[str, Any]]:
    acciones: list[dict[str, Any]] = []
    tel = (telefono or '').strip()
    est = (tarjeta.get('estado') or 'verde').lower()

    if dominio == 'caja':
        if tel and est in ('rojo', 'amarillo'):
            acciones.append({
                'id': 'call',
                'label': 'Llamar supervisor',
                'tipo': 'tel',
                'href': 'tel:' + tel.replace(' ', ''),
            })
        acciones.append({
            'id': 'cc',
            'label': 'Control Center',
            'tipo': 'nav',
            'href': _URL_CONTROL_CENTER,
        })
    elif dominio == 'inventario':
        acciones.append({
            'id': 'quiebre',
            'label': 'Ver quiebre stock',
            'tipo': 'nav',
            'href': _URL_ABASTECIMIENTO,
        })
        if est == 'rojo' and tel:
            acciones.append({
                'id': 'call',
                'label': 'Llamar supervisor',
                'tipo': 'tel',
                'href': 'tel:' + tel.replace(' ', ''),
            })
    elif dominio == 'credito':
        acciones.append({
            'id': 'creditos',
            'label': 'Cartera y cobranza',
            'tipo': 'nav',
            'href': _URL_CREDITOS,
        })
    elif dominio == 'compras':
        acciones.append({
            'id': 'oc',
            'label': 'Órdenes de compra',
            'tipo': 'nav',
            'href': _URL_ORDENES_COMPRA,
        })
    return acciones


def _tarjeta_v3(
    tarjeta: dict[str, Any],
    *,
    dominio: str,
    prioridad: int,
    telefono: str,
) -> dict[str, Any]:
    est = (tarjeta.get('estado') or 'verde').lower()
    out = dict(tarjeta)
    out['dominio'] = dominio
    out['status'] = _estado_a_status(est)
    out['prioridad'] = prioridad
    out['acciones'] = _acciones_para_tarjeta(dominio, tarjeta, telefono=telefono)
    return out


def _feed_preview(*, perfil: PerfilGuardian, limite: int = 5) -> list[dict[str, Any]]:
    rows = listar_alertas_operativas(limite=limite, solo_abiertas=True)
    feed = []
    for row in rows:
        payload = parse_payload_json(row.payload_json)
        venta_id = row.venta_id or payload.get('venta_id')
        nav = _URL_CONTROL_CENTER
        if venta_id:
            nav = f'/editar_venta/{venta_id}'
        elif (row.codigo or '') in _CODIGOS_CAJA:
            nav = _URL_CONTROL_CENTER
        mensaje = cuerpo_alerta_para_ui(row.cuerpo, payload)
        feed.append({
            'id': row.id,
            'tipo': 'alerta',
            'agente': row.agente_nombre or 'operador',
            'severidad': (row.severidad or 'info').lower(),
            'codigo': row.codigo or '',
            'titulo': (row.titulo or 'Alerta operador')[:120],
            'mensaje': mensaje[:280] if mensaje else '',
            'enriquecido': bool(payload.get('enriquecido_semantico')),
            'hace': _fmt_hace(row.updated_at or row.created_at),
            'estado': row.estado,
            'nav_href': nav,
        })
    if perfil.alcance == 'sucursal' and perfil.sucursal_label:
        suc_u = perfil.sucursal_label.upper()
        feed = [
            f for f in feed
            if suc_u in (f.get('titulo') or '').upper() or 'CAJA' in (f.get('codigo') or '').upper()
        ] or feed[:limite]
    return feed[:limite]


def _status_global(*statuses: str) -> str:
    if 'red' in statuses:
        return 'red'
    if 'amber' in statuses:
        return 'amber'
    return 'green'


def _guardian_un_local() -> bool:
    """Un establecimiento vs red — ver Admin > Empresa o env OWNER_GUARDIAN_UN_LOCAL."""
    return es_operacion_un_local()


def _establecimiento_label() -> str:
    return (
        os.getenv('LHEXIA_CLIENTE_SD_NOMBRE')
        or os.getenv('OWNER_GUARDIAN_ESTABLECIMIENTO')
        or os.getenv('OWNER_GUARDIAN_SUCURSAL_LABEL')
        or 'Ferretería en operación'
    ).strip()


def _consolidado_financiero(
    *,
    calcular_ctx_caja: Callable,
    perfil: PerfilGuardian,
    kpis_ventas: dict[str, Any],
) -> dict[str, Any]:
    un_local = _guardian_un_local()
    establecimiento = _establecimiento_label()
    base = {
        'visible': False,
        'ventas_hoy_clp': kpis_ventas.get('ventas_hoy_clp', 0),
        'ventas_hoy_fmt': kpis_ventas.get('ventas_hoy_fmt', '$0'),
        'var_vs_ayer_pct': kpis_ventas.get('var_vs_ayer_pct'),
        'transacciones_hoy': kpis_ventas.get('transacciones_hoy', 0),
        'un_local': un_local,
        'establecimiento_label': establecimiento,
    }
    if perfil.alcance != 'global':
        return base

    bloque = obtener_tarjetas_sucursales(calcular_ctx=calcular_ctx_caja)
    total = int(bloque.get('alerta_global_clp') or 0)
    cajas_desc = int(bloque.get('cajas_con_descuadre', 0) or 0)
    sucursales_n = 1 if un_local else obtener_sucursales_red_n()
    if un_local:
        detalle = (
            f'{establecimiento} · {cajas_desc} cierre(s) con diferencia'
            if cajas_desc
            else f'{establecimiento} · arqueos al día'
        )
        kicker = 'Arqueo · establecimiento'
    else:
        detalle = f'{cajas_desc} cierre(s) · vista red ({sucursales_n} locales demo)'
        kicker = 'Desfalco · red VERTEX'

    return {
        **base,
        'visible': True,
        'descuadre_acumulado_clp': total,
        'descuadre_acumulado_fmt': bloque.get('alerta_global_fmt') or _fmt_clp(total),
        'cajas_con_descuadre': cajas_desc,
        'sucursales_monitoreadas': sucursales_n,
        'alertas_operador_red': bloque.get('alertas_operador_abiertas', 0),
        'desfalco_kicker': kicker,
        'desfalco_detalle': detalle,
    }


def _texto_copiloto_enriquecido(feed_preview: list[dict[str, Any]] | None) -> str:
    """Un solo bloque Ollama (evita repetir caja + feed + consolidado)."""
    for item in feed_preview or []:
        if item.get('enriquecido') and (item.get('mensaje') or '').strip():
            return (item['mensaje'] or '').strip()[:480]
    return ''


def _mensaje_ia(
    *,
    perfil: PerfilGuardian,
    tarjeta_caja: dict[str, Any],
    tarjeta_inventario: dict[str, Any],
    consolidado: dict[str, Any],
    feed_preview: list[dict[str, Any]] | None = None,
) -> str:
    partes = []
    if perfil.codigo == 'mock_dueno':
        partes.append('Modo demostración Guardián.')

    enrich = _texto_copiloto_enriquecido(feed_preview)
    if enrich:
        partes.append(enrich)
        return ' '.join(p.strip() for p in partes if p).strip()[:600]

    est_caja = tarjeta_caja.get('estado', 'verde')
    if est_caja == 'rojo':
        if consolidado.get('visible') and consolidado.get('descuadre_acumulado_fmt'):
            if consolidado.get('un_local'):
                est = (consolidado.get('establecimiento_label') or 'el local').strip()
                partes.append(
                    f"Prioridad: revisar arqueo en {est} — "
                    f"diferencia {consolidado['descuadre_acumulado_fmt']}."
                )
            else:
                partes.append(
                    f"Prioridad: revisar desfalco consolidado de "
                    f"{consolidado['descuadre_acumulado_fmt']} en la red."
                )
        msg_caja = (tarjeta_caja.get('mensaje') or 'Alerta crítica de caja.').strip()
        if msg_caja and msg_caja not in ' '.join(partes):
            partes.append(msg_caja)
    elif est_caja == 'amarillo':
        partes.append(tarjeta_caja.get('mensaje') or 'Caja requiere supervisión.')
    else:
        partes.append('Caja estable.')

    est_inv = tarjeta_inventario.get('estado', 'verde')
    if not guardian_suprimir_alertas_stock():
        if est_inv == 'rojo':
            partes.append(tarjeta_inventario.get('mensaje') or 'Inventario crítico.')
        elif est_inv == 'amarillo':
            partes.append('Inventario con SKUs bajo mínimo.')
    elif perfil.alcance == 'sucursal' and perfil.sucursal_label:
        partes.append(f"Vigilancia acotada a {perfil.sucursal_label}.")

    return ' '.join(p.strip() for p in partes if p).strip()[:600]


def _supervisor_telefono() -> str:
    return (
        os.getenv('OWNER_SUPERVISOR_TELEFONO')
        or os.getenv('OWNER_SUPERVISOR_TEL')
        or ''
    ).strip()


def construir_owner_dashboard(
    *,
    calcular_ctx_caja: Callable,
    usuario=None,
) -> dict[str, Any]:
    """Payload `data` para GET /api/v1/owner/dashboard (v3, compatible v2)."""
    perfil = detectar_perfil_guardian(usuario)
    telefono = _supervisor_telefono()
    kpis = _kpis_ventas_hoy()

    tarjeta_caja = _tarjeta_caja(calcular_ctx_caja=calcular_ctx_caja, perfil=perfil)
    tarjeta_inventario = _tarjeta_inventario(perfil=perfil)
    tarjeta_credito = _tarjeta_credito(perfil=perfil)
    tarjeta_compras = _tarjeta_compras(perfil=perfil)

    consolidado = _consolidado_financiero(
        calcular_ctx_caja=calcular_ctx_caja,
        perfil=perfil,
        kpis_ventas=kpis,
    )

    t_caja = _tarjeta_v3(tarjeta_caja, dominio='caja', prioridad=1, telefono=telefono)
    t_inv = _tarjeta_v3(tarjeta_inventario, dominio='inventario', prioridad=2, telefono=telefono)
    t_cred = _tarjeta_v3(tarjeta_credito, dominio='credito', prioridad=3, telefono=telefono)
    t_comp = _tarjeta_v3(tarjeta_compras, dominio='compras', prioridad=4, telefono=telefono)

    tarjetas = sorted(
        [t_caja, t_inv, t_cred, t_comp],
        key=lambda t: (t.get('prioridad') or 99, {'rojo': 0, 'amarillo': 1, 'verde': 2}.get(t.get('estado'), 3)),
    )

    st_caja = t_caja['status']
    st_inv = t_inv['status']
    st_cred = t_cred['status']
    st_comp = t_comp['status']
    st_global = _status_global(st_caja, st_inv, st_cred, st_comp)

    feed = _feed_preview(perfil=perfil, limite=5)

    mensaje_ia = _mensaje_ia(
        perfil=perfil,
        tarjeta_caja=tarjeta_caja,
        tarjeta_inventario=tarjeta_inventario,
        consolidado=consolidado,
        feed_preview=feed,
    )
    if t_cred['estado'] in ('rojo', 'amarillo'):
        cred_msg = (t_cred.get('mensaje') or '').strip()
        if cred_msg and cred_msg not in mensaje_ia:
            mensaje_ia = (mensaje_ia + ' ' + cred_msg).strip()[:600]

    return {
        'version': 'guardian_v3',
        'ecosystem': 'lhexia_vertex',
        'perfil': perfil.codigo,
        'alcance': perfil.alcance,
        'nombre_usuario': perfil.nombre_usuario,
        'saludo': perfil.saludo,
        'sucursal_label': perfil.sucursal_label,
        'status_caja': st_caja,
        'status_inventario': st_inv,
        'status_credito': st_cred,
        'status_compras': st_comp,
        'status_global': st_global,
        'mensaje_ia': mensaje_ia,
        'supervisor_telefono': telefono,
        'tarjeta_caja': tarjeta_caja,
        'tarjeta_inventario': tarjeta_inventario,
        'tarjeta_credito': tarjeta_credito,
        'tarjeta_compras': tarjeta_compras,
        'tarjetas': tarjetas,
        'consolidado': consolidado,
        'feed_preview': feed,
        'meta': {
            'alertas_abiertas': contar_alertas_abiertas(),
            'supervisor_telefono': telefono,
            'generado_en': datetime.now().isoformat(timespec='seconds'),
            'version': 'guardian_v3',
            'ecosystem': 'lhexia_vertex',
            'poll_recomendado_ms': 30000,
            'presentacion_ui': 'vertex_guardian_pro',
            'operador_enriquecimiento': 'ollama_pc_sucursal',
            'operador_scan_cron': '/api/agente/operador/dispatch-scan',
            'establecimiento_label': _establecimiento_label(),
            'un_local': _guardian_un_local(),
        },
    }
