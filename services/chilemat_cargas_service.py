"""Operaciones de carga/borrado Chilemat → ERP (masivo y selectivo)."""
from __future__ import annotations

from typing import Any

ACCIONES = (
    'sync_staging',
    'reset_total',
    'reset_taxonomia',
    'borrar_productos',
    'cargar_productos',
)


def partes_path(path: str | None) -> tuple[str, str, str]:
    partes = [p.strip() for p in (path or '').split('/') if p.strip()]
    rubro = partes[0] if len(partes) > 0 else ''
    sub = partes[1] if len(partes) > 1 else ''
    sub2 = partes[2] if len(partes) > 2 else ''
    return rubro, sub, sub2


def uniq_barcode(base: str, usados: set[str], vid: str) -> str:
    b = (base or '').strip()[:50]
    if not b:
        b = f'CHM-BC-{vid}'[:50]
    if b not in usados:
        usados.add(b)
        return b
    i = 2
    while True:
        cand = f'{b[:42]}-{i}'[:50]
        if cand not in usados:
            usados.add(cand)
            return cand
        i += 1


def resumen_bd() -> dict[str, Any]:
    from app import CatalogoCategoria, CatalogoSubcategoria, ChilematVtexProducto, Producto, db
    from sqlalchemy import func

    total_vt = int(db.session.query(func.count(ChilematVtexProducto.vtex_product_id)).scalar() or 0)
    vinc = int(
        db.session.query(func.count(ChilematVtexProducto.vtex_product_id))
        .filter(ChilematVtexProducto.producto_id.isnot(None))
        .scalar()
        or 0
    )
    return {
        'productos_erp': int(db.session.query(func.count(Producto.id)).scalar() or 0),
        'categorias_erp': int(db.session.query(func.count(CatalogoCategoria.id)).scalar() or 0),
        'subcategorias_erp': int(db.session.query(func.count(CatalogoSubcategoria.id)).scalar() or 0),
        'vtex_staging': total_vt,
        'vtex_vinculados': vinc,
        'vtex_sin_vincular': total_vt - vinc,
    }


def sync_staging(*, solo_faltantes: bool = False, max_productos: int | None = None) -> dict[str, Any]:
    from services.chilemat_catalogo_service import sync_categorias, sync_productos_vtex

    out_cat = sync_categorias(solo_faltantes=solo_faltantes)
    out_prod = sync_productos_vtex(max_productos=max_productos, solo_faltantes=solo_faltantes)
    return {'ok': True, 'categorias': out_cat, 'productos': out_prod}


def load_vt_data(
    *,
    rubro: str = '',
    rubro_vtex_id: int | None = None,
    q: str = '',
    limit: int | None = None,
) -> list[dict[str, Any]]:
    from app import ChilematCategoria, ChilematVtexProducto, db

    query = ChilematVtexProducto.query
    rubro_nombre = ''
    if rubro_vtex_id:
        cat = ChilematCategoria.query.filter_by(vtex_id=int(rubro_vtex_id)).first()
        if cat:
            rubro_nombre = (cat.nombre or '').strip()
    if rubro_nombre:
        query = query.filter(ChilematVtexProducto.categoria_path.ilike(f'%/{rubro_nombre}/%'))
    elif (rubro or '').strip():
        rr = rubro.strip()
        query = query.filter(ChilematVtexProducto.categoria_path.ilike(f'%/{rr}/%'))

    qn = (q or '').strip()
    if qn:
        like = f'%{qn}%'
        query = query.filter(
            db.or_(
                ChilematVtexProducto.nombre.ilike(like),
                ChilematVtexProducto.product_reference.ilike(like),
                ChilematVtexProducto.ean.ilike(like),
                ChilematVtexProducto.vtex_product_id.ilike(like),
            )
        )
    query = query.order_by(
        ChilematVtexProducto.nombre.asc().nullslast(),
        ChilematVtexProducto.vtex_product_id.asc(),
    )
    if limit and int(limit) > 0:
        query = query.limit(int(limit))
    rows = query.all()
    return [
        {
            'vtex_product_id': (r.vtex_product_id or '').strip(),
            'product_reference': (r.product_reference or '').strip(),
            'nombre': (r.nombre or '').strip(),
            'link': (r.link or '').strip(),
            'categoria_path': (r.categoria_path or '').strip(),
            'brand': (r.brand or '').strip(),
            'precio_lista': float(r.precio_lista or 0) if r.precio_lista else 0.0,
            'ean': (r.ean or '').strip(),
            'imagen_url': (getattr(r, 'imagen_url', None) or '').strip(),
            'descripcion_web': (getattr(r, 'descripcion_web', None) or ''),
            'descripcion_corta': (getattr(r, 'descripcion_corta', None) or '').strip(),
        }
        for r in rows
        if (r.vtex_product_id or '').strip()
    ]


def replace_taxonomia(vt_data: list[dict], *, preview: bool = False) -> dict[str, Any]:
    from app import CatalogoCategoria, CatalogoSubcategoria, db

    cat_map: dict[str, int] = {}
    sub_map: dict[tuple[str, str, str], int] = {}
    if preview:
        for r in vt_data:
            rubro, sub, sub2 = partes_path(r.get('categoria_path'))
            if not rubro:
                continue
            if rubro not in cat_map:
                cat_map[rubro] = -1
            if sub:
                sub_map[(rubro, sub[:80], (sub2 or sub)[:80])] = -1
        return {'categorias': len(cat_map), 'subcategorias': len(sub_map), 'preview': True}

    db.session.query(CatalogoSubcategoria).delete(synchronize_session=False)
    db.session.query(CatalogoCategoria).delete(synchronize_session=False)
    db.session.flush()
    for r in vt_data:
        rubro, sub, sub2 = partes_path(r.get('categoria_path'))
        if not rubro:
            continue
        if rubro not in cat_map:
            cat = CatalogoCategoria(nombre=rubro[:80], orden=0, activo=True)
            db.session.add(cat)
            db.session.flush()
            cat_map[rubro] = cat.id
        if sub:
            n2 = sub[:80]
            leaf = (sub2 or sub)[:80]
            key = (rubro, n2, leaf)
            if key not in sub_map:
                sc = CatalogoSubcategoria(
                    categoria_id=cat_map[rubro],
                    nivel2=n2,
                    nombre=leaf,
                    orden=0,
                    activo=True,
                )
                db.session.add(sc)
                db.session.flush()
                sub_map[key] = sc.id
    db.session.commit()
    return {'categorias': len(cat_map), 'subcategorias': len(sub_map)}


def borrar_productos(
    *,
    vt_data: list[dict],
    masivo: bool = False,
    forzar: bool = False,
    preview: bool = False,
) -> dict[str, Any]:
    from app import Producto, db
    from sqlalchemy import func

    if masivo:
        if not forzar:
            return {'ok': False, 'error': 'forzar_requerido', 'mensaje': 'Borrado masivo requiere confirmación explícita.'}
        if preview:
            n = int(db.session.query(func.count(Producto.id)).scalar() or 0)
            return {'ok': True, 'productos_a_borrar': n, 'masivo': True, 'preview': True}
        db.session.execute(db.text('TRUNCATE TABLE productos RESTART IDENTITY CASCADE'))
        db.session.commit()
        return {'ok': True, 'productos_borrados': 'all', 'masivo': True}

    refs = {(r.get('product_reference') or '').strip() for r in vt_data if (r.get('product_reference') or '').strip()}
    vids = {(r.get('vtex_product_id') or '').strip() for r in vt_data if (r.get('vtex_product_id') or '').strip()}
    if not refs and not vids:
        return {'ok': True, 'productos_borrados': 0, 'masivo': False}

    conds = []
    if refs:
        conds.append(Producto.codigo_chilemat.in_(list(refs)))
    if vids:
        conds.append(Producto.codigo_interno.in_([f'CHM-{v}'[:32] for v in vids]))
    ids = [int(x.id) for x in Producto.query.filter(db.or_(*conds)).all()]
    if preview:
        return {'ok': True, 'productos_a_borrar': len(ids), 'masivo': False, 'preview': True}
    if not ids:
        return {'ok': True, 'productos_borrados': 0, 'masivo': False}
    Producto.query.filter(Producto.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return {'ok': True, 'productos_borrados': len(ids), 'masivo': False}


def cargar_productos(*, vt_data: list[dict], preview: bool = False) -> dict[str, Any]:
    from app import CatalogoSubcategoria, ChilematVtexProducto, Producto, db

    sub_map: dict[tuple[str, str, str], int] = {}
    for s in CatalogoSubcategoria.query.all():
        c = s.categoria
        if not c:
            continue
        key = ((c.nombre or '').strip(), (s.nivel2 or '').strip(), (s.nombre or '').strip())
        sub_map[key] = int(s.id)

    usados_barra = {
        x[0]
        for x in db.session.query(Producto.codigo_barra).filter(Producto.codigo_barra.isnot(None)).all()
        if x[0]
    }
    by_codigo_interno = {
        p.codigo_interno: p for p in Producto.query.filter(Producto.codigo_interno.ilike('CHM-%')).all()
    }
    by_codigo_chm = {p.codigo_chilemat: p for p in Producto.query.filter(Producto.codigo_chilemat.isnot(None)).all()}

    crear = actualizar = linked = 0
    for r in vt_data:
        vid = (r.get('vtex_product_id') or '').strip()
        if not vid:
            continue
        ref = (r.get('product_reference') or '').strip()
        ean = (r.get('ean') or '').strip()
        interno = (f'CHM-{vid}')[:32]
        p = by_codigo_interno.get(interno) or (by_codigo_chm.get(ref) if ref else None)
        era_nuevo = p is None
        if p is None:
            p = Producto(codigo_interno=interno, activo=True)
            crear += 1
        else:
            actualizar += 1

        rubro, sub, sub2 = partes_path(r.get('categoria_path'))
        key_sub = (rubro, sub[:80] if sub else '', (sub2 or sub)[:80] if (sub or sub2) else '')
        sub_fk = sub_map.get(key_sub) if rubro and sub else None
        precio = float(r.get('precio_lista') or 0)

        p.nombre = (r.get('nombre') or f'Chilemat {vid}')[:100]
        p.codigo_chilemat = ref[:80] if ref else p.codigo_chilemat
        if era_nuevo:
            p.codigo_barra = uniq_barcode(ean or ref or f'CHM-BC-{vid}', usados_barra, vid)
        img = (r.get('imagen_url') or '').strip()[:500]
        if img:
            p.imagen_url = img
        p.precio_venta = precio
        p.precio_mayoreo = precio
        p.precio_compra = round(precio * 0.75, 2) if precio > 0 else float(p.precio_compra or 0)
        p.unidad = p.unidad or 'UN'
        p.unidad_compra = p.unidad_compra or 'UN'
        p.unidad_venta = p.unidad_venta or 'UN'
        p.factor_conversion = p.factor_conversion or 1.0
        p.stock = int(p.stock or 0)
        p.categoria = (rubro or 'Chilemat')[:50]
        p.subcategoria = ((sub2 or sub or '')[:50] if (sub or sub2) else None)
        p.subcategoria_catalogo_id = sub_fk
        p.activo = True

        if not preview:
            if era_nuevo:
                db.session.add(p)
                db.session.flush()
                by_codigo_interno[interno] = p
                if ref:
                    by_codigo_chm[ref] = p
            row = ChilematVtexProducto.query.get(vid)
            if row:
                row.producto_id = p.id
        linked += 1

    if not preview:
        db.session.commit()
    return {
        'ok': True,
        'creados': crear,
        'actualizados': actualizar,
        'vtex_linked': linked,
        'preview': preview,
    }


def ejecutar(
    *,
    accion: str,
    sin_sync: bool = False,
    solo_faltantes_sync: bool = False,
    rubro: str = '',
    rubro_vtex_id: int | None = None,
    q: str = '',
    limit: int | None = None,
    masivo: bool = False,
    forzar: bool = False,
    preview: bool = False,
    confirmacion: str = '',
) -> dict[str, Any]:
    accion = (accion or '').strip()
    if accion not in ACCIONES:
        return {'ok': False, 'error': 'accion_invalida'}

    if accion in ('reset_total', 'reset_taxonomia') and not forzar:
        return {'ok': False, 'error': 'forzar_requerido', 'mensaje': 'Marque «Forzar» para esta acción.'}
    if accion == 'borrar_productos' and masivo and not forzar:
        return {'ok': False, 'error': 'forzar_requerido'}

    if accion == 'reset_total':
        if (confirmacion or '').strip().upper() != 'RESET TOTAL':
            return {
                'ok': False,
                'error': 'confirmacion_requerida',
                'mensaje': 'Escriba RESET TOTAL para confirmar.',
            }

    out: dict[str, Any] = {'ok': True, 'accion': accion}

    try:
        if accion == 'sync_staging':
            out['resultado'] = sync_staging(solo_faltantes=solo_faltantes_sync, max_productos=limit)
            return out

        if not sin_sync:
            out['sync'] = sync_staging(solo_faltantes=False, max_productos=None)

        vt_data = load_vt_data(rubro=rubro, rubro_vtex_id=rubro_vtex_id, q=q, limit=limit)
        out['vtex_filtrados'] = len(vt_data)

        if accion == 'reset_total':
            out['taxonomia'] = replace_taxonomia(vt_data, preview=preview)
            out['borrado'] = borrar_productos(vt_data=vt_data, masivo=True, forzar=True, preview=preview)
            if not preview:
                vt_data = load_vt_data(rubro=rubro, rubro_vtex_id=rubro_vtex_id, q=q, limit=limit)
            out['carga'] = cargar_productos(vt_data=vt_data, preview=preview)
        elif accion == 'reset_taxonomia':
            out['taxonomia'] = replace_taxonomia(vt_data, preview=preview)
        elif accion == 'borrar_productos':
            out['borrado'] = borrar_productos(
                vt_data=vt_data, masivo=masivo, forzar=forzar, preview=preview
            )
        elif accion == 'cargar_productos':
            out['carga'] = cargar_productos(vt_data=vt_data, preview=preview)

        if not preview:
            out['resumen_bd'] = resumen_bd()
        return out
    except Exception as ex:
        from app import db

        db.session.rollback()
        return {'ok': False, 'error': 'excepcion', 'mensaje': str(ex)}
