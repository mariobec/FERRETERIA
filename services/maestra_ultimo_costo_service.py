"""Último costo unitario desde maestra SD (cache en memoria para recepción/alertas)."""
from __future__ import annotations

import time
from typing import Any

from services.maestra_reportes_costos_service import (
    _norm_proveedor,
    _norm_text,
    load_maestra,
    resolve_maestra_path,
)

_CACHE: dict[str, Any] = {'ts': 0.0, 'index': {}}
_TTL = 600


def _build_index() -> dict[tuple[str, str], float]:
    path = resolve_maestra_path()
    if not path.is_file():
        return {}
    df = load_maestra(path)
    idx: dict[tuple[str, str], float] = {}
    for (pv, cf), grp in df.groupby(['proveedor_n', 'codigo_factura_n']):
        last = grp.iloc[-1]
        cant = float(last['cantidad'] or 0)
        if cant <= 0:
            continue
        cu = float(last['neto'] or 0) / cant
        if cu > 0:
            idx[(str(pv), str(cf))] = cu
    return idx


def indice_ultimos_costos(*, force: bool = False) -> dict[tuple[str, str], float]:
    global _CACHE
    now = time.time()
    if not force and _CACHE.get('index') and now - float(_CACHE.get('ts') or 0) < _TTL:
        return _CACHE['index']
    idx = _build_index()
    _CACHE = {'ts': now, 'index': idx}
    return idx


def ultimo_costo_por_codigo(proveedor_nombre: str, codigo_factura: str) -> float | None:
    pv = _norm_proveedor(proveedor_nombre)
    cf = _norm_text(codigo_factura)
    if not pv or not cf:
        return None
    v = indice_ultimos_costos().get((pv, cf))
    return float(v) if v else None


def ultimo_costo_por_proveedor_id(app, proveedor_id: int | None, codigo_factura: str) -> float | None:
    if not proveedor_id or not (codigo_factura or '').strip():
        return None
    with app.app_context():
        from app import Proveedor

        pr = Proveedor.query.get(int(proveedor_id))
        if not pr:
            return None
        return ultimo_costo_por_codigo(pr.nombre or '', codigo_factura)


def alerta_precio_vs_historico(
    producto,
    proveedor_id: int | None,
    codigo_factura: str | None,
    precio_factura: float | None,
    *,
    app,
    umbral_pct: float | None = None,
) -> str | None:
    """
    Compara precio en factura (o catálogo) vs último costo maestra y vs precio_compra ERP.
    Prioriza aviso maestra si hay dato histórico.
    """
    import os

    if precio_factura is None:
        return None
    try:
        precio_f = float(precio_factura)
    except (TypeError, ValueError):
        return None
    if precio_f <= 0:
        return None

    umbral = float(
        umbral_pct if umbral_pct is not None else os.getenv('ALERTA_COSTO_FACTURA_PCT', '15')
    )

    ultimo_m = None
    if proveedor_id and codigo_factura:
        ultimo_m = ultimo_costo_por_proveedor_id(app, proveedor_id, codigo_factura)

    if ultimo_m and ultimo_m > 0:
        pct_m = (precio_f - ultimo_m) / ultimo_m * 100.0
        if abs(pct_m) >= umbral:
            return (
                f'Factura ${precio_f:,.0f} vs última compra histórica ${ultimo_m:,.0f} '
                f'({pct_m:+.1f}%). Revise antes de recepcionar.'
            ).replace(',', '.')

    if not producto:
        return None
    ref = float(producto.precio_compra or 0)
    if ref <= 0:
        return None
    pct = (precio_f - ref) / ref * 100.0
    if abs(pct) < umbral:
        return None
    return (
        f'Precio en factura ${precio_f:,.0f} difiere {pct:+.1f}% '
        f'del precio_compra en catálogo (${ref:,.0f}).'
    ).replace(',', '.')
