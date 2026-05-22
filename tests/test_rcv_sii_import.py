"""Parser RCV SII — importación compras."""
from __future__ import annotations

import pytest

from services.rcv_sii_import_service import (
    ESTADO_PENDIENTE_ITEMS,
    normalizar_rut,
    parsear_rcv_compras,
)


@pytest.mark.smoke
def test_normalizar_rut():
    assert normalizar_rut('76.123.456-K') == '76123456-K'
    assert normalizar_rut('76123456k') == '76123456-K'


@pytest.mark.smoke
def test_parsear_rcv_semicolon_factura_33():
    raw = (
        'Tipo Doc;Rut Emisor;Razon Social;Folio;Fecha Docto;Monto Neto;Monto Total\n'
        '33;76111222-3;Chilemat SpA;12345;15-01-2026;100000;119000\n'
        '61;76111222-3;Chilemat SpA;99;15-01-2026;5000;5950\n'
    ).encode('utf-8')
    lineas, cols, n = parsear_rcv_compras(raw, tipos_doc=frozenset({33}))
    assert cols.get('tipo_doc') is not None
    assert n == 2
    assert len(lineas) == 1
    assert lineas[0].folio == '12345'
    assert lineas[0].rut == '76111222-3'
    assert lineas[0].monto_neto == 100000.0
    assert lineas[0].monto_total == 119000.0


@pytest.mark.smoke
def test_estado_pendiente_items_literal():
    assert ESTADO_PENDIENTE_ITEMS == 'Pendiente de Items'
