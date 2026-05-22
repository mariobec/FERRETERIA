"""Modo de operación empresa — un local vs red multi-sucursal (Guardián, copy UI)."""
from __future__ import annotations

import os


def _env_un_local_explicito() -> bool | None:
    """Override solo si OWNER_GUARDIAN_UN_LOCAL está definido en entorno."""
    raw = os.getenv('OWNER_GUARDIAN_UN_LOCAL')
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip().lower() not in ('0', 'false', 'no')


def es_operacion_un_local() -> bool:
    """
    True = un establecimiento (SD-1 típico: almacenes tienda/bodega, sin red).
    Prioridad: OWNER_GUARDIAN_UN_LOCAL (si definido) > empresa_config > default un local.
    """
    env = _env_un_local_explicito()
    if env is not None:
        return env
    from app import obtener_config_empresa

    cfg = obtener_config_empresa()
    v = str(cfg.get('operacion_un_local', '1')).strip().lower()
    if v in ('0', 'false', 'no', 'multi', 'multi_sucursal', 'red'):
        return False
    return True


def obtener_sucursales_red_n() -> int:
    """
    Cantidad de locales mostrada en copy demo red (hasta existir tabla sucursales).
    Prioridad: OWNER_GUARDIAN_SUCURSALES_N > operacion_sucursales_red_n en JSON > 3.
    """
    env = (os.getenv('OWNER_GUARDIAN_SUCURSALES_N') or '').strip()
    if env.isdigit():
        return max(1, int(env))
    from app import obtener_config_empresa

    cfg = obtener_config_empresa()
    try:
        n = int(str(cfg.get('operacion_sucursales_red_n', '3')).strip() or '3')
    except (TypeError, ValueError):
        n = 3
    return max(1, n)
