"""Carga manual de precios venta SD — piloto Santo Domingo (sin Radar)."""
from __future__ import annotations

from typing import Any

MOTIVO_PREFIJO = 'Piloto SD'


def stats_precios_piloto() -> dict[str, int]:
    from app import Producto, db
    from sqlalchemy import func

    q = Producto.query.filter(Producto.activo == True)  # noqa: E712
    total = q.count()
    sin_precio = q.filter(
        db.or_(Producto.precio_venta_sd.is_(None), Producto.precio_venta_sd <= 0)
    ).count()
    con_precio = (
        db.session.query(func.count(Producto.id))
        .filter(Producto.activo == True)  # noqa: E712
        .filter(Producto.precio_venta_sd > 0)
        .scalar()
        or 0
    )
    return {
        'total_activos': int(total),
        'sin_precio': int(sin_precio),
        'con_precio': int(con_precio),
    }


def serializar_producto_precios_piloto(producto) -> dict[str, Any]:
    from app import _stock_ui_producto, precio_efectivo_pos_producto

    st = _stock_ui_producto(producto)
    lista = float(producto.precio_venta or 0)
    pm = float(producto.precio_mayoreo or 0)
    sd = float(getattr(producto, 'precio_venta_sd', None) or 0)
    ef = float(precio_efectivo_pos_producto(producto) or 0)
    codigo = (
        (producto.codigo_barra or '').strip()
        or (producto.codigo_interno or '').strip()
        or (producto.codigo_chilemat or '').strip()
        or '—'
    )
    return {
        'id': producto.id,
        'nombre': producto.nombre or '',
        'codigo': codigo,
        'costo': float(producto.precio_compra or 0),
        'precio_lista': lista,
        'precio_mayoreo': pm,
        'precio_venta_sd': sd,
        'precio_efectivo': ef,
        'sin_precio': ef <= 0,
        'stock_tienda': int(st.get('tienda') or 0),
        'stock_bodega': int(st.get('bodega') or 0),
        'categoria': (producto.categoria or '').strip() or '—',
    }


def aplicar_precio_venta_sd(producto, precio_nuevo: float) -> float:
    """Graba precio venta SD sin tocar precio lista (precio_venta)."""
    precio_nuevo = float(precio_nuevo)
    if precio_nuevo <= 0:
        raise ValueError('precio_invalido')
    producto.precio_venta_sd = precio_nuevo
    return precio_nuevo


def guardar_precio_piloto(
    *,
    producto_id: int,
    precio_nuevo: float,
    motivo: str,
    usuario: str | None,
) -> dict[str, Any]:
    from app import (
        Producto,
        _bitacora_precios_disponible,
        db,
        precio_efectivo_pos_producto,
        registrar_bitacora_precio,
    )

    p = Producto.query.get(producto_id)
    if not p:
        return {'ok': False, 'error': 'producto_no_encontrado'}
    if not p.activo:
        return {'ok': False, 'error': 'producto_inactivo'}

    motivo_txt = (motivo or '').strip()
    if not motivo_txt:
        return {'ok': False, 'error': 'motivo_requerido'}
    if not motivo_txt.lower().startswith(MOTIVO_PREFIJO.lower()):
        motivo_txt = f'{MOTIVO_PREFIJO}: {motivo_txt}'

    precio_anterior = float(precio_efectivo_pos_producto(p) or 0)
    try:
        nuevo_ef = aplicar_precio_venta_sd(p, precio_nuevo)
    except ValueError:
        return {'ok': False, 'error': 'precio_invalido'}

    if abs(precio_anterior - nuevo_ef) < 0.01:
        return {
            'ok': True,
            'sin_cambio': True,
            'producto': serializar_producto_precios_piloto(p),
        }

    if _bitacora_precios_disponible():
        registrar_bitacora_precio(
            producto_id=p.id,
            precio_anterior=precio_anterior,
            precio_nuevo=nuevo_ef,
            costo_referencia=p.precio_compra or 0,
            margen_objetivo=None,
            usuario=usuario,
            motivo=motivo_txt,
        )
    db.session.commit()
    return {
        'ok': True,
        'sin_cambio': False,
        'precio_anterior': precio_anterior,
        'precio_nuevo': nuevo_ef,
        'producto': serializar_producto_precios_piloto(p),
    }


def bitacora_reciente_piloto(limite: int = 20) -> list:
    from app import BitacoraPrecioVenta, _bitacora_precios_disponible
    from sqlalchemy.orm import joinedload

    if not _bitacora_precios_disponible():
        return []
    limite = max(1, min(int(limite or 20), 100))
    return (
        BitacoraPrecioVenta.query.options(joinedload(BitacoraPrecioVenta.producto))
        .filter(BitacoraPrecioVenta.motivo.ilike(f'{MOTIVO_PREFIJO}%'))
        .order_by(BitacoraPrecioVenta.id.desc())
        .limit(limite)
        .all()
    )
