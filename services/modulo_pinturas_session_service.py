"""
Sesiones del módulo cliente Fábrica de Color (pinturas).
Fase A: preview lab vía env. Fase B: token firmado emitido desde caja/POS.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

LAB_TOKEN = 'lab'
SERIALIZER_SALT = 'modulo-pinturas-v1'
DEFAULT_TTL_MINUTES = 20


def preview_habilitado() -> bool:
    return (os.getenv('VITRINA_FABRICA_COLOR_PREVIEW', '0').strip().lower() in ('1', 'true', 'si', 'yes', 'on'))


def ttl_minutos() -> int:
    try:
        return max(5, min(int(os.getenv('MODULO_PINTURAS_TTL_MIN', str(DEFAULT_TTL_MINUTES))), 120))
    except (TypeError, ValueError):
        return DEFAULT_TTL_MINUTES


def _serializer():
    from flask import current_app

    return URLSafeTimedSerializer(current_app.secret_key, salt=SERIALIZER_SALT)


def crear_sesion_modulo_pinturas(*, usuario_id: int, usuario_nombre: str) -> dict[str, Any]:
    ttl = ttl_minutos()
    payload = {
        'uid': int(usuario_id),
        'nombre': (usuario_nombre or 'Mostrador')[:80],
        'mod': 'fabrica_color',
    }
    token = _serializer().dumps(payload)
    exp = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    path = f'/modulos/pinturas/{token}'
    return {
        'ok': True,
        'token': token,
        'path': path,
        'modulo': 'fabrica_color',
        'ttl_minutos': ttl,
        'expires_at': exp.isoformat(),
        'habilitado_por': payload['nombre'],
    }


def validar_acceso(token: str) -> dict[str, Any] | None:
    t = (token or '').strip()
    if not t:
        return None
    if t == LAB_TOKEN:
        if preview_habilitado():
            return {
                'modo': 'lab',
                'uid': 0,
                'nombre': 'Preview lab',
                'mod': 'fabrica_color',
            }
        return None
    try:
        data = _serializer().loads(t, max_age=ttl_minutos() * 60)
        if not isinstance(data, dict):
            return None
        return {
            'modo': 'caja',
            'uid': int(data.get('uid') or 0),
            'nombre': (data.get('nombre') or 'Mostrador')[:80],
            'mod': data.get('mod') or 'fabrica_color',
        }
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def acceso_permitido(token: str) -> bool:
    return validar_acceso(token) is not None
