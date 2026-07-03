"""Centro de Inteligencia de Inventario — agregaciones BI (Fase 1 SD-1)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from services.pinturas_compras_remates_service import (
    DIAS_VENTAS,
    _analizar_sku,
)
from services.stock_valorizado_informe_service import (
    _fetch_lineas_stock,
    _fmt_clp,
    _inferir_marca,
    _norm_txt,
)

_CHART_PALETTE = (
    '#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2',
    '#db2777', '#ca8a04', '#059669', '#ea580c', '#4f46e5', '#0d9488',
)

_ESTADO_OK = 'ok'
_ESTADO_CRITICO = 'critico'
_ESTADO_SIN = 'sin_stock'
_ESTADO_SOBRE = 'sobrestock'

_PERIODO_DIAS = {
    '7d': 7,
    '30d': 30,
    '90d': 90,
    'yoy': 30,
}


def parse_periodo_dias(filtros: dict[str, Any] | None) -> int:
    raw = ((filtros or {}).get('periodo') or '30d').strip().lower()
    return _PERIODO_DIAS.get(raw, 30)


def periodo_trend_label(filtros: dict[str, Any] | None) -> str:
    raw = ((filtros or {}).get('periodo') or '30d').strip().lower()
    if raw == 'yoy':
        return 'vs mismo período año anterior'
    if raw == '7d':
        return 'vs 7d anteriores'
    if raw == '90d':
        return 'vs 90d anteriores'
    return 'vs 30d anterior'


def _bool_filtro(val: Any, *, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('1', 'true', 'si', 'sí', 'yes', 'on')


def _fetch_ventas_por_ids(dias: int, producto_ids: list[int]) -> dict[int, float]:
    """Ventas agregadas solo para los SKU del informe (evita scan global)."""
    if not producto_ids:
        return {}
    import app as m

    hoy = datetime.now().date()
    inicio = datetime.combine(hoy - timedelta(days=dias), datetime.min.time())
    fin = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    rows = (
        m.db.session.query(m.DetalleVenta.id_producto, m.db.func.sum(m.DetalleVenta.cantidad))
        .join(m.Venta, m.Venta.id == m.DetalleVenta.id_venta)
        .filter(
            m.Venta.fecha >= inicio,
            m.Venta.fecha < fin,
            m.Venta.estado != 'Abierta',
            m.DetalleVenta.id_producto.in_(producto_ids),
        )
        .group_by(m.DetalleVenta.id_producto)
        .all()
    )
    return {int(pid): float(qty or 0) for pid, qty in rows if pid}


from services.inventario_catalogo_filtro_service import (
    build_fetch_filtros_taxonomia,
    fetch_opts_filtro_catalogo,
)


def _catalogo_contadores(umbral: int) -> dict[str, int]:
    from services.stock_consulta_service import contadores_stock_tienda_activos

    return contadores_stock_tienda_activos(umbral_critico=umbral)


def _fmt_num(n: float | int) -> str:
    return f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _chart_payload(rows: list[dict[str, Any]], *, label_key: str, value_key: str, top: int = 10) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda r: float(r.get(value_key) or 0), reverse=True)
    slice_rows = sorted_rows[:top]
    otros = sorted_rows[top:]
    labels = [str(r.get(label_key) or r.get('label') or '—')[:40] for r in slice_rows]
    values = [float(r.get(value_key) or 0) for r in slice_rows]
    if otros:
        labels.append('Otros')
        values.append(sum(float(r.get(value_key) or 0) for r in otros))
    colors = [_CHART_PALETTE[i % len(_CHART_PALETTE)] for i in range(len(labels))]
    return {'labels': labels, 'values': values, 'colors': colors}


def _classificar_estado_tienda(st_tienda: int, umbral: int, sobrestock_u: int) -> str:
    if sobrestock_u > 0:
        return _ESTADO_SOBRE
    if st_tienda <= 0:
        return _ESTADO_SIN
    if st_tienda <= umbral:
        return _ESTADO_CRITICO
    return _ESTADO_OK


def _enrich_lineas(
    lineas: list[dict[str, Any]],
    *,
    umbral: int,
    ventas_30: dict[int, float],
    ventas_90: dict[int, float],
    dias_ventas: int = 30,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln in lineas:
        pid = int(ln['id'])
        v30 = float(ventas_30.get(pid, 0) or 0)
        v90 = float(ventas_90.get(pid, 0) or 0)
        analisis = _analizar_sku(
            ventas_30=v30,
            ventas_90=v90,
            stock_total=int(ln.get('stock_total') or 0),
            stock_tienda=int(ln.get('stock_tienda') or 0),
            precio_compra=float(ln.get('precio_compra') or 0),
            precio_venta=float(ln.get('precio_venta') or 0),
            dias_ventas=dias_ventas,
        )
        marca = _inferir_marca(ln.get('nombre', ''), ln.get('marca', ''))
        st_t = int(ln.get('stock_tienda') or 0)
        sob_u = int(analisis.get('sobrestock_unidades') or 0)
        estado = _classificar_estado_tienda(st_t, umbral, sob_u)
        cob = analisis.get('cobertura_dias')
        inmov = float(ln.get('mercaderia_bodega') or 0) if (
            int(ln.get('stock_bodega') or 0) > 0 and (v90 <= 0 or (cob and float(cob) >= 90))
        ) else 0.0
        row = {
            **ln,
            'marca': marca,
            'ventas_30': v30,
            'ventas_90': v90,
            'estado': estado,
            'cobertura_dias': cob,
            'sobrestock_unidades': sob_u,
            'compra_unidades': int(analisis.get('compra_unidades') or 0),
            'capital_inmovilizado': inmov,
            'rotacion_mes': round(v30, 1),
        }
        out.append(row)
    return out


def _filter_lineas(lineas: list[dict[str, Any]], filtros: dict[str, Any], umbral: int) -> list[dict[str, Any]]:
    marca_f = _norm_txt(filtros.get('marca'))
    estado_f = _norm_txt(filtros.get('estado')).lower()
    deposito_f = _norm_txt(filtros.get('deposito')).lower()
    solo_stock = _bool_filtro(filtros.get('solo_con_stock'), default=True)

    out = []
    for ln in lineas:
        if solo_stock and int(ln.get('stock_total') or 0) <= 0:
            continue
        if marca_f and _norm_txt(ln.get('marca')) != marca_f:
            continue
        if estado_f and ln.get('estado') != estado_f:
            continue
        if deposito_f == 'tienda' and int(ln.get('stock_tienda') or 0) <= 0:
            continue
        if deposito_f == 'bodega' and int(ln.get('stock_bodega') or 0) <= 0:
            continue
        out.append(ln)
    return out


def _agg_por_categoria(lineas: list[dict[str, Any]], umbral: int) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'categoria': '',
        'skus': 0,
        'ok': 0,
        'critico': 0,
        'sin_stock': 0,
        'sobrestock': 0,
        'mercaderia_total': 0.0,
        'mercaderia_tienda': 0.0,
        'mercaderia_bodega': 0.0,
        'capital_total': 0.0,
        'ventas_30': 0.0,
        'stock_tienda': 0,
        'stock_bodega': 0,
    })
    for ln in lineas:
        cat = _norm_txt(ln.get('categoria'), 'Sin categoría')
        b = buckets[cat]
        b['categoria'] = cat
        b['skus'] += 1
        b['mercaderia_total'] += float(ln.get('mercaderia_total') or 0)
        b['mercaderia_tienda'] += float(ln.get('mercaderia_tienda') or 0)
        b['mercaderia_bodega'] += float(ln.get('mercaderia_bodega') or 0)
        b['capital_total'] += float(ln.get('capital_total') or 0)
        b['ventas_30'] += float(ln.get('ventas_30') or 0)
        b['stock_tienda'] += int(ln.get('stock_tienda') or 0)
        b['stock_bodega'] += int(ln.get('stock_bodega') or 0)
        est = ln.get('estado')
        if est == _ESTADO_OK:
            b['ok'] += 1
        elif est == _ESTADO_CRITICO:
            b['critico'] += 1
        elif est == _ESTADO_SIN:
            b['sin_stock'] += 1
        elif est == _ESTADO_SOBRE:
            b['sobrestock'] += 1
    rows = list(buckets.values())
    rows.sort(key=lambda r: (-r['mercaderia_total'], r['categoria'].lower()))
    return rows


def _agg_por_subcategoria(lineas: list[dict[str, Any]], umbral: int) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'subcategoria': '',
        'skus': 0,
        'mercaderia_total': 0.0,
        'mercaderia_tienda': 0.0,
        'mercaderia_bodega': 0.0,
    })
    for ln in lineas:
        sub = _norm_txt(ln.get('subcategoria'), 'Sin subcategoría')
        b = buckets[sub]
        b['subcategoria'] = sub
        b['skus'] += 1
        b['mercaderia_total'] += float(ln.get('mercaderia_total') or 0)
        b['mercaderia_tienda'] += float(ln.get('mercaderia_tienda') or 0)
        b['mercaderia_bodega'] += float(ln.get('mercaderia_bodega') or 0)
    rows = list(buckets.values())
    rows.sort(key=lambda r: (-r['mercaderia_total'], r['subcategoria'].lower()))
    return rows


def _categoria_filtro_activo(filtros: dict[str, Any]) -> str | None:
    modo = filtros.get('categoria_modo') or ''
    nombre = (filtros.get('categoria') or '').strip()
    if modo in ('catalog', 'legacy') and nombre:
        return nombre
    return None


def _subcategoria_filtro_activo(filtros: dict[str, Any]) -> bool:
    if filtros.get('subcategoria_catalogo_id'):
        return True
    sub = (filtros.get('subcategoria') or '').strip()
    return bool(sub)


def _build_valor_mercaderia_bar(
    lineas: list[dict[str, Any]],
    por_cat: list[dict[str, Any]],
    filtros: dict[str, Any],
    *,
    umbral: int,
) -> dict[str, Any]:
    cat_filtro = _categoria_filtro_activo(filtros)
    if cat_filtro and not _subcategoria_filtro_activo(filtros):
        por_sub = _agg_por_subcategoria(lineas, umbral)
        top_merc = [
            {
                'categoria': r['subcategoria'],
                'label': r['subcategoria'],
                'mercaderia_total': r['mercaderia_total'],
            }
            for r in por_sub
        ]
        payload = _chart_payload(
            top_merc,
            label_key='categoria',
            value_key='mercaderia_total',
            top=5,
        )
        payload['drill'] = 'subcategoria'
        payload['parent'] = cat_filtro
        return payload

    top_cat_merc = [
        {
            'categoria': r['categoria'],
            'label': r['categoria'],
            'mercaderia_total': r['mercaderia_total'],
        }
        for r in por_cat
    ]
    payload = _chart_payload(
        top_cat_merc,
        label_key='categoria',
        value_key='mercaderia_total',
        top=10,
    )
    payload['drill'] = 'categoria'
    return payload


def _calc_kpis(lineas: list[dict[str, Any]], umbral: int) -> dict[str, Any]:
    n = len(lineas)
    sin_stock = sum(1 for ln in lineas if ln.get('estado') == _ESTADO_SIN)
    critico = sum(1 for ln in lineas if ln.get('estado') == _ESTADO_CRITICO)
    sobrestock = sum(1 for ln in lineas if ln.get('estado') == _ESTADO_SOBRE)
    con_stock = n - sin_stock
    mercaderia = sum(float(ln.get('mercaderia_total') or 0) for ln in lineas)
    capital = sum(float(ln.get('capital_total') or 0) for ln in lineas)
    inmov = sum(float(ln.get('capital_inmovilizado') or 0) for ln in lineas)
    compra_u = sum(int(ln.get('compra_unidades') or 0) for ln in lineas)

    cob_vals = [
        float(ln['cobertura_dias'])
        for ln in lineas
        if ln.get('cobertura_dias') is not None and float(ln['cobertura_dias']) < 9000
    ]
    cob_prom = round(sum(cob_vals) / len(cob_vals), 1) if cob_vals else None

    st_sum = sum(int(ln.get('stock_tienda') or 0) for ln in lineas)
    v30_sum = sum(float(ln.get('ventas_30') or 0) for ln in lineas)
    rotacion = round(v30_sum / max(st_sum, 1), 2) if st_sum > 0 else 0.0

    nivel_servicio = round(100.0 * con_stock / n, 1) if n else 0.0

    return {
        'sku_activos': n,
        'sin_stock': sin_stock,
        'critico': critico,
        'sobrestock': sobrestock,
        'con_stock': con_stock,
        'mercaderia_clp': mercaderia,
        'capital_clp': capital,
        'capital_inmovilizado_clp': inmov,
        'cobertura_promedio_dias': cob_prom,
        'rotacion_mes': rotacion,
        'nivel_servicio_pct': nivel_servicio,
        'compra_sugerida_unidades': compra_u,
        'umbral_critico': umbral,
    }


def _riesgo_sku_clp(ln: dict[str, Any], *, dias_riesgo: int = 7) -> float:
    if ln.get('estado') not in (_ESTADO_CRITICO, _ESTADO_SIN):
        return 0.0
    v30 = float(ln.get('ventas_30') or 0)
    pv = float(ln.get('precio_venta') or 0)
    if v30 > 0 and pv > 0:
        return (v30 / 30.0) * dias_riesgo * pv
    if pv > 0:
        return pv * 0.05 * dias_riesgo
    return 0.0


def _trend_ventas(
    lineas: list[dict[str, Any]],
    dias: int = 30,
    *,
    modo_yoy: bool = False,
) -> dict[str, Any]:
    """Variación ventas unidades período actual vs anterior (o YoY)."""
    import app as m

    if not lineas:
        return {'pct': None, 'actual': 0.0, 'anterior': 0.0}
    pids = {int(ln['id']) for ln in lineas}
    hoy = datetime.now().date()
    fin = datetime.combine(hoy + timedelta(days=1), datetime.min.time())

    if modo_yoy:
        ini_act = datetime.combine(hoy - timedelta(days=dias), datetime.min.time())
        ini_ant = datetime.combine(hoy - timedelta(days=365 + dias), datetime.min.time())
        fin_ant = datetime.combine(hoy - timedelta(days=365), datetime.min.time())
    else:
        ini_act = datetime.combine(hoy - timedelta(days=dias), datetime.min.time())
        ini_ant = datetime.combine(hoy - timedelta(days=dias * 2), datetime.min.time())
        fin_ant = ini_act

    def _sum_range(dt_i, dt_f):
        rows = (
            m.db.session.query(m.DetalleVenta.id_producto, m.db.func.sum(m.DetalleVenta.cantidad))
            .join(m.Venta, m.Venta.id == m.DetalleVenta.id_venta)
            .filter(
                m.Venta.fecha >= dt_i,
                m.Venta.fecha < dt_f,
                m.Venta.estado != 'Abierta',
                m.DetalleVenta.id_producto.in_(pids),
            )
            .group_by(m.DetalleVenta.id_producto)
            .all()
        )
        return sum(float(q or 0) for _, q in rows)

    actual = _sum_range(ini_act, fin)
    anterior = _sum_range(ini_ant, fin_ant)
    pct = None
    if anterior > 0:
        pct = round(((actual - anterior) / anterior) * 100.0, 1)
    return {'pct': pct, 'actual': actual, 'anterior': anterior}


def _generar_insights(lineas: list[dict[str, Any]], kpis: dict[str, Any], por_cat: list[dict[str, Any]]) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    if not lineas:
        insights.append({
            'tipo': 'info',
            'titulo': 'Sin datos',
            'texto': 'No hay SKU con los filtros actuales. Probá ampliar categoría o incluir productos sin stock.',
        })
        return insights

    n = int(kpis.get('sku_activos') or 0)
    sin = int(kpis.get('sin_stock') or 0)
    if n and sin / n >= 0.5:
        insights.append({
            'tipo': 'danger',
            'titulo': 'Quiebre masivo en tienda',
            'texto': f'{_fmt_num(sin)} SKU ({round(100*sin/n)}%) sin stock en tienda. Priorizá reposición bodega→tienda.',
        })

    crit = int(kpis.get('critico') or 0)
    if crit > 0:
        insights.append({
            'tipo': 'warn',
            'titulo': 'Stock crítico',
            'texto': f'{_fmt_num(crit)} SKU con stock ≤ {kpis.get("umbral_critico")} unidades en tienda.',
        })

    inmov = float(kpis.get('capital_inmovilizado_clp') or 0)
    if inmov > 0:
        top_inmov = sorted(lineas, key=lambda x: float(x.get('capital_inmovilizado') or 0), reverse=True)[:3]
        pct_top = 100.0 * sum(float(x.get('capital_inmovilizado') or 0) for x in top_inmov) / inmov if inmov else 0
        insights.append({
            'tipo': 'danger',
            'titulo': 'Capital inmovilizado',
            'texto': f'{_fmt_clp(inmov)} en bodega lenta o sin venta. Top 3 familias concentran ~{pct_top:.0f}%.',
        })

    if por_cat:
        peor = max(por_cat, key=lambda c: c.get('sin_stock', 0))
        if peor.get('sin_stock', 0) > 5:
            insights.append({
                'tipo': 'warn',
                'titulo': f'Familia «{peor["categoria"][:30]}»',
                'texto': f'{peor["sin_stock"]} SKU sin stock en tienda · mercadería {_fmt_clp(peor["mercaderia_total"])}.',
            })

    compra = int(kpis.get('compra_sugerida_unidades') or 0)
    if compra > 0:
        n_oc = sum(1 for ln in lineas if int(ln.get('compra_unidades') or 0) > 0)
        insights.append({
            'tipo': 'info',
            'titulo': 'Reposición sugerida',
            'texto': f'{n_oc} SKU requieren compra/traslado (~{_fmt_num(compra)} unidades según venta 30d).',
        })

    sob = int(kpis.get('sobrestock') or 0)
    if sob > 0:
        insights.append({
            'tipo': 'info',
            'titulo': 'Sobrestock',
            'texto': f'{_fmt_num(sob)} SKU con exceso vs consumo reciente.',
        })

    ns = float(kpis.get('nivel_servicio_pct') or 0)
    if ns >= 90:
        insights.append({
            'tipo': 'ok',
            'titulo': 'Nivel de servicio',
            'texto': f'{ns:.1f}% de SKU con stock en tienda.',
        })

    return insights[:8]


def _funnel(lineas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _merc(subset: list[dict[str, Any]]) -> float:
        return sum(float(ln.get('mercaderia_total') or 0) for ln in subset)

    total = len(lineas)
    ln_ventas = [ln for ln in lineas if float(ln.get('ventas_30') or 0) > 0]
    ln_bajo = [ln for ln in lineas if ln.get('estado') in (_ESTADO_CRITICO, _ESTADO_SIN)]
    ln_crit = [ln for ln in lineas if ln.get('estado') == _ESTADO_CRITICO]
    ln_sin = [ln for ln in lineas if ln.get('estado') == _ESTADO_SIN]
    ln_compra = [ln for ln in lineas if int(ln.get('compra_unidades') or 0) > 0]
    ln_urg = [
        ln for ln in lineas
        if int(ln.get('compra_unidades') or 0) > 0 and ln.get('estado') == _ESTADO_SIN
    ]
    steps = [
        ('SKU en filtro', lineas, total),
        ('Con ventas período', ln_ventas, len(ln_ventas)),
        ('Bajo / sin stock tienda', ln_bajo, len(ln_bajo)),
        ('Críticos', ln_crit, len(ln_crit)),
        ('Sin stock tienda', ln_sin, len(ln_sin)),
        ('Requieren reposición', ln_compra, len(ln_compra)),
        ('Urgentes (sin stock + compra)', ln_urg, len(ln_urg)),
    ]
    out = []
    for lbl, subset, val in steps:
        monto = _merc(subset)
        out.append({
            'label': lbl,
            'value': val,
            'monto_clp': monto,
            'fmt_monto': _fmt_clp(monto),
        })
    return out


def _chart_riesgo_quiebre(lineas: list[dict[str, Any]], *, top: int = 5) -> dict[str, Any]:
    rows = []
    for ln in lineas:
        riesgo = _riesgo_sku_clp(ln)
        if riesgo <= 0:
            continue
        rows.append({
            'label': (ln.get('nombre') or ln.get('codigo') or 'SKU')[:32],
            'valor': riesgo,
        })
    return _chart_payload(rows, label_key='label', value_key='valor', top=top)


def _rankings(lineas: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    def _row(ln: dict[str, Any]) -> dict[str, Any]:
        return {
            'id': ln['id'],
            'codigo': ln.get('codigo', ''),
            'nombre': (ln.get('nombre') or '')[:70],
            'categoria': ln.get('categoria', ''),
            'stock_tienda': int(ln.get('stock_tienda') or 0),
            'ventas_30': float(ln.get('ventas_30') or 0),
            'cobertura': ln.get('cobertura_dias'),
            'mercaderia': float(ln.get('mercaderia_total') or 0),
            'estado': ln.get('estado'),
        }

    mas_vendidos = sorted(lineas, key=lambda x: float(x.get('ventas_30') or 0), reverse=True)[:20]
    sin_mov = sorted(
        [ln for ln in lineas if float(ln.get('ventas_90') or 0) <= 0 and int(ln.get('stock_total') or 0) > 0],
        key=lambda x: float(x.get('mercaderia_total') or 0),
        reverse=True,
    )[:20]
    criticos = [ln for ln in lineas if ln.get('estado') in (_ESTADO_CRITICO, _ESTADO_SIN)]
    criticos.sort(key=lambda x: (x.get('estado') != _ESTADO_SIN, float(x.get('mercaderia_total') or 0)), reverse=True)
    inmov = sorted(lineas, key=lambda x: float(x.get('capital_inmovilizado') or 0), reverse=True)[:20]

    return {
        'mas_vendidos': [_row(ln) for ln in mas_vendidos if ln.get('ventas_30', 0) > 0],
        'sin_movimiento': [_row(ln) for ln in sin_mov],
        'criticos': [_row(ln) for ln in criticos[:30]],
        'inmovilizado': [_row(ln) for ln in inmov if ln.get('capital_inmovilizado', 0) > 0],
    }


def _tabla_inteligente(lineas: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    """Top filas por impacto: críticos/sin stock primero, luego mercadería."""
    prio = {_ESTADO_SIN: 0, _ESTADO_CRITICO: 1, _ESTADO_SOBRE: 2, _ESTADO_OK: 3}
    sorted_ln = sorted(
        lineas,
        key=lambda x: (
            prio.get(x.get('estado'), 9),
            -float(x.get('mercaderia_total') or 0),
        ),
    )
    rows = []
    for ln in sorted_ln[:limit]:
        rows.append({
            'id': ln['id'],
            'codigo': ln.get('codigo', ''),
            'nombre': (ln.get('nombre') or '')[:80],
            'stock_tienda': int(ln.get('stock_tienda') or 0),
            'stock_bodega': int(ln.get('stock_bodega') or 0),
            'cobertura': ln.get('cobertura_dias'),
            'rotacion_mes': ln.get('rotacion_mes'),
            'mercaderia_fmt': _fmt_clp(ln.get('mercaderia_total')),
            'ventas_30': float(ln.get('ventas_30') or 0),
            'categoria': ln.get('categoria', ''),
            'marca': ln.get('marca', ''),
            'estado': ln.get('estado'),
        })
    return rows


def _opts_from_lineas(lineas: list[dict[str, Any]]) -> dict[str, list[str]]:
    cats, subs, marcas = set(), set(), set()
    for ln in lineas:
        cats.add(_norm_txt(ln.get('categoria'), 'Sin categoría'))
        subs.add(_norm_txt(ln.get('subcategoria'), 'Sin subcategoría'))
        m = _norm_txt(ln.get('marca'))
        if m:
            marcas.add(m)
    return {
        'categorias': sorted(cats, key=str.lower),
        'subcategorias': sorted(subs, key=str.lower),
        'marcas': sorted(marcas, key=str.lower),
    }


def collect_inventario_bi_centro(filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    """Payload completo para Centro de Inteligencia de Inventario."""
    import app as m

    filtros = dict(filtros or {})
    umbral = max(1, min(int(filtros.get('umbral') or filtros.get('umbral_critico') or 5), 50))
    solo_stock = _bool_filtro(filtros.get('solo_con_stock'), default=True)
    dias_periodo = parse_periodo_dias(filtros)
    modo_yoy = ((filtros.get('periodo') or '').strip().lower() == 'yoy')

    fetch_f = build_fetch_filtros_taxonomia(filtros, extra_keys=('q',))
    fetch_f['solo_con_stock'] = solo_stock

    lineas_raw = _fetch_lineas_stock(fetch_f)
    pids = [int(ln['id']) for ln in lineas_raw]
    ventas_period = _fetch_ventas_por_ids(dias_periodo, pids)
    ventas_90 = _fetch_ventas_por_ids(90, pids)
    lineas_all = _enrich_lineas(
        lineas_raw,
        umbral=umbral,
        ventas_30=ventas_period,
        ventas_90=ventas_90,
        dias_ventas=dias_periodo,
    )
    opts = fetch_opts_filtro_catalogo(filtros)
    lineas = _filter_lineas(lineas_all, filtros, umbral)
    catalogo = _catalogo_contadores(umbral)

    kpis = _calc_kpis(lineas, umbral)
    trend = _trend_ventas(lineas, dias_periodo, modo_yoy=modo_yoy)
    trend_label = periodo_trend_label(filtros)
    por_cat = _agg_por_categoria(lineas, umbral)

    merc_tienda = sum(float(ln.get('mercaderia_tienda') or 0) for ln in lineas)
    merc_bodega = sum(float(ln.get('mercaderia_bodega') or 0) for ln in lineas)

    estado_counts = {
        'ok': sum(1 for ln in lineas if ln.get('estado') == _ESTADO_OK),
        'critico': sum(1 for ln in lineas if ln.get('estado') == _ESTADO_CRITICO),
        'sin_stock': sum(1 for ln in lineas if ln.get('estado') == _ESTADO_SIN),
        'sobrestock': sum(1 for ln in lineas if ln.get('estado') == _ESTADO_SOBRE),
    }

    charts = {
        'valor_categoria_bar': _build_valor_mercaderia_bar(lineas, por_cat, filtros, umbral=umbral),
        'estado_pie': {
            'labels': ['Con stock OK', 'Crítico', 'Sin stock tienda', 'Sobrestock'],
            'values': [
                estado_counts['ok'],
                estado_counts['critico'],
                estado_counts['sin_stock'],
                estado_counts['sobrestock'],
            ],
            'colors': ['#16a34a', '#f59e0b', '#dc2626', '#6366f1'],
        },
        'inmovilizado_top': _chart_payload(
            [
                {
                    'label': (ln.get('nombre') or ln.get('codigo') or 'SKU')[:32],
                    'valor': float(ln.get('capital_inmovilizado') or 0),
                }
                for ln in sorted(lineas, key=lambda x: -float(x.get('capital_inmovilizado') or 0))
                if float(ln.get('capital_inmovilizado') or 0) > 0
            ],
            label_key='label',
            value_key='valor',
            top=10,
        ),
        'riesgo_quiebre': _chart_riesgo_quiebre(lineas, top=5),
        'stacked_categoria': {
            'labels': [r['categoria'][:28] for r in por_cat[:10]],
            'ok': [r['ok'] for r in por_cat[:10]],
            'critico': [r['critico'] for r in por_cat[:10]],
            'sin_stock': [r['sin_stock'] for r in por_cat[:10]],
        },
        'deposito_resumen': {
            'labels': [],
            'values': [],
            'fmt_values': [],
        },
    }

    nom_tienda = 'Tienda'
    nom_bodega = 'Bodega'
    try:
        aid_t = m.id_almacen_tienda()
        aid_b = m.id_almacen_bodega()
        if aid_t:
            at = m.db.session.get(m.Almacen, aid_t)
            if at:
                nom_tienda = ((at.nombre or at.codigo or nom_tienda).strip()) or nom_tienda
        if aid_b:
            ab = m.db.session.get(m.Almacen, aid_b)
            if ab:
                nom_bodega = ((ab.nombre or ab.codigo or nom_bodega).strip()) or nom_bodega
    except Exception:
        pass

    charts['deposito_resumen'] = {
        'labels': [nom_tienda, nom_bodega],
        'values': [merc_tienda, merc_bodega],
        'fmt_values': [_fmt_clp(merc_tienda), _fmt_clp(merc_bodega)],
        'colors': ['#2563eb', '#f59e0b'],
    }

    insights = _generar_insights(lineas, kpis, por_cat)

    from services.inventario_bi_decision_service import build_decision_layer

    kpis_fmt = {
        **kpis,
        'fmt_mercaderia': _fmt_clp(kpis['mercaderia_clp']),
        'fmt_capital': _fmt_clp(kpis['capital_clp']),
        'fmt_inmovilizado': _fmt_clp(kpis['capital_inmovilizado_clp']),
        'trend_ventas_pct': trend.get('pct'),
    }
    acciones_urls = filtros.get('_acciones_urls') or {}
    decision = build_decision_layer(
        kpis_fmt,
        lineas,
        por_cat,
        trend,
        umbral=umbral,
        trend_label=trend_label,
        acciones_urls=acciones_urls,
        filtros=filtros,
        periodo_label={
            '7d': '7 días',
            '30d': '30 días',
            '90d': '90 días',
            'yoy': 'vs año anterior',
        }.get((filtros.get('periodo') or '30d').strip().lower(), '30 días'),
    )

    return {
        'kpis': kpis_fmt,
        'kpi_cards': decision['kpi_cards'],
        'salud_inventario': decision['salud_inventario'],
        'recomendaciones': decision['recomendaciones'],
        'acciones': decision['acciones'],
        'charts': charts,
        'insights': insights,
        'por_categoria': por_cat,
        'funnel': _funnel(lineas),
        'rankings': _rankings(lineas),
        'tabla': _tabla_inteligente(lineas),
        'opts': opts,
        'meta': {
            'generado': datetime.now().strftime('%d-%m-%Y %H:%M'),
            'nom_tienda': nom_tienda,
            'nom_bodega': nom_bodega,
            'dias_ventas': DIAS_VENTAS,
            'sku_en_vista': len(lineas),
            'sku_catalogo_activos': int(catalogo.get('total_activos') or 0),
            'sku_catalogo_sin_stock': int(catalogo.get('sin_stock') or 0),
            'solo_con_stock': solo_stock,
            'tooltips': decision['meta_tooltips'],
            'periodo': filtros.get('periodo') or '30d',
            'periodo_dias': dias_periodo,
            'periodo_label': {
                '7d': '7 días',
                '30d': '30 días',
                '90d': '90 días',
                'yoy': 'vs año anterior',
            }.get((filtros.get('periodo') or '30d').strip().lower(), '30 días'),
        },
        'filtros_aplicados': filtros,
    }
