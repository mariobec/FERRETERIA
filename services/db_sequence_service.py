"""Reparación de secuencias SERIAL/IDENTITY en PostgreSQL (post-dump o inserts manuales)."""
from __future__ import annotations

import re

from sqlalchemy import text

_TABLA_ID_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def reparar_secuencia_id(session, tabla: str, columna: str = 'id') -> bool:
    """
    Alinea la secuencia de `tabla.id` con MAX(id)+1.
    Retorna True si se ejecutó en PostgreSQL, False si no aplica (SQLite, sin secuencia).
    """
    if not _TABLA_ID_RE.match(tabla or '') or not _TABLA_ID_RE.match(columna or ''):
        return False
    bind = session.get_bind()
    if bind is None or bind.dialect.name != 'postgresql':
        return False
    seq_row = session.execute(
        text('SELECT pg_get_serial_sequence(:tabla, :col)'),
        {'tabla': tabla, 'col': columna},
    ).scalar()
    if not seq_row:
        return False
    max_id = session.execute(
        text(f'SELECT COALESCE(MAX({columna}), 0) FROM "{tabla}"')
    ).scalar()
    nuevo = max(int(max_id or 0), 1)
    session.execute(text('SELECT setval(:seq, :val, true)'), {'seq': seq_row, 'val': nuevo})
    return True


def es_violacion_pk_rol_permisos(exc: BaseException) -> bool:
    msg = str(getattr(exc, 'orig', exc) or exc).lower()
    return 'rol_permisos_pkey' in msg or (
        'uniqueviolation' in msg and 'rol_permisos' in msg
    )


# Tablas pequeñas de configuración — suelen desfasarse tras sync Neon/dump
_TABLAS_SECUENCIA_ADMIN = (
    'rol_permisos',
    'permisos',
    'roles',
    'usuarios',
)


def reparar_secuencias_tablas(session, tablas: tuple[str, ...] | list[str] | None = None) -> int:
    """Repara secuencias id de varias tablas. Retorna cantidad ajustada."""
    lista = tuple(tablas) if tablas else _TABLAS_SECUENCIA_ADMIN
    n = 0
    for tabla in lista:
        if reparar_secuencia_id(session, tabla):
            n += 1
    return n


def guardar_permisos_rol(session, rol_id: int, permiso_ids: list[int]) -> None:
    """Reemplaza permisos de un rol (delete + insert) con secuencia reparada."""
    from app import Permiso, RolPermiso

    with session.no_autoflush:
        RolPermiso.query.filter_by(rol_id=rol_id).delete(synchronize_session=False)
    reparar_secuencia_id(session, 'rol_permisos')
    for pid in permiso_ids:
        if Permiso.query.get(pid):
            session.add(RolPermiso(rol_id=rol_id, permiso_id=pid))
