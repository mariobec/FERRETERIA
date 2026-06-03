"""Registro de entrega por QR ticket (tienda / bodega) — SD-1."""
from __future__ import annotations

from typing import Any


def parse_folio_vale(q: str | None) -> int | None:
    """Acepta 'VL000123', 'VL123', '123'."""
    if not q:
        return None
    s = q.strip().upper()
    if s.startswith('VL'):
        s = s[2:]
    s = s.lstrip('0') or '0'
    try:
        vid = int(s)
    except ValueError:
        return None
    return vid if vid > 0 else None


def _canal_retiro_linea(detalle, venta, *, retiro_por_linea: bool) -> str:
    if retiro_por_linea:
        pl = (getattr(detalle, 'punto_retiro_linea', None) or '').strip()
        if pl:
            return pl
    return (getattr(venta, 'punto_retiro', None) or 'Tienda').strip() or 'Tienda'


def lineas_entrega_para_vale(venta, *, retiro_por_linea: bool, ver_tienda: bool, ver_bodega: bool) -> list[dict[str, Any]]:
    """Líneas visibles para entrega según canal y rol."""
    out: list[dict[str, Any]] = []
    for d in venta.detalles or []:
        if getattr(d, 'a_pedido', False):
            continue
        canal = _canal_retiro_linea(d, venta, retiro_por_linea=retiro_por_linea)
        ck = canal.strip().lower()
        if ck == 'tienda' and not ver_tienda:
            continue
        if ck == 'bodega' and not ver_bodega:
            continue
        if ck == 'despacho' and not (ver_tienda or ver_bodega):
            continue
        vend = int(d.cantidad or 0)
        if ck == 'bodega':
            ent = int(getattr(d, 'cantidad_entregada_retiro_bodega', None) or 0)
        else:
            ent = int(getattr(d, 'cantidad_entregada_retiro_tienda', None) or 0)
        pend = max(0, vend - ent)
        pref = {'Tienda': '[T]', 'Bodega': '[B]', 'Despacho': '[D]'}.get(canal, '')
        nom = (d.producto.nombre if d.producto else f'#{d.id_producto}') or '—'
        out.append(
            {
                'detalle_id': d.id,
                'canal': canal,
                'prefijo': pref,
                'nombre': nom,
                'cantidad': vend,
                'entregada': ent,
                'pendiente': pend,
                'puede_entregar': pend > 0,
            }
        )
    return out


def venta_entrega_resumen(lineas: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(lineas)
    pendientes = sum(1 for ln in lineas if int(ln.get('pendiente') or 0) > 0)
    return {
        'total_lineas': total,
        'lineas_pendientes': pendientes,
        'completa': total > 0 and pendientes == 0,
    }
