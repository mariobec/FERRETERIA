"""Tests unitarios del dominio Venta (sin BD ni Flask)."""
import pytest

from core.domain.venta import (
    CobroNoPermitidoError,
    DetalleVenta,
    EstadoVenta,
    EstadoVentaInvalidoError,
    MetodoPago,
    Money,
    PuntoRetiro,
    Venta,
    VentaSinLineasError,
)


def _vale_abierto_con_linea() -> Venta:
    v = Venta(estado=EstadoVenta.ABIERTA)
    v.agregar_linea(producto_id=1, cantidad=2, precio_unitario=1000.0)
    return v


def test_agregar_linea_recalcula_total():
    v = _vale_abierto_con_linea()
    assert v.monto_total.amount_clp == 2000
    assert v.neto.amount_clp + v.iva.amount_clp == v.monto_total.amount_clp


def test_finalizar_abierta_a_pendiente():
    v = _vale_abierto_con_linea()
    v.finalizar(
        cliente_id=10,
        punto_retiro=PuntoRetiro.BODEGA.value,
        prioridad_cola=3,
        usuario_vendedor="Vendedor QA",
    )
    assert v.estado == EstadoVenta.PENDIENTE
    assert v.cliente_id == 10
    assert v.prioridad == 3
    assert not v.stock_ya_descontado_en_reglas_legacy()


def test_finalizar_sin_lineas_falla():
    v = Venta(estado=EstadoVenta.ABIERTA)
    with pytest.raises(VentaSinLineasError):
        v.finalizar(
            cliente_id=1,
            punto_retiro=PuntoRetiro.TIENDA.value,
            prioridad_cola=1,
            usuario_vendedor="x",
        )


def test_cobro_efectivo_pagado():
    v = _vale_abierto_con_linea()
    v.finalizar(
        cliente_id=1,
        punto_retiro=PuntoRetiro.TIENDA.value,
        prioridad_cola=1,
        usuario_vendedor="x",
    )
    v.registrar_cobro(
        metodo=MetodoPago.EFECTIVO,
        monto_recibido=2000.0,
        caja_id=1,
    )
    assert v.estado == EstadoVenta.PAGADO
    assert v.metodo_pago == "Efectivo"
    assert v.vuelto == 0.0
    assert v.stock_ya_descontado_en_reglas_legacy()


def test_cobro_credito_queda_pendiente():
    v = _vale_abierto_con_linea()
    v.finalizar(
        cliente_id=1,
        punto_retiro=PuntoRetiro.TIENDA.value,
        prioridad_cola=1,
        usuario_vendedor="x",
    )
    v.registrar_cobro(
        metodo=MetodoPago.CREDITO,
        monto_recibido=0,
        credito_plan_codigo="30_60_90",
        caja_id=1,
    )
    assert v.estado == EstadoVenta.PENDIENTE
    assert v.credito_plan_codigo == "30_60_90"
    assert v.stock_ya_descontado_en_reglas_legacy()


def test_no_cobrar_dos_veces():
    v = _vale_abierto_con_linea()
    v.finalizar(
        cliente_id=1,
        punto_retiro=PuntoRetiro.TIENDA.value,
        prioridad_cola=1,
        usuario_vendedor="x",
    )
    v.registrar_cobro(metodo=MetodoPago.EFECTIVO, monto_recibido=5000, caja_id=1)
    with pytest.raises(CobroNoPermitidoError):
        v.puede_registrar_cobro(caja_id_abierta=1)


def test_no_agregar_linea_si_no_abierta():
    v = _vale_abierto_con_linea()
    v.finalizar(
        cliente_id=1,
        punto_retiro=PuntoRetiro.TIENDA.value,
        prioridad_cola=1,
        usuario_vendedor="x",
    )
    with pytest.raises(EstadoVentaInvalidoError):
        v.agregar_linea(producto_id=2, cantidad=1, precio_unitario=100)


def test_money_desglosa_iva():
    neto, iva = Money.desglosar_iva_desde_total_bruto(Money(1190))
    assert neto.amount_clp + iva.amount_clp == 1190
