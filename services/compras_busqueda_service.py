"""Filtros de búsqueda por producto en módulo Compras (OC y recepciones)."""
from __future__ import annotations

from sqlalchemy import exists, or_


def _like_patron(texto: str) -> str:
    return f'%{(texto or "").strip()}%'


def filtro_oc_por_texto(consulta, texto: str):
    """
    OC por número, proveedor o producto (nombre, código barra, código interno).
    """
    q = (texto or '').strip()
    if not q:
        return consulta
    from app import DetalleOrdenCompra, OrdenCompra, Producto, Proveedor

    like = _like_patron(q)
    prod_en_oc = exists().where(
        DetalleOrdenCompra.orden_compra_id == OrdenCompra.id,
        DetalleOrdenCompra.producto_id == Producto.id,
        or_(
            Producto.nombre.ilike(like),
            Producto.codigo_barra.ilike(like),
            Producto.codigo_interno.ilike(like),
        ),
    )
    return (
        consulta.outerjoin(Proveedor, Proveedor.id == OrdenCompra.proveedor_id)
        .filter(
            or_(
                OrdenCompra.numero.ilike(like),
                Proveedor.nombre.ilike(like),
                prod_en_oc,
            )
        )
        .distinct()
    )


def filtro_recepcion_por_producto(consulta, texto: str):
    """Recepciones que tengan al menos una línea con ese producto."""
    q = (texto or '').strip()
    if not q:
        return consulta
    from app import DetalleRecepcion, Producto, RecepcionCompra

    like = _like_patron(q)
    prod_en_rcv = exists().where(
        DetalleRecepcion.recepcion_id == RecepcionCompra.id,
        DetalleRecepcion.producto_id == Producto.id,
        or_(
            Producto.nombre.ilike(like),
            Producto.codigo_barra.ilike(like),
            Producto.codigo_interno.ilike(like),
        ),
    )
    return consulta.filter(prod_en_rcv).distinct()
