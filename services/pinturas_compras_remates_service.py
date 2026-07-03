"""Sugerido de compras y remates — pinturas por marca, categoría, subcategoría y color."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable

from services.stock_valorizado_informe_service import (
    _fmt_clp,
    _inferir_marca,
    _inferir_tono_color,
    _norm_txt,
)

_PINTURA_KEYWORDS = (
    'PINTUR', 'ESMALTE', 'BARNIZ', 'LATEX', 'LÁTEX', 'ANTICOR', 'ANTIOX',
    'POLIURET', 'THINNER', 'THINER', 'DISOLVENT', 'EPOXI', 'IMPRIM',
    'FONDO', 'GRAFIATO', 'ESMALTE', 'AEROSOL', 'SPRAY', 'ESPRAY',
    'HERRAMIENTA PINT', 'RODILLO', 'BROCHA PINT', 'LATEX',
)

DIAS_VENTAS = 30
DIAS_VENTAS_LARGO = 90
DIAS_COBERTURA_OBJETIVO = 45
STOCK_MIN_TIENDA = 2
SOBRESTOCK_FACTOR = 1.55
REMATE_COBERTURA_DIAS = 100
REMATE_SIN_VENTA_DIAS = 90


def _es_pintura(categoria: str, subcategoria: str, nombre: str) -> bool:
    blob = f'{categoria or ""} {subcategoria or ""} {nombre or ""}'.upper()
    return any(kw in blob for kw in _PINTURA_KEYWORDS)


def _fmt_num(n: float | int) -> str:
    return f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _analizar_sku(
    *,
    ventas_30: float,
    ventas_90: float,
    stock_total: int,
    stock_tienda: int,
    precio_compra: float,
    precio_venta: float,
    dias_ventas: int | None = None,
) -> dict[str, Any]:
    dias_v = max(1, int(dias_ventas or DIAS_VENTAS))
    consumo_dia = ventas_30 / float(dias_v) if ventas_30 > 0 else 0.0
    objetivo = max(STOCK_MIN_TIENDA, int(math.ceil(consumo_dia * DIAS_COBERTURA_OBJETIVO)))
    if consumo_dia <= 0 and stock_tienda < STOCK_MIN_TIENDA and stock_total > 0:
        objetivo = max(objetivo, STOCK_MIN_TIENDA)

    compra_unidades = 0
    if stock_total < objetivo or stock_tienda < STOCK_MIN_TIENDA:
        compra_unidades = max(0, objetivo - stock_total)
        if compra_unidades == 0 and stock_tienda < STOCK_MIN_TIENDA:
            compra_unidades = STOCK_MIN_TIENDA - stock_tienda

    cobertura_dias = (stock_total / consumo_dia) if consumo_dia > 0 else (9999 if stock_total > 0 else 0)
    umbral_sobre = int(math.ceil(objetivo * SOBRESTOCK_FACTOR))
    sobrestock_unidades = max(0, stock_total - umbral_sobre) if stock_total > umbral_sobre else 0

    remate_pct = 0
    remate_unidades = 0
    motivo_remate = ''
    if sobrestock_unidades > 0:
        if ventas_90 <= 0:
            remate_pct = 20
            remate_unidades = stock_total
            motivo_remate = 'Sin venta 90 días'
        elif cobertura_dias >= REMATE_COBERTURA_DIAS:
            remate_pct = 15
            remate_unidades = sobrestock_unidades
            motivo_remate = f'Cobertura {int(cobertura_dias)} días'
        elif cobertura_dias >= 60:
            remate_pct = 10
            remate_unidades = sobrestock_unidades
            motivo_remate = 'Rotación lenta'

    costo = float(precio_compra or 0)
    venta = float(precio_venta or 0)
    return {
        'ventas_30': float(ventas_30),
        'ventas_90': float(ventas_90),
        'consumo_dia': round(consumo_dia, 3),
        'stock_objetivo': objetivo,
        'cobertura_dias': round(cobertura_dias, 1) if cobertura_dias < 9000 else None,
        'compra_unidades': int(compra_unidades),
        'compra_clp': int(compra_unidades * costo),
        'sobrestock_unidades': int(sobrestock_unidades),
        'sobrestock_capital': int(sobrestock_unidades * venta),
        'remate_pct': int(remate_pct),
        'remate_unidades': int(remate_unidades),
        'remate_capital': int(remate_unidades * venta),
        'remate_motivo': motivo_remate,
        'alerta': 'CRITICO' if compra_unidades > 0 and (cobertura_dias or 0) <= 10 else (
            'BAJO' if compra_unidades > 0 else ('REMATE' if remate_unidades > 0 else 'OK')
        ),
    }


def _fetch_ventas_por_producto(dias: int) -> dict[int, float]:
    import app as m

    hoy = datetime.now().date()
    inicio = datetime.combine(hoy - timedelta(days=dias), datetime.min.time())
    fin = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    rows = (
        m.db.session.query(m.DetalleVenta.id_producto, m.db.func.sum(m.DetalleVenta.cantidad))
        .join(m.Venta, m.Venta.id == m.DetalleVenta.id_venta)
        .filter(m.Venta.fecha >= inicio, m.Venta.fecha < fin, m.Venta.estado != 'Abierta')
        .group_by(m.DetalleVenta.id_producto)
        .all()
    )
    return {int(pid): float(qty or 0) for pid, qty in rows if pid}


def _fetch_lineas_pinturas(filtros: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from services.stock_valorizado_informe_service import _fetch_lineas_stock

    filtros = dict(filtros or {})
    filtros.setdefault('solo_con_stock', False)
    lineas = _fetch_lineas_stock(filtros)
    out = []
    for ln in lineas:
        if not _es_pintura(ln.get('categoria', ''), ln.get('subcategoria', ''), ln.get('nombre', '')):
            continue
        ln = dict(ln)
        ln['marca'] = _inferir_marca(ln.get('nombre', ''), ln.get('marca', ''))
        ln['tono_color'] = _inferir_tono_color(ln.get('nombre', ''), ln.get('tono_color', ''))
        out.append(ln)
    return out


def _agg_filas(
    filas: list[dict[str, Any]],
    key_fn: Callable[[dict[str, Any]], tuple],
    label_fn: Callable[[dict[str, Any], tuple], dict[str, str]],
) -> list[dict[str, Any]]:
    buckets: dict[tuple, dict[str, Any]] = defaultdict(lambda: {
        'skus': 0,
        'stock_total': 0,
        'ventas_30': 0.0,
        'ventas_90': 0.0,
        'compra_unidades': 0,
        'compra_clp': 0,
        'sobrestock_unidades': 0,
        'sobrestock_capital': 0,
        'remate_unidades': 0,
        'remate_capital': 0,
        'skus_compra': 0,
        'skus_remate': 0,
    })
    for f in filas:
        key = key_fn(f)
        b = buckets[key]
        b['skus'] += 1
        b['stock_total'] += int(f.get('stock_total') or 0)
        b['ventas_30'] += float(f.get('ventas_30') or 0)
        b['ventas_90'] += float(f.get('ventas_90') or 0)
        b['compra_unidades'] += int(f.get('compra_unidades') or 0)
        b['compra_clp'] += int(f.get('compra_clp') or 0)
        b['sobrestock_unidades'] += int(f.get('sobrestock_unidades') or 0)
        b['sobrestock_capital'] += int(f.get('sobrestock_capital') or 0)
        b['remate_unidades'] += int(f.get('remate_unidades') or 0)
        b['remate_capital'] += int(f.get('remate_capital') or 0)
        if int(f.get('compra_unidades') or 0) > 0:
            b['skus_compra'] += 1
        if int(f.get('remate_unidades') or 0) > 0:
            b['skus_remate'] += 1
        if '_labels' not in b:
            b['_labels'] = label_fn(f, key)

    rows = []
    for key, b in buckets.items():
        lbl = b.pop('_labels', {})
        rows.append({
            'key': key,
            **lbl,
            'skus': b['skus'],
            'stock_total': b['stock_total'],
            'ventas_30': round(b['ventas_30'], 1),
            'ventas_90': round(b['ventas_90'], 1),
            'compra_unidades': b['compra_unidades'],
            'compra_clp': b['compra_clp'],
            'compra_clp_fmt': _fmt_clp(b['compra_clp']),
            'sobrestock_unidades': b['sobrestock_unidades'],
            'sobrestock_capital': b['sobrestock_capital'],
            'sobrestock_capital_fmt': _fmt_clp(b['sobrestock_capital']),
            'remate_unidades': b['remate_unidades'],
            'remate_capital': b['remate_capital'],
            'remate_capital_fmt': _fmt_clp(b['remate_capital']),
            'skus_compra': b['skus_compra'],
            'skus_remate': b['skus_remate'],
        })
    rows.sort(key=lambda r: (-r['compra_clp'], -r['remate_capital'], r.get('marca', '')))
    return rows


def generar_informe_pinturas_compras_remates(filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    filtros = dict(filtros or {})
    solo_compra = str(filtros.get('solo_compra', '')).lower() in ('1', 'true', 'si', 'yes')
    solo_remate = str(filtros.get('solo_remate', '')).lower() in ('1', 'true', 'si', 'yes')
    marca_f = _norm_txt(filtros.get('marca'))

    lineas_base = _fetch_lineas_pinturas(filtros)
    if marca_f and marca_f != 'Todas':
        lineas_base = [ln for ln in lineas_base if ln.get('marca') == marca_f]

    ventas_30 = _fetch_ventas_por_producto(DIAS_VENTAS)
    ventas_90 = _fetch_ventas_por_producto(DIAS_VENTAS_LARGO)

    filas: list[dict[str, Any]] = []
    for ln in lineas_base:
        pid = int(ln['id'])
        v30 = ventas_30.get(pid, 0.0)
        v90 = ventas_90.get(pid, 0.0)
        analisis = _analizar_sku(
            ventas_30=v30,
            ventas_90=v90,
            stock_total=int(ln.get('stock_total') or 0),
            stock_tienda=int(ln.get('stock_tienda') or 0),
            precio_compra=float(ln.get('precio_compra') or 0),
            precio_venta=float(ln.get('precio_venta') or 0),
        )
        if solo_compra and analisis['compra_unidades'] <= 0:
            continue
        if solo_remate and analisis['remate_unidades'] <= 0:
            continue
        fila = {**ln, **analisis}
        fila['ventas_30_fmt'] = _fmt_num(v30)
        fila['ventas_90_fmt'] = _fmt_num(v90)
        filas.append(fila)

    filas.sort(
        key=lambda r: (
            0 if r.get('alerta') == 'CRITICO' else 1 if r.get('alerta') == 'BAJO' else 2,
            -int(r.get('compra_unidades') or 0),
            -int(r.get('remate_capital') or 0),
        )
    )

    por_marca = _agg_filas(
        filas,
        lambda f: (f.get('marca') or 'Sin marca',),
        lambda f, k: {'marca': k[0], 'categoria': '—', 'subcategoria': '—', 'tono_color': '—'},
    )
    por_marca_cat_sub = _agg_filas(
        filas,
        lambda f: (f.get('marca'), f.get('categoria'), f.get('subcategoria')),
        lambda f, k: {
            'marca': k[0],
            'categoria': k[1],
            'subcategoria': k[2],
            'tono_color': '—',
        },
    )
    por_marca_tono = _agg_filas(
        filas,
        lambda f: (f.get('marca'), f.get('categoria'), f.get('subcategoria'), f.get('tono_color')),
        lambda f, k: {
            'marca': k[0],
            'categoria': k[1],
            'subcategoria': k[2],
            'tono_color': k[3],
        },
    )

    compras = [f for f in filas if int(f.get('compra_unidades') or 0) > 0]
    remates = [f for f in filas if int(f.get('remate_unidades') or 0) > 0]

    tot = {
        'skus': len(filas),
        'compra_unidades': sum(int(f.get('compra_unidades') or 0) for f in filas),
        'compra_clp': sum(int(f.get('compra_clp') or 0) for f in filas),
        'sobrestock_unidades': sum(int(f.get('sobrestock_unidades') or 0) for f in filas),
        'remate_skus': len(remates),
        'remate_capital': sum(int(f.get('remate_capital') or 0) for f in filas),
        'skus_critico': sum(1 for f in filas if f.get('alerta') == 'CRITICO'),
    }

    marcas_opts = sorted({ln.get('marca') or 'Sin marca' for ln in _fetch_lineas_pinturas({'solo_con_stock': False})})

    return {
        'meta': {
            'generado': datetime.now().strftime('%d-%m-%Y %H:%M'),
            'dias_ventas': DIAS_VENTAS,
            'dias_ventas_largo': DIAS_VENTAS_LARGO,
            'dias_cobertura_objetivo': DIAS_COBERTURA_OBJETIVO,
            'fmt_compra_clp': _fmt_clp(tot['compra_clp']),
            'fmt_remate_capital': _fmt_clp(tot['remate_capital']),
        },
        'totales': tot,
        'filas': filas,
        'compras': compras,
        'remates': remates,
        'por_marca': por_marca,
        'por_marca_cat_sub': por_marca_cat_sub,
        'por_marca_tono': por_marca_tono,
        'marcas_opts': marcas_opts,
    }
