"""Semáforo POS y venta en verde (servicio de búsqueda)."""
import pytest

from services.pos_busqueda_service import (
    SEMAFORO_AMARILLO,
    SEMAFORO_AZUL,
    SEMAFORO_VERDE,
    clasificar_semaforo,
    construir_badges_semaforo,
    ordenar_candidatos_busqueda,
)


def test_clasificar_semaforo():
    assert clasificar_semaforo(3, 0) == SEMAFORO_VERDE
    assert clasificar_semaforo(0, 5) == SEMAFORO_AMARILLO
    assert clasificar_semaforo(0, 0) == SEMAFORO_AZUL


def test_orden_candidatos_verde_antes_azul():
    items = [
        {"semaforo": SEMAFORO_AZUL, "stock_tienda": 0, "stock_bodega": 0, "stock_total": 0},
        {"semaforo": SEMAFORO_VERDE, "stock_tienda": 2, "stock_bodega": 0, "stock_total": 2},
        {"semaforo": SEMAFORO_AMARILLO, "stock_tienda": 0, "stock_bodega": 1, "stock_total": 1},
    ]
    orden = ordenar_candidatos_busqueda(items)
    assert [x["semaforo"] for x in orden] == [SEMAFORO_VERDE, SEMAFORO_AMARILLO, SEMAFORO_AZUL]


def test_badges_incluyen_semaforo():
    item = {"semaforo": SEMAFORO_VERDE, "stock_tienda": 1, "stock_bodega": 0, "precio": 1000}
    badges = construir_badges_semaforo(item, 1000, 2000)
    assert badges[0]["tipo"] == SEMAFORO_VERDE
