"""Smoke — bytes ESC/POS vale (sin hardware)."""
import pytest

from services.ticket_impresion_escpos import GS, build_vale_escpos_bytes
from services.ticket_impresion_service import pos_impresion_modo
def test_build_vale_escpos_bytes():
    ctx = {
        'venta_id': 3131,
        'empresa': 'Ferretería Santo Domingo',
        'fecha_fmt': '01/06/2026 16:09',
        'prioridad': 79,
        'vendedor': 'Vendedor Prueba',
        'cliente': 'GASTON RIVERA',
        'punto_retiro': 'Tienda',
        'folio_barcode': 'VL003131',
        'qr_url': 'http://127.0.0.1:5000/pos/despacho/vale/3131?t=abc',
        'telefono_contacto': '+5695331233',
        'direccion_empresa': 'Arturo Prat 439 Florida',
        'total': 500000,
        'lineas': [{'prefijo': '[T]', 'nombre': 'Calefactor a leña', 'cantidad': 1, 'subtotal': 500000}],
        'bloques': [],
        'es_borrador': False,
    }
    data = build_vale_escpos_bytes(ctx)
    assert isinstance(data, bytes)
    assert len(data) > 120
    assert b'VALE' in data
    assert b'VL003131' in data or GS + b'k' in data
    assert b'PENDIENTE DE COBRO EN CAJA' in data
    assert b'Arturo Prat' in data
    assert b'+5695331233' in data
    assert b'ESCANEO BODEGA' in data
    assert b'Producto' in data


def test_pos_impresion_modo_default_browser(monkeypatch):
    monkeypatch.delenv('POS_IMPRESION_MODO', raising=False)
    assert pos_impresion_modo() == 'browser'
