"""
Descuento de stock tienda + kardex al cobrar un vale.

Fase 1.3: extraído desde procesar_cobro_caja (app.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LineaStockCobro:
    detalle_id: int
    producto_id: int
    cantidad_venta: int
    consumo_stock: int
    consumo_tienda: int


class PrepararLineasStockCobroPort(Protocol):
    def preparar_lineas(self, venta_id: int) -> list[LineaStockCobro]:
        """Valida stock y devuelve líneas a descontar (puede lanzar ValueError)."""
        ...


class AplicarStockCobroPort(Protocol):
    def aplicar_descontos(
        self,
        venta_id: int,
        lineas: list[LineaStockCobro],
        metodo_pago: str,
        usuario: str | None,
    ) -> None:
        """Descuenta stock tienda y registra kardex SALIDA por línea."""
        ...


class DescontarStockCobroService:
    def __init__(
        self,
        preparar: PrepararLineasStockCobroPort,
        aplicar: AplicarStockCobroPort,
    ) -> None:
        self._preparar = preparar
        self._aplicar = aplicar

    def preparar_lineas(self, venta_id: int) -> list[LineaStockCobro]:
        return self._preparar.preparar_lineas(venta_id)

    def aplicar_descontos(
        self,
        venta_id: int,
        lineas: list[LineaStockCobro],
        metodo_pago: str,
        usuario: str | None,
    ) -> None:
        if not lineas:
            return
        self._aplicar.aplicar_descontos(venta_id, lineas, metodo_pago, usuario)
