"""
Dominio Venta + líneas (vale POS, cobro en caja).

Entidades puras; persistencia vía core.infrastructure.persistence.venta_repository.
"""

from core.domain.venta.entities import DetalleVenta, Venta
from core.domain.venta.exceptions import (
    CobroNoPermitidoError,
    EstadoVentaInvalidoError,
    VentaDomainError,
    VentaSinLineasError,
    VentaTotalInvalidoError,
)
from core.domain.venta.value_objects import (
    EstadoVenta,
    IVA_CHILE_FACTOR,
    MetodoPago,
    Money,
    PuntoRetiro,
    TipoDocumento,
)

__all__ = [
    "DetalleVenta",
    "Venta",
    "CobroNoPermitidoError",
    "EstadoVentaInvalidoError",
    "VentaDomainError",
    "VentaSinLineasError",
    "VentaTotalInvalidoError",
    "EstadoVenta",
    "IVA_CHILE_FACTOR",
    "MetodoPago",
    "Money",
    "PuntoRetiro",
    "TipoDocumento",
]
