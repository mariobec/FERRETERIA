"""Smoke y unit tests para PDF de orden de compra."""

from types import SimpleNamespace

import pytest

from services.orden_compra_pdf_service import (
    lineas_presentacion_oc,
    paginas_pdf_lineas,
    presentacion_totales_oc,
    subtotal_linea_oc,
)


def _oc_mock(detalles):
    return SimpleNamespace(
        numero='OC-001',
        detalles=detalles,
    )


@pytest.mark.smoke
def test_subtotal_linea_oc():
    assert subtotal_linea_oc(2, 1500) == 3000.0


@pytest.mark.smoke
def test_lineas_presentacion_oc_codigo_producto():
    prod = SimpleNamespace(nombre='Tornillo', codigo_barra='ABC123', codigo=None)
    det = SimpleNamespace(id=1, producto=prod, cantidad=10, precio_unitario=100)
    lineas = lineas_presentacion_oc(_oc_mock([det]))
    assert len(lineas) == 1
    assert lineas[0]['codigo_impresion'] == 'ABC123'
    assert lineas[0]['codigo_es_ref'] is False
    assert lineas[0]['subtotal'] == 1000.0


@pytest.mark.smoke
def test_presentacion_totales_oc_iva():
    prod = SimpleNamespace(nombre='X', codigo_barra='X1', codigo=None)
    det = SimpleNamespace(id=1, producto=prod, cantidad=1, precio_unitario=10000)
    tot = presentacion_totales_oc(_oc_mock([det]))
    assert tot['neto'] == 10000
    assert tot['iva'] == 1900
    assert tot['total'] == 11900


@pytest.mark.smoke
def test_paginas_pdf_lineas_multipagina():
    items = [{'indice': i} for i in range(1, 30)]
    paginas = paginas_pdf_lineas(items, lineas_p1=24, lineas_sig=34)
    assert len(paginas) == 2
    assert paginas[0]['es_primera'] is True
    assert paginas[1]['es_ultima'] is True


@pytest.mark.smoke
def test_orden_compra_pdf_route_404(app_client):
    r = app_client.get('/compras/ordenes/999999999/pdf')
    assert r.status_code == 404
