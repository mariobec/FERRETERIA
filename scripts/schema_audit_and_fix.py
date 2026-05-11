"""
Audita diferencias modelo SQLAlchemy ↔ BD y ejecuta schema_sync (create_all + ADD COLUMN).

Carga la misma config que la app (.env.qa / .env.local / DATABASE_URL).
Uso desde la raíz del proyecto:

  python scripts/schema_audit_and_fix.py

Salida: informe en stdout + aplicación de correcciones (sin prompts).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    sys.path.insert(0, str(root))

    from app import app, db  # noqa: E402
    from schema_sync import listar_diferencias_esquema, sincronizar_esquema_modelos  # noqa: E402

    r: dict = {"tablas_creadas": 0, "columnas_agregadas": 0, "errores": []}

    try:
        with app.app_context():
            uri_full = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
            tail = uri_full.split("@")[-1] if "@" in uri_full else uri_full[:80]
            print("Dialecto:", db.engine.dialect.name)
            print("BD (host/recurso):", tail[:120])
            print("--- Antes ---")
            diff = listar_diferencias_esquema(db)
            print(f"Tablas solo en BD (legacy/extra): {len(diff['tablas_solo_en_bd'])}")
            for t in diff["tablas_solo_en_bd"][:40]:
                print(f"  + {t}")
            if len(diff["tablas_solo_en_bd"]) > 40:
                print(f"  ... y {len(diff['tablas_solo_en_bd']) - 40} más")

            print(f"Tablas solo en modelo (se crearán si faltan): {len(diff['tablas_ausentes_en_bd'])}")
            for t in diff["tablas_ausentes_en_bd"][:30]:
                print(f"  - {t}")
            if len(diff["tablas_ausentes_en_bd"]) > 30:
                print(f"  ... y {len(diff['tablas_ausentes_en_bd']) - 30} más")

            print(f"Columnas/tablas faltantes según modelo: {len(diff['columnas_faltantes_en_bd'])}")
            for c in diff["columnas_faltantes_en_bd"][:80]:
                print(f"  · {c}")
            if len(diff["columnas_faltantes_en_bd"]) > 80:
                print(f"  ... y {len(diff['columnas_faltantes_en_bd']) - 80} más")

            print("--- Aplicando sincronizar_esquema_modelos ---")
            r = sincronizar_esquema_modelos(app, db)

            print(f"Tablas nuevas: {r['tablas_creadas']}")
            print(f"Columnas agregadas: {r['columnas_agregadas']}")
            if r.get("errores"):
                print("Errores:")
                for e in r["errores"]:
                    print(f"  ! {e}")

            print("--- Después ---")
            diff2 = listar_diferencias_esquema(db)
            pendientes = len(diff2["columnas_faltantes_en_bd"])
            print(f"Pendientes modelo vs BD (requieren migración manual): {pendientes}")
            for c in diff2["columnas_faltantes_en_bd"][:30]:
                print(f"  · {c}")
            if pendientes > 30:
                print(f"  ... y {pendientes - 30} más")

    except Exception as ex:
        print("Falló conexión o sincronización:", ex)
        print("Revisá DATABASE_URL / encoding (.env.local) y que Postgres esté arriba.")
        return 2

    return 1 if r.get("errores") else 0


if __name__ == "__main__":
    sys.exit(main())
