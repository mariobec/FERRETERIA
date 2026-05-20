"""Tests política IVA retail Chile (Decimal, Status 7)."""
from __future__ import annotations

import pytest

from core.domain.shared.iva_chile import (
    ErrorFallaMatematicaDTE,
    desglosar_iva_clp,
    distribuir_neto_en_lineas,
    iva_desde_neto_clp,
    linea_dte_item,
    subtotal_linea_bruto_clp,
    validar_contexto_dte_matematico,
)


@pytest.mark.parametrize(
    'bruto, neto, iva, total',
    [
        (1190, 1000, 190, 1190),
        (50000, 42017, 7983, 50000),
        (0, 0, 0, 0),
    ],
)
def test_desglosar_iva_clp_coherente(bruto, neto, iva, total):
    n, i, t = desglosar_iva_clp(bruto)
    assert (n, i, t) == (neto, iva, total)
    assert n + i == t
    assert i == iva_desde_neto_clp(n)


def test_subtotal_linea_sin_float():
    assert subtotal_linea_bruto_clp(3, 1990, 10) == 5373


def test_linea_dte_prc_por_qty_factura():
    it = linea_dte_item('Cemento', 2, 2380, 33, neto_linea_asignado=2000)
    assert it['prc_item'] * it['cantidad'] == it['monto_linea']


def test_validar_contexto_factura_ok():
    ctx = {
        'dte_tipo': 33,
        'monto_neto': 1000,
        'monto_iva': 190,
        'monto_total': 1190,
        'items': [linea_dte_item('X', 1, 1190, 33, neto_linea_asignado=1000)],
    }
    validar_contexto_dte_matematico(ctx)


def test_validar_contexto_rechaza_iva_incoherente():
    ctx = {
        'dte_tipo': 33,
        'monto_neto': 1000,
        'monto_iva': 191,
        'monto_total': 1191,
        'items': [],
    }
    with pytest.raises(ErrorFallaMatematicaDTE, match='19%'):
        validar_contexto_dte_matematico(ctx)


def test_distribuir_neto_suma_header():
    brutos = [10000, 190]
    neto_h, _, _ = desglosar_iva_clp(sum(brutos))
    netos = distribuir_neto_en_lineas(brutos, neto_h)
    assert sum(netos) == neto_h
