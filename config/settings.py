"""
Lectura centralizada de variables de entorno.

No reemplaza aún la config Flask en app.py; uso opt-in desde código nuevo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    secret_key: str | None
    sii_ambiente: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI"),
        secret_key=os.getenv("SECRET_KEY"),
        sii_ambiente=os.getenv("SII_AMBIENTE"),
    )
