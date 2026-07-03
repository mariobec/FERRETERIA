"""Informe de stock valorizado: categoría, subcategoría, almacén, ubicación y capital dormido."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

_MARCAS_FERRETERIA = (
    'TRICOLOR', 'LANCO', 'PETRILAC', 'SHERWIN', 'BEHR', 'DULUX', 'CONSTRUCTORA',
    'BASF', 'SAYERLACK', 'RUST-OLEUM', 'RUST OLEUM', '3M', 'BOSCH', 'DEWALT',
    'MAKITA', 'STANLEY', 'BLACK+DECKER', 'BLACK DECKER', 'BELLOTA', 'TRUPER',
    'BREMEN', 'URREA', 'PRETUL', 'NORTON', 'BESSEY', 'FISCHER',
    'CHILEMAT', 'SOQUINA', 'SINTEPLAST', 'TARCO', 'SIKA',
)

_TONOS_PINTURA = (
    'ROJO INDUSTRIAL', 'ROJO FERRARI', 'ROJO TEJA', 'ROJO', 'AZUL MARINO', 'AZUL',
    'VERDE INGLÉS', 'VERDE INGLES', 'VERDE', 'BLANCO', 'NEGRO', 'AMARILLO',
    'GRIS', 'OCRE', 'CELESTE', 'BEIGE', 'MARRÓN', 'MARRON', 'CAOBA', 'VERONICA',
    'VERÓNICA', 'NARANJA', 'VIOLETA', 'TERRACOTA', 'ALMENDRA', 'HUESO', 'CREMA',
    'PLATEADO', 'DORADO', 'TRANSPARENTE', 'INCOLORO', 'SATINADO', 'BRILLANTE',
    'MATE', 'ANTICOR', 'GALVANIZADO',
)


def _norm_txt(val: Any, default: str = '') -> str:
    return (str(val or '').strip()) or default


def _fmt_clp(val: float) -> str:
    return f"${int(round(float(val or 0))):,}".replace(',', '.')


def _inferir_marca(nombre: str, marca_db: str = '') -> str:
    m = _norm_txt(marca_db)
    if m:
        return m[:80]
    up = (nombre or '').upper()
    for marca in _MARCAS_FERRETERIA:
        if marca and marca in up:
            return marca[:80]
    return 'Sin marca'


def _inferir_tono_color(nombre: str, tono_db: str = '') -> str:
    t = _norm_txt(tono_db)
    if t:
        return t[:80]
    up = (nombre or '').upper()
    for tono in sorted(_TONOS_PINTURA, key=len, reverse=True):
        if tono in up:
            return tono.title()[:80]
    m = re.search(r'\b(COLOR|Tono|TONO)\s+([A-ZÁÉÍÓÚÑ0-9\- ]{3,30})', nombre or '', re.I)
    if m:
        return m.group(2).strip().title()[:80]
    return 'Sin tono'


def _venta_unit(precio_sd: float | None, precio_venta: float | None) -> float:
    sd = float(precio_sd or 0)
    if sd > 0:
        return sd
    return float(precio_venta or 0)


def _linea_valorizada(
    *,
    pid: int,
    nombre: str,
    codigo_barra: str,
    codigo_interno: str,
    categoria: str,
    subcategoria: str,
    ubicacion_pasillo: str,
    ubicacion_estante: str,
    ubicacion_nivel: str,
    precio_compra: float,
    precio_venta: float,
    precio_venta_sd: float,
    stock_tienda: int,
    stock_bodega: int,
    marca_db: str = '',
    tono_db: str = '',
) -> dict[str, Any]:
    costo = float(precio_compra or 0)
    venta = _venta_unit(precio_venta_sd, precio_venta)
    st_t = int(stock_tienda or 0)
    st_b = int(stock_bodega or 0)
    cat = _norm_txt(categoria, 'Sin categoría')
    sub = _norm_txt(subcategoria, 'Sin subcategoría')
    p = _norm_txt(ubicacion_pasillo)
    e = _norm_txt(ubicacion_estante)
    n = _norm_txt(ubicacion_nivel)
    ubic = f'{p}-{e}-{n}'.strip('-') if (p or e or n) else 'Sin ubicación'
    marca = _inferir_marca(nombre, marca_db)
    tono = _inferir_tono_color(nombre, tono_db)
    return {
        'id': int(pid),
        'nombre': _norm_txt(nombre, 'Sin nombre')[:100],
        'codigo': _norm_txt(codigo_barra) or _norm_txt(codigo_interno) or str(pid),
        'categoria': cat,
        'subcategoria': sub,
        'marca': marca,
        'tono_color': tono,
        'ubicacion': ubic,
        'ubicacion_pasillo': p or '—',
        'ubicacion_estante': e or '—',
        'ubicacion_nivel': n or '—',
        'stock_tienda': st_t,
        'stock_bodega': st_b,
        'stock_total': st_t + st_b,
        'precio_compra': costo,
        'precio_venta': venta,
        'mercaderia_tienda': st_t * costo,
        'mercaderia_bodega': st_b * costo,
        'mercaderia_total': (st_t + st_b) * costo,
        'capital_tienda': st_t * venta,
        'capital_bodega': st_b * venta,
        'capital_total': (st_t + st_b) * venta,
        'sin_costo': costo <= 0 and (st_t + st_b) > 0,
    }


def _fetch_lineas_stock(filtros: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    import app as m
    from sqlalchemy import and_, func, or_
    from sqlalchemy.orm import aliased

    filtros = dict(filtros or {})
    m._asegurar_columnas_productos_legacy()

    Producto = m.Producto
    StockPorAlmacen = m.StockPorAlmacen
    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    mult = bool(m._tablas_inventario_almacen_existen() and aid_t)

    insp_cols = set()
    try:
        from sqlalchemy import inspect as sa_inspect

        insp_cols = {c['name'] for c in sa_inspect(m.db.engine).get_columns('productos')}
    except Exception:
        insp_cols = set()

    has_marca = 'marca' in insp_cols
    has_tono = 'tono_color' in insp_cols

    st_t_expr = func.coalesce(StockPorAlmacen.cantidad, 0)
    if mult:
        StT = aliased(StockPorAlmacen)
        StB = aliased(StockPorAlmacen)
        st_t_col = func.coalesce(StT.cantidad, 0).label('st_t')
        st_b_col = func.coalesce(StB.cantidad, 0).label('st_b')
        q = (
            m.db.session.query(
                Producto.id,
                Producto.nombre,
                Producto.codigo_barra,
                Producto.codigo_interno,
                Producto.categoria,
                Producto.subcategoria,
                Producto.ubicacion_pasillo,
                Producto.ubicacion_estante,
                Producto.ubicacion_nivel,
                Producto.precio_compra,
                Producto.precio_venta,
                Producto.precio_venta_sd,
                st_t_col,
                st_b_col,
                *( [getattr(Producto, 'marca')] if has_marca else [] ),
                *( [getattr(Producto, 'tono_color')] if has_tono else [] ),
            )
            .outerjoin(
                StT,
                and_(StT.id_producto == Producto.id, StT.id_almacen == int(aid_t)),
            )
            .outerjoin(
                StB,
                and_(StB.id_producto == Producto.id, StB.id_almacen == int(aid_b or 0)),
            )
        )
    else:
        st_master = func.coalesce(Producto.stock, 0)
        q = m.db.session.query(
            Producto.id,
            Producto.nombre,
            Producto.codigo_barra,
            Producto.codigo_interno,
            Producto.categoria,
            Producto.subcategoria,
            Producto.ubicacion_pasillo,
            Producto.ubicacion_estante,
            Producto.ubicacion_nivel,
            Producto.precio_compra,
            Producto.precio_venta,
            Producto.precio_venta_sd,
            st_master.label('st_t'),
            func.literal(0).label('st_b'),
            *( [getattr(Producto, 'marca')] if has_marca else [] ),
            *( [getattr(Producto, 'tono_color')] if has_tono else [] ),
        )

    q = q.filter(Producto.activo.is_(True))

    tax_modo = _norm_txt(filtros.get('categoria_modo'))
    sub_cat_id = filtros.get('subcategoria_catalogo_id')
    if sub_cat_id or tax_modo in ('catalog', 'legacy'):
        from services.inventario_catalogo_filtro_service import apply_filtros_taxonomia_producto

        q = apply_filtros_taxonomia_producto(q, Producto, filtros)
    else:
        cat_f = _norm_txt(filtros.get('categoria'))
        if cat_f:
            if cat_f == 'Sin categoría':
                q = q.filter(or_(Producto.categoria.is_(None), func.trim(Producto.categoria) == ''))
            else:
                q = q.filter(Producto.categoria == cat_f)

        sub_f = _norm_txt(filtros.get('subcategoria'))
        if sub_f:
            if sub_f == 'Sin subcategoría':
                q = q.filter(or_(Producto.subcategoria.is_(None), func.trim(Producto.subcategoria) == ''))
            else:
                q = q.filter(Producto.subcategoria == sub_f)

    qtxt = _norm_txt(filtros.get('q'))
    if qtxt:
        like = f'%{qtxt}%'
        q = q.filter(
            or_(
                Producto.nombre.ilike(like),
                Producto.codigo_barra.ilike(like),
                Producto.codigo_interno.ilike(like),
            )
        )

    pasillo_f = _norm_txt(filtros.get('pasillo'))
    if pasillo_f:
        q = q.filter(func.upper(func.trim(Producto.ubicacion_pasillo)) == pasillo_f.upper())

    solo_stock = filtros.get('solo_con_stock', True)
    if isinstance(solo_stock, str):
        solo_stock = solo_stock.strip().lower() not in ('0', 'false', 'no')

    if solo_stock:
        if mult:
            q = q.filter(
                (func.coalesce(StT.cantidad, 0) + func.coalesce(StB.cantidad, 0)) > 0
            )
        else:
            q = q.filter(func.coalesce(Producto.stock, 0) > 0)

    rows = q.all()
    lineas: list[dict[str, Any]] = []

    base_len = 14
    for row in rows:
        pid = int(row[0])
        nombre = row[1]
        codigo_barra = row[2]
        codigo_interno = row[3]
        categoria = row[4]
        subcategoria = row[5]
        up = row[6]
        ue = row[7]
        un = row[8]
        pc = row[9]
        pv = row[10]
        psd = row[11]
        st_t = row[12]
        st_b = row[13]
        marca_db = row[base_len] if has_marca else ''
        tono_db = row[base_len + (1 if has_marca else 0)] if has_tono else ''

        linea = _linea_valorizada(
            pid=pid,
            nombre=nombre,
            codigo_barra=codigo_barra,
            codigo_interno=codigo_interno,
            categoria=categoria,
            subcategoria=subcategoria,
            ubicacion_pasillo=up,
            ubicacion_estante=ue,
            ubicacion_nivel=un,
            precio_compra=float(pc or 0),
            precio_venta=float(pv or 0),
            precio_venta_sd=float(psd or 0),
            stock_tienda=int(st_t or 0),
            stock_bodega=int(st_b or 0),
            marca_db=marca_db or '',
            tono_db=tono_db or '',
        )
        if solo_stock and linea['stock_total'] <= 0:
            continue
        lineas.append(linea)
    return lineas


def _agg_from_lineas(lineas: list[dict[str, Any]], key_fn, sort_key=None) -> list[dict[str, Any]]:
    buckets: dict[Any, dict[str, Any]] = defaultdict(lambda: {
        'skus': 0,
        'stock_tienda': 0,
        'stock_bodega': 0,
        'stock_total': 0,
        'mercaderia_tienda': 0.0,
        'mercaderia_bodega': 0.0,
        'mercaderia_total': 0.0,
        'capital_tienda': 0.0,
        'capital_bodega': 0.0,
        'capital_total': 0.0,
    })
    for ln in lineas:
        key = key_fn(ln)
        b = buckets[key]
        b['skus'] += 1
        b['stock_tienda'] += ln['stock_tienda']
        b['stock_bodega'] += ln['stock_bodega']
        b['stock_total'] += ln['stock_total']
        b['mercaderia_tienda'] += ln['mercaderia_tienda']
        b['mercaderia_bodega'] += ln['mercaderia_bodega']
        b['mercaderia_total'] += ln['mercaderia_total']
        b['capital_tienda'] += ln['capital_tienda']
        b['capital_bodega'] += ln['capital_bodega']
        b['capital_total'] += ln['capital_total']

    out = []
    for key, b in buckets.items():
        row = {'clave': key, **b}
        row['brecha_total'] = row['capital_total'] - row['mercaderia_total']
        out.append(row)
    sk = sort_key or (lambda r: (-float(r['mercaderia_total']), str(r['clave'])))
    out.sort(key=sk)
    return out


def _totales(lineas: list[dict[str, Any]]) -> dict[str, Any]:
    t = {
        'skus': len(lineas),
        'stock_tienda': 0,
        'stock_bodega': 0,
        'stock_total': 0,
        'mercaderia_tienda': 0.0,
        'mercaderia_bodega': 0.0,
        'mercaderia_total': 0.0,
        'capital_tienda': 0.0,
        'capital_bodega': 0.0,
        'capital_total': 0.0,
        'sin_costo_skus': 0,
    }
    for ln in lineas:
        t['stock_tienda'] += ln['stock_tienda']
        t['stock_bodega'] += ln['stock_bodega']
        t['stock_total'] += ln['stock_total']
        t['mercaderia_tienda'] += ln['mercaderia_tienda']
        t['mercaderia_bodega'] += ln['mercaderia_bodega']
        t['mercaderia_total'] += ln['mercaderia_total']
        t['capital_tienda'] += ln['capital_tienda']
        t['capital_bodega'] += ln['capital_bodega']
        t['capital_total'] += ln['capital_total']
        if ln['sin_costo']:
            t['sin_costo_skus'] += 1
    t['brecha_total'] = t['capital_total'] - t['mercaderia_total']
    if t['mercaderia_total'] > 0:
        t['pct_bodega_mercaderia'] = round(t['mercaderia_bodega'] / t['mercaderia_total'] * 100, 1)
    else:
        t['pct_bodega_mercaderia'] = 0.0
    return t


def _por_categoria_subcategoria(lineas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nested: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'categoria': '',
        'skus': 0,
        'stock_tienda': 0,
        'stock_bodega': 0,
        'mercaderia_total': 0.0,
        'capital_total': 0.0,
        'subcategorias': defaultdict(lambda: {
            'subcategoria': '',
            'skus': 0,
            'stock_tienda': 0,
            'stock_bodega': 0,
            'mercaderia_total': 0.0,
            'capital_total': 0.0,
        }),
    })
    for ln in lineas:
        cat = ln['categoria']
        sub = ln['subcategoria']
        c = nested[cat]
        c['categoria'] = cat
        c['skus'] += 1
        c['stock_tienda'] += ln['stock_tienda']
        c['stock_bodega'] += ln['stock_bodega']
        c['mercaderia_tienda'] = c.get('mercaderia_tienda', 0) + ln['mercaderia_tienda']
        c['mercaderia_bodega'] = c.get('mercaderia_bodega', 0) + ln['mercaderia_bodega']
        c['mercaderia_total'] += ln['mercaderia_total']
        c['capital_total'] += ln['capital_total']
        s = c['subcategorias'][sub]
        s['subcategoria'] = sub
        s['skus'] += 1
        s['stock_tienda'] += ln['stock_tienda']
        s['stock_bodega'] += ln['stock_bodega']
        s['mercaderia_tienda'] = s.get('mercaderia_tienda', 0) + ln['mercaderia_tienda']
        s['mercaderia_bodega'] = s.get('mercaderia_bodega', 0) + ln['mercaderia_bodega']
        s['mercaderia_total'] += ln['mercaderia_total']
        s['capital_total'] += ln['capital_total']

    filas = []
    for cat, c in nested.items():
        subs = list(c['subcategorias'].values())
        subs.sort(key=lambda r: (-float(r['mercaderia_total']), r['subcategoria']))
        for s in subs:
            s['brecha_total'] = s['capital_total'] - s['mercaderia_total']
        filas.append({
            'categoria': cat,
            'skus': c['skus'],
            'stock_tienda': c['stock_tienda'],
            'stock_bodega': c['stock_bodega'],
            'mercaderia_tienda': c.get('mercaderia_tienda', 0),
            'mercaderia_bodega': c.get('mercaderia_bodega', 0),
            'mercaderia_total': c['mercaderia_total'],
            'capital_total': c['capital_total'],
            'brecha_total': c['capital_total'] - c['mercaderia_total'],
            'subcategorias': subs,
        })
    filas.sort(key=lambda r: (-float(r['mercaderia_total']), r['categoria']))
    return filas


def _nombres_almacenes() -> tuple[str, str]:
    import app as m

    nom_tienda = 'Tienda'
    nom_bodega = 'Bodega'
    try:
        Almacen = m.Almacen
        tid = m.id_almacen_tienda()
        bid = m.id_almacen_bodega()
        if tid:
            at = Almacen.query.get(int(tid))
            if at:
                nom_tienda = (_norm_txt(at.nombre) or _norm_txt(at.codigo) or nom_tienda)
        if bid:
            ab = Almacen.query.get(int(bid))
            if ab:
                nom_bodega = (_norm_txt(ab.nombre) or _norm_txt(ab.codigo) or nom_bodega)
    except Exception:
        pass
    return nom_tienda, nom_bodega


def generar_informe_stock_valorizado(filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    """Informe completo para pantalla / export."""
    filtros = dict(filtros or {})
    lineas = _fetch_lineas_stock(filtros)
    tot = _totales(lineas)
    nom_tienda, nom_bodega = _nombres_almacenes()

    por_cat_sub = _por_categoria_subcategoria(lineas)
    por_ubicacion = _agg_from_lineas(
        lineas,
        lambda ln: ln['ubicacion'],
        sort_key=lambda r: (-float(r['mercaderia_total']), r['clave']),
    )
    por_pasillo = _agg_from_lineas(
        lineas,
        lambda ln: ln['ubicacion_pasillo'],
        sort_key=lambda r: (-float(r['mercaderia_total']), r['clave']),
    )
    por_marca = _agg_from_lineas(
        lineas,
        lambda ln: ln['marca'],
        sort_key=lambda r: (-float(r['mercaderia_total']), r['clave']),
    )
    por_marca_tono = _agg_from_lineas(
        lineas,
        lambda ln: (ln['marca'], ln['tono_color']),
        sort_key=lambda r: (-float(r['mercaderia_total']), str(r['clave'])),
    )

    dormido = [
        ln for ln in lineas
        if ln['stock_bodega'] > 0 and ln['mercaderia_bodega'] > 0
    ]
    dormido.sort(key=lambda ln: (-float(ln['mercaderia_bodega']), -int(ln['stock_bodega']), ln['nombre'].lower()))
    top_dormido = dormido[:80]

    categorias_opts = sorted({ln['categoria'] for ln in lineas})
    return {
        'totales': tot,
        'por_categoria_subcategoria': por_cat_sub,
        'por_ubicacion': por_ubicacion,
        'por_pasillo': por_pasillo,
        'por_marca': por_marca,
        'por_marca_tono': por_marca_tono,
        'capital_dormido_top': top_dormido,
        'lineas_total': len(lineas),
        'filtros': filtros,
        'meta': {
            'nom_tienda': nom_tienda,
            'nom_bodega': nom_bodega,
            'generado_at': datetime.now(),
            'fmt_mercaderia_total': _fmt_clp(tot['mercaderia_total']),
            'fmt_mercaderia_bodega': _fmt_clp(tot['mercaderia_bodega']),
            'fmt_capital_total': _fmt_clp(tot['capital_total']),
        },
        'categorias_opts': categorias_opts,
    }


def exportar_informe_excel(filtros: dict[str, Any] | None = None) -> bytes:
    """Workbook multi-hoja del informe."""
    import pandas as pd
    import io

    data = generar_informe_stock_valorizado(filtros)
    tot = data['totales']
    meta = data['meta']

    resumen = pd.DataFrame([{
        'SKUs con stock': tot['skus'],
        'Unidades tienda': tot['stock_tienda'],
        'Unidades bodega': tot['stock_bodega'],
        'Mercadería tienda CLP': round(tot['mercaderia_tienda']),
        'Mercadería bodega CLP': round(tot['mercaderia_bodega']),
        'Mercadería total CLP': round(tot['mercaderia_total']),
        'Capital total CLP': round(tot['capital_total']),
        '% mercadería en bodega': tot.get('pct_bodega_mercaderia', 0),
        'Almacén tienda': meta['nom_tienda'],
        'Almacén bodega': meta['nom_bodega'],
    }])

    cat_rows = []
    for c in data['por_categoria_subcategoria']:
        for s in c['subcategorias']:
            cat_rows.append({
                'categoria': c['categoria'],
                'subcategoria': s['subcategoria'],
                'skus': s['skus'],
                'stock_tienda': s['stock_tienda'],
                'stock_bodega': s['stock_bodega'],
                'mercaderia_clp': round(s['mercaderia_total']),
                'capital_clp': round(s['capital_total']),
            })
    df_cat = pd.DataFrame(cat_rows)

    df_ubic = pd.DataFrame([
        {
            'ubicacion': r['clave'],
            'skus': r['skus'],
            'stock_tienda': r['stock_tienda'],
            'stock_bodega': r['stock_bodega'],
            'mercaderia_clp': round(r['mercaderia_total']),
            'capital_clp': round(r['capital_total']),
        }
        for r in data['por_ubicacion']
    ])

    df_marca = pd.DataFrame([
        {
            'marca': r['clave'][0] if isinstance(r['clave'], tuple) else r['clave'],
            'tono_color': r['clave'][1] if isinstance(r['clave'], tuple) else '',
            'skus': r['skus'],
            'stock_bodega': r['stock_bodega'],
            'mercaderia_bodega_clp': round(r['mercaderia_bodega']),
            'mercaderia_total_clp': round(r['mercaderia_total']),
        }
        for r in data['por_marca_tono']
    ])

    df_dormido = pd.DataFrame([
        {
            'codigo': ln['codigo'],
            'nombre': ln['nombre'],
            'categoria': ln['categoria'],
            'subcategoria': ln['subcategoria'],
            'marca': ln['marca'],
            'tono_color': ln['tono_color'],
            'ubicacion': ln['ubicacion'],
            'stock_bodega': ln['stock_bodega'],
            'stock_tienda': ln['stock_tienda'],
            'mercaderia_bodega_clp': round(ln['mercaderia_bodega']),
            'capital_bodega_clp': round(ln['capital_bodega']),
        }
        for ln in data['capital_dormido_top']
    ])

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        resumen.to_excel(writer, index=False, sheet_name='Resumen')
        df_cat.to_excel(writer, index=False, sheet_name='Categoria subcat')
        df_ubic.to_excel(writer, index=False, sheet_name='Ubicacion')
        df_marca.to_excel(writer, index=False, sheet_name='Marca tono')
        df_dormido.to_excel(writer, index=False, sheet_name='Capital dormido')
    bio.seek(0)
    return bio.getvalue()


def listar_categorias_informe() -> list[str]:
    import app as m

    Producto = m.Producto
    rows = (
        m.db.session.query(Producto.categoria)
        .filter(Producto.activo.is_(True))
        .distinct()
        .order_by(Producto.categoria.asc())
        .all()
    )
    out = []
    for (cat,) in rows:
        c = _norm_txt(cat)
        out.append(c if c else 'Sin categoría')
    return sorted(set(out), key=lambda x: x.lower())
