"""Métricas reales para /inventario/dashboard-premium (catálogo + stock + salud)."""
from __future__ import annotations

import re
from typing import Any

_PALETTE = ('#38bdf8', '#f43f5e', '#f59e0b', '#22c55e', '#818cf8', '#a78bfa', '#fb7185', '#2dd4bf')


def _slug_categoria(nombre: str | None) -> str:
    s = (nombre or 'sin-categoria').strip().lower()
    s = re.sub(r'[^\w\s-]', '', s, flags=re.UNICODE)
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s[:48] or 'sin-categoria'


def _estado_stock(stock: int, umbral: int) -> str:
    if stock <= 0:
        return 'Sin stock'
    if stock <= umbral:
        return 'Crítico'
    if stock <= umbral * 3:
        return 'Medio'
    return 'OK'


def _estado_clase(estado: str) -> str:
    if estado in ('Crítico', 'Sin stock'):
        return 'risk'
    if estado == 'Medio':
        return 'warn'
    return 'ok'


def collect_dashboard_premium(
    *,
    umbral_critico: int = 5,
    productos_por_categoria: int = 12,
    max_categorias: int = 8,
) -> dict[str, Any]:
    """
    Agrega inventario activo para vista premium.
    No inventa ventas ni tendencias: solo catálogo y stock actual.
    """
    import app as m
    from sqlalchemy import func, text

    from services.stock_consulta_service import contadores_stock_tienda_activos, stock_tienda_por_ids

    db = m.db
    Producto = m.Producto
    umbral = max(1, min(int(umbral_critico or 5), 50))
    lim_cat = max(3, min(int(max_categorias or 8), 12))
    lim_prod = max(5, min(int(productos_por_categoria or 12), 30))

    cont = contadores_stock_tienda_activos(umbral_critico=umbral)
    total_activos = int(cont['total_activos'])
    sin_stock = int(cont['sin_stock'])
    con_stock = int(cont['con_stock'])
    critico = int(cont['critico'])
    pend_barras = (
        Producto.query.filter(
            Producto.activo.is_(True),
            Producto.codigo_barra.isnot(None),
            Producto.codigo_barra.like('PEND-%'),
        ).count()
    )
    con_chilemat = (
        Producto.query.filter(
            Producto.activo.is_(True),
            Producto.codigo_chilemat.isnot(None),
            Producto.codigo_chilemat != '',
        ).count()
    )

    activos_ids = [int(r[0]) for r in db.session.query(Producto.id).filter(Producto.activo.is_(True)).all()]
    stocks_activos = stock_tienda_por_ids(activos_ids) if activos_ids else {}
    activos_rows = (
        Producto.query.filter(Producto.id.in_(activos_ids)).all() if activos_ids else []
    )
    capital_activo_clp = 0.0
    mercaderia_clp = 0.0
    stock_valorizado_tienda = 0
    stock_valorizado_costo = 0.0
    for p in activos_rows:
        st = int(stocks_activos.get(int(p.id), 0) or 0)
        costo = float(p.precio_compra or 0)
        venta = float(m.precio_efectivo_pos_producto(p) or p.precio_venta or 0)
        stock_valorizado_tienda += st
        capital_activo_clp += st * venta
        mercaderia_clp += st * costo

    salud_global = int(round(100.0 * con_stock / total_activos)) if total_activos else 0
    salud_catalogo = (
        int(round(100.0 * (total_activos - pend_barras) / total_activos))
        if total_activos
        else 0
    )

    cat_label = func.coalesce(
        func.nullif(func.trim(Producto.categoria), ''),
        'Sin categoría',
    )
    filas_cat = (
        db.session.query(
            cat_label.label('nombre'),
            func.count(Producto.id).label('cnt'),
        )
        .filter(Producto.activo.is_(True))
        .group_by(text('1'))
        .order_by(func.count(Producto.id).desc())
        .limit(lim_cat)
        .all()
    )

    categories: list[dict[str, Any]] = []
    products: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(filas_cat):
        nombre = (row.nombre or 'Sin categoría').strip()
        cnt = int(row.cnt or 0)
        slug = _slug_categoria(nombre)
        color = _PALETTE[idx % len(_PALETTE)]
        span = 'span-3' if idx < 2 and cnt >= 200 else 'span-2'
        q_prod = Producto.query.filter(Producto.activo.is_(True))
        if nombre == 'Sin categoría':
            q_prod = q_prod.filter(
                db.or_(
                    Producto.categoria.is_(None),
                    func.trim(Producto.categoria) == '',
                )
            )
        else:
            q_prod = q_prod.filter(Producto.categoria == nombre)
        rows_p = (
            q_prod.order_by(Producto.nombre.asc())
            .limit(max(lim_prod * 3, 36))
            .all()
        )
        cat_ids = [int(r[0]) for r in q_prod.with_entities(Producto.id).all()]
        st_cat = stock_tienda_por_ids(cat_ids) if cat_ids else {}
        con_st = sum(1 for cid in cat_ids if int(st_cat.get(cid, 0) or 0) > 0)
        products[slug] = []
        for p in sorted(
            rows_p,
            key=lambda x: (int(st_cat.get(x.id, 0) or 0), (x.nombre or '')),
        ):
            if len(products[slug]) >= lim_prod:
                continue
            st = int(st_cat.get(p.id, 0) or 0)
            estado = _estado_stock(st, umbral)
            code = (
                (p.codigo_chilemat or '').strip()
                or (p.codigo_barra or '').strip()
                or (p.codigo_interno or '').strip()
                or f'ID-{p.id}'
            )
            products[slug].append(
                {
                    'code': code[:50],
                    'name': (p.nombre or '').strip()[:100],
                    'stock': st,
                    'status': estado,
                    'status_class': _estado_clase(estado),
                    'producto_id': p.id,
                }
            )
        score = int(round(100.0 * con_st / cnt)) if cnt else 0
        categories.append(
            {
                'id': slug,
                'name': nombre,
                'items': cnt,
                'score': score,
                'color': color,
                'span': span,
                'con_stock': con_st,
            }
        )

    n_desajuste = 0
    n_reposicion = 0
    try:
        pl = m._inventario_salud_payload('', 1)
        n_desajuste = int(pl.get('n_desajuste') or 0)
        n_reposicion = int(pl.get('n_reposicion') or 0)
    except Exception:
        pass

    foco = []
    for c in categories[:3]:
        foco.append(
            {
                'name': c['name'],
                'score': c['score'],
                'items': c['items'],
            }
        )

    return {
        'total_activos': total_activos,
        'con_stock': con_stock,
        'sin_stock': sin_stock,
        'critico': critico,
        'umbral_critico': umbral,
        'pend_barras': pend_barras,
        'con_chilemat': con_chilemat,
        'salud_global': salud_global,
        'salud_catalogo': salud_catalogo,
        'n_desajuste': n_desajuste,
        'n_reposicion': n_reposicion,
        'capital_activo_clp': capital_activo_clp,
        'mercaderia_clp': mercaderia_clp,
        'stock_valorizado_tienda': stock_valorizado_tienda,
        'categories': categories,
        'products': products,
        'foco': foco,
        'datos_reales': True,
    }
