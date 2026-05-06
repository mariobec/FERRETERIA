"""
Uso local (una vez o cuando no haya usuarios):
  set ADMIN_EMAIL=admin@local
  set ADMIN_PASSWORD=tu_clave_segura
  python bootstrap_admin_local.py

Si ADMIN_EMAIL / ADMIN_PASSWORD no están definidos, usa valores por defecto solo para desarrollo.
"""
import os
import sys

from app import app, db, Rol, Usuario


def _ensure_roles():
    base_roles = [
        ("Administrador", "Acceso total al ERP"),
        ("Supervisor", "Supervisión operativa"),
        ("Cajero", "Operación de caja y ventas"),
        ("Vendedor", "Ventas y atención"),
        ("Bodeguero", "Recepción y bodega"),
        ("Auditor", "Auditoría de inventario"),
    ]
    for nombre, descripcion in base_roles:
        if not Rol.query.filter_by(nombre=nombre).first():
            db.session.add(Rol(nombre=nombre, descripcion=descripcion))


def _ensure_admin():
    correo = (os.getenv("ADMIN_EMAIL") or "admin@local").strip()
    password = (os.getenv("ADMIN_PASSWORD") or "").strip()
    if not password:
        password = "admin12345"
        print("ADVERTENCIA: usando ADMIN_PASSWORD por defecto (solo desarrollo). Define ADMIN_PASSWORD.", file=sys.stderr)

    admin_rol = Rol.query.filter_by(nombre="Administrador").first()
    if not admin_rol:
        print("No existe rol Administrador. Ejecuta de nuevo tras crear roles.", file=sys.stderr)
        return

    if Usuario.query.filter_by(correo=correo).first():
        print(f"Ya existe usuario con correo {correo}. No se creó otro.")
        return

    u = Usuario(
        nombre="Administrador",
        correo=correo,
        rol_id=admin_rol.id,
        perfil="ACTIVO",
    )
    u.set_password(password)
    db.session.add(u)
    print(f"Usuario admin creado: {correo}")


if __name__ == "__main__":
    with app.app_context():
        _ensure_roles()
        db.session.commit()
        _ensure_admin()
        db.session.commit()
    print("Listo.")
