#!/usr/bin/env python3
"""
Crea o actualiza rol + usuario de prueba para piso (POS, caja, consulta stock).

Uso:
  python scripts/crear_usuario_test_piso.py
  set TEST_PISO_EMAIL=test.piso@sd.local
  set TEST_PISO_PASSWORD=MiClave123
  python scripts/crear_usuario_test_piso.py --reset-password

Solo entornos locales / QAS — no ejecutar apuntando a Neon productivo.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('LHEXIA_SKIP_VENV_BOOTSTRAP', '1')

from app import (
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    _PERMISOS_SISTEMA_INICIAL,
    _seed_permisos_roles_operativos,
    app,
    db,
)

ROL_NOMBRE = 'Test Piso'
ROL_DESCRIPCION = 'Pruebas: POS, caja y consulta de stock (sin admin)'

PERMISOS_TEST_PISO = frozenset({
    'pos_emitir_vale',
    'caja_cobrar_vale',
    'caja_abrir',
    'caja_movimientos',
    'caja_cerrar',
    'ver_inventario',
})


def _asegurar_permisos_base():
    existentes = {p.nombre for p in Permiso.query.all()}
    nuevos = [Permiso(nombre=n) for n in _PERMISOS_SISTEMA_INICIAL if n not in existentes]
    if nuevos:
        db.session.add_all(nuevos)
        db.session.commit()
    _seed_permisos_roles_operativos()


def _asegurar_rol_test_piso():
    rol = Rol.query.filter(db.func.lower(Rol.nombre) == ROL_NOMBRE.lower()).first()
    if not rol:
        rol = Rol(nombre=ROL_NOMBRE, descripcion=ROL_DESCRIPCION)
        db.session.add(rol)
        db.session.flush()

    permisos = {p.nombre: p for p in Permiso.query.all()}
    actuales = {rp.permiso.nombre for rp in rol.rol_permisos if rp.permiso}
    for nombre in PERMISOS_TEST_PISO:
        if nombre in actuales:
            continue
        perm = permisos.get(nombre)
        if not perm:
            continue
        db.session.add(RolPermiso(rol_id=rol.id, permiso_id=perm.id))
    db.session.commit()
    return rol


def _asegurar_usuario(rol: Rol, *, email: str, password: str, reset_password: bool):
    u = Usuario.query.filter(db.func.lower(Usuario.correo) == email.lower()).first()
    if not u:
        u = Usuario(
            nombre='Usuario Test Piso',
            correo=email,
            rol_id=rol.id,
            perfil='ACTIVO',
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u, True

    u.rol_id = rol.id
    u.perfil = 'ACTIVO'
    if reset_password:
        u.set_password(password)
    db.session.commit()
    return u, False


def _bloquear_si_remoto():
    url = (
        os.getenv('DATABASE_URL')
        or os.getenv('SQLALCHEMY_DATABASE_URI')
        or ''
    ).lower()
    hosts_cloud = ('neon.tech', 'render.com', 'railway.app', 'supabase.co')
    if any(h in url for h in hosts_cloud) and os.getenv('ALLOW_TEST_USER_ON_REMOTE') != '1':
        print(
            'BLOQUEADO: DATABASE_URL parece nube productiva.\n'
            'Use Postgres local o defina ALLOW_TEST_USER_ON_REMOTE=1 bajo su responsabilidad.',
            file=sys.stderr,
        )
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description='Crear usuario test piso (POS + caja + stock)')
    parser.add_argument(
        '--reset-password',
        action='store_true',
        help='Actualiza la clave aunque el usuario ya exista',
    )
    args = parser.parse_args()

    email = (os.getenv('TEST_PISO_EMAIL') or 'test.piso@sd.local').strip().lower()
    password = (os.getenv('TEST_PISO_PASSWORD') or 'TestPiso2026!').strip()
    if len(password) < 8:
        print('TEST_PISO_PASSWORD debe tener al menos 8 caracteres.', file=sys.stderr)
        sys.exit(1)

    _bloquear_si_remoto()

    with app.app_context():
        _asegurar_permisos_base()
        rol = _asegurar_rol_test_piso()
        _u, was_new = _asegurar_usuario(
            rol,
            email=email,
            password=password,
            reset_password=args.reset_password,
        )

    print('')
    print('=== Usuario test piso ===')
    print(f'  Rol:      {ROL_NOMBRE}')
    print(f'  Correo:   {email}')
    if was_new or args.reset_password:
        print(f'  Clave:    {password}')
    else:
        print('  Clave:    (sin cambio — use --reset-password)')
    print('')
    print('  Acceso:')
    print('    - Abrir caja          /abrir_caja  (sin admin — incluido en el rol)')
    print('    - Punto de venta      /punto_venta')
    print('    - Caja / vales        /caja/vales_pendientes')
    print('    - Consulta stock      /consulta-stock')
    print('    - Catalogo / stock    /productos')
    print('')
    print('  Tras login, si no hay caja abierta va directo a Abrir caja.')
    print('')
    print('  [OK] Usuario', 'creado.' if was_new else 'actualizado.')
    print('')


if __name__ == '__main__':
    main()
