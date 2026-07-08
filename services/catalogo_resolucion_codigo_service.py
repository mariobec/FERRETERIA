"""Resolución unificada producto por código escaneado (POS, enrolador, escáner móvil)."""
from __future__ import annotations

from typing import Any, Callable


def _por_barra_o_interno(cnorm: str, *, Producto, db):
    p = (
        Producto.query.filter(db.func.upper(db.func.trim(Producto.codigo_barra)) == cnorm)
        .first()
    )
    if p:
        return p
    return (
        Producto.query.filter(
            Producto.codigo_interno.isnot(None),
            db.func.upper(db.func.trim(Producto.codigo_interno)) == cnorm,
        )
        .first()
    )


def resolver_codigo_escaneado(
    codigo: str | None,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
    buscar_chilemat_fn: Callable[[str], Any | None],
) -> dict[str, Any]:
    """
    Resuelve código pistola → producto maestro.

    Orden: exacto barras/interno → alias POS → variantes EAN (sin colapsar SKUs distintos).

    Retorna dict con claves:
      producto, ambiguo, candidatos, variante, codigo
    """
    vacio = {
        'producto': None,
        'ambiguo': False,
        'candidatos': [],
        'variante': None,
        'codigo': '',
    }
    cnorm = (codigo or '').strip().upper()
    if not cnorm:
        return vacio

    buscar_fn = lambda c: _por_barra_o_interno(c, Producto=Producto, db=db)

    # 1) Coincidencia EXACTA con código maestro (barras/interno).
    p_exacto = buscar_fn(cnorm)
    if p_exacto:
        return {
            'producto': p_exacto,
            'ambiguo': False,
            'candidatos': [],
            'variante': cnorm,
            'codigo': cnorm,
        }

    # 2) Alias POS.
    from services.producto_codigo_escaneo_service import buscar_producto_por_alias

    p_alias = buscar_producto_por_alias(
        codigo,
        Producto=Producto,
        ProductoCodigoEscaneo=ProductoCodigoEscaneo,
        db=db,
        app=app,
    )
    if p_alias:
        return {
            'producto': p_alias,
            'ambiguo': False,
            'candidatos': [],
            'variante': cnorm,
            'codigo': cnorm,
        }

    # 3) Variantes EAN — si homologan a 2+ productos distintos → ambiguo (no auto-elegir).
    from services.pos_codigo_escaneo_service import buscar_producto_por_variantes_codigo

    producto, variant, candidatos = buscar_producto_por_variantes_codigo(
        codigo,
        buscar_fn=buscar_fn,
        buscar_chilemat_fn=buscar_chilemat_fn,
    )
    if candidatos:
        return {
            'producto': None,
            'ambiguo': True,
            'candidatos': candidatos,
            'variante': None,
            'codigo': cnorm,
        }
    return {
        'producto': producto,
        'ambiguo': False,
        'candidatos': [],
        'variante': variant,
        'codigo': cnorm,
    }


def buscar_producto_por_codigo_escaneado(
    codigo: str | None,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
    buscar_chilemat_fn: Callable[[str], Any | None],
) -> Any | None:
    """
    Atajo: retorna producto o None (incluye None si el código es ambiguo entre 2+ maestros).
    """
    return resolver_codigo_escaneado(
        codigo,
        Producto=Producto,
        ProductoCodigoEscaneo=ProductoCodigoEscaneo,
        db=db,
        app=app,
        buscar_chilemat_fn=buscar_chilemat_fn,
    ).get('producto')
