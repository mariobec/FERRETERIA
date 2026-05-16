"""
Comandos (entrada) para casos de uso Venta / Caja.

DTOs inmutables; sin lógica de negocio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class FinalizarVentaCommand:
    """Emitir vale: Abierta → Pendiente."""

    venta_id: int
    cliente_id: int
    punto_retiro: str
    usuario_vendedor: str
    prioridad_cola: int
    retiro_por_linea: bool = False


@dataclass(frozen=True, slots=True)
class ProcesarCobroCommand:
    """Cobrar vale en caja (stock/kardex/FE fuera del comando)."""

    venta_id: int
    caja_id: int
    metodo_pago: str
    tipo_documento: str = "Boleta"
    monto_recibido: float = 0.0
    saldo_favor_usado: float = 0.0
    credito_plan_codigo: Optional[str] = None
    usuario_cobro: Optional[str] = None
