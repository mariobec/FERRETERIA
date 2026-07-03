"""Helpers SQL para tests — IN (:ids) compatible con Postgres (pg8000)."""
from __future__ import annotations

from sqlalchemy import bindparam, text


def sa_text_in(statement: str, *param_names: str):
    """text() con parámetros expanding para cláusulas IN en PostgreSQL."""
    stmt = text(statement)
    for name in param_names:
        stmt = stmt.bindparams(bindparam(name, expanding=True))
    return stmt
