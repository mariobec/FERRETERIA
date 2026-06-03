"""Smoke — folio caja y entrega ticket QR."""
from services.entrega_ticket_service import (
    lineas_entrega_para_vale,
    parse_folio_vale,
    venta_entrega_resumen,
)


def test_parse_folio_vale():
    assert parse_folio_vale('VL003131') == 3131
    assert parse_folio_vale('3131') == 3131
    assert parse_folio_vale('') is None
    assert parse_folio_vale('VL') is None


class _Det:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Prod:
    nombre = 'Tornillo'


class _Venta:
    punto_retiro = 'Tienda'
    detalles = []


def test_lineas_entrega_tienda_pendiente():
    d = _Det(
        id=1,
        cantidad=2,
        a_pedido=False,
        cantidad_entregada_retiro_tienda=0,
        cantidad_entregada_retiro_bodega=0,
        producto=_Prod(),
    )
    v = _Venta()
    v.detalles = [d]
    lineas = lineas_entrega_para_vale(v, retiro_por_linea=False, ver_tienda=True, ver_bodega=False)
    assert len(lineas) == 1
    assert lineas[0]['pendiente'] == 2
    res = venta_entrega_resumen(lineas)
    assert res['completa'] is False
