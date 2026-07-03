"""Filtros categoría/subcategoría — catálogo oficial + bucket legacy (Centro BI SD-1)."""
from __future__ import annotations

import time
from typing import Any

LEGACY_PREFIX = 'legacy:'

_OPTS_CACHE: dict[str, Any] | None = None
_OPTS_CACHE_AT: float = 0.0
_OPTS_CACHE_TTL_S: float = 300.0
_OPTS_CACHE_VERSION = 2
_CATALOGO_NOMBRES_CACHE: set[str] | None = None
_PRODUCTO_FK_COL: bool | None = None

def _norm_txt(val: Any, default: str = '') -> str:
    return (str(val or '').strip()) or default


def parse_categoria_request(val: str | None) -> tuple[str, str | None]:
    """
    Devuelve (modo, nombre):
      - ('catalog', nombre) — categoría del catálogo oficial
      - ('legacy', nombre) — categoría texto huérfana
      - ('', None) — sin filtro
    """
    raw = _norm_txt(val)
    if not raw:
        return '', None
    if raw.lower().startswith(LEGACY_PREFIX):
        nombre = raw[len(LEGACY_PREFIX):].strip()
        return ('legacy', nombre) if nombre else ('legacy', None)
    return 'catalog', raw


def categoria_param_from_filtros(filtros: dict[str, Any]) -> str:
    """Valor para <select name=categoria> según filtros parseados."""
    modo = filtros.get('categoria_modo') or ''
    nombre = filtros.get('categoria')
    if not nombre:
        return ''
    if modo == 'legacy':
        return f'{LEGACY_PREFIX}{nombre}'
    return str(nombre)


def _catalogo_disponible(m) -> bool:
    try:
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(m.db.engine)
        return insp.has_table('catalogo_categorias') and insp.has_table('catalogo_subcategorias')
    except Exception:
        return False


def _catalogo_nombres_upper(m) -> set[str]:
    global _CATALOGO_NOMBRES_CACHE
    if _CATALOGO_NOMBRES_CACHE is not None:
        return _CATALOGO_NOMBRES_CACHE
    if not _catalogo_disponible(m):
        _CATALOGO_NOMBRES_CACHE = set()
        return _CATALOGO_NOMBRES_CACHE
    _CATALOGO_NOMBRES_CACHE = {
        str(c.nombre or '').strip().upper()
        for c in m.CatalogoCategoria.query.filter_by(activo=True).all()
        if c.nombre
    }
    return _CATALOGO_NOMBRES_CACHE


def _producto_tiene_fk_col(m) -> bool:
    global _PRODUCTO_FK_COL
    if _PRODUCTO_FK_COL is not None:
        return _PRODUCTO_FK_COL
    try:
        from sqlalchemy import inspect as sa_inspect

        cols = {c['name'] for c in sa_inspect(m.db.engine).get_columns('productos')}
        _PRODUCTO_FK_COL = 'subcategoria_catalogo_id' in cols
    except Exception:
        _PRODUCTO_FK_COL = False
    return _PRODUCTO_FK_COL

def subcategorias_catalogo_para(categoria_nombre: str) -> list[dict[str, Any]]:
    """Subcategorías del catálogo bajo una categoría (id + etiqueta)."""
    import app as m

    if not _catalogo_disponible(m) or not categoria_nombre:
        return []
    cat = (
        m.CatalogoCategoria.query.filter_by(nombre=categoria_nombre.strip(), activo=True).first()
    )
    if not cat:
        return []
    out = []
    subs = (
        cat.subcategorias.filter_by(activo=True)
        .order_by(
            m.CatalogoSubcategoria.nivel2.asc(),
            m.CatalogoSubcategoria.orden.asc(),
            m.CatalogoSubcategoria.nombre.asc(),
        )
        .all()
    )
    for s in subs:
        n2 = (s.nivel2 or '').strip()
        label = f'{n2} — {s.nombre}' if n2 else (s.nombre or '')
        out.append({'id': int(s.id), 'etiqueta': label})
    return out


def catalogo_tree_para_js() -> dict[str, list[dict[str, Any]]]:
    """Mapa categoría → lista {id, etiqueta} para cascada en el front (1 query)."""
    import app as m

    tree: dict[str, list[dict[str, Any]]] = {}
    if not _catalogo_disponible(m):
        return tree
    Cat = m.CatalogoCategoria
    Sub = m.CatalogoSubcategoria
    rows = (
        m.db.session.query(Cat.nombre, Sub.id, Sub.nivel2, Sub.nombre)
        .join(Sub, Sub.categoria_id == Cat.id)
        .filter(Cat.activo.is_(True), Sub.activo.is_(True))
        .order_by(Cat.orden.asc(), Cat.nombre.asc(), Sub.nivel2.asc(), Sub.orden.asc(), Sub.nombre.asc())
        .all()
    )
    for cat_n, sid, n2, sn in rows:
        if not cat_n or str(cat_n).startswith('_'):
            continue
        n2s = (n2 or '').strip()
        label = f'{n2s} — {sn}' if n2s else (sn or '')
        tree.setdefault(str(cat_n), []).append({'id': int(sid), 'etiqueta': label})
    return tree

def legacy_categorias() -> list[str]:
    """Categorías texto en productos sin FK al catálogo oficial."""
    import app as m
    from sqlalchemy import func

    Producto = m.Producto
    catalog = _catalogo_nombres_upper(m)
    q = m.db.session.query(Producto.categoria).filter(
        Producto.activo.is_(True),
        Producto.subcategoria_catalogo_id.is_(None),
        Producto.categoria.isnot(None),
        func.trim(Producto.categoria) != '',
    )
    if catalog:
        q = q.filter(func.upper(func.trim(Producto.categoria)).notin_(list(catalog)))
    return sorted({str(r[0]).strip() for r in q.distinct().all() if r[0]}, key=str.lower)


def legacy_subcategorias_map() -> dict[str, list[str]]:
    """Mapa categoría legacy → subcategorías texto."""
    import app as m
    from sqlalchemy import func

    Producto = m.Producto
    catalog = _catalogo_nombres_upper(m)
    q = (
        m.db.session.query(Producto.categoria, Producto.subcategoria)
        .filter(
            Producto.activo.is_(True),
            Producto.subcategoria_catalogo_id.is_(None),
            Producto.categoria.isnot(None),
            func.trim(Producto.categoria) != '',
            Producto.subcategoria.isnot(None),
            func.trim(Producto.subcategoria) != '',
        )
    )
    if catalog:
        q = q.filter(func.upper(func.trim(Producto.categoria)).notin_(list(catalog)))
    out: dict[str, set[str]] = {}
    for cat, sub in q.distinct().all():
        if not cat or not sub:
            continue
        out.setdefault(str(cat).strip(), set()).add(str(sub).strip())
    return {k: sorted(v, key=str.lower) for k, v in sorted(out.items(), key=lambda x: x[0].lower())}


def _clausulas_categoria_catalogo(Producto, m, cat_name: str, *, tiene_fk: bool) -> list[Any]:
    """
    Productos de una familia de catálogo: FK a subcategorías + texto exacto o que contenga el nombre.
    Cubre catálogos duplicados vacíos (ej. «Pintura» vs «Pinturas y Accesorios» en maestro).
    """
    from sqlalchemy import func, or_

    cat_name = _norm_txt(cat_name)
    if not cat_name:
        return []
    cat_upper = cat_name.upper()
    cat_expr = func.upper(func.trim(Producto.categoria))
    parts: list[Any] = [
        Producto.categoria == cat_name,
        cat_expr.like(f'%{cat_upper}%'),
    ]
    if _catalogo_disponible(m) and tiene_fk:
        cat = m.CatalogoCategoria.query.filter_by(nombre=cat_name, activo=True).first()
        if cat:
            sub_ids = [int(s.id) for s in cat.subcategorias.filter_by(activo=True).all()]
            if sub_ids:
                parts.append(Producto.subcategoria_catalogo_id.in_(sub_ids))
    return parts


def _clausulas_categoria_catalogo_estricta(Producto, m, cat_name: str, *, tiene_fk: bool) -> list[Any]:
    """Solo coincidencia exacta de texto + FK (para listar categorías con SKU reales)."""
    cat_name = _norm_txt(cat_name)
    if not cat_name:
        return []
    parts: list[Any] = [Producto.categoria == cat_name]
    if _catalogo_disponible(m) and tiene_fk:
        cat = m.CatalogoCategoria.query.filter_by(nombre=cat_name, activo=True).first()
        if cat:
            sub_ids = [int(s.id) for s in cat.subcategorias.filter_by(activo=True).all()]
            if sub_ids:
                parts.append(Producto.subcategoria_catalogo_id.in_(sub_ids))
    return parts


def _count_productos_categoria_catalogo(cat_name: str, *, estricto: bool = False) -> int:
    import app as m
    from sqlalchemy import func, or_

    Producto = m.Producto
    tiene_fk = _producto_tiene_fk_col(m)
    if estricto:
        parts = _clausulas_categoria_catalogo_estricta(Producto, m, cat_name, tiene_fk=tiene_fk)
    else:
        parts = _clausulas_categoria_catalogo(Producto, m, cat_name, tiene_fk=tiene_fk)
    if not parts:
        return 0
    return int(
        m.db.session.query(func.count(Producto.id))
        .filter(Producto.activo.is_(True), or_(*parts))
        .scalar()
        or 0
    )


def categorias_catalogo() -> list[dict[str, Any]]:
    import app as m

    if not _catalogo_disponible(m):
        return []
    out: list[dict[str, Any]] = []
    for c in (
        m.CatalogoCategoria.query.filter_by(activo=True)
        .order_by(m.CatalogoCategoria.orden.asc(), m.CatalogoCategoria.nombre.asc())
        .all()
    ):
        if not c.nombre or str(c.nombre).startswith('_'):
            continue
        sku = _count_productos_categoria_catalogo(c.nombre, estricto=True)
        if sku <= 0:
            continue
        out.append({'nombre': c.nombre, 'sku_count': sku})
    out.sort(key=lambda r: (-int(r.get('sku_count') or 0), str(r['nombre']).lower()))
    return out


def _fetch_marcas_opts() -> list[str]:
    import app as m
    from sqlalchemy import func, inspect as sa_inspect

    Producto = m.Producto
    try:
        cols = {c['name'] for c in sa_inspect(m.db.engine).get_columns('productos')}
        if 'marca' not in cols:
            return []
        return sorted(
            {
                str(r[0]).strip()
                for r in m.db.session.query(Producto.marca)
                .filter(
                    Producto.activo.is_(True),
                    Producto.marca.isnot(None),
                    func.trim(Producto.marca) != '',
                )
                .distinct()
                .limit(400)
                .all()
                if r[0]
            },
            key=str.lower,
        )
    except Exception:
        return []


def _build_opts_base() -> dict[str, Any]:
    return {
        '_v': _OPTS_CACHE_VERSION,
        'categorias_catalogo': categorias_catalogo(),
        'legacy_categorias': legacy_categorias(),
        'catalogo_tree': catalogo_tree_para_js(),
        'legacy_subs_map': legacy_subcategorias_map(),
        'marcas': _fetch_marcas_opts(),
    }


def fetch_opts_filtro_catalogo(filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    global _OPTS_CACHE, _OPTS_CACHE_AT

    filtros = dict(filtros or {})
    modo = filtros.get('categoria_modo') or ''
    cat = filtros.get('categoria')

    now = time.time()
    if (
        _OPTS_CACHE is None
        or _OPTS_CACHE.get('_v') != _OPTS_CACHE_VERSION
        or (now - _OPTS_CACHE_AT) >= _OPTS_CACHE_TTL_S
    ):
        _OPTS_CACHE = _build_opts_base()
        _OPTS_CACHE_AT = now

    opts = dict(_OPTS_CACHE)
    opts['subcategorias_catalogo'] = []
    opts['legacy_subcategorias'] = []
    if modo == 'catalog' and cat:
        opts['subcategorias_catalogo'] = (opts.get('catalogo_tree') or {}).get(str(cat), [])
    elif modo == 'legacy' and cat:
        opts['legacy_subcategorias'] = (opts.get('legacy_subs_map') or {}).get(str(cat), [])
    return opts

def build_fetch_filtros_taxonomia(filtros: dict[str, Any], *, extra_keys: tuple[str, ...] = ('q',)) -> dict[str, Any]:
    """Traduce filtros UI → params para _fetch_lineas_stock."""
    out = {k: filtros[k] for k in extra_keys if filtros.get(k)}
    sub_id = filtros.get('subcategoria_catalogo_id')
    if sub_id:
        out['subcategoria_catalogo_id'] = int(sub_id)
        return out
    modo = filtros.get('categoria_modo') or ''
    cat = filtros.get('categoria')
    if not cat:
        return out
    out['categoria'] = cat
    out['categoria_modo'] = modo
    if modo == 'legacy' and filtros.get('subcategoria'):
        out['subcategoria'] = filtros['subcategoria']
    return out


def apply_filtros_taxonomia_producto(q, Producto, filtros: dict[str, Any]):
    """
    Aplica filtro catálogo / legacy sobre query SQLAlchemy de Producto.
    Si no hay keys de taxonomía nueva, no modifica (caller usa filtro texto legacy).
    """
    import app as m
    from sqlalchemy import and_, func, or_

    sub_id = filtros.get('subcategoria_catalogo_id')
    modo = _norm_txt(filtros.get('categoria_modo'))
    cat_name = _norm_txt(filtros.get('categoria'))
    sub_txt = _norm_txt(filtros.get('subcategoria'))
    tiene_fk = _producto_tiene_fk_col(m)
    catalog = _catalogo_nombres_upper(m)

    if sub_id and tiene_fk:
        return q.filter(Producto.subcategoria_catalogo_id == int(sub_id))

    if modo == 'catalog' and cat_name:
        parts = _clausulas_categoria_catalogo(Producto, m, cat_name, tiene_fk=tiene_fk)
        if parts:
            return q.filter(or_(*parts))
        return q.filter(Producto.id == -1)

    if modo == 'legacy' and cat_name:
        legacy_parts = [
            Producto.subcategoria_catalogo_id.is_(None),
            Producto.categoria == cat_name,
        ]
        if catalog:
            legacy_parts.append(func.upper(func.trim(Producto.categoria)).notin_(list(catalog)))
        q = q.filter(and_(*legacy_parts))
        if sub_txt:
            if sub_txt == 'Sin subcategoría':
                q = q.filter(or_(Producto.subcategoria.is_(None), func.trim(Producto.subcategoria) == ''))
            else:
                q = q.filter(Producto.subcategoria == sub_txt)
        return q

    return q
