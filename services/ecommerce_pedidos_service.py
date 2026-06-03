"""Bandeja pedidos web (PED-WEB / Maylén vitrina) — preparación, historial y métricas."""
from __future__ import annotations

import csv
import io
import os
import re
from datetime import datetime, timedelta
from typing import Any

from services.vitrina_tienda_service import (
    ASISTENTE_NOMBRE,
    codigo_pedido_web,
    es_usuario_pedido_web,
    filtro_sql_usuario_pedido_web,
)

ESTADOS_PREPARACION = ('PENDIENTE', 'EN_PREPARACION', 'LISTO_RETIRO', 'ENTREGA_PARCIAL', 'CERRADO')
ESTADOS_ACTIVOS = ('PENDIENTE', 'EN_PREPARACION', 'LISTO_RETIRO', 'ENTREGA_PARCIAL')


def es_pedido_web(venta) -> bool:
    return es_usuario_pedido_web(getattr(venta, 'usuario', None))


def _sla_minutos_config() -> tuple[int, int, int]:
    raw = (os.getenv('ECOM_PEDIDO_SLA_MINUTOS') or '10,20,30').strip()
    parts = [int(x.strip()) for x in raw.split(',') if x.strip().isdigit()]
    while len(parts) < 3:
        parts.append((10, 20, 30)[len(parts)])
    return parts[0], parts[1], parts[2]


def sla_pedido_web(minutos: int | None, estado_prep: str) -> tuple[int, str, str]:
    """tier 0-3, css class, label."""
    if minutos is None:
        return 0, 'sla-ok', 'En tiempo'
    u1, u2, u3 = _sla_minutos_config()
    est = (estado_prep or 'PENDIENTE').strip().upper()
    if est == 'LISTO_RETIRO':
        u1, u2, u3 = u1 + 5, u2 + 10, u3 + 15
    if minutos >= u3:
        return 3, 'sla-critical', 'Urgente'
    if minutos >= u2:
        return 2, 'sla-delayed', 'Demorado'
    if minutos >= u1:
        return 1, 'sla-attention', 'Atención'
    return 0, 'sla-ok', 'En tiempo'


def parse_contacto_pedido_web(usuario: str | None) -> dict[str, str]:
    u = (usuario or '').strip()
    out = {'nombre': '', 'telefono': '', 'texto': ''}
    if not es_usuario_pedido_web(u):
        return out
    if '(' in u and u.endswith(')'):
        inner = u[u.find('(') + 1 : -1].strip()
        out['texto'] = inner
        for part in inner.split(';'):
            p = part.strip()
            if p.lower().startswith('nombre:'):
                out['nombre'] = p.split(':', 1)[1].strip()[:80]
            elif p.lower().startswith('tel:'):
                out['telefono'] = p.split(':', 1)[1].strip()[:30]
    return out


def parse_contacto_liz_web(usuario: str | None) -> dict[str, str]:
    """Alias legado — usar parse_contacto_pedido_web."""
    return parse_contacto_pedido_web(usuario)


def _norm_tel_digits(telefono: str | None) -> str:
    return ''.join(ch for ch in (telefono or '') if ch.isdigit())


def resolver_cliente_pedido_web(nombre: str = '', telefono: str = ''):
    """Busca cliente por teléfono o crea registro web mínimo."""
    from app import Cliente, db

    cn = (nombre or '').strip()[:100]
    ct = (telefono or '').strip()[:30]
    digits = _norm_tel_digits(ct)
    if digits:
        q = Cliente.query.filter(Cliente.telefono.isnot(None))
        for c in q.limit(500):
            if digits[-8:] in _norm_tel_digits(c.telefono):
                if cn and not (c.nombre or '').strip():
                    c.nombre = cn
                    db.session.flush()
                return c
    if not cn and not ct:
        from app import obtener_o_crear_cliente_final

        return obtener_o_crear_cliente_final()
    seq = int(db.session.query(db.func.max(Cliente.id)).scalar() or 0) + 1
    rut_body = f'{9900000 + (seq % 999999):06d}'
    rut = f'99.{rut_body[:3]}.{rut_body[3:6]}-6'
    while Cliente.query.filter_by(rut=rut).first():
        seq += 1
        rut_body = f'{9900000 + (seq % 999999):06d}'
        rut = f'99.{rut_body[:3]}.{rut_body[3:6]}-6'
    cli = Cliente(
        rut=rut,
        nombre=cn or f'Cliente web {digits[-4:] if digits else seq}',
        telefono=ct or None,
        estado_credito='Activo',
    )
    db.session.add(cli)
    db.session.flush()
    return cli


def validar_stock_lineas_carrito(lineas: list[dict[str, Any]], *, bloquear: bool = True) -> dict[str, Any]:
    """Valida stock tienda antes de crear PED-WEB."""
    from app import Producto

    from services.stock_service import stock_disponible_venta_tienda

    faltas: list[str] = []
    for ln in lineas or []:
        try:
            pid = int(ln.get('producto_id') or 0)
            qty = int(ln.get('cantidad') or 1)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        prod = Producto.query.get(pid)
        if not prod:
            faltas.append(f'Producto #{pid} no existe')
            continue
        disp = int(stock_disponible_venta_tienda(prod) or 0)
        nom = (prod.nombre or f'#{pid}')[:50]
        if disp < qty:
            faltas.append(f'{nom}: piden {qty}, hay {disp} en tienda')
    ok = len(faltas) == 0
    if bloquear and not ok:
        return {
            'ok': False,
            'error': 'sin_stock',
            'mensaje': '; '.join(faltas[:3]),
            'faltas': faltas,
        }
    return {'ok': True, 'faltas': faltas, 'advertencias': faltas}


def requiere_caja_abierta_pedido_web() -> bool:
    v = (os.getenv('ECOM_PEDIDO_REQUIERE_CAJA') or '0').strip().lower()
    return v in ('1', 'true', 'si', 'yes', 'on')


def _asegurar_columnas_bodega() -> None:
    try:
        from app import (
            _asegurar_columnas_bodega_retiro,
            _asegurar_columnas_entrega_ticket,
            _asegurar_columnas_ventas_bodega_despacho,
        )

        _asegurar_columnas_ventas_bodega_despacho()
        _asegurar_columnas_bodega_retiro()
        _asegurar_columnas_entrega_ticket()
    except Exception:
        pass


def _metodos_pago_web_online() -> tuple[str, ...]:
    return ('Webpay', 'Debito', 'TarjetaCredito')


def _filtro_pedidos_web_bandeja():
    """Cola activa: cobro pendiente en caja o ya pagado online (Webpay)."""
    from app import Venta, db

    cobro_caja = db.and_(
        Venta.estado == 'Pendiente',
        Venta.metodo_pago.is_(None),
    )
    pagado_web = db.and_(
        Venta.estado == 'Pagado',
        Venta.metodo_pago.in_(_metodos_pago_web_online()),
    )
    return db.or_(cobro_caja, pagado_web)


def _query_pedidos_web_base():
    from app import Venta

    _asegurar_columnas_bodega()
    return Venta.query.filter(
        _filtro_pedidos_web_bandeja(),
        filtro_sql_usuario_pedido_web(),
    )


def _query_pedidos_web_historial(dias: int = 7):
    from app import Venta, db

    _asegurar_columnas_bodega()
    desde = datetime.now() - timedelta(days=max(1, min(int(dias or 7), 90)))
    return Venta.query.filter(
        filtro_sql_usuario_pedido_web(),
        Venta.fecha >= desde,
        db.or_(
            Venta.estado.in_(('Pagado', 'Anulada')),
            Venta.bodega_preparacion_estado == 'CERRADO',
        ),
    )


def contadores_bandeja() -> dict[str, int]:
    from app import Venta, db

    rows = (
        db.session.query(Venta.bodega_preparacion_estado, db.func.count(Venta.id))
        .filter(
            _filtro_pedidos_web_bandeja(),
            filtro_sql_usuario_pedido_web(),
        )
        .group_by(Venta.bodega_preparacion_estado)
        .all()
    )
    out = {'total': 0, 'pendiente': 0, 'en_preparacion': 0, 'listo': 0, 'otros': 0}
    for est, cnt in rows:
        n = int(cnt or 0)
        out['total'] += n
        e = (est or 'PENDIENTE').strip().upper()
        if e == 'PENDIENTE' or not e:
            out['pendiente'] += n
        elif e == 'EN_PREPARACION':
            out['en_preparacion'] += n
        elif e in ('LISTO_RETIRO', 'CERRADO'):
            out['listo'] += n
        else:
            out['otros'] += n
    return out


def metricas_ecommerce(dias: int = 7) -> dict[str, Any]:
    from app import Venta, db

    _asegurar_columnas_bodega()
    dias = max(1, min(int(dias or 7), 90))
    desde = datetime.now() - timedelta(days=dias)
    hoy_ini = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    base = Venta.query.filter(filtro_sql_usuario_pedido_web(), Venta.fecha >= desde)
    creados = base.count()
    cobrados = base.filter(Venta.estado == 'Pagado').count()
    anulados = base.filter(Venta.estado == 'Anulada').count()
    hoy = Venta.query.filter(filtro_sql_usuario_pedido_web(), Venta.fecha >= hoy_ini).count()

    prep_rows = (
        db.session.query(Venta.fecha, Venta.bodega_preparacion_at)
        .filter(
            filtro_sql_usuario_pedido_web(),
            Venta.fecha >= desde,
            Venta.bodega_preparacion_at.isnot(None),
        )
        .limit(500)
        .all()
    )
    mins_list = []
    for f, at in prep_rows:
        if f and at:
            try:
                mins_list.append(max(0, int((at - f).total_seconds() // 60)))
            except Exception:
                pass
    tmedio = int(sum(mins_list) / len(mins_list)) if mins_list else None
    tasa = round(100.0 * cobrados / creados, 1) if creados else 0.0

    return {
        'dias': dias,
        'pedidos_creados': creados,
        'pedidos_cobrados': cobrados,
        'pedidos_anulados': anulados,
        'pedidos_hoy': hoy,
        'tasa_cobro_pct': tasa,
        'tiempo_medio_prep_min': tmedio,
    }


def listar_pedidos_web(
    *,
    estado: str | None = None,
    limite: int = 200,
    filtro_extra: str | None = None,
) -> list[Any]:
    from sqlalchemy.orm import joinedload

    from app import DetalleVenta, Producto, Venta

    q = _query_pedidos_web_base().options(
        joinedload(Venta.cliente),
        joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
    )
    est = (estado or '').strip().upper()
    if est == 'NUEVOS':
        q = q.filter(
            (Venta.bodega_preparacion_estado.is_(None))
            | (Venta.bodega_preparacion_estado == 'PENDIENTE')
        )
    elif est in ESTADOS_PREPARACION:
        q = q.filter(Venta.bodega_preparacion_estado == est)
    elif est == 'ACTIVOS':
        q = q.filter(
            (Venta.bodega_preparacion_estado.is_(None))
            | (Venta.bodega_preparacion_estado.in_(list(ESTADOS_ACTIVOS)))
        )
    else:
        q = q.filter(
            (Venta.bodega_preparacion_estado.is_(None))
            | (Venta.bodega_preparacion_estado != 'CERRADO')
        )

    extra = (filtro_extra or '').strip().lower()
    rows = q.order_by(Venta.fecha.asc()).limit(max(1, min(int(limite or 200), 400))).all()
    if extra == 'sin_caja':
        rows = [v for v in rows if not getattr(v, 'caja_id', None)]
    elif extra == 'urgente':
        rows = [v for v in rows if enriquecer_pedido_fila(v).get('sla_tier', 0) >= 2]
    elif extra == 'sin_stock':
        ok_rows = []
        for v in rows:
            if _venta_tiene_alerta_stock(v):
                ok_rows.append(v)
        rows = ok_rows
    return rows


def listar_pedidos_historial(*, dias: int = 7, limite: int = 150) -> list[Any]:
    from sqlalchemy.orm import joinedload

    from app import DetalleVenta, Venta

    q = _query_pedidos_web_historial(dias).options(
        joinedload(Venta.cliente),
        joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
    )
    return q.order_by(Venta.fecha.desc()).limit(max(1, min(int(limite or 150), 400))).all()


def _venta_tiene_alerta_stock(venta) -> bool:
    from services.stock_service import stock_disponible_venta_tienda

    for d in venta.detalles or []:
        p = d.producto
        if not p:
            continue
        pend = int(d.cantidad or 0)
        if pend > int(stock_disponible_venta_tienda(p) or 0):
            return True
    return False


def _lineas_detalle_stock(venta) -> list[dict[str, Any]]:
    from app import Producto

    from services.stock_service import stock_disponible_venta_tienda

    out = []
    for d in venta.detalles or []:
        p = d.producto
        if not p and getattr(d, 'id_producto', None):
            p = Producto.query.get(int(d.id_producto))
        qty = int(d.cantidad or 0)
        disp = int(stock_disponible_venta_tienda(p) or 0) if p else 0
        out.append(
            {
                'detalle_id': d.id,
                'nombre': (p.nombre if p else 'Producto')[:100],
                'cantidad': qty,
                'subtotal': int(d.subtotal or 0),
                'precio_unitario': int(d.precio_unitario or 0),
                'stock_tienda': disp,
                'falta_stock': qty > disp,
            }
        )
    return out


def enriquecer_pedido_fila(venta) -> dict[str, Any]:
    est = (getattr(venta, 'bodega_preparacion_estado', None) or 'PENDIENTE').strip().upper()
    if not est:
        est = 'PENDIENTE'
    mins = None
    if getattr(venta, 'fecha', None):
        try:
            mins = int((datetime.now() - venta.fecha).total_seconds() // 60)
        except Exception:
            mins = None
    tier, sla_css, sla_label = sla_pedido_web(mins, est)
    contacto_d = parse_contacto_liz_web(getattr(venta, 'usuario', None))
    contacto = contacto_d.get('texto') or contacto_d.get('nombre') or ''
    lineas = []
    for ln in _lineas_detalle_stock(venta):
        lineas.append({'nombre': ln['nombre'][:80], 'cantidad': ln['cantidad'], 'subtotal': ln['subtotal']})
    return {
        'venta': venta,
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
        'vale_folio': f'VL{int(venta.id):06d}',
        'estado_prep': est,
        'estado_venta': (getattr(venta, 'estado', None) or '').strip(),
        'minutos': mins,
        'sla_tier': tier,
        'sla_css': sla_css,
        'sla_label': sla_label,
        'lineas_resumen': lineas,
        'contacto': contacto,
        'contacto_nombre': contacto_d.get('nombre') or '',
        'contacto_telefono': contacto_d.get('telefono') or '',
        'unidades': sum(int(d.cantidad or 0) for d in (venta.detalles or [])),
        'sin_caja': not getattr(venta, 'caja_id', None),
        'alerta_stock': _venta_tiene_alerta_stock(venta),
    }


def timeline_pedido(venta) -> list[dict[str, Any]]:
    """Eventos ordenados para UI timeline."""
    events: list[dict[str, Any]] = []
    if getattr(venta, 'fecha', None):
        events.append(
            {
                'ts': venta.fecha,
                'titulo': f'Pedido creado en vitrina ({ASISTENTE_NOMBRE})',
                'detalle': codigo_pedido_web(int(venta.id)),
                'icono': 'fa-shopping-cart',
            }
        )
    prep_at = getattr(venta, 'bodega_preparacion_at', None)
    prep_est = (getattr(venta, 'bodega_preparacion_estado', None) or '').strip().upper()
    prep_user = getattr(venta, 'bodega_preparacion_usuario', None)
    if prep_at and prep_est == 'EN_PREPARACION':
        events.append(
            {
                'ts': prep_at,
                'titulo': 'En preparación',
                'detalle': prep_user or 'Operador',
                'icono': 'fa-box-open',
            }
        )
    if prep_at and prep_est == 'LISTO_RETIRO':
        events.append(
            {
                'ts': prep_at,
                'titulo': 'Listo para retiro en tienda',
                'detalle': prep_user or 'Operador',
                'icono': 'fa-check-circle',
            }
        )
    cobrado_at = getattr(venta, 'bodega_preparacion_cobrado_at', None)
    st = (getattr(venta, 'estado', None) or '').strip()
    if st == 'Pagado':
        ts = cobrado_at or prep_at or getattr(venta, 'fecha', None)
        events.append(
            {
                'ts': ts,
                'titulo': 'Cobrado en caja',
                'detalle': f'Folio {venta.metodo_pago or "pago registrado"}',
                'icono': 'fa-cash-register',
            }
        )
    entrega_st = (getattr(venta, 'entrega_ticket_estado', None) or '').strip().upper()
    entrega_at = getattr(venta, 'entrega_ticket_cerrado_at', None)
    if entrega_st in ('PARCIAL', 'CERRADO'):
        events.append(
            {
                'ts': entrega_at or prep_at,
                'titulo': f'Entrega ticket: {entrega_st}',
                'detalle': 'QR / registro entrega',
                'icono': 'fa-qrcode',
            }
        )
    if st == 'Anulada':
        events.append(
            {
                'ts': getattr(venta, 'fecha_anulacion', None) or getattr(venta, 'fecha', None),
                'titulo': 'Pedido anulado',
                'detalle': (getattr(venta, 'motivo_anulacion', None) or '')[:120],
                'icono': 'fa-ban',
            }
        )
    cerrado_at = getattr(venta, 'bodega_preparacion_cerrado_at', None)
    if prep_est == 'CERRADO' and cerrado_at:
        events.append(
            {
                'ts': cerrado_at,
                'titulo': 'Preparación cerrada',
                'detalle': '',
                'icono': 'fa-flag-checkered',
            }
        )
    events.sort(key=lambda e: e['ts'] or datetime.min)
    return events


def mensaje_whatsapp_listo_pedido(venta, *, empresa: str = 'Ferretería Santo Domingo') -> str:
    contacto = parse_contacto_liz_web(getattr(venta, 'usuario', None))
    nom = contacto.get('nombre') or 'cliente'
    cod = codigo_pedido_web(int(venta.id))
    folio = f'VL{int(venta.id):06d}'
    return (
        f'Hola {nom}, su pedido {cod} ({folio}) está *listo para retiro* en {empresa}. '
        f'Acérquese a caja con este código para pagar y retirar. Gracias.'
    )


def url_whatsapp_pedido(telefono: str | None, mensaje: str) -> str | None:
    from services.pos_pedidos_a_pedido_service import url_whatsapp_aviso

    return url_whatsapp_aviso(telefono, mensaje)


def enriquecer_pedido_detalle(venta) -> dict[str, Any]:
    fila = enriquecer_pedido_fila(venta)
    fila['lineas'] = _lineas_detalle_stock(venta)
    fila['timeline'] = timeline_pedido(venta)
    fila['whatsapp_url'] = url_whatsapp_pedido(
        fila.get('contacto_telefono'),
        mensaje_whatsapp_listo_pedido(venta),
    )
    fila['entrega_estado'] = (getattr(venta, 'entrega_ticket_estado', None) or '').strip()
    fila['puede_anular'] = (
        (getattr(venta, 'estado', None) or '').strip() == 'Pendiente'
        and getattr(venta, 'metodo_pago', None) is None
    )
    return fila


def obtener_pedido_web(venta_id: int):
    from sqlalchemy.orm import joinedload

    from app import DetalleVenta, Venta

    v = (
        Venta.query.options(
            joinedload(Venta.cliente),
            joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
        )
        .filter(Venta.id == int(venta_id))
        .first()
    )
    if not v or not es_pedido_web(v):
        return None
    return v


def actualizar_estado_preparacion(
    venta_id: int,
    accion: str,
    *,
    operador: str,
    notificar_whatsapp: bool = False,
) -> dict[str, Any]:
    from app import Venta, db

    venta = obtener_pedido_web(venta_id)
    if not venta:
        return {'ok': False, 'error': 'no_encontrado'}

    acc = (accion or '').strip().lower()
    ahora = datetime.now()
    op = (operador or 'operador')[:80]

    if acc in ('tomar', 'preparar', 'en_preparacion'):
        venta.bodega_preparacion_estado = 'EN_PREPARACION'
        venta.bodega_preparacion_usuario = op
        venta.bodega_preparacion_at = ahora
    elif acc in ('listo', 'listo_retiro', 'listo_meson'):
        venta.bodega_preparacion_estado = 'LISTO_RETIRO'
        venta.bodega_preparacion_usuario = op
        venta.bodega_preparacion_at = ahora
    elif acc in ('pendiente', 'revertir'):
        venta.bodega_preparacion_estado = 'PENDIENTE'
        venta.bodega_preparacion_usuario = op
        venta.bodega_preparacion_at = ahora
    elif acc in ('entregado', 'cerrar', 'cerrado'):
        venta.bodega_preparacion_estado = 'CERRADO'
        venta.bodega_preparacion_cerrado_at = ahora
        venta.bodega_preparacion_usuario = op
    else:
        return {'ok': False, 'error': 'accion_invalida'}

    wa_url = None
    if acc in ('listo', 'listo_retiro', 'listo_meson') or notificar_whatsapp:
        det = enriquecer_pedido_detalle(venta)
        wa_url = det.get('whatsapp_url')

    db.session.commit()
    return {
        'ok': True,
        'venta_id': int(venta.id),
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
        'estado': venta.bodega_preparacion_estado,
        'whatsapp_url': wa_url,
    }


def anular_pedido_web(venta_id: int, *, motivo: str, operador: str) -> dict[str, Any]:
    from app import Venta, db

    venta = obtener_pedido_web(venta_id)
    if not venta:
        return {'ok': False, 'error': 'no_encontrado', 'mensaje': 'Pedido no encontrado.'}
    if (venta.estado or '').strip() != 'Pendiente':
        return {'ok': False, 'error': 'estado', 'mensaje': 'Solo se anulan pedidos pendientes de cobro.'}
    if venta.metodo_pago is not None:
        return {'ok': False, 'error': 'estado', 'mensaje': 'El pedido ya tiene pago registrado.'}

    op = (operador or 'ecommerce')[:80]
    mot = (motivo or 'Anulado desde bandeja e-commerce')[:500]
    venta.estado = 'Anulada'
    venta.motivo_anulacion = mot
    venta.fecha_anulacion = datetime.now()
    venta.usuario_anulacion = op
    venta.bodega_preparacion_estado = 'CERRADO'
    venta.bodega_preparacion_cerrado_at = datetime.now()
    db.session.commit()
    return {
        'ok': True,
        'venta_id': int(venta.id),
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
        'mensaje': 'Pedido web anulado.',
    }


def serializar_pedido_api(fila: dict[str, Any]) -> dict[str, Any]:
    v = fila.get('venta')
    return {
        'id': int(v.id) if v else None,
        'ped_web_codigo': fila.get('ped_web_codigo'),
        'vale_folio': fila.get('vale_folio'),
        'estado_prep': fila.get('estado_prep'),
        'estado_venta': fila.get('estado_venta'),
        'minutos': fila.get('minutos'),
        'sla_label': fila.get('sla_label'),
        'contacto': fila.get('contacto'),
        'telefono': fila.get('contacto_telefono'),
        'unidades': fila.get('unidades'),
        'total': int(getattr(v, 'monto_total', 0) or 0) if v else 0,
        'sin_caja': fila.get('sin_caja'),
        'alerta_stock': fila.get('alerta_stock'),
        'fecha': v.fecha.isoformat() if v and getattr(v, 'fecha', None) else None,
    }


def exportar_pedidos_csv(pedidos: list[Any], *, historial: bool = False) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';')
    w.writerow(
        [
            'ped_web_codigo',
            'vale_folio',
            'estado_venta',
            'estado_prep',
            'contacto',
            'telefono',
            'unidades',
            'total',
            'minutos',
            'fecha',
        ]
    )
    for v in pedidos:
        f = enriquecer_pedido_fila(v)
        w.writerow(
            [
                f['ped_web_codigo'],
                f['vale_folio'],
                f.get('estado_venta') or (v.estado if v else ''),
                f['estado_prep'],
                f.get('contacto_nombre') or f['contacto'],
                f.get('contacto_telefono') or '',
                f['unidades'],
                int(v.monto_total or 0) if v else 0,
                f.get('minutos') or '',
                v.fecha.strftime('%Y-%m-%d %H:%M') if v and v.fecha else '',
            ]
        )
    return buf.getvalue()


def cobrar_pedido_web_tarjeta(venta_id: int, *, metodo_pago: str = 'Webpay') -> dict[str, Any]:
    """Registra cobro ERP tras pago Webpay aprobado (requiere caja abierta)."""
    from datetime import datetime

    from sqlalchemy.orm import joinedload

    from app import Venta, db, obtener_caja_activa
    from core.application.bootstrap import build_descontar_stock_cobro_service, build_procesar_cobro_use_case
    from core.application.ventas.commands import ProcesarCobroCommand
    from services.venta_service import transaccion_critica

    venta = (
        Venta.query.options(joinedload(Venta.detalles), joinedload(Venta.cliente))
        .filter(Venta.id == int(venta_id))
        .first()
    )
    if not venta or not es_pedido_web(venta):
        return {'ok': False, 'error': 'no_encontrado', 'mensaje': 'Pedido web no encontrado.'}
    if (venta.estado or '').strip() == 'Pagado':
        return {'ok': True, 'ya_cobrado': True, 'venta_id': int(venta.id)}
    if (venta.estado or '').strip() != 'Pendiente' or venta.metodo_pago is not None:
        return {'ok': False, 'error': 'estado', 'mensaje': 'El pedido no está pendiente de cobro.'}

    caja = None
    try:
        caja = obtener_caja_activa()
    except Exception:
        caja = None
    if not caja:
        return {
            'ok': False,
            'error': 'sin_caja',
            'mensaje': 'Pago recibido pero no hay caja abierta. Cobrar manualmente en caja.',
        }

    chk = validar_stock_lineas_carrito(
        [
            {
                'producto_id': d.id_producto,
                'cantidad': d.cantidad,
            }
            for d in (venta.detalles or [])
        ],
        bloquear=True,
    )
    if not chk.get('ok'):
        return {
            'ok': False,
            'error': chk.get('error') or 'sin_stock',
            'mensaje': chk.get('mensaje') or 'Stock insuficiente al confirmar pago.',
        }

    stock_cobro_svc = build_descontar_stock_cobro_service()
    lineas_stock = stock_cobro_svc.preparar_lineas(int(venta.id))
    total = float(venta.monto_total or 0)
    metodo = (metodo_pago or 'Webpay').strip()[:40]

    try:
        with transaccion_critica():
            build_procesar_cobro_use_case(transaccion_critica=None).execute(
                ProcesarCobroCommand(
                    venta_id=int(venta.id),
                    caja_id=int(caja.id),
                    metodo_pago=metodo,
                    tipo_documento='Boleta',
                    monto_recibido=total,
                    saldo_favor_usado=0.0,
                    usuario_cobro='Maylen-Web',
                )
            )
            venta = Venta.query.options(joinedload(Venta.detalles)).filter_by(id=int(venta.id)).first()
            if venta:
                venta.fecha = datetime.now()
                if not (venta.bodega_preparacion_estado or '').strip():
                    venta.bodega_preparacion_estado = 'PENDIENTE'
            stock_cobro_svc.aplicar_descontos(int(venta.id), lineas_stock, metodo, 'Maylen-Web')
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return {'ok': False, 'error': 'cobro_fallido', 'mensaje': str(ex)[:200]}

    return {
        'ok': True,
        'venta_id': int(venta.id),
        'estado': venta.estado,
        'metodo_pago': venta.metodo_pago,
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
    }
