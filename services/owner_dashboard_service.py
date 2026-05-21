"""Lhexia Guardián v2 — dashboard multiperfil (Dueño / Supervisor / mock dev)."""
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
    parse_payload_json,
)
from services.control_center_service import obtener_tarjetas_sucursales

_CODIGOS_CAJA = ('caja_descuadre', 'caja_dia_anterior')

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
    m = {'verde': 'green', 'rojo': 'red', 'amarillo': 'amber'}
    return m.get((estado or '').lower(), 'green')


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

    bajo = Producto.query.filter(Producto.stock < 5, Producto.activo.is_(True)).count()
    if bajo >= 15:
        estado, titulo = 'rojo', 'Inventario: crítico'
    elif bajo >= 5:
        estado, titulo = 'amarillo', 'Inventario: atención'
    else:
        estado, titulo = 'verde', 'Inventario: OK'

    sucursal = perfil.sucursal_label or _sucursal_label_default()
    if perfil.alcance == 'global':
        sucursal = (os.getenv('OWNER_PWA_SUCURSAL_LABEL') or 'todas las sucursales').strip()

    return {
        'estado': estado,
        'titulo': titulo,
        'mensaje': f'{bajo} SKU bajo mínimo (<5 u). Ámbito: {sucursal}.',
        'timestamp': 'Ahora',
        'accion_requerida': estado != 'verde',
        'tipo_accion': 'llamada_supervisor' if estado == 'rojo' else None,
        'skus_bajo_minimo': int(bajo),
    }


def _consolidado_financiero(*, calcular_ctx_caja: Callable, perfil: PerfilGuardian) -> dict[str, Any]:
    if perfil.alcance != 'global':
        return {'visible': False}

    bloque = obtener_tarjetas_sucursales(calcular_ctx=calcular_ctx_caja)
    total = int(bloque.get('alerta_global_clp') or 0)
    return {
        'visible': True,
        'descuadre_acumulado_clp': total,
        'descuadre_acumulado_fmt': bloque.get('alerta_global_fmt') or _fmt_clp(total),
        'cajas_con_descuadre': bloque.get('cajas_con_descuadre', 0),
        'sucursales_monitoreadas': int(os.getenv('OWNER_GUARDIAN_SUCURSALES_N', '3') or 3),
        'alertas_operador_red': bloque.get('alertas_operador_abiertas', 0),
    }


def _mensaje_ia(
    *,
    perfil: PerfilGuardian,
    tarjeta_caja: dict[str, Any],
    tarjeta_inventario: dict[str, Any],
    consolidado: dict[str, Any],
) -> str:
    partes = []
    if perfil.codigo == 'mock_dueno':
        partes.append('Modo demostración Guardián.')

    est_caja = tarjeta_caja.get('estado', 'verde')
    if est_caja == 'rojo':
        if consolidado.get('visible') and consolidado.get('descuadre_acumulado_fmt'):
            partes.append(
                f"Prioridad: revisar desfalco consolidado de "
                f"{consolidado['descuadre_acumulado_fmt']} en toda la red."
            )
        partes.append(tarjeta_caja.get('mensaje') or 'Alerta crítica de caja.')
    elif est_caja == 'amarillo':
        partes.append(tarjeta_caja.get('mensaje') or 'Caja requiere supervisión.')
    else:
        partes.append('Caja estable.')

    est_inv = tarjeta_inventario.get('estado', 'verde')
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
    """Payload `data` para GET /api/v1/owner/dashboard (v2 multiperfil)."""
    perfil = detectar_perfil_guardian(usuario)
    tarjeta_caja = _tarjeta_caja(calcular_ctx_caja=calcular_ctx_caja, perfil=perfil)
    tarjeta_inventario = _tarjeta_inventario(perfil=perfil)
    consolidado = _consolidado_financiero(calcular_ctx_caja=calcular_ctx_caja, perfil=perfil)
    telefono = _supervisor_telefono()

    return {
        'perfil': perfil.codigo,
        'alcance': perfil.alcance,
        'nombre_usuario': perfil.nombre_usuario,
        'saludo': perfil.saludo,
        'sucursal_label': perfil.sucursal_label,
        'status_caja': _estado_a_status(tarjeta_caja.get('estado')),
        'status_inventario': _estado_a_status(tarjeta_inventario.get('estado')),
        'mensaje_ia': _mensaje_ia(
            perfil=perfil,
            tarjeta_caja=tarjeta_caja,
            tarjeta_inventario=tarjeta_inventario,
            consolidado=consolidado,
        ),
        'supervisor_telefono': telefono,
        'tarjeta_caja': tarjeta_caja,
        'tarjeta_inventario': tarjeta_inventario,
        'consolidado': consolidado,
        'meta': {
            'alertas_abiertas': contar_alertas_abiertas(),
            'supervisor_telefono': telefono,
            'generado_en': datetime.now().isoformat(timespec='seconds'),
            'version': 'guardian_v2',
        },
    }
