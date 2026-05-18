"""
Uso de saldo a favor al cobrar (débito de ClienteSaldoFavor).

Fase 1.4: extraído desde procesar_cobro_caja (app.py).
"""
from __future__ import annotations

from typing import Protocol


class PostCobroSaldoFavorPort(Protocol):
    def aplicar_debito_cobro(self, venta_id: int, monto: float) -> None:
        ...


class PostCobroSaldoFavorService:
    def __init__(self, port: PostCobroSaldoFavorPort) -> None:
        self._port = port

    def aplicar_uso_saldo_favor(self, venta_id: int, monto: float) -> None:
        if float(monto or 0) <= 0:
            return
        self._port.aplicar_debito_cobro(venta_id, float(monto))
