"""Bandeja pedidos web (PED-WEB / Liz vitrina) — preparación antes de cobro en caja."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services.vitrina_tienda_service import codigo_pedido_web

ESTADOS_PREPARACION = ('PENDIENTE', 'EN_PREPARACION', 'LISTO_RETIRO', 'ENTREGA_PARCIAL', 'CERRADO')
ESTADOS_ACTIVOS = ('PENDIENTE', 'EN_PREPARACION', 'LISTO_RETIRO', 'ENTREGA_PARCIAL')


def es_pedido_web(venta) -> bool:
    u = (getattr(venta, 'usuario', None) or '').strip()
    return u.startswith('Liz-Web')


def _asegurar_columnas_bodega() -> None:
    try:
        from app import _asegurar_columnas_ventas_bodega_despacho

        _asegurar_columnas_ventas_bodega_despacho()
    except Exception:
        pass


def _query_pedidos_web_base():
    from app import Venta

    _asegurar_columnas_bodega()
    return Venta.query.filter(
        Venta.estado == 'Pendiente',
        Venta.metodo_pago.is_(None),
        Venta.usuario.ilike('Liz-Web%'),
    )


def contadores_bandeja() -> dict[str, int]:
    from app import Venta, db

    q = _query_pedidos_web_base()
    rows = (
        db.session.query(Venta.bodega_preparacion_estado, db.func.count(Venta.id))
        .filter(
            Venta.estado == 'Pendiente',
            Venta.metodo_pago.is_(None),
            Venta.usuario.ilike('Liz-Web%'),
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


def listar_pedidos_web(
    *,
    estado: str | None = None,
    limite: int = 200,
) -> list[Any]:
    from sqlalchemy.orm import joinedload

    from app import DetalleVenta, Venta

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
    return q.order_by(Venta.fecha.asc()).limit(max(1, min(int(limite or 200), 400))).all()


def enriquecer_pedido_fila(venta) -> dict[str, Any]:
    """Campos UI para una fila de bandeja."""
    from app import Producto

    est = (getattr(venta, 'bodega_preparacion_estado', None) or 'PENDIENTE').strip().upper()
    if not est:
        est = 'PENDIENTE'
    mins = None
    if getattr(venta, 'fecha', None):
        try:
            mins = int((datetime.now() - venta.fecha).total_seconds() // 60)
        except Exception:
            mins = None
    lineas = []
    for d in venta.detalles or []:
        p = d.producto if getattr(d, 'producto', None) else None
        if not p and getattr(d, 'id_producto', None):
            p = Producto.query.get(int(d.id_producto))
        lineas.append(
            {
                'nombre': (p.nombre if p else 'Producto')[:80],
                'cantidad': int(d.cantidad or 0),
                'subtotal': int(d.subtotal or 0),
            }
        )
    contacto = ''
    u = (venta.usuario or '')
    if '(' in u and u.endswith(')'):
        contacto = u[u.find('(') + 1 : -1].strip()
    return {
        'venta': venta,
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
        'vale_folio': f'VL{int(venta.id):06d}',
        'estado_prep': est,
        'minutos': mins,
        'lineas_resumen': lineas,
        'contacto': contacto,
        'unidades': sum(int(d.cantidad or 0) for d in (venta.detalles or [])),
    }


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

    db.session.commit()
    return {
        'ok': True,
        'venta_id': int(venta.id),
        'ped_web_codigo': codigo_pedido_web(int(venta.id)),
        'estado': venta.bodega_preparacion_estado,
    }
