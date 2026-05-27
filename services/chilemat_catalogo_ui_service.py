"""Consultas UI — explorador catálogo Chilemat (VTEX)."""
from __future__ import annotations

from typing import Any

PROVEEDOR_NOMBRE = 'Chilemat'
PROVEEDOR_SLUG = 'chilemat'


def _path_partes(categoria_path: str | None) -> tuple[str, str, str]:
    partes = [p.strip() for p in (categoria_path or '').split('/') if p.strip()]
    rubro = partes[0] if len(partes) > 0 else ''
    sub = partes[1] if len(partes) > 1 else ''
    sub2 = partes[2] if len(partes) > 2 else ''
    return rubro, sub, sub2


def _asegurar_tablas() -> None:
    import app as erp

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()


def resolver_proveedor_chilemat():
    from app import Proveedor

    for nombre in ('Chilemat', 'CHILEMAT', 'Chilemat Central de Compras'):
        p = Proveedor.query.filter(Proveedor.nombre.ilike(nombre)).first()
        if p:
            return p
    return Proveedor.query.filter(Proveedor.nombre.ilike('%chilemat%')).first()


def estadisticas_explorador() -> dict[str, Any]:
    from app import ChilematCategoria, ChilematVtexProducto, ProductoRelacion, db

    _asegurar_tablas()
    total = ChilematVtexProducto.query.count()
    vinc = ChilematVtexProducto.query.filter(ChilematVtexProducto.producto_id.isnot(None)).count()
    cats = ChilematCategoria.query.count()
    rubros = ChilematCategoria.query.filter_by(depth=0).count()
    rel = ProductoRelacion.query.filter_by(activo=True, fuente='chilemat_vtex').count()
    rel_sd = ProductoRelacion.query.filter_by(activo=True, fuente='historico_sd').count()

    precio_avg = (
        db.session.query(db.func.avg(ChilematVtexProducto.precio_lista))
        .filter(ChilematVtexProducto.precio_lista.isnot(None), ChilematVtexProducto.precio_lista > 0)
        .scalar()
    )
    ultimo = (
        db.session.query(db.func.max(ChilematVtexProducto.synced_at)).scalar()
    )
    prov = resolver_proveedor_chilemat()

    return {
        'proveedor_nombre': prov.nombre if prov else PROVEEDOR_NOMBRE,
        'proveedor_id': prov.id if prov else None,
        'total_productos': int(total or 0),
        'vinculados_erp': int(vinc or 0),
        'sin_vincular': int(total or 0) - int(vinc or 0),
        'categorias_nodos': int(cats or 0),
        'rubros': int(rubros or 0),
        'relaciones_chilemat': int(rel or 0),
        'relaciones_historico_sd': int(rel_sd or 0),
        'precio_lista_promedio': int(round(float(precio_avg or 0))),
        'ultimo_sync': ultimo.isoformat() if ultimo else None,
    }


def opciones_filtros() -> dict[str, Any]:
    from app import ChilematCategoria

    _asegurar_tablas()
    rubros = (
        ChilematCategoria.query.filter_by(depth=0)
        .order_by(ChilematCategoria.nombre.asc())
        .all()
    )
    rubro_opts = [{'id': r.vtex_id, 'slug': r.slug, 'nombre': r.nombre} for r in rubros]

    subs_raw = (
        ChilematCategoria.query.filter(ChilematCategoria.depth >= 1)
        .order_by(ChilematCategoria.depth.asc(), ChilematCategoria.nombre.asc())
        .all()
    )
    sub_por_padre: dict[int, list[dict]] = {}
    id_a_nombre = {r.vtex_id: r.nombre for r in rubros}
    for s in subs_raw:
        pid = s.parent_vtex_id or 0
        sub_por_padre.setdefault(pid, []).append(
            {'id': s.vtex_id, 'slug': s.slug, 'nombre': s.nombre, 'depth': s.depth}
        )

    return {
        'rubros': rubro_opts,
        'subcategorias_por_rubro': sub_por_padre,
        'id_a_nombre': id_a_nombre,
    }


def listar_productos(
    *,
    q: str = '',
    rubro_vtex_id: int | None = None,
    sub_vtex_id: int | None = None,
    solo_vinculados: bool = False,
    solo_sin_vincular: bool = False,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    from app import ChilematCategoria, ChilematVtexProducto, Producto, db

    _asegurar_tablas()
    page = max(1, int(page or 1))
    per_page = max(10, min(int(per_page or 50), 100))

    query = ChilematVtexProducto.query
    rubro_nombre = ''
    sub_nombre = ''

    if rubro_vtex_id:
        rub = ChilematCategoria.query.filter_by(vtex_id=int(rubro_vtex_id)).first()
        if rub:
            rubro_nombre = rub.nombre
            query = query.filter(ChilematVtexProducto.categoria_path.ilike(f'%/{rubro_nombre}/%'))

    if sub_vtex_id:
        sub = ChilematCategoria.query.filter_by(vtex_id=int(sub_vtex_id)).first()
        if sub:
            sub_nombre = sub.nombre
            query = query.filter(ChilematVtexProducto.categoria_path.ilike(f'%/{sub_nombre}/%'))

    if solo_vinculados:
        query = query.filter(ChilematVtexProducto.producto_id.isnot(None))
    elif solo_sin_vincular:
        query = query.filter(ChilematVtexProducto.producto_id.is_(None))

    q_norm = (q or '').strip()
    if q_norm:
        like = f'%{q_norm}%'
        query = query.filter(
            db.or_(
                ChilematVtexProducto.nombre.ilike(like),
                ChilematVtexProducto.product_reference.ilike(like),
                ChilematVtexProducto.ean.ilike(like),
                ChilematVtexProducto.brand.ilike(like),
                ChilematVtexProducto.vtex_product_id.ilike(like),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ChilematVtexProducto.nombre.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items: list[dict[str, Any]] = []
    for r in rows:
        rubro, sub, sub2 = _path_partes(r.categoria_path)
        prod_erp = None
        if r.producto_id:
            p = Producto.query.get(int(r.producto_id))
            if p:
                prod_erp = {
                    'id': p.id,
                    'nombre': (p.nombre or '')[:80],
                    'codigo_chilemat': (p.codigo_chilemat or '').strip(),
                    'codigo_interno': (p.codigo_interno or '').strip(),
                }
        items.append(
            {
                'vtex_id': r.vtex_product_id,
                'codigo': (r.product_reference or r.ean or r.vtex_product_id or '').strip(),
                'ean': (r.ean or '').strip(),
                'nombre': (r.nombre or '').strip(),
                'marca': (r.brand or '').strip(),
                'precio_lista': int(round(float(r.precio_lista or 0))),
                'categoria': rubro or rubro_nombre,
                'subcategoria': sub,
                'subcategoria2': sub2,
                'link': (r.link or '').strip(),
                'vinculado': r.producto_id is not None,
                'producto_erp': prod_erp,
            }
        )

    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'filtros': {
            'q': q_norm,
            'rubro_vtex_id': rubro_vtex_id,
            'sub_vtex_id': sub_vtex_id,
            'rubro_nombre': rubro_nombre,
            'sub_nombre': sub_nombre,
            'solo_vinculados': solo_vinculados,
            'solo_sin_vincular': solo_sin_vincular,
        },
    }
