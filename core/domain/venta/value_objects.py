"""
Value objects del contexto Venta (Chile / CLP).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


IVA_CHILE_FACTOR = Decimal("1.19")


class EstadoVenta(str, Enum):
    ABIERTA = "Abierta"
    PENDIENTE = "Pendiente"
    PAGADO = "Pagado"
    ANULADA = "Anulada"


class PuntoRetiro(str, Enum):
    BODEGA = "Bodega"
    TIENDA = "Tienda"
    DESPACHO = "Despacho"
    MIXTO = "Mixto"

    @classmethod
    def valores_linea(cls) -> frozenset[str]:
        return frozenset({cls.BODEGA.value, cls.TIENDA.value, cls.DESPACHO.value})


class MetodoPago(str, Enum):
    EFECTIVO = "Efectivo"
    DEBITO = "Debito"
    TARJETA_CREDITO = "TarjetaCredito"
    TRANSFERENCIA = "Transferencia"
    CREDITO = "Credito"


class TipoDocumento(str, Enum):
    BOLETA = "Boleta"
    FACTURA = "Factura"


@dataclass(frozen=True, slots=True)
class Money:
    """Monto en pesos chilenos enteros (misma regla que POS: sin centavos)."""

    amount_clp: int

    @classmethod
    def from_float(cls, value: float | int | None) -> Money:
        return cls(int(round(float(value or 0))))

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    def __add__(self, other: Money) -> Money:
        return Money(self.amount_clp + other.amount_clp)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount_clp - other.amount_clp)

    def __lt__(self, other: Money) -> bool:
        return self.amount_clp < other.amount_clp

    def __le__(self, other: Money) -> bool:
        return self.amount_clp <= other.amount_clp

    def max_with_zero(self) -> Money:
        return Money(max(0, self.amount_clp))

    def to_float(self) -> float:
        return float(self.amount_clp)

    @staticmethod
    def desglosar_iva_desde_total_bruto(total_bruto: Money) -> tuple[Money, Money]:
        """Neto + IVA desde total bruto (política única `desglosar_iva_clp`)."""
        from core.domain.shared.iva_chile import desglosar_iva_clp

        neto, iva, _total = desglosar_iva_clp(int(total_bruto.amount_clp))
        return Money(neto), Money(iva)
