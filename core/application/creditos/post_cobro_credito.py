"""
Efectos post-cobro a crédito: cuotas y saldo_deudor del cliente.

Fase 1.4: extraído desde procesar_cobro_caja (app.py).
"""
from __future__ import annotations

from typing import Protocol


class PostCobroCreditoPort(Protocol):
    def normalizar_plan_cuotas(self, raw: str | None) -> str:
        """Devuelve código de plan válido o cadena vacía."""
        ...

    def aplicar_cobro_credito(self, venta_id: int, plan_codigo: str | None) -> None:
        """Regenera cuotas (si hay plan) y suma monto_total a saldo_deudor."""
        ...


class PostCobroCreditoService:
    def __init__(self, port: PostCobroCreditoPort) -> None:
        self._port = port

    def normalizar_plan_cuotas(self, raw: str | None) -> str:
        return self._port.normalizar_plan_cuotas(raw)

    def aplicar_cobro_credito(self, venta_id: int, plan_codigo: str | None) -> None:
        self._port.aplicar_cobro_credito(venta_id, plan_codigo)
