"""Tickets QR de retiro post-cobro (cliente) — SD-1."""
from __future__ import annotations

from typing import Any


def canales_retiro_ticket(venta, *, agrupar_fn, usar_bloques_fn) -> list[str]:
    """Canales con líneas para imprimir ticket QR (Tienda / Bodega)."""
    buckets, _, _ = agrupar_fn(venta)
    if not usar_bloques_fn(venta, buckets):
        pr = (getattr(venta, 'punto_retiro', None) or 'Tienda').strip()
        pk = pr if pr in ('Tienda', 'Bodega', 'Despacho') else 'Tienda'
        return ['Bodega' if pk == 'Bodega' else 'Tienda']
    out: list[str] = []
    if buckets.get('Tienda') or buckets.get('Despacho'):
        out.append('Tienda')
    if buckets.get('Bodega'):
        out.append('Bodega')
    return out or ['Tienda']


def detalles_ticket_canal(venta, canal: str, *, agrupar_fn) -> list:
    buckets, _, _ = agrupar_fn(venta)
    ck = (canal or 'Tienda').strip()
    if ck == 'Tienda':
        return list(buckets.get('Tienda') or []) + list(buckets.get('Despacho') or [])
    if ck == 'Bodega':
        return list(buckets.get('Bodega') or [])
    return list(venta.detalles or [])


def build_slices_retiro_ticket(
    venta,
    *,
    agrupar_fn,
    usar_bloques_fn,
    token_create_fn,
    url_qr_fn,
    qr_png_fn,
) -> list[dict[str, Any]]:
    """Un slice por canal (mixto → 2 tickets QR)."""
    tok = token_create_fn(venta.id)
    if not tok:
        return []
    slices: list[dict[str, Any]] = []
    labels = {'Tienda': 'TICKET QR [TIENDA]', 'Bodega': 'TICKET QR [BODEGA]'}
    for canal in canales_retiro_ticket(venta, agrupar_fn=agrupar_fn, usar_bloques_fn=usar_bloques_fn):
        detalles = detalles_ticket_canal(venta, canal, agrupar_fn=agrupar_fn)
        if not detalles:
            continue
        qr_url = url_qr_fn(venta.id, tok, canal=canal)
        qr_src = None
        try:
            qr_src = qr_png_fn(qr_url)
        except Exception:
            qr_src = None
        subtotal = sum(float(d.subtotal or 0) for d in detalles)
        slices.append(
            {
                'canal': canal,
                'canal_label': labels.get(canal, canal.upper()),
                'detalles': detalles,
                'subtotal': subtotal,
                'qr_url': qr_url,
                'qr_src': qr_src,
                'token': tok,
            }
        )
    return slices
