"""Excepciones base del dominio (sin Flask ni SQLAlchemy)."""


class DomainError(Exception):
    """Error de regla de negocio recuperable en aplicación."""


class InvariantViolation(DomainError):
    """Violación de invariante del dominio."""
