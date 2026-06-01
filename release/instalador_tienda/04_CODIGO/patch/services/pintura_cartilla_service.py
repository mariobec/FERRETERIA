"""Cartilla Kölor/Topex — paleta Fábrica de Color (JSON + vínculo opcional ERP)."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

_FAMILIAS_ORDEN = ('blanco', 'beige', 'amarillo', 'verde', 'azul', 'gris', 'rojo', 'neutro')


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _cartilla_path() -> str:
    override = (os.getenv('PINTURA_CARTILLA_JSON') or '').strip()
    if override and os.path.isfile(override):
        return override
    return os.path.join(_repo_root(), 'data', 'pintura_cartilla_sd.json')


def _slug_codigo(codigo: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (codigo or '').strip().lower()).strip('-')


@lru_cache(maxsize=1)
def _raw_cartilla() -> dict[str, Any]:
    path = _cartilla_path()
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get('colores'), list):
                return data
    except OSError:
        pass
    except json.JSONDecodeError:
        pass
    return {'colores': [], 'version': 'fallback'}


def _normalizar_color(row: dict[str, Any]) -> dict[str, Any]:
    codigo = (row.get('codigo') or '').strip().upper()
    familia = (row.get('familia') or 'neutro').strip().lower()
    if familia not in _FAMILIAS_ORDEN:
        familia = 'neutro'
    return {
        'id': _slug_codigo(codigo),
        'codigo': codigo,
        'nombre': (row.get('nombre') or codigo).strip()[:80],
        'familia': familia,
        'hex': (row.get('hex') or '#CCCCCC').strip(),
        'marca': (row.get('marca') or 'Kolor').strip()[:40],
        'exterior': bool(row.get('exterior')),
    }


def paleta_completa(*, solo_exterior: bool | None = None) -> list[dict[str, Any]]:
    rows = [_normalizar_color(r) for r in (_raw_cartilla().get('colores') or []) if isinstance(r, dict)]
    if solo_exterior is True:
        rows = [c for c in rows if c.get('exterior')]
    elif solo_exterior is False:
        rows = [c for c in rows if not c.get('exterior')]
    return rows


def color_por_id(color_id: str) -> dict[str, Any] | None:
    cid = (color_id or '').strip().lower()
    if not cid:
        return None
    for c in paleta_completa():
        if c['id'] == cid:
            return dict(c)
    return None


def color_por_codigo(codigo: str) -> dict[str, Any] | None:
    cod = (codigo or '').strip().upper()
    for c in paleta_completa():
        if c.get('codigo') == cod:
            return dict(c)
    return None


def familias_colores(*, uso: str = 'interior') -> list[dict[str, Any]]:
    uso = (uso or 'interior').strip().lower()
    cols = list(paleta_completa())
    if uso == 'exterior':
        cols.sort(
            key=lambda c: (
                0 if c.get('exterior') else 1,
                _FAMILIAS_ORDEN.index(c['familia']) if c.get('familia') in _FAMILIAS_ORDEN else 99,
                c.get('codigo') or '',
            )
        )
    out: list[dict[str, Any]] = []
    for fam in _FAMILIAS_ORDEN:
        fam_cols = [c for c in cols if c.get('familia') == fam]
        if fam_cols:
            out.append({'id': fam, 'nombre': fam.capitalize(), 'colores': fam_cols})
    return out


def meta_cartilla() -> dict[str, Any]:
    raw = _raw_cartilla()
    cols = paleta_completa()
    return {
        'version': raw.get('version') or '',
        'total_colores': len(cols),
        'marcas': sorted({c.get('marca') for c in cols if c.get('marca')}),
        'fuente': os.path.basename(_cartilla_path()),
    }


def bases_pintura_erp(*, marca: str | None = None, limite: int = 8) -> list[dict[str, Any]]:
    """Bases latex/esmalte en ERP que coinciden con marca cartilla (Kolor/Topex)."""
    try:
        from app import Producto
        from services.stock_service import stock_tienda_por_producto_ids

        marca_q = (marca or '').strip().lower()
        q = (
            Producto.query.filter(Producto.activo.is_(True))
            .filter((Producto.precio_venta > 0) | (Producto.precio_mayoreo > 0))
            .order_by(Producto.precio_venta.asc())
        )
        rows = q.limit(500).all()
        out = []
        for p in rows:
            nombre = (p.nombre or '').lower()
            cat = (p.categoria or '').lower()
            if any(x in nombre for x in ('rodillo', 'brocha', 'thinner', 'diluyente', 'cinta', 'lija')):
                continue
            if not ('pintur' in cat or 'latex' in nombre or 'esmalte' in nombre or 'látex' in nombre):
                continue
            pm = (getattr(p, 'marca', None) or '').lower()
            if marca_q and marca_q not in pm and marca_q not in nombre:
                continue
            out.append(p)
            if len(out) >= limite * 3:
                break
        pids = [p.id for p in out[:limite]]
        stocks = stock_tienda_por_producto_ids(pids) if pids else {}
        serial = []
        for p in out[:limite]:
            serial.append({
                'producto_id': p.id,
                'nombre': (p.nombre or '')[:100],
                'marca': (getattr(p, 'marca', None) or '')[:40],
                'precio': int(round(float(p.precio_venta or p.precio_mayoreo or 0))),
                'stock_tienda': int(stocks.get(p.id, 0)),
            })
        return serial
    except Exception:
        return []
