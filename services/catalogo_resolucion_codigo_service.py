"""Resolución unificada producto por código escaneado (POS, enrolador, escáner móvil)."""
from __future__ import annotations

from typing import Any, Callable


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
    Código maestro EXACTO (barras/interno) → alias POS → variantes EAN → Chilemat.
    Misma cadena que el mostrador; usar en enrolador y API escáner móvil.

    El maestro exacto va primero para que un alias viejo no tape el producto real
    cuando se escanea su propio código de barras (caso 6931598203983 vs alias).
    """
    if not codigo:
        return None

    def _por_barra_o_interno(cnorm: str):
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

    # 1) Coincidencia EXACTA con código maestro (barras/interno) gana sobre cualquier alias.
    cnorm = (codigo or '').strip().upper()
    if cnorm:
        p_exacto = _por_barra_o_interno(cnorm)
        if p_exacto:
            return p_exacto

    # 2) Alias POS (código pistola mapeado manualmente a un maestro).
    from services.producto_codigo_escaneo_service import buscar_producto_por_alias

    p_alias = buscar_producto_por_alias(
        codigo,
        Producto=Producto,
        ProductoCodigoEscaneo=ProductoCodigoEscaneo,
        db=db,
        app=app,
    )
    if p_alias:
        return p_alias

    # 3) Variantes EAN (ceros, dígito de empaque) + interno + Chilemat.
    from services.pos_codigo_escaneo_service import buscar_producto_por_variantes_codigo

    producto, _variant = buscar_producto_por_variantes_codigo(
        codigo,
        buscar_fn=_por_barra_o_interno,
        buscar_chilemat_fn=buscar_chilemat_fn,
    )
    return producto
