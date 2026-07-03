"""Capa de decisiones — Centro de stock (KPI enriquecidos, salud, recomendaciones)."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from urllib.parse import urlencode

from services.stock_valorizado_informe_service import _fmt_clp, _norm_txt

_META_NIVEL_SERVICIO = 97.0
_META_NIVEL_WARN = 95.0
_COBERTURA_IDEAL_MIN = 30
_COBERTURA_IDEAL_MAX = 90
_COBERTURA_NARANJA = 180

_ESTADO_OK = 'ok'
_ESTADO_CRITICO = 'critico'
_ESTADO_SIN = 'sin_stock'
_ESTADO_SOBRE = 'sobrestock'


def _fmt_num(n: float | int) -> str:
    return f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _fmt_trend(pct: float | None, *, label: str = 'vs 30d anterior') -> dict[str, Any] | None:
    if pct is None:
        return None
    return {
        'pct': abs(pct),
        'dir': 'up' if pct >= 0 else 'down',
        'label': label,
        'raw': pct,
    }


def _eval_nivel_servicio(pct: float) -> str:
    if pct >= _META_NIVEL_SERVICIO:
        return 'ok'
    if pct >= _META_NIVEL_WARN:
        return 'warn'
    return 'danger'


def _eval_cobertura(dias: float | None) -> str:
    if dias is None:
        return 'info'
    if _COBERTURA_IDEAL_MIN <= dias <= _COBERTURA_IDEAL_MAX:
        return 'ok'
    if dias <= _COBERTURA_NARANJA:
        return 'warn'
    return 'danger'


def _eval_rotacion(rot: float) -> tuple[str, str]:
    if rot >= 0.5:
        return 'ok', 'Alta'
    if rot >= 0.15:
        return 'ok', 'Normal'
    if rot >= 0.05:
        return 'warn', 'Baja'
    return 'danger', 'Muy baja'


def _eval_inmov_pct(pct: float) -> str:
    if pct <= 15:
        return 'ok'
    if pct <= 30:
        return 'warn'
    return 'danger'


def _riesgo_ventas_clp(lineas: list[dict[str, Any]], *, dias_riesgo: int = 7) -> float:
    total = 0.0
    for ln in lineas:
        if ln.get('estado') not in (_ESTADO_CRITICO, _ESTADO_SIN):
            continue
        v30 = float(ln.get('ventas_30') or 0)
        pv = float(ln.get('precio_venta') or 0)
        if v30 > 0 and pv > 0:
            total += (v30 / 30.0) * dias_riesgo * pv
        elif pv > 0:
            total += pv * 0.05 * dias_riesgo
    return total


def _compra_clp(lineas: list[dict[str, Any]]) -> float:
    return sum(
        int(ln.get('compra_unidades') or 0) * float(ln.get('precio_compra') or 0)
        for ln in lineas
    )


def _capital_cobertura_exceso(lineas: list[dict[str, Any]]) -> float:
    total = 0.0
    for ln in lineas:
        cob = ln.get('cobertura_dias')
        if cob is None or float(cob) <= _COBERTURA_IDEAL_MAX:
            continue
        total += float(ln.get('mercaderia_total') or 0)
    return total


def _top_familias_inmov(lineas: list[dict[str, Any]], top_n: int = 3) -> list[dict[str, Any]]:
    buckets: dict[str, float] = defaultdict(float)
    for ln in lineas:
        v = float(ln.get('capital_inmovilizado') or 0)
        if v <= 0:
            continue
        cat = _norm_txt(ln.get('categoria'), 'Sin categoría')
        buckets[cat] += v
    rows = sorted(buckets.items(), key=lambda x: -x[1])
    total = sum(v for _, v in rows) or 1.0
    return [
        {'nombre': name, 'valor': val, 'pct': round(100.0 * val / total, 0)}
        for name, val in rows[:top_n]
    ]


def _tooltips() -> dict[str, dict[str, str]]:
    return {
        'valor_inventario': {
            'calculo': 'Suma del costo × stock (tienda + bodega) de los SKU en vista.',
            'significado': 'Capital total inmovilizado en mercadería a costo.',
            'rango': 'Monitorear tendencia; alzas sin ventas sugieren exceso.',
            'accion': 'Revisar familias con mayor peso y rotación baja.',
        },
        'capital_inmovilizado': {
            'calculo': 'Valor en bodega de SKU con baja venta o cobertura ≥ 90 días.',
            'significado': 'Dinero estancado difícil de recuperar pronto.',
            'rango': 'Ideal < 15% del inventario total.',
            'accion': 'Liquidar, transferir o reducir compras en esas familias.',
        },
        'nivel_servicio': {
            'calculo': 'SKU con stock en tienda ÷ SKU en vista × 100.',
            'significado': 'Disponibilidad en anaquel para el cliente.',
            'rango': 'Verde > 97%, amarillo 95–97%, rojo < 95%.',
            'accion': 'Priorizar reposición de críticos y sin stock.',
        },
        'sin_stock': {
            'calculo': 'SKU con cero unidades en tienda (puede haber en bodega).',
            'significado': 'Quiebre de anaquel; venta perdida inmediata.',
            'rango': 'Meta operativa: 0 críticos recurrentes.',
            'accion': 'Transferir desde bodega o comprar según prioridad.',
        },
        'sku_vista': {
            'calculo': 'Cantidad de SKU que cumplen los filtros activos.',
            'significado': 'Universo analizado en este informe.',
            'rango': 'Usar «solo con stock» para análisis operativo.',
            'accion': 'Acotar por categoría para drill-down.',
        },
        'cobertura': {
            'calculo': 'Stock tienda ÷ venta diaria promedio (30 días).',
            'significado': 'Días de venta cubiertos sin reponer.',
            'rango': 'Ideal 30–90 días; > 180 días es exceso.',
            'accion': 'Reducir compras o promover liquidación si hay exceso.',
        },
        'rotacion': {
            'calculo': 'Unidades vendidas 30d ÷ stock total tienda.',
            'significado': 'Velocidad de salida del inventario en anaquel.',
            'rango': 'Alta ≥ 0,5 · Normal 0,15–0,5 · Muy baja < 0,05.',
            'accion': 'Revisar precio, exhibición o eliminar SKU muerto.',
        },
        'reposicion': {
            'calculo': 'Unidades sugeridas según venta 30d y stock actual.',
            'significado': 'Compra o traslado recomendado para no quiebrar.',
            'rango': 'Priorizar sin stock y críticos con venta reciente.',
            'accion': 'Ir a Acciones o crear orden de compra.',
        },
    }


def _tooltip_title(tip: dict[str, str]) -> str:
    return (
        f"Cálculo: {tip['calculo']}\n"
        f"Significado: {tip['significado']}\n"
        f"Rango: {tip['rango']}\n"
        f"Acción: {tip['accion']}"
    )


def _ia_slot() -> dict[str, Any]:
    return {'recomendacion': None, 'prediccion': None, 'impacto_clp': None, 'simulacion': None}


def build_kpi_cards(
    kpis: dict[str, Any],
    lineas: list[dict[str, Any]],
    *,
    trend: dict[str, Any],
    umbral: int,
    trend_label: str = 'vs 30d anterior',
    periodo_label: str = '30 días',
) -> dict[str, dict[str, Any]]:
    tips = _tooltips()
    merc = float(kpis.get('mercaderia_clp') or 0)
    inmov = float(kpis.get('capital_inmovilizado_clp') or 0)
    inmov_pct = round(100.0 * inmov / merc, 1) if merc > 0 else 0.0
    familias = _top_familias_inmov(lineas)
    fam_pct = sum(f['pct'] for f in familias)
    fam_nombres = ', '.join(f['nombre'][:20] for f in familias)

    ns = float(kpis.get('nivel_servicio_pct') or 0)
    cob = kpis.get('cobertura_promedio_dias')
    cob_f = float(cob) if cob is not None else None
    exceso_d = round(cob_f - _COBERTURA_IDEAL_MAX, 0) if cob_f and cob_f > _COBERTURA_IDEAL_MAX else None
    cap_cob = _capital_cobertura_exceso(lineas)

    rot = float(kpis.get('rotacion_mes') or 0)
    rot_estado, rot_label = _eval_rotacion(rot)
    st_sum = sum(int(ln.get('stock_tienda') or 0) for ln in lineas)
    v30_sum = sum(float(ln.get('ventas_30') or 0) for ln in lineas)
    freq_dias = round(st_sum / (v30_sum / 30.0), 0) if v30_sum > 0 and st_sum > 0 else None

    riesgo = _riesgo_ventas_clp(lineas)
    crit_sin = int(kpis.get('critico') or 0) + int(kpis.get('sin_stock') or 0)
    compra_clp = _compra_clp(lineas)
    compra_u = int(kpis.get('compra_sugerida_unidades') or 0)
    trend_pct = trend.get('pct')

    def _trend_fmt(pct: float | None) -> dict[str, Any] | None:
        if pct is None:
            return None
        return _fmt_trend(pct, label=trend_label)

    inmov_trend = None
    if trend_pct is not None:
        inmov_trend = _fmt_trend(-trend_pct, label=f'proxy actividad {trend_label}')

    def _card(card_id: str, **kwargs: Any) -> dict[str, Any]:
        tip = tips.get(card_id, {})
        ctx = kwargs.pop('contexto', [])
        base = {
            'id': card_id,
            'tooltip': tip,
            'tooltip_title': _tooltip_title(tip) if tip else '',
            'ia': _ia_slot(),
            'contexto': [c for c in ctx if c],
        }
        base.update(kwargs)
        return base

    return {
        'valor_inventario': _card(
            'valor_inventario',
            tier='hero',
            icon='fa-coins',
            label='Valor inventario (costo)',
            valor=kpis.get('fmt_mercaderia', ''),
            valor_raw=merc,
            estado='info',
            tendencia=_trend_fmt(trend_pct),
            contexto=[f'Capital POS {kpis.get("fmt_capital", "")}'],
            meta_objetivo=None,
        ),
        'capital_inmovilizado': _card(
            'capital_inmovilizado',
            tier='hero',
            icon='fa-snowflake',
            label='Capital inmovilizado',
            valor=kpis.get('fmt_inmovilizado', ''),
            valor_raw=inmov,
            estado=_eval_inmov_pct(inmov_pct),
            tendencia=inmov_trend,
            contexto=[
                f'Representa {inmov_pct}% del inventario',
                f'{len(familias)} familias concentran {fam_pct:.0f}%: {fam_nombres}' if familias else 'Sin concentración relevante',
            ],
            meta_objetivo={'valor': 15, 'label': 'Meta: < 15% inventario', 'cumple': inmov_pct <= 15},
        ),
        'nivel_servicio': _card(
            'nivel_servicio',
            tier='hero',
            icon='fa-gauge-high',
            label='Nivel de servicio',
            valor=f'{ns}%',
            valor_raw=ns,
            estado=_eval_nivel_servicio(ns),
            tendencia=None,
            contexto=[f'{kpis.get("con_stock", 0)} SKU con stock en tienda'],
            meta_objetivo={
                'valor': _META_NIVEL_SERVICIO,
                'label': f'Meta: {_META_NIVEL_SERVICIO:.0f}%',
                'cumple': ns >= _META_NIVEL_SERVICIO,
            },
        ),
        'sin_stock': _card(
            'sin_stock',
            tier='hero',
            icon='fa-circle-xmark',
            label='Sin stock en tienda',
            valor=_fmt_num(kpis.get('sin_stock') or 0),
            valor_raw=int(kpis.get('sin_stock') or 0),
            estado='danger' if int(kpis.get('sin_stock') or 0) > 0 else 'ok',
            tendencia=None,
            contexto=[
                f'{kpis.get("critico", 0)} críticos · {kpis.get("sobrestock", 0)} sobrestock',
                f'Riesgo estimado: {_fmt_clp(riesgo)} en ventas potenciales' if riesgo > 0 else 'Sin riesgo cuantificado',
            ],
            meta_objetivo=None,
        ),
        'sku_vista': _card(
            'sku_vista',
            tier='compact',
            icon='fa-boxes-stacked',
            label='SKU en vista',
            valor=_fmt_num(kpis.get('sku_activos') or 0),
            valor_raw=int(kpis.get('sku_activos') or 0),
            estado='info',
            tendencia=None,
            contexto=[],
            meta_objetivo=None,
        ),
        'cobertura': _card(
            'cobertura',
            tier='compact',
            icon='fa-calendar-days',
            label='Cobertura prom.',
            valor=f'{cob_f} d' if cob_f is not None else '—',
            valor_raw=cob_f,
            estado=_eval_cobertura(cob_f),
            tendencia=None,
            contexto=[
                f'Ideal: {_COBERTURA_IDEAL_MIN}–{_COBERTURA_IDEAL_MAX} días',
                f'Exceso: +{int(exceso_d)} días' if exceso_d else None,
                f'Capital asociado: {_fmt_clp(cap_cob)}' if cap_cob > 0 else None,
            ],
            meta_objetivo={
                'valor': _COBERTURA_IDEAL_MAX,
                'label': f'Ideal: {_COBERTURA_IDEAL_MIN}–{_COBERTURA_IDEAL_MAX} d',
                'cumple': cob_f is not None and _COBERTURA_IDEAL_MIN <= cob_f <= _COBERTURA_IDEAL_MAX,
            },
        ),
        'rotacion': _card(
            'rotacion',
            tier='compact',
            icon='fa-arrows-rotate',
            label=f'Rotación ({periodo_label})',
            valor=f'{rot} u',
            valor_raw=rot,
            estado=rot_estado,
            tendencia=_trend_fmt(trend_pct),
            contexto=[
                f'Estado: {rot_label}',
                f'Frecuencia: 1 venta cada {int(freq_dias)} días' if freq_dias else 'Sin ventas recientes',
            ],
            meta_objetivo=None,
        ),
        'reposicion': _card(
            'reposicion',
            tier='compact',
            icon='fa-cart-shopping',
            label='Reposición sug.',
            valor=f'{_fmt_num(compra_u)} u',
            valor_raw=compra_u,
            estado='warn' if compra_u > 0 else 'ok',
            tendencia=None,
            contexto=[f'Compra estimada: {_fmt_clp(compra_clp)}' if compra_clp > 0 else 'Sin reposición pendiente'],
            meta_objetivo=None,
        ),
    }


def _prioridades_operativas(lineas: list[dict[str, Any]], umbral: int) -> dict[str, int]:
    comprar = sum(1 for ln in lineas if int(ln.get('compra_unidades') or 0) > 0)
    transferir = sum(
        1 for ln in lineas
        if ln.get('estado') == _ESTADO_SIN and int(ln.get('stock_bodega') or 0) > 0
    )
    liquidar = sum(
        1 for ln in lineas
        if ln.get('estado') == _ESTADO_SOBRE
        or (float(ln.get('ventas_90') or 0) <= 0 and int(ln.get('stock_total') or 0) > 0
            and float(ln.get('capital_inmovilizado') or 0) > 0)
    )
    return {'comprar': comprar, 'transferir': transferir, 'liquidar': liquidar}


def build_salud_inventario(
    kpi_cards: dict[str, dict[str, Any]],
    kpis: dict[str, Any],
    lineas: list[dict[str, Any]],
    *,
    umbral: int,
) -> dict[str, Any]:
    score = 50
    fortalezas: list[str] = []
    debilidades: list[str] = []

    ns_card = kpi_cards.get('nivel_servicio', {})
    ns = float(kpis.get('nivel_servicio_pct') or 0)
    if ns >= _META_NIVEL_SERVICIO:
        score += 25
        fortalezas.append(f'Nivel de servicio {ns:.1f}% sobre meta {_META_NIVEL_SERVICIO:.0f}%')
    elif ns >= _META_NIVEL_WARN:
        score += 10
        debilidades.append(f'Nivel de servicio {ns:.1f}% cerca del mínimo ({_META_NIVEL_WARN:.0f}%)')
    else:
        score -= 15
        debilidades.append(f'Nivel de servicio crítico: {ns:.1f}%')

    cob_card = kpi_cards.get('cobertura', {})
    cob_est = cob_card.get('estado')
    if cob_est == 'ok':
        score += 15
        fortalezas.append('Cobertura dentro del rango ideal')
    elif cob_est == 'warn':
        score -= 5
        debilidades.append('Cobertura elevada vs ideal')
    elif cob_est == 'danger':
        score -= 20
        debilidades.append('Cobertura excesiva — capital atrapado')

    inmov_card = kpi_cards.get('capital_inmovilizado', {})
    if inmov_card.get('estado') == 'ok':
        score += 15
        fortalezas.append('Capital inmovilizado bajo control')
    elif inmov_card.get('estado') == 'warn':
        score -= 10
        debilidades.append('Capital inmovilizado moderado')
    else:
        score -= 15
        debilidades.append('Capital inmovilizado alto')

    crit = int(kpis.get('critico') or 0) + int(kpis.get('sin_stock') or 0)
    n = max(int(kpis.get('sku_activos') or 0), 1)
    if crit / n < 0.05:
        score += 10
    elif crit / n > 0.2:
        score -= 10
        debilidades.append(f'{crit} SKU críticos o sin stock')

    score = max(0, min(100, score))
    if score >= 85:
        nivel, nivel_label = 'excelente', 'Excelente'
    elif score >= 65:
        nivel, nivel_label = 'buena', 'Buena'
    else:
        nivel, nivel_label = 'riesgo', 'Riesgo'

    pri = _prioridades_operativas(lineas, umbral)
    prioridades = []
    if pri['comprar']:
        prioridades.append({'tipo': 'comprar', 'count': pri['comprar'], 'label': f'Comprar {pri["comprar"]} SKU'})
    if pri['transferir']:
        prioridades.append({'tipo': 'transferir', 'count': pri['transferir'], 'label': f'Transferir {pri["transferir"]} SKU'})
    if pri['liquidar']:
        prioridades.append({'tipo': 'liquidar', 'count': pri['liquidar'], 'label': f'Liquidar {pri["liquidar"]} SKU'})

    return {
        'score': score,
        'nivel': nivel,
        'nivel_label': nivel_label,
        'fortalezas': fortalezas[:4],
        'debilidades': debilidades[:4],
        'prioridades': prioridades,
    }


def generar_recomendaciones(
    lineas: list[dict[str, Any]],
    kpis: dict[str, Any],
    por_cat: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    if not lineas:
        return [{
            'tipo': 'info',
            'titulo': 'Sin datos',
            'texto': 'No hay SKU con los filtros actuales.',
            'accion': 'Ampliá categoría o incluí productos sin stock.',
            'impacto_texto': '',
            'impacto_clp': 0,
            'fmt_impacto': '',
            'prioridad': 5,
            'sku_count': 0,
            'ia': _ia_slot(),
        }]

    n = int(kpis.get('sku_activos') or 0)
    umbral = int(kpis.get('umbral_critico') or 5)
    sin = int(kpis.get('sin_stock') or 0)
    crit = int(kpis.get('critico') or 0)
    crit_total = crit + sin

    if crit_total > 0:
        prio_n = sum(
            1 for ln in lineas
            if int(ln.get('compra_unidades') or 0) > 0
            and ln.get('estado') in (_ESTADO_CRITICO, _ESTADO_SIN)
        )
        prio_n = max(prio_n, min(22, crit_total))
        riesgo = _riesgo_ventas_clp(lineas)
        ns = float(kpis.get('nivel_servicio_pct') or 0)
        ns_est = min(99.0, ns + min(8.0, crit_total * 0.15))
        recs.append({
            'tipo': 'danger' if sin > crit else 'warn',
            'titulo': 'Stock crítico' if crit else 'Sin stock en tienda',
            'texto': f'{_fmt_num(crit_total)} SKU bajo el mínimo operativo (≤ {umbral} u o cero).',
            'accion': f'Generar orden de compra o traslado para {prio_n} SKU prioritarios.',
            'impacto_texto': f'Nivel de servicio estimado ~{ns_est:.0f}%.',
            'impacto_clp': riesgo,
            'fmt_impacto': _fmt_clp(riesgo) if riesgo > 0 else '',
            'prioridad': 1,
            'sku_count': crit_total,
            'ia': _ia_slot(),
        })

    inmov = float(kpis.get('capital_inmovilizado_clp') or 0)
    if inmov > 0:
        familias = _top_familias_inmov(lineas, 3)
        top = familias[0] if familias else None
        libera = round(inmov * 0.2, 0) if top else 0
        fam_txt = ', '.join(f['nombre'][:18] for f in familias)
        pct_top = sum(f['pct'] for f in familias)
        accion = (
            f'Reducir ~20% la próxima compra de «{top["nombre"][:24]}».'
            if top else 'Revisar compras en familias de baja rotación.'
        )
        recs.append({
            'tipo': 'danger',
            'titulo': 'Capital inmovilizado',
            'texto': f'{_fmt_clp(inmov)} en bodega lenta. {len(familias)} familias concentran ~{pct_top:.0f}% ({fam_txt}).',
            'accion': accion,
            'impacto_texto': f'Liberaría aprox. {_fmt_clp(libera)}.' if libera else '',
            'impacto_clp': libera,
            'fmt_impacto': _fmt_clp(libera) if libera else '',
            'prioridad': 2,
            'sku_count': sum(1 for ln in lineas if float(ln.get('capital_inmovilizado') or 0) > 0),
            'ia': _ia_slot(),
        })

    compra_u = int(kpis.get('compra_sugerida_unidades') or 0)
    if compra_u > 0:
        n_oc = sum(1 for ln in lineas if int(ln.get('compra_unidades') or 0) > 0)
        compra_clp = _compra_clp(lineas)
        recs.append({
            'tipo': 'info',
            'titulo': 'Reposición sugerida',
            'texto': f'{n_oc} SKU requieren compra o traslado (~{_fmt_num(compra_u)} unidades).',
            'accion': 'Armar borrador de OC con los SKU de mayor venta 30d.',
            'impacto_texto': f'Inversión estimada {_fmt_clp(compra_clp)}.',
            'impacto_clp': compra_clp,
            'fmt_impacto': _fmt_clp(compra_clp),
            'prioridad': 2,
            'sku_count': n_oc,
            'ia': _ia_slot(),
        })

    sob = int(kpis.get('sobrestock') or 0)
    if sob > 0:
        recs.append({
            'tipo': 'warn',
            'titulo': 'Sobrestock',
            'texto': f'{_fmt_num(sob)} SKU con exceso vs consumo reciente.',
            'accion': 'Evaluar promoción, devolución a bodega o pausa de compra.',
            'impacto_texto': 'Libera espacio en anaquel y mejora rotación.',
            'impacto_clp': 0,
            'fmt_impacto': '',
            'prioridad': 3,
            'sku_count': sob,
            'ia': _ia_slot(),
        })

    if por_cat:
        peor = max(por_cat, key=lambda c: c.get('sin_stock', 0))
        if peor.get('sin_stock', 0) > 3:
            recs.append({
                'tipo': 'warn',
                'titulo': f'Familia «{peor["categoria"][:28]}»',
                'texto': f'{peor["sin_stock"]} SKU sin stock · mercadería {_fmt_clp(peor["mercaderia_total"])}.',
                'accion': 'Filtrar por esta categoría y ejecutar reposición focalizada.',
                'impacto_texto': '',
                'impacto_clp': 0,
                'fmt_impacto': '',
                'prioridad': 3,
                'sku_count': peor['sin_stock'],
                'ia': _ia_slot(),
            })

    ns = float(kpis.get('nivel_servicio_pct') or 0)
    if ns >= _META_NIVEL_SERVICIO and len(recs) < 6:
        recs.append({
            'tipo': 'ok',
            'titulo': 'Nivel de servicio',
            'texto': f'{ns:.1f}% de SKU con stock en tienda.',
            'accion': 'Mantener política de reposición; monitorear críticos.',
            'impacto_texto': f'Sobre meta {_META_NIVEL_SERVICIO:.0f}%.',
            'impacto_clp': 0,
            'fmt_impacto': '',
            'prioridad': 5,
            'sku_count': int(kpis.get('con_stock') or 0),
            'ia': _ia_slot(),
        })

    recs.sort(key=lambda r: r['prioridad'])
    return recs[:8]


def _accion_item(ln: dict[str, Any], *, qty_key: str = 'compra_unidades', monto: float | None = None) -> dict[str, Any]:
    qty = int(ln.get(qty_key) or 0)
    pc = float(ln.get('precio_compra') or 0)
    pv = float(ln.get('precio_venta') or 0)
    m = monto if monto is not None else qty * pc
    return {
        'id': ln['id'],
        'codigo': ln.get('codigo', ''),
        'nombre': (ln.get('nombre') or '')[:70],
        'cantidad': qty,
        'stock_tienda': int(ln.get('stock_tienda') or 0),
        'stock_bodega': int(ln.get('stock_bodega') or 0),
        'monto_clp': m,
        'fmt_monto': _fmt_clp(m),
        'estado': ln.get('estado', ''),
        'categoria': ln.get('categoria', ''),
    }


def _dash_query(filtros: dict[str, Any], **extra: Any) -> str:
    params: dict[str, Any] = {
        'umbral': filtros.get('umbral') or 5,
        'solo_stock_explicit': '1',
        'solo_con_stock': '1' if filtros.get('solo_con_stock', True) else '0',
        'periodo': filtros.get('periodo') or '30d',
    }
    for key in ('q', 'marca', 'deposito', 'estado'):
        val = filtros.get(key)
        if val:
            params[key] = val
    if filtros.get('categoria_param'):
        params['categoria'] = filtros['categoria_param']
    if filtros.get('subcategoria_catalogo_id'):
        params['subcategoria_catalogo_id'] = filtros['subcategoria_catalogo_id']
    elif filtros.get('subcategoria'):
        params['subcategoria'] = filtros['subcategoria']
    params.update({k: v for k, v in extra.items() if v is not None})
    return urlencode(params)


def build_acciones(
    lineas: list[dict[str, Any]],
    *,
    umbral: int,
    urls: dict[str, str],
    filtros: dict[str, Any],
) -> list[dict[str, Any]]:
    """Tarjetas accionables para pestaña Acciones."""
    dash_base = urls.get('dashboard') or '/inventario/dashboard-premium'

    comprar_ln = [
        ln for ln in lineas
        if int(ln.get('compra_unidades') or 0) > 0
    ]
    comprar_ln.sort(
        key=lambda x: (
            x.get('estado') != _ESTADO_SIN,
            x.get('estado') != _ESTADO_CRITICO,
            -int(x.get('compra_unidades') or 0),
        ),
    )
    comprar_items = [_accion_item(ln) for ln in comprar_ln[:12]]
    comprar_monto = sum(i['monto_clp'] for i in comprar_items)

    transferir_ln = [
        ln for ln in lineas
        if ln.get('estado') == _ESTADO_SIN and int(ln.get('stock_bodega') or 0) > 0
    ]
    transferir_ln.sort(key=lambda x: -int(x.get('stock_bodega') or 0))
    transferir_items = [
        _accion_item(ln, qty_key='stock_bodega', monto=float(ln.get('mercaderia_bodega') or 0))
        for ln in transferir_ln[:12]
    ]
    transferir_monto = sum(i['monto_clp'] for i in transferir_items)

    liquidar_ln = [
        ln for ln in lineas
        if ln.get('estado') == _ESTADO_SOBRE
        or (
            float(ln.get('ventas_90') or 0) <= 0
            and int(ln.get('stock_total') or 0) > 0
            and float(ln.get('capital_inmovilizado') or 0) > 0
        )
    ]
    liquidar_ln.sort(key=lambda x: -float(x.get('capital_inmovilizado') or x.get('mercaderia_total') or 0))
    liquidar_items = [
        _accion_item(
            ln,
            qty_key='sobrestock_unidades',
            monto=float(ln.get('capital_inmovilizado') or ln.get('mercaderia_total') or 0),
        )
        for ln in liquidar_ln[:12]
    ]
    liquidar_monto = sum(i['monto_clp'] for i in liquidar_items)

    minimos_ln = [ln for ln in lineas if ln.get('estado') == _ESTADO_CRITICO]
    minimos_ln.sort(key=lambda x: int(x.get('stock_tienda') or 0))
    minimos_items = [_accion_item(ln, qty_key='compra_unidades') for ln in minimos_ln[:12]]
    minimos_monto = sum(i['monto_clp'] for i in minimos_items)

    oc_payload = [
        {'id': ln['id'], 'qty': max(1, int(ln.get('compra_unidades') or 1))}
        for ln in comprar_ln[:25]
    ]
    oc_url = urls.get('orden_compra_nueva') or '/compras/ordenes/nueva'
    if oc_payload:
        oc_url = f'{oc_url}?{urlencode({"sugerencias_payload": json.dumps(oc_payload, separators=(",", ":"))})}'

    def _block(
        tipo: str,
        titulo: str,
        desc: str,
        items: list[dict[str, Any]],
        monto: float,
        ver_extra: dict[str, Any],
        ejecutar_url: str,
        ejecutar_label: str,
        icon: str,
    ) -> dict[str, Any]:
        return {
            'tipo': tipo,
            'titulo': titulo,
            'descripcion': desc,
            'icon': icon,
            'count': len(items),
            'monto_total_clp': monto,
            'fmt_monto': _fmt_clp(monto) if monto > 0 else '',
            'filas': items,
            'ver_url': f'{dash_base}?{_dash_query(filtros, **ver_extra)}',
            'ejecutar_url': ejecutar_url,
            'ejecutar_label': ejecutar_label,
            'ia': _ia_slot(),
        }

    blocks = [
        _block(
            'comprar',
            'Comprar',
            f'Reposición sugerida según ventas y stock (umbral {umbral} u).',
            comprar_items,
            comprar_monto,
            {'vista': 'rankings', 'estado': 'critico'},
            oc_url,
            'Crear OC',
            'fa-cart-shopping',
        ),
        _block(
            'transferir',
            'Transferir',
            'Sin stock en tienda pero con unidades en bodega.',
            transferir_items,
            transferir_monto,
            {'vista': 'rankings', 'estado': 'sin_stock'},
            urls.get('bodega') or '/bodega/plataforma',
            'Ir a bodega',
            'fa-truck-ramp-box',
        ),
        _block(
            'liquidar',
            'Liquidar',
            'Sobrestock o sin movimiento con capital atrapado.',
            liquidar_items,
            liquidar_monto,
            {'vista': 'rankings'},
            urls.get('pinturas_remates') or urls.get('productos') or '/productos',
            'Ver remates',
            'fa-tags',
        ),
        _block(
            'minimos',
            'Actualizar mínimos',
            'SKU en zona crítica recurrente — revisar parámetros.',
            minimos_items,
            minimos_monto,
            {'vista': 'rankings', 'estado': 'critico'},
            urls.get('productos') or '/productos',
            'Abrir catálogo',
            'fa-sliders',
        ),
        _block(
            'crear_oc',
            'Crear OC',
            'Borrador listo con SKU prioritarios del informe.',
            comprar_items[:8],
            comprar_monto,
            {'vista': 'acciones'},
            oc_url,
            'Ejecutar OC',
            'fa-file-circle-plus',
        ),
    ]
    return blocks


def build_decision_layer(
    kpis: dict[str, Any],
    lineas: list[dict[str, Any]],
    por_cat: list[dict[str, Any]],
    trend: dict[str, Any],
    *,
    umbral: int,
    trend_label: str = 'vs 30d anterior',
    acciones_urls: dict[str, str] | None = None,
    filtros: dict[str, Any] | None = None,
    periodo_label: str = '30 días',
) -> dict[str, Any]:
    """Payload Fase 1+2: KPI enriquecidos, salud, recomendaciones, acciones, tooltips."""
    kpi_cards = build_kpi_cards(
        kpis, lineas, trend=trend, umbral=umbral,
        trend_label=trend_label, periodo_label=periodo_label,
    )
    recomendaciones = generar_recomendaciones(lineas, kpis, por_cat)
    salud = build_salud_inventario(kpi_cards, kpis, lineas, umbral=umbral)
    tips = _tooltips()
    acciones = build_acciones(lineas, umbral=umbral, urls=acciones_urls or {}, filtros=filtros or {})
    return {
        'kpi_cards': kpi_cards,
        'salud_inventario': salud,
        'recomendaciones': recomendaciones,
        'acciones': acciones,
        'meta_tooltips': {k: _tooltip_title(v) for k, v in tips.items()},
    }
