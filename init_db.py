from app import app, db, Rol, Usuario
from schema_sync import listar_diferencias_esquema, sincronizar_esquema_modelos


def ensure_roles():
    base_roles = [
        ("Administrador", "Acceso total al ERP"),
        ("Supervisor", "Supervisión operativa"),
        ("Cajero", "Operación de caja y ventas"),
        ("Vendedor", "Ventas y atención"),
        ("Bodeguero", "Recepción y bodega"),
        ("Auditor", "Auditoría de inventario"),
    ]
    for nombre, descripcion in base_roles:
        rol = Rol.query.filter_by(nombre=nombre).first()
        if not rol:
            db.session.add(Rol(nombre=nombre, descripcion=descripcion))


def ensure_admin_from_env():
    correo = (app.config.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip() or ""
    nombre = (app.config.get("BOOTSTRAP_ADMIN_NAME") or "").strip() or "Administrador"
    password = (app.config.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip() or ""
    if not correo or not password:
        return
    admin_rol = Rol.query.filter_by(nombre="Administrador").first()
    if not admin_rol:
        return
    user = Usuario.query.filter_by(correo=correo).first()
    if not user:
        user = Usuario(nombre=nombre, correo=correo, rol_id=admin_rol.id, perfil="ACTIVO")
        user.set_password(password)
        db.session.add(user)


with app.app_context():
    # Config optional bootstrap vars through env.
    app.config["BOOTSTRAP_ADMIN_EMAIL"] = __import__("os").getenv("BOOTSTRAP_ADMIN_EMAIL")
    app.config["BOOTSTRAP_ADMIN_NAME"] = __import__("os").getenv("BOOTSTRAP_ADMIN_NAME")
    app.config["BOOTSTRAP_ADMIN_PASSWORD"] = __import__("os").getenv("BOOTSTRAP_ADMIN_PASSWORD")

    diff_antes = listar_diferencias_esquema(db)
    n_col = len(diff_antes["columnas_faltantes_en_bd"])
    n_tb_bd = len(diff_antes["tablas_solo_en_bd"])
    n_tb_new = len(diff_antes["tablas_ausentes_en_bd"])
    print(
        f"Auditoría modelo vs BD: tablas extra en BD={n_tb_bd}, tablas modelo sin crear={n_tb_new}, "
        f"columnas/tablas faltantes={n_col}"
    )
    if n_col and n_col <= 50:
        for line in diff_antes["columnas_faltantes_en_bd"]:
            print(f"  · {line}")
    elif n_col > 50:
        for line in diff_antes["columnas_faltantes_en_bd"][:40]:
            print(f"  · {line}")
        print(f"  … (+{n_col - 40} más; ejecutá python scripts/schema_audit_and_fix.py para listado completo)")

    resultado_sync = sincronizar_esquema_modelos(app, db)
    if resultado_sync["errores"]:
        print("Schema sync warnings:")
        for err in resultado_sync["errores"]:
            print(f" - {err}")
    else:
        print(
            "Schema sync OK "
            f"(tablas nuevas: {resultado_sync['tablas_creadas']}, "
            f"columnas nuevas: {resultado_sync['columnas_agregadas']})"
        )

    diff_despues = listar_diferencias_esquema(db)
    pend = len(diff_despues["columnas_faltantes_en_bd"])
    if pend:
        print(f"Aviso: quedan {pend} diferencias (PK omitidas o errores). Revisar warnings arriba.")
    ensure_roles()
    ensure_admin_from_env()
    db.session.commit()
    print("DB init OK")
