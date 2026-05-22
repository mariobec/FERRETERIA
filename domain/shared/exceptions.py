"""Excepciones base del dominio (sin dependencias de framework)."""


class DomainError(Exception):
    """Error de regla de negocio recuperable en la capa de aplicación."""


class InvariantViolation(DomainError):
    """Violación de invariante (stock, estados de venta, caja, etc.)."""
