"""Consultas de stock operativo (tienda) para métricas e inventario — fuente única con POS/vitrina."""
from __future__ import annotations

from typing import Any


def stock_tienda_producto(producto) -> int:
    """Stock en almacén tienda; fallback a maestro si no hay multi-almacén."""
    from services.stock_service import stock_disponible_venta_tienda

    return int(stock_disponible_venta_tienda(producto) or 0)


def stock_tienda_por_ids(producto_ids: list[int]) -> dict[int, int]:
    from services.stock_service import stock_tienda_por_producto_ids

    return stock_tienda_por_producto_ids(producto_ids)


def contadores_stock_tienda_activos(*, umbral_critico: int = 5) -> dict[str, int]:
    """
    Conteos sobre productos activos usando stock TIENDA (no productos.stock maestro).
    """
    import app as m
    from sqlalchemy import and_, case, func

    Producto = m.Producto
    umbral = max(1, min(int(umbral_critico or 5), 50))
    aid = m.id_almacen_tienda()

    if not aid or not m._tablas_inventario_almacen_existen():
        total = int(
            m.db.session.query(func.count(Producto.id))
            .filter(Producto.activo.is_(True))
            .scalar()
            or 0
        )
        return {
            'total_activos': total,
            'con_stock': 0,
            'sin_stock': total,
            'critico': 0,
        }

    st = func.coalesce(m.StockPorAlmacen.cantidad, 0)
    row = (
        m.db.session.query(
            func.count(Producto.id),
            func.sum(case((st <= 0, 1), else_=0)),
            func.sum(case((st > 0, 1), else_=0)),
            func.sum(case((and_(st > 0, st <= umbral), 1), else_=0)),
        )
        .select_from(Producto)
        .outerjoin(
            m.StockPorAlmacen,
            (m.StockPorAlmacen.id_producto == Producto.id)
            & (m.StockPorAlmacen.id_almacen == int(aid)),
        )
        .filter(Producto.activo.is_(True))
        .one()
    )
    total = int(row[0] or 0)
    sin_stock = int(row[1] or 0)
    con_stock = int(row[2] or 0)
    critico = int(row[3] or 0)
    return {
        'total_activos': total,
        'con_stock': con_stock,
        'sin_stock': sin_stock,
        'critico': critico,
    }


def enriquecer_productos_stock_tienda(productos) -> None:
    """Adjunta stock_tienda_operativo a instancias Producto (in-place)."""
    items = list(productos or [])
    if not items:
        return
    pids = [int(p.id) for p in items if getattr(p, 'id', None)]
    stocks = stock_tienda_por_ids(pids)
    for p in items:
        p.stock_tienda_operativo = int(stocks.get(int(p.id), 0) or 0)
