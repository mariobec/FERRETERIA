"""Semáforo POS y venta en verde (servicio de búsqueda)."""
import pytest

from services.pos_busqueda_service import (
    SEMAFORO_AMARILLO,
    SEMAFORO_AZUL,
    SEMAFORO_VERDE,
    clasificar_semaforo,
    construir_badges_semaforo,
    filtrar_productos_por_filtro_pos,
    ordenar_candidatos_busqueda,
    resolver_filtro_busqueda_pos,
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


def test_filtro_operativo_incluye_azul_y_tienda_excluye_azul():
    rows = [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]
    st_t = {1: 5, 2: 0, 3: 0}
    st_b = {1: 0, 2: 3, 3: 0}
    cfg = {"pos_permite_venta_verde": "1"}
    op = filtrar_productos_por_filtro_pos(rows, st_t, st_b, "operativo", cfg)
    assert {int(r["id"]) for r in op} == {1, 2, 3}
    ti = filtrar_productos_por_filtro_pos(rows, st_t, st_b, "tienda", cfg)
    assert {int(r["id"]) for r in ti} == {1}


def test_resolver_filtro_pos_default_operativo():
    class Args:
        def get(self, k, default=None):
            d = {"origen": "pos"}
            return d.get(k, default)

    assert resolver_filtro_busqueda_pos(Args()) == "operativo"
