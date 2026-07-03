"""Informe visual de stock — pinturas por categoría, marca y tono/color."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from services.pinturas_compras_remates_service import _fetch_lineas_pinturas
from services.stock_valorizado_informe_service import _fmt_clp, _norm_txt

_CHART_PALETTE = (
    '#f59e0b', '#2563eb', '#16a34a', '#dc2626', '#7c3aed', '#0891b2',
    '#db2777', '#ca8a04', '#059669', '#ea580c', '#4f46e5', '#0d9488',
    '#be123c', '#65a30d', '#9333ea', '#0369a1',
)


def _fmt_num(n: float | int) -> str:
    return f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _agg_dimension(filas: list[dict[str, Any]], key: str, label_key: str | None = None) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'skus': 0,
        'stock_total': 0,
        'stock_tienda': 0,
        'stock_bodega': 0,
        'mercaderia_total': 0.0,
        'capital_total': 0.0,
    })
    for f in filas:
        lbl = _norm_txt(f.get(key), f'Sin {key}')
        b = buckets[lbl]
        b['skus'] += 1
        b['stock_total'] += int(f.get('stock_total') or 0)
        b['stock_tienda'] += int(f.get('stock_tienda') or 0)
        b['stock_bodega'] += int(f.get('stock_bodega') or 0)
        b['mercaderia_total'] += float(f.get('mercaderia_total') or 0)
        b['capital_total'] += float(f.get('capital_total') or 0)
    lk = label_key or key
    rows = []
    for lbl, b in buckets.items():
        rows.append({
            lk: lbl,
            'label': lbl,
            **b,
            'mercaderia_fmt': _fmt_clp(b['mercaderia_total']),
            'capital_fmt': _fmt_clp(b['capital_total']),
        })
    rows.sort(key=lambda r: (-r['stock_total'], r['label'].lower()))
    return rows


def _chart_payload(rows: list[dict[str, Any]], *, value_key: str = 'stock_total', top: int = 12) -> dict[str, Any]:
    slice_rows = rows[:top]
    otros = rows[top:]
    labels = [r['label'] for r in slice_rows]
    values = [int(r.get(value_key) or 0) for r in slice_rows]
    if otros:
        labels.append('Otros')
        values.append(sum(int(r.get(value_key) or 0) for r in otros))
    colors = [_CHART_PALETTE[i % len(_CHART_PALETTE)] for i in range(len(labels))]
    return {'labels': labels, 'values': values, 'colors': colors}


def _generar_insights(
    filas: list[dict[str, Any]],
    totales: dict[str, Any],
    por_categoria: list[dict[str, Any]],
    por_marca: list[dict[str, Any]],
    por_tono: list[dict[str, Any]],
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    if not filas:
        insights.append({
            'tipo': 'info',
            'titulo': 'Sin datos',
            'texto': 'No hay SKU de pinturas con los filtros actuales. Probá incluir productos sin stock o ampliar la búsqueda.',
        })
        return insights

    st_tot = int(totales.get('stock_total') or 0)
    pct_bod = float(totales.get('pct_bodega') or 0)
    if pct_bod >= 55:
        insights.append({
            'tipo': 'warn',
            'titulo': 'Capital en bodega',
            'texto': f'El {pct_bod:.0f}% de las unidades está en bodega ({_fmt_num(totales.get("stock_bodega"))} u). '
            f'Revisá remates o traslado a tienda en tonos de alta rotación.',
        })

    if por_marca and st_tot > 0:
        top_m = por_marca[0]
        pct_m = 100.0 * int(top_m['stock_total']) / st_tot
        if pct_m >= 35:
            insights.append({
                'tipo': 'info',
                'titulo': 'Concentración por marca',
                'texto': f'«{top_m["marca"]}» concentra {pct_m:.0f}% del stock ({_fmt_num(top_m["stock_total"])} u, '
                f'{top_m["skus"]} SKU).',
            })

    sin_marca = sum(1 for f in filas if (f.get('marca') or '').startswith('Sin'))
    if sin_marca >= 3:
        insights.append({
            'tipo': 'tip',
            'titulo': 'Completar marcas',
            'texto': f'{sin_marca} SKU sin marca en maestro. Completar en catálogo mejora compras y este informe.',
        })

    sin_tono = sum(1 for f in filas if (f.get('tono_color') or '').startswith('Sin'))
    if sin_tono >= 3:
        insights.append({
            'tipo': 'tip',
            'titulo': 'Completar tonos',
            'texto': f'{sin_tono} SKU sin tono/color. Usá el campo «Tono» al editar filas en catálogo (Piso y Pared / Pinturas).',
        })

    solo_bodega = [f for f in filas if int(f.get('stock_tienda') or 0) == 0 and int(f.get('stock_bodega') or 0) > 0]
    if len(solo_bodega) >= 5:
        insights.append({
            'tipo': 'warn',
            'titulo': 'Sin exposición en tienda',
            'texto': f'{len(solo_bodega)} referencias con stock solo en bodega. Posible quiebre visual en pasillo de pinturas.',
        })

    if por_categoria:
        top_c = por_categoria[0]
        insights.append({
            'tipo': 'ok',
            'titulo': 'Categoría principal',
            'texto': f'«{top_c["categoria"]}» lidera con {_fmt_num(top_c["stock_total"])} u '
            f'({_fmt_clp(top_c["mercaderia_total"])} a costo).',
        })

    if por_tono:
        tonos_con_stock = [t for t in por_tono if int(t.get('stock_total') or 0) > 0 and not t['tono_color'].startswith('Sin')]
        if tonos_con_stock:
            insights.append({
                'tipo': 'ok',
                'titulo': 'Paleta activa',
                'texto': f'{len(tonos_con_stock)} tonos con stock. El más cargado: «{tonos_con_stock[0]["tono_color"]}» '
                f'({_fmt_num(tonos_con_stock[0]["stock_total"])} u).',
            })

    return insights[:6]


def generar_informe_pinturas_stock(filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    import app as m

    filtros = dict(filtros or {})
    categoria_f = _norm_txt(filtros.get('categoria'))
    marca_f = _norm_txt(filtros.get('marca'))
    tono_f = _norm_txt(filtros.get('tono_color'))
    q = _norm_txt(filtros.get('q'))
    solo_stock = str(filtros.get('solo_con_stock', '1')).lower() in ('1', 'true', 'si', 'yes')

    fetch_filtros: dict[str, Any] = {'solo_con_stock': solo_stock}
    if q:
        fetch_filtros['q'] = q
    if categoria_f:
        fetch_filtros['categoria'] = categoria_f

    lineas = _fetch_lineas_pinturas(fetch_filtros)
    if marca_f:
        lineas = [ln for ln in lineas if ln.get('marca') == marca_f]
    if tono_f:
        lineas = [ln for ln in lineas if ln.get('tono_color') == tono_f]

    por_categoria = _agg_dimension(lineas, 'categoria', 'categoria')
    por_marca = _agg_dimension(lineas, 'marca', 'marca')
    por_tono = _agg_dimension(lineas, 'tono_color', 'tono_color')

    stock_total = sum(int(ln.get('stock_total') or 0) for ln in lineas)
    stock_tienda = sum(int(ln.get('stock_tienda') or 0) for ln in lineas)
    stock_bodega = sum(int(ln.get('stock_bodega') or 0) for ln in lineas)
    mercaderia = sum(float(ln.get('mercaderia_total') or 0) for ln in lineas)
    capital = sum(float(ln.get('capital_total') or 0) for ln in lineas)

    totales = {
        'skus': len(lineas),
        'stock_total': stock_total,
        'stock_tienda': stock_tienda,
        'stock_bodega': stock_bodega,
        'mercaderia_total': mercaderia,
        'capital_total': capital,
        'pct_bodega': round(100.0 * stock_bodega / stock_total, 1) if stock_total else 0.0,
        'pct_tienda': round(100.0 * stock_tienda / stock_total, 1) if stock_total else 0.0,
    }

    nom_tienda = 'Tienda'
    nom_bodega = 'Bodega'
    try:
        aid_t = m.id_almacen_tienda()
        aid_b = m.id_almacen_bodega()
        if aid_t:
            alm_t = m.Almacen.query.get(int(aid_t))
            if alm_t and alm_t.nombre:
                nom_tienda = str(alm_t.nombre)[:40]
        if aid_b:
            alm_b = m.Almacen.query.get(int(aid_b))
            if alm_b and alm_b.nombre:
                nom_bodega = str(alm_b.nombre)[:40]
    except Exception:
        pass

    top_marcas = por_marca[:8]
    charts = {
        'categoria_pie': _chart_payload(por_categoria, value_key='stock_total', top=10),
        'categoria_bar_merc': _chart_payload(por_categoria, value_key='mercaderia_total', top=10),
        'marca_bar': _chart_payload(por_marca, value_key='stock_total', top=10),
        'marca_pie': _chart_payload(por_marca, value_key='stock_total', top=8),
        'tono_pie': _chart_payload(por_tono, value_key='stock_total', top=12),
        'tono_bar': _chart_payload(por_tono, value_key='stock_total', top=12),
        'marca_stacked': {
            'labels': [r['marca'] for r in top_marcas],
            'tienda': [int(r['stock_tienda']) for r in top_marcas],
            'bodega': [int(r['stock_bodega']) for r in top_marcas],
        },
    }

    categorias_opts = sorted({ln.get('categoria') for ln in _fetch_lineas_pinturas({'solo_con_stock': False}) if ln.get('categoria')})
    marcas_opts = sorted({ln.get('marca') for ln in _fetch_lineas_pinturas({'solo_con_stock': False}) if ln.get('marca')})
    tonos_opts = sorted({ln.get('tono_color') for ln in _fetch_lineas_pinturas({'solo_con_stock': False}) if ln.get('tono_color')})
    try:
        from services.catalogo_pinturas_maestro_service import listar_marcas, listar_tonos
        marcas_opts = sorted(set(marcas_opts) | set(listar_marcas(solo_activas=True)), key=str.lower)
        tonos_opts = sorted(set(tonos_opts) | {t['nombre'] for t in listar_tonos(solo_activas=True)}, key=str.lower)
    except Exception:
        pass

    detalle = sorted(lineas, key=lambda r: (-int(r.get('stock_total') or 0), r.get('nombre', '').lower()))[:40]

    return {
        'totales': totales,
        'meta': {
            'generado': datetime.now().strftime('%d-%m-%Y %H:%M'),
            'nom_tienda': nom_tienda,
            'nom_bodega': nom_bodega,
            'fmt_mercaderia': _fmt_clp(mercaderia),
            'fmt_capital': _fmt_clp(capital),
            'fmt_stock': _fmt_num(stock_total),
        },
        'por_categoria': por_categoria,
        'por_marca': por_marca,
        'por_tono': por_tono,
        'charts': charts,
        'insights': _generar_insights(lineas, totales, por_categoria, por_marca, por_tono),
        'detalle': detalle,
        'categorias_opts': categorias_opts,
        'marcas_opts': marcas_opts,
        'tonos_opts': tonos_opts,
    }
