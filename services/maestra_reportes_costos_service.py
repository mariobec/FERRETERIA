"""Reportes de impacto — Maestra compras 2024-2026 × ERP."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAESTRA = Path(
    os.getenv(
        'MAESTRA_SD_XLSX',
        r'C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx',
    )
)

_CACHE: dict[str, Any] = {'ts': 0.0, 'payload': None}
_CACHE_TTL = int(os.getenv('MAESTRA_REPORTES_CACHE_SEC', '300'))


def _norm_text(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    return re.sub(r'\s+', ' ', str(x).strip().upper())


def _norm_proveedor(x) -> str:
    return re.sub(r'[^A-Z0-9 ]', '', _norm_text(x))


def _fmt_clp(n: float | int | None) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return '$0'
    return f'${int(round(float(n))):,}'.replace(',', '.')


def resolve_maestra_path() -> Path:
    p = Path(os.getenv('MAESTRA_SD_XLSX', str(DEFAULT_MAESTRA)))
    if p.is_file():
        return p
    alt = ROOT.parent / 'Maestra_Ferreteria_Santo_Domingo.xlsx'
    if alt.is_file():
        return alt
    return p


def load_maestra(path: Path | None = None) -> pd.DataFrame:
    path = path or resolve_maestra_path()
    if not path.is_file():
        raise FileNotFoundError(f'No se encuentra la maestra: {path}')

    df = pd.read_excel(path, sheet_name=0)
    rename: dict[str, str] = {}
    for c in df.columns:
        cl = str(c).lower()
        cla = cl.replace('ó', 'o').replace('í', 'i').replace('é', 'e').replace('á', 'a')
        if cl in ('año', 'ano') or 'año' in cl or cla == 'ano':
            rename[c] = 'anio'
        elif 'razon' in cl and 'proveedor' in cl:
            rename[c] = 'proveedor'
        elif str(c).strip().upper() == 'OC':
            rename[c] = 'oc'
        elif ('codigo' in cla or 'cod' in cla) and 'producto' in cla:
            rename[c] = 'codigo_factura'
        elif 'descrip' in cla and 'producto' in cla:
            rename[c] = 'descripcion'
        elif 'grupo5' in cl:
            rename[c] = 'grupo5'
        elif 'grupo4' in cl:
            rename[c] = 'grupo4'
        elif 'cantidad' in cl:
            rename[c] = 'cantidad'
        elif 'neto' in cl:
            rename[c] = 'neto'
    df = df.rename(columns=rename)
    df['anio'] = pd.to_numeric(df.get('anio'), errors='coerce')
    df = df[df['anio'].between(2024, 2026)]
    df['neto'] = pd.to_numeric(df['neto'], errors='coerce').fillna(0)
    df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce').fillna(0)
    df['costo_u'] = df['neto'] / df['cantidad'].replace(0, pd.NA)
    df['codigo_factura_n'] = df['codigo_factura'].map(_norm_text)
    df['proveedor_n'] = df['proveedor'].map(_norm_proveedor)
    return df


def _load_erp_puentes(app) -> tuple[pd.DataFrame, dict[str, int], dict[tuple[int, str], int]]:
    from app import Producto, ProductoCodigoProveedor, Proveedor, db

    with app.app_context():
        productos = pd.DataFrame(
            [
                {
                    'producto_id': p.id,
                    'nombre_erp': p.nombre,
                    'codigo_barra': p.codigo_barra,
                    'precio_compra': float(p.precio_compra or 0),
                    'precio_venta': float(p.precio_venta or 0),
                    'categoria': p.categoria,
                }
                for p in Producto.query.filter(Producto.activo == True).all()
            ]
        )
        prov_norm: dict[str, int] = {}
        for pr in Proveedor.query.all():
            k = _norm_proveedor(pr.nombre)
            if k and k not in prov_norm:
                prov_norm[k] = int(pr.id)

        puente_map: dict[tuple[int, str], int] = {}
        for row in ProductoCodigoProveedor.query.all():
            k = (int(row.proveedor_id), _norm_text(row.codigo_factura_proveedor))
            if k[1]:
                puente_map[k] = int(row.producto_id)

    return productos, prov_norm, puente_map


def _match_producto_id(
    row: pd.Series,
    prov_norm: dict[str, int],
    puente_map: dict[tuple[int, str], int],
    productos: pd.DataFrame,
) -> int | None:
    pn = row['proveedor_n']
    cf = row['codigo_factura_n']
    pid = prov_norm.get(pn)
    if pid and (pid, cf) in puente_map:
        return puente_map[(pid, cf)]
    if productos.empty:
        return None
    for col in ('codigo_barra',):
        hit = productos[productos[col].map(_norm_text) == cf]
        if len(hit) == 1:
            return int(hit.iloc[0]['producto_id'])
    return None


def build_reports(app, *, umbral_pct: float = 5.0) -> dict[str, Any]:
    path = resolve_maestra_path()
    df = load_maestra(path)
    productos, prov_norm, puente_map = _load_erp_puentes(app)

    # —— Agregado por código factura + proveedor ——
    gcols = ['codigo_factura', 'codigo_factura_n', 'proveedor', 'proveedor_n']
    agg_kw: dict[str, tuple] = {
        'descripcion': ('descripcion', 'last'),
        'neto_total': ('neto', 'sum'),
        'cantidad_total': ('cantidad', 'sum'),
        'ultimo_costo': ('costo_u', 'last'),
        'lineas': ('neto', 'count'),
    }
    if 'grupo5' in df.columns:
        agg_kw['grupo5'] = ('grupo5', 'last')
    agg = df.groupby(gcols, as_index=False).agg(**agg_kw)
    if 'grupo5' not in agg.columns:
        agg['grupo5'] = 'Sin rubro'

    # Cantidad comprada en 2025 (proxy recompra anual)
    c25 = (
        df[df['anio'] == 2025]
        .groupby(['codigo_factura_n', 'proveedor_n'])['cantidad']
        .sum()
        .reset_index(name='cantidad_2025')
    )
    agg = agg.merge(c25, on=['codigo_factura_n', 'proveedor_n'], how='left')
    agg['cantidad_2025'] = agg['cantidad_2025'].fillna(0)

    filas_fuga: list[dict[str, Any]] = []
    for _, row in agg.iterrows():
        pid = _match_producto_id(row, prov_norm, puente_map, productos)
        if not pid:
            continue
        prod = productos[productos['producto_id'] == pid]
        if prod.empty:
            continue
        pr = prod.iloc[0]
        costo_erp = float(pr['precio_compra'] or 0)
        ultimo = float(row['ultimo_costo'] or 0)
        if costo_erp <= 0 or ultimo <= 0:
            continue
        delta_pct = (ultimo - costo_erp) / costo_erp * 100.0
        if delta_pct < umbral_pct:
            continue
        delta_u = ultimo - costo_erp
        qty25 = float(row['cantidad_2025'] or 0)
        fuga_recompra = delta_u * qty25 if qty25 > 0 else delta_u * float(row['cantidad_total'] or 0) * 0.25
        venta = float(pr['precio_venta'] or 0)
        margen_erp = ((venta - costo_erp) / venta * 100) if venta > 0 else None
        margen_real = ((venta - ultimo) / venta * 100) if venta > 0 else None
        filas_fuga.append(
            {
                'producto_id': pid,
                'codigo_factura': row['codigo_factura'],
                'proveedor': row['proveedor'],
                'descripcion': row['descripcion'],
                'grupo5': row.get('grupo5') or '',
                'costo_erp': round(costo_erp),
                'ultimo_costo_maestra': round(ultimo),
                'delta_pct': round(delta_pct, 1),
                'delta_unitario': round(delta_u),
                'neto_comprado_historico': int(row['neto_total']),
                'cantidad_2025': round(qty25, 1),
                'fuga_recompra_clp': int(max(fuga_recompra, 0)),
                'precio_venta': round(venta),
                'margen_erp_pct': round(margen_erp, 1) if margen_erp is not None else None,
                'margen_real_pct': round(margen_real, 1) if margen_real is not None else None,
                'nombre_erp': pr['nombre_erp'],
            }
        )

    filas_fuga.sort(key=lambda x: x['fuga_recompra_clp'], reverse=True)
    top_fuga = filas_fuga[:80]
    fuga_total = sum(x['fuga_recompra_clp'] for x in filas_fuga)
    skus_criticos = len([x for x in filas_fuga if x['delta_pct'] >= 15])

    # —— Reporte 2: inflación ——
    neto_anio = (
        df.groupby('anio', dropna=False)['neto']
        .sum()
        .reindex([2024, 2025, 2026], fill_value=0)
    )
    por_proveedor_anio = (
        df.groupby(['proveedor', 'anio'])['neto']
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=[2024, 2025, 2026], fill_value=0)
    )
    prov_rows: list[dict[str, Any]] = []
    for prov, ser in por_proveedor_anio.iterrows():
        n24, n25, n26 = float(ser[2024]), float(ser[2025]), float(ser[2026])
        base = n24 if n24 > 0 else n25
        yoy_26 = ((n26 - n25) / n25 * 100) if n25 > 0 else 0
        yoy_total = ((n26 - base) / base * 100) if base > 0 else 0
        prov_rows.append(
            {
                'proveedor': prov,
                'neto_2024': int(n24),
                'neto_2025': int(n25),
                'neto_2026': int(n26),
                'neto_total': int(n24 + n25 + n26),
                'variacion_24_26_pct': round(yoy_total, 1),
                'variacion_25_26_pct': round(yoy_26, 1),
            }
        )
    prov_rows.sort(key=lambda x: x['neto_total'], reverse=True)
    neto_total_periodo = float(df['neto'].sum())
    top3_share = 0.0
    if prov_rows and neto_total_periodo > 0:
        top3_share = sum(p['neto_total'] for p in prov_rows[:3]) / neto_total_periodo * 100

    rubro_col = 'grupo5' if 'grupo5' in df.columns else None
    rubro_rows: list[dict[str, Any]] = []
    if rubro_col:
        por_rubro = (
            df.groupby([rubro_col, 'anio'])['neto']
            .sum()
            .unstack(fill_value=0)
            .reindex(columns=[2024, 2025, 2026], fill_value=0)
        )
        for rubro, ser in por_rubro.iterrows():
            n24, n25, n26 = float(ser[2024]), float(ser[2025]), float(ser[2026])
            base = n24 if n24 > 0 else n25
            var = ((n26 - base) / base * 100) if base > 0 else 0
            rubro_rows.append(
                {
                    'rubro': rubro or 'Sin rubro',
                    'neto_2024': int(n24),
                    'neto_2025': int(n25),
                    'neto_2026': int(n26),
                    'variacion_24_26_pct': round(var, 1),
                }
            )
        rubro_rows.sort(key=lambda x: x['variacion_24_26_pct'], reverse=True)

    # Códigos con mayor subida de costo unitario (mismo SKU, 2024→2026)
    cod_infl: list[dict[str, Any]] = []
    for (cf, pv), g in df.groupby(['codigo_factura', 'proveedor']):
        por_a = g.groupby('anio')['costo_u'].mean().dropna()
        if 2024 not in por_a.index or 2026 not in por_a.index:
            continue
        c0, c1 = float(por_a[2024]), float(por_a[2026])
        if c0 <= 0:
            continue
        var = (c1 - c0) / c0 * 100
        if var < 8:
            continue
        cod_infl.append(
            {
                'codigo_factura': cf,
                'proveedor': pv,
                'descripcion': g['descripcion'].iloc[-1],
                'costo_2024': round(c0),
                'costo_2026': round(c1),
                'variacion_pct': round(var, 1),
                'neto_total': int(g['neto'].sum()),
            }
        )
    cod_infl.sort(key=lambda x: (x['variacion_pct'], x['neto_total']), reverse=True)

    return {
        'maestra_path': str(path),
        'generado_ts': time.strftime('%Y-%m-%d %H:%M'),
        'umbral_pct': umbral_pct,
        'fuga': {
            'kpis': {
                'fuga_total_clp': int(fuga_total),
                'fuga_total_fmt': _fmt_clp(fuga_total),
                'skus_desactualizados': len(filas_fuga),
                'skus_criticos_15pct': skus_criticos,
                'neto_compras_periodo': int(neto_total_periodo),
                'neto_compras_fmt': _fmt_clp(neto_total_periodo),
            },
            'filas': top_fuga,
        },
        'inflacion': {
            'kpis': {
                'neto_2024': int(neto_anio[2024]),
                'neto_2025': int(neto_anio[2025]),
                'neto_2026': int(neto_anio[2026]),
                'neto_2024_fmt': _fmt_clp(neto_anio[2024]),
                'neto_2025_fmt': _fmt_clp(neto_anio[2025]),
                'neto_2026_fmt': _fmt_clp(neto_anio[2026]),
                'concentracion_top3_pct': round(top3_share, 1),
                'proveedores_activos': int(df['proveedor'].nunique()),
            },
            'proveedores': prov_rows[:40],
            'rubros': rubro_rows[:25],
            'codigos_subida': cod_infl[:50],
            'chart_anios': {
                'labels': ['2024', '2025', '2026'],
                'neto': [int(neto_anio[2024]), int(neto_anio[2025]), int(neto_anio[2026])],
            },
            'chart_top_prov': {
                'labels': [p['proveedor'][:28] for p in prov_rows[:8]],
                'neto': [p['neto_total'] for p in prov_rows[:8]],
            },
        },
    }


def get_reports_cached(app, *, umbral_pct: float = 5.0, force: bool = False) -> dict[str, Any]:
    global _CACHE
    now = time.time()
    if (
        not force
        and _CACHE.get('payload')
        and now - float(_CACHE.get('ts') or 0) < _CACHE_TTL
    ):
        return _CACHE['payload']
    payload = build_reports(app, umbral_pct=umbral_pct)
    _CACHE = {'ts': now, 'payload': payload}
    return payload


def fuga_to_csv_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get('fuga', {}).get('filas') or []


def inflacion_proveedores_csv(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get('inflacion', {}).get('proveedores') or []


def _oc_numero_str(raw) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ''
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        return str(raw).strip()[:50]


def historial_compras_detalle(
    app,
    *,
    codigo_factura: str,
    proveedor: str,
    producto_id: int | None = None,
) -> dict[str, Any]:
    """Líneas de la maestra para un código factura + proveedor (drill-down)."""
    df = load_maestra()
    cf_n = _norm_text(codigo_factura)
    pv_n = _norm_proveedor(proveedor)
    sub = df[(df['codigo_factura_n'] == cf_n) & (df['proveedor_n'] == pv_n)].copy()
    if sub.empty:
        return {'ok': False, 'error': 'sin_historial'}

    sub = sub.sort_values(['anio', 'oc'], ascending=[True, True], na_position='last')
    lineas: list[dict[str, Any]] = []
    for i, row in sub.iterrows():
        cant = float(row['cantidad'] or 0)
        neto = float(row['neto'] or 0)
        cu = float(row['costo_u'] or 0) if cant > 0 else 0
        oc_raw = row.get('oc')
        anio = int(row['anio']) if pd.notna(row.get('anio')) else None
        lineas.append(
            {
                'anio': anio,
                'oc': _oc_numero_str(oc_raw),
                'oc_raw': oc_raw,
                'cantidad': round(cant, 2),
                'neto': int(neto),
                'neto_fmt': _fmt_clp(neto),
                'costo_unitario': round(cu),
                'costo_fmt': _fmt_clp(cu),
                'descripcion': row.get('descripcion') or '',
                'es_ultima': False,
            }
        )
    if lineas:
        lineas[-1]['es_ultima'] = True

    ult = lineas[-1]
    erp_info: dict[str, Any] = {}
    with app.app_context():
        from app import OrdenCompra, Producto, Proveedor, db

        if producto_id:
            p = Producto.query.get(producto_id)
            if p:
                erp_info = {
                    'producto_id': p.id,
                    'nombre': p.nombre,
                    'precio_compra': int(float(p.precio_compra or 0)),
                    'precio_compra_fmt': _fmt_clp(p.precio_compra),
                    'precio_venta': int(float(p.precio_venta or 0)),
                }

        pr = Proveedor.query.filter(
            db.func.upper(Proveedor.nombre).like(f'%{proveedor[:20].upper()}%')
        ).first()
        if not pr:
            for pobj in Proveedor.query.all():
                if _norm_proveedor(pobj.nombre) == pv_n:
                    pr = pobj
                    break

        oc_erp_links: list[dict[str, Any]] = []
        if pr:
            vistos: set[str] = set()
            for ln in lineas:
                num = ln['oc']
                if not num or num in vistos:
                    continue
                vistos.add(num)
                candidatos = [num]
                if ln.get('anio'):
                    candidatos.append(f'{num}-{ln["anio"]}')
                for candidato in candidatos:
                    oc = OrdenCompra.query.filter_by(
                        proveedor_id=pr.id, numero=candidato
                    ).first()
                    if oc:
                        oc_erp_links.append(
                            {
                                'oc_maestra': num,
                                'oc_erp_id': oc.id,
                                'numero_erp': oc.numero,
                                'estado': oc.estado,
                                'fecha': oc.fecha_emision.isoformat() if oc.fecha_emision else '',
                            }
                        )
                        break

        erp_info['proveedor_id'] = pr.id if pr else None
        erp_info['oc_en_erp'] = oc_erp_links

    costo_erp = int(erp_info.get('precio_compra') or 0)
    ultimo_real = int(ult['costo_unitario'])
    delta_pct = round((ultimo_real - costo_erp) / costo_erp * 100, 1) if costo_erp > 0 else 0

    return {
        'ok': True,
        'codigo_factura': codigo_factura,
        'proveedor': proveedor,
        'descripcion': ult.get('descripcion') or '',
        'lineas': lineas,
        'resumen': {
            'lineas_total': len(lineas),
            'neto_historico': int(sub['neto'].sum()),
            'neto_historico_fmt': _fmt_clp(sub['neto'].sum()),
            'cantidad_total': round(float(sub['cantidad'].sum()), 1),
            'costo_erp': costo_erp,
            'costo_erp_fmt': _fmt_clp(costo_erp),
            'ultimo_costo': ultimo_real,
            'ultimo_costo_fmt': _fmt_clp(ultimo_real),
            'delta_pct': delta_pct,
            'anio_ultima': ult.get('anio'),
            'oc_ultima': ult.get('oc'),
        },
        'erp': erp_info,
        'nota_fecha': (
            'La maestra trae año y N° OC/folio de compra; no fecha exacta de factura. '
            'Si la OC está cargada en el ERP (histórico maestra), aparece el enlace abajo.'
        ),
    }
