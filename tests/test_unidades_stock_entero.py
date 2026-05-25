"""Invariante stock entero — productos por peso."""
from types import SimpleNamespace

from services.unidades_service import consumo_stock_entero_desde_cantidad, es_unidad_peso_producto


def test_es_unidad_peso_kg():
    p = SimpleNamespace(unidad_venta='KG', unidad='UN')
    assert es_unidad_peso_producto(p) is True


def test_consumo_kg_a_gramos_enteros():
    p = SimpleNamespace(unidad_venta='KG', unidad='GR', unidad_compra='KG', factor_conversion=1)
    # 1.5 kg → 1500 g enteros
    assert consumo_stock_entero_desde_cantidad(1.5, p) == 1500


def test_consumo_unidad_no_peso_entero():
    p = SimpleNamespace(unidad_venta='UN', unidad='UN', unidad_compra='UN', factor_conversion=1)
    assert consumo_stock_entero_desde_cantidad(3, p) == 3
