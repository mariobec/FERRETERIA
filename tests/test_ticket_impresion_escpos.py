"""Smoke — bytes ESC/POS vale / retiro (sin hardware)."""
import pytest

from services.ticket_impresion_escpos import GS, build_retiro_escpos_bytes, build_vale_escpos_bytes
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
    # Cabecera sin doble ancho truncado ("Ferreter" + hueco)
    assert b'FERRETERIA' in data
    assert b'SANTO DOMINGO' in data
    assert b'Ferreter' not in data or b'FERRETERIA' in data
    # Logo raster ESC/POS (GS v 0) o fallback texto CHILEMAT
    assert GS + b'v0' in data or b'CHILEMAT' in data


def test_empresa_lineas_marca_sin_corte():
    from services.ticket_impresion_escpos import _empresa_lineas_marca

    lines = _empresa_lineas_marca('Ferretería Santo Domingo')
    assert lines[0] == 'FERRETERIA'
    assert 'SANTO' in lines[1]
    assert all(len(ln) <= 48 for ln in lines)


def test_build_retiro_escpos_bytes_precicado():
    ctx = {
        'venta_id': 3597,
        'empresa': 'Ferretería Santo Domingo',
        'fecha_fmt': '23/07/2026 14:58',
        'cliente': 'Cliente final',
        'folio_barcode': 'VL003597',
        'slices': [
            {
                'canal': 'Tienda',
                'canal_label': 'Retiro · Tienda',
                'subtotal': 6500,
                'qr_url': 'http://127.0.0.1:5000/pos/despacho/vale/3597?t=tok&canal=Tienda',
                'lineas': [{'nombre': 'BARNIZ MARINO 1/4', 'cantidad': 1}],
            },
            {
                'canal': 'Bodega',
                'canal_label': 'Retiro · Bodega',
                'subtotal': 10500,
                'qr_url': 'http://127.0.0.1:5000/pos/despacho/vale/3597?t=tok&canal=Bodega',
                'lineas': [{'nombre': 'ANTICORROSIVO 1/4', 'cantidad': 1}],
            },
        ],
    }
    data = build_retiro_escpos_bytes(ctx)
    assert isinstance(data, bytes)
    assert len(data) > 200
    assert b'TICKET DE RETIRO' in data
    assert b'RETIRO' in data
    assert b'BARNIZ' in data
    assert b'ANTICORROSIVO' in data
    assert b'Precicado' in data
    # Dos cortes: uno entre mitades + uno al final (tienda y bodega en papeles distintos)
    assert data.count(GS + b'V\x00') >= 2
    assert b'VL003597' in data or GS + b'k' in data
    assert b'FERRETERIA' in data
    # QR Epson: modelo + store + print (secuencia corregida)
    assert GS + b'(k' + bytes([4, 0, 49, 65, 50, 0]) in data
    assert GS + b'(k' + bytes([3, 0, 49, 81, 48]) in data
    # Orden HTML: QR/barras antes de productos
    idx_prod = data.find(b'PRODUCTO')
    idx_qr_print = data.find(GS + b'(k' + bytes([3, 0, 49, 81, 48]))
    assert idx_qr_print >= 0 and idx_prod > idx_qr_print


def test_qr_model2_secuencia_epson():
    from services.ticket_impresion_escpos import _qr_model2

    q = _qr_model2('http://127.0.0.1:5000/x', module_size=6)
    assert GS + b'(k' + bytes([4, 0, 49, 65, 50, 0]) in q
    assert GS + b'(k' + bytes([3, 0, 49, 67, 6]) in q
    assert GS + b'(k' + bytes([3, 0, 49, 69, 49]) in q
    assert bytes([49, 80, 48]) + b'http://127.0.0.1:5000/x' in q
    assert GS + b'(k' + bytes([3, 0, 49, 81, 48]) in q
    # No meter tamaño módulo dentro del store (bug previo)
    assert bytes([49, 80, 48, 6, 49]) not in q


def test_pos_impresion_modo_default_browser(monkeypatch):
    monkeypatch.delenv('POS_IMPRESION_MODO', raising=False)
    assert pos_impresion_modo() == 'browser'
