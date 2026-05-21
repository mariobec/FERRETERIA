"""Modo de cierre de caja — empresa (JSON) con override opcional por env."""
from __future__ import annotations

import os

MODOS_VALIDOS = ('ciego', 'visible')


def obtener_modo_cierre_caja() -> str:
    """
    Resuelve el modo activo: `ciego` (PLAT-1.1) o `visible` (teórico en pantalla).
    Prioridad: CIERRE_CAJA_MODO en entorno > data/empresa_config.json > default ciego.
    """
    env = (os.getenv('CIERRE_CAJA_MODO') or '').strip().lower()
    if env in MODOS_VALIDOS:
        return env
    from app import obtener_config_empresa

    cfg = obtener_config_empresa()
    modo = (cfg.get('cierre_caja_modo') or 'ciego').strip().lower()
    return modo if modo in MODOS_VALIDOS else 'ciego'


def es_cierre_a_ciegas() -> bool:
    return obtener_modo_cierre_caja() == 'ciego'
