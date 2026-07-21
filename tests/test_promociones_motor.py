"""Tests LX-PROMO-COM-1 — motor de promociones (sin POS)."""
from __future__ import annotations

import os

import pytest

from services.promociones_service import (
    LineaCarrito,
    evaluar_promociones,
    motor_promociones_activo,
)


def _linea(pid: int, qty: float, precio: int, detalle_id: int | None = 1) -> LineaCarrito:
    return LineaCarrito(
        producto_id=pid,
        cantidad=qty,
        precio_unitario=precio,
        subtotal_clp=int(round(qty * precio)),
        detalle_id=detalle_id,
    )


def test_flag_default_apagado(monkeypatch):
    monkeypatch.delenv('MOTOR_PROMOCIONES_ACTIVO', raising=False)
    assert motor_promociones_activo(None) is False
    assert motor_promociones_activo({}) is False
    assert motor_promociones_activo({'motor_promociones_activo': '0'}) is False


def test_flag_env_on(monkeypatch):
    monkeypatch.setenv('MOTOR_PROMOCIONES_ACTIVO', '1')
    assert motor_promociones_activo({'motor_promociones_activo': '0'}) is True


def test_2x1_tornillos():
    """2 × $5.000 → promo -$5.000 → total $5.000 (estilo Walmart)."""
    lineas = [_linea(10, 2, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1-TORN',
            'nombre': '2x1 Tornillos',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'exclusiva': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.subtotal_clp == 10000
    assert r.descuento_promos_clp == 5000
    assert r.total_clp == 5000
    assert len(r.aplicaciones) == 1
    assert r.aplicaciones[0].etiqueta_ticket == '2x1 Tornillos'


def test_2x1_cuatro_unidades():
    lineas = [_linea(10, 4, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1',
            'nombre': '2x1',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.subtotal_clp == 20000
    assert r.descuento_promos_clp == 10000
    assert r.total_clp == 10000


def test_lleve_3_pague_2():
    lineas = [_linea(3, 3, 2000)]
    reglas = [
        {
            'id': 2,
            'codigo': '3X2',
            'nombre': 'Lleve 3 pague 2',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'condiciones': {'producto_ids': [3]},
            'beneficio': {'n': 3, 'm': 2},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.subtotal_clp == 6000
    assert r.descuento_promos_clp == 2000
    assert r.total_clp == 4000


def test_segundo_al_50():
    lineas = [_linea(8, 2, 10000)]
    reglas = [
        {
            'id': 3,
            'codigo': 'SEG50',
            'nombre': 'Segundo al 50%',
            'tipo': 'SEGUNDO_PCT',
            'prioridad': 20,
            'activo': True,
            'condiciones': {'producto_ids': [8]},
            'beneficio': {'pct': 50},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.subtotal_clp == 20000
    assert r.descuento_promos_clp == 5000
    assert r.total_clp == 15000


def test_escala_cantidad_precio_fijo():
    """Lista $5.000; 5–9 → $4.800 c/u vía renglón (no muta lista)."""
    lineas = [_linea(7, 5, 5000)]
    reglas = [
        {
            'id': 4,
            'codigo': 'ESC-7',
            'nombre': 'Escala producto 7',
            'tipo': 'ESCALA_QTY',
            'prioridad': 30,
            'activo': True,
            'condiciones': {'producto_ids': [7]},
            'beneficio': {
                'tramos': [
                    {'desde': 1, 'hasta': 4, 'precio_unitario': 5000},
                    {'desde': 5, 'hasta': 9, 'precio_unitario': 4800},
                    {'desde': 10, 'hasta': None, 'precio_unitario': 4500},
                ]
            },
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.subtotal_clp == 25000
    assert r.descuento_promos_clp == 1000  # 5 * 200
    assert r.total_clp == 24000


def test_motor_inactivo_no_aplica():
    lineas = [_linea(10, 2, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1',
            'nombre': '2x1',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        }
    ]
    r = evaluar_promociones(lineas, reglas, activo=False)
    assert r.descuento_promos_clp == 0
    assert r.total_clp == 10000
    assert r.aplicaciones == []


def test_exclusiva_bloquea_segunda_promo_mismo_sku():
    lineas = [_linea(10, 2, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1',
            'nombre': '2x1',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'exclusiva': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        },
        {
            'id': 2,
            'codigo': 'SEG50',
            'nombre': 'Segundo 50',
            'tipo': 'SEGUNDO_PCT',
            'prioridad': 20,
            'activo': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'pct': 50},
        },
    ]
    r = evaluar_promociones(lineas, reglas)
    assert len(r.aplicaciones) == 1
    assert r.aplicaciones[0].codigo == '2X1'
    assert r.total_clp == 5000


def test_producto_no_elegible_sin_descuento():
    lineas = [_linea(99, 2, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1',
            'nombre': '2x1',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    assert r.descuento_promos_clp == 0
    assert r.total_clp == 10000


def test_resultado_ticket_shape():
    """Contrato para ticket: subtotal, aplicaciones, total."""
    lineas = [_linea(10, 2, 5000)]
    reglas = [
        {
            'id': 1,
            'codigo': '2X1-TORN',
            'nombre': '2x1 Tornillos',
            'tipo': 'NXM',
            'prioridad': 10,
            'activo': True,
            'condiciones': {'producto_ids': [10]},
            'beneficio': {'n': 2, 'm': 1},
        }
    ]
    r = evaluar_promociones(lineas, reglas)
    d = r.as_dict()
    assert d['subtotal_clp'] == 10000
    assert d['descuento_promos_clp'] == 5000
    assert d['total_clp'] == 5000
    assert d['aplicaciones'][0]['etiqueta_ticket'] == '2x1 Tornillos'


def _regla_precio_par(pid=10):
    return {
        'id': 9,
        'codigo': 'PAR-3200',
        'nombre': '2 por $3.200',
        'tipo': 'PRECIO_PAR',
        'prioridad': 10,
        'activo': True,
        'exclusiva': True,
        'condiciones': {'producto_ids': [pid]},
        'beneficio': {'pack_qty': 2, 'precio_pack': 3200},
    }


def test_precio_par_dos_unidades_3200():
    """Lista $1.700 c/u · lleva 2 → total $3.200."""
    r = evaluar_promociones([_linea(10, 2, 1700)], [_regla_precio_par()])
    assert r.subtotal_clp == 3400
    assert r.descuento_promos_clp == 200
    assert r.total_clp == 3200


def test_precio_par_tres_unidades_4900():
    """Lleva 3 → un par a $3.200 + 1 suelta $1.700 = $4.900."""
    r = evaluar_promociones([_linea(10, 3, 1700)], [_regla_precio_par()])
    assert r.subtotal_clp == 5100
    assert r.descuento_promos_clp == 200
    assert r.total_clp == 4900


def test_precio_par_cuatro_unidades_6400():
    """Lleva 4 → dos pares a $3.200 = $6.400."""
    r = evaluar_promociones([_linea(10, 4, 1700)], [_regla_precio_par()])
    assert r.subtotal_clp == 6800
    assert r.descuento_promos_clp == 400
    assert r.total_clp == 6400
