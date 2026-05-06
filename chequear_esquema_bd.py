"""
Compara tablas/columnas del modelo SQLAlchemy con la base (SQLALCHEMY_DATABASE_URI).

Uso:
  set SQLALCHEMY_DATABASE_URI=mysql+pymysql://usuario:clave@host/nombre_bd
  python chequear_esquema_bd.py
  python chequear_esquema_bd.py --sugerir-sql

--sugerir-sql : imprime ALTER TABLE ... ADD COLUMN ... (MySQL) para columnas que
               faltan en la BD. Revísalo antes de ejecutarlo (no aplica cambios solo).

No se conecta desde internet a tu servidor: esto corre donde ejecutes Python
(tu PC o el servidor donde esté el proyecto y el acceso a MySQL).
"""
from __future__ import annotations

import argparse
import os
import sys

_uri = (os.getenv("SQLALCHEMY_DATABASE_URI") or "").strip()
if _uri:
    os.environ["SQLALCHEMY_DATABASE_URI"] = _uri

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mysql as mysql_dialect

from app import app, db


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar modelo Flask-SQLAlchemy vs BD")
    parser.add_argument(
        "--sugerir-sql",
        action="store_true",
        help="Imprime ALTER TABLE sugeridos (MySQL) para columnas faltantes",
    )
    args = parser.parse_args()

    try:
        with app.app_context():
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            print("URI (sin password):", _mask_uri(str(uri)))
            insp = sa_inspect(db.engine)
            # Prueba de conexión
            db.engine.connect().close()
            print("Conexion a BD: OK\n")

            problems = 0
            dialect = mysql_dialect.dialect()

            for table in db.metadata.sorted_tables:
                tname = table.name
                if not insp.has_table(tname):
                    print(f"[TABLA FALTA EN BD] {tname}")
                    problems += 1
                    continue

                db_cols = {c["name"] for c in insp.get_columns(tname)}
                model_cols = {c.name for c in table.columns}
                missing = model_cols - db_cols
                extra = db_cols - model_cols
                if missing or extra:
                    problems += 1
                    print(f"\n[{tname}]")
                    if missing:
                        print("  Columnas en CODIGO que NO estan en BD:", sorted(missing))
                        if args.sugerir_sql:
                            for cname in sorted(missing):
                                col = table.c[cname]
                                print(_sugerir_add_column_sql(tname, col, dialect))
                    if extra:
                        print("  Columnas en BD que NO estan en el modelo:", sorted(extra))

            if problems == 0:
                print("\nOK: tablas revisadas coinciden en columnas con el modelo.")
            else:
                print(f"\nTotal tablas/columnas con diferencias: {problems}")
                if not args.sugerir_sql:
                    print('Vuelve a ejecutar con --sugerir-sql para ver ALTER sugeridos.')
                return 1
    except OSError as e:
        print(f"\n[ERROR] No se pudo conectar a la base: {e}", file=sys.stderr)
        print(
            "Define SQLALCHEMY_DATABASE_URI (PowerShell: $env:SQLALCHEMY_DATABASE_URI='...') "
            "y asegurate de que MySQL acepte conexiones desde esta maquina.",
            file=sys.stderr,
        )
        return 2
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    return 0


def _sugerir_add_column_sql(tname: str, col, dialect) -> str:
    """Una línea ALTER ... ADD COLUMN aproximada para MySQL (revisar defaults/nullable)."""
    typ = col.type.compile(dialect=dialect)
    parts = [f"ALTER TABLE `{tname}` ADD COLUMN `{col.name}` {typ}"]
    if col.primary_key and col.autoincrement is True:
        parts.append("AUTO_INCREMENT")
    if not col.nullable and not col.primary_key:
        parts.append("NOT NULL")
    else:
        if not col.primary_key:
            parts.append("NULL")
    if col.server_default is not None:
        try:
            sd = col.server_default.arg.text if hasattr(col.server_default.arg, "text") else str(col.server_default.arg)
            parts.append(f"DEFAULT ({sd})" if sd.strip().upper().startswith("(") else f"DEFAULT {sd}")
        except Exception:
            pass
    elif col.default is not None and getattr(col.default, "is_scalar", False):
        v = col.default.arg
        if isinstance(v, str):
            parts.append(f"DEFAULT '{v.replace(chr(39), chr(39)+chr(39))}'")
        elif isinstance(v, bool):
            parts.append("DEFAULT 1" if v else "DEFAULT 0")
        elif v is not None:
            parts.append(f"DEFAULT {repr(v)}")
    parts.append(";")
    return "  -- Revisar antes de ejecutar:\n  " + " ".join(parts)


def _mask_uri(uri: str) -> str:
    if "@" not in uri or "://" not in uri:
        return uri
    try:
        head, tail = uri.split("://", 1)
        cred, host = tail.rsplit("@", 1)
        if ":" in cred:
            user, _ = cred.split(":", 1)
            return f"{head}://{user}:***@{host}"
    except ValueError:
        pass
    return uri


if __name__ == "__main__":
    sys.exit(main())
