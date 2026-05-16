"""Excepciones del bounded context Venta."""

from core.domain.shared.exceptions import DomainError, InvariantViolation


class VentaDomainError(DomainError):
    """Error genérico del agregado Venta."""


class EstadoVentaInvalidoError(VentaDomainError):
    """Transición de estado no permitida."""


class VentaSinLineasError(VentaDomainError):
    """El vale no tiene líneas de detalle."""


class VentaTotalInvalidoError(VentaDomainError):
    """Monto total inválido para emitir o cobrar."""


class CobroNoPermitidoError(VentaDomainError):
    """No se puede registrar cobro en el estado actual."""


class PuntoRetiroInvalidoError(VentaDomainError):
    """Punto de retiro no válido para finalizar el vale."""


class InvarianteVentaError(InvariantViolation):
    """Invariante de venta/stock/consumo violada (validación de dominio)."""
