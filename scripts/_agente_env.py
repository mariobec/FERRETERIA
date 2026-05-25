"""Carga .env.local y resuelve DATABASE_URL para workers LhexIA Operador (PC sucursal)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cargar_env_local() -> None:
    for name in ('.env.local', '.env'):
        p = ROOT / name
        if not p.is_file():
            continue
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def resolver_database_url() -> str:
    """
    PC Santo Domingo: AGENTE_OPERADOR_USE_NEON=1 → misma BD que Render (Neon).
    Desarrollo local: DATABASE_URL (Postgres local) por defecto.
    """
    use_neon = (os.getenv('AGENTE_OPERADOR_USE_NEON') or '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )
    neon = (os.getenv('NEON_DATABASE_URL') or '').strip()
    local = (os.getenv('DATABASE_URL') or '').strip()

    if use_neon and neon:
        os.environ['DATABASE_URL'] = neon
        return neon
    if not local and neon:
        os.environ['DATABASE_URL'] = neon
        return neon
    if local:
        return local
    if neon:
        os.environ['DATABASE_URL'] = neon
        return neon
    return ''
