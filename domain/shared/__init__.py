"""Tipos y utilidades compartidas entre bounded contexts."""

from domain.shared.exceptions import DomainError, InvariantViolation

__all__ = ["DomainError", "InvariantViolation"]
