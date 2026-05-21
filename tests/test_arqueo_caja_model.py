"""Tests cuadratura fusionada en Caja + servicio SII (PLAT-1.1)."""
from __future__ import annotations

import pytest

from services.cuadratura_arqueo_service import (
    calcular_indicadores_sii_turno,
    calcular_monto_teorico_gaveta_turno,
)


class _VentaStub:
    def __init__(self, metodo, total, dte_estado=None, folio=None, track=None):
        self.metodo_pago = metodo
        self.monto_total = total
        self.saldo_favor_usado = 0
        self.dte_estado = dte_estado
        self.nro_documento = folio
        self.dte_track_id = track


def test_monto_teorico_gaveta_formula():
    t = calcular_monto_teorico_gaveta_turno(
        monto_inicial=50000,
        total_efectivo=10000,
        total_abonos_efectivo=2000,
        cambios_efectivo_recibido=500,
        ingresos_manuales=0,
        cambios_efectivo_devuelto=300,
        egresos=1000,
    )
    assert t == 50000 + 10000 + 2000 + 500 - 300 - 1000


def test_indicadores_sii_track_exitoso():
    ventas = [
        _VentaStub('Efectivo', 10000, dte_estado='ENVIADO', folio=1, track='T-OK'),
        _VentaStub('Debito', 5000, dte_estado='RECHAZADO', folio=2, track=''),
        _VentaStub('Efectivo', 3000),
    ]
    r = calcular_indicadores_sii_turno(ventas)
    assert r['boletas_emitidas_qty'] == 2
    assert r['boletas_sincronizadas_qty'] == 1
    assert r['monto_total_ventas'] == 18000
    assert r['monto_total_sii'] == 10000


@pytest.mark.smoke
def test_caja_modelo_tiene_campos_arqueo_ciego(app_ctx):
    import app as m

    cols = {c.name for c in m.Caja.__table__.columns}
    assert 'monto_declarado_cajero' in cols
    assert 'monto_declarado_tarjeta' in cols
    assert 'boletas_emitidas_qty' in cols
    assert 'boletas_sincronizadas_qty' in cols
    assert 'monto_total_sii' in cols
    assert not hasattr(m, 'ArqueoCaja')
