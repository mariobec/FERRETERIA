"""Smoke: Code128 SVG para cotizaciones."""
from services.barcode_code128_service import code128_svg


def test_code128_svg_cotizacion_numero():
    svg = code128_svg('COT-000123')
    assert svg.startswith('<svg')
    assert 'COT-000123' in svg
    assert '<rect' in svg


def test_code128_svg_rechaza_vacio():
    import pytest

    with pytest.raises(ValueError):
        code128_svg('   ')
