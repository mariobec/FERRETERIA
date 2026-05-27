"""Consultas y alta de producto_relacion (cross-sell POS)."""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def upsert_relacion(
    producto_id: int,
    relacionado_id: int,
    *,
    tipo: str = 'complemento',
    fuente: str = 'manual',
    peso: float = 1.0,
    commit: bool = True,
) -> bool:
    from app import ProductoRelacion, db

    if not producto_id or not relacionado_id or int(producto_id) == int(relacionado_id):
        return False
    _asegurar()
    pid = int(producto_id)
    rid = int(relacionado_id)
    tipo = (tipo or 'complemento')[:32]
    fuente = (fuente or 'manual')[:32]
    try:
        peso_f = float(peso)
    except (TypeError, ValueError):
        peso_f = 1.0

    row = ProductoRelacion.query.filter_by(
        producto_id=pid,
        relacionado_id=rid,
        tipo=tipo,
        fuente=fuente,
    ).first()
    changed = False
    if row is None:
        row = ProductoRelacion(
            producto_id=pid,
            relacionado_id=rid,
            tipo=tipo,
            fuente=fuente,
            peso=peso_f,
            activo=True,
        )
        db.session.add(row)
        changed = True
    else:
        if abs(float(row.peso or 0) - peso_f) > 0.001:
            row.peso = peso_f
            changed = True
        if not row.activo:
            row.activo = True
            changed = True
    if commit:
        db.session.commit()
    return True


def sugerencias_para_carrito(
    cart_product_ids: list[int],
    *,
    limite: int = 8,
    excluir_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Productos relacionados activos con stock, ordenados por peso."""
    from app import Producto, ProductoRelacion, db

    if not cart_product_ids:
        return []
    _asegurar()
    pids = [int(x) for x in cart_product_ids if x is not None]
    if not pids:
        return []

    excl = set(pids)
    if excluir_ids:
        excl |= {int(x) for x in excluir_ids if x is not None}

    rows = (
        ProductoRelacion.query.filter(
            ProductoRelacion.activo.is_(True),
            ProductoRelacion.producto_id.in_(pids),
            ~ProductoRelacion.relacionado_id.in_(list(excl)),
        )
        .order_by(ProductoRelacion.peso.desc())
        .limit(max(limite * 4, 24))
        .all()
    )

    items: list[dict[str, Any]] = []
    seen_rel: set[int] = set()
    for rel in rows:
        rid = int(rel.relacionado_id)
        if rid in seen_rel or rid in excl:
            continue
        p = Producto.query.filter(
            Producto.id == rid,
            Producto.activo.isnot(False),
            Producto.stock > 0,
        ).first()
        if not p:
            continue
        seen_rel.add(rid)
        items.append(
            {
                'id': p.id,
                'nombre': p.nombre,
                'precio': int(round(float(p.precio_venta or 0))),
                'codigo': p.codigo_barra or p.codigo_interno or '',
                'fuente': rel.fuente,
                'tipo': rel.tipo,
                'peso': float(rel.peso or 0),
            }
        )
        if len(items) >= limite:
            break
    return items


def _asegurar() -> None:
    import app as erp

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()
