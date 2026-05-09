"""
Ejecuta schema_sync contra NEON_DATABASE_URL definida en .env.local.
Debe correrse con el cwd en la raíz del proyecto.

Uso:
  cd "ruta\\sistema_ventas_limpio"
  python scripts/schema_sync_neon.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    env = _parse_env_file(root / ".env.local")
    neon = (env.get("NEON_DATABASE_URL") or "").strip()
    if not neon:
        print("No hay NEON_DATABASE_URL en .env.local; nada que hacer en Neon.")
        sys.exit(0)
    # Importar app solo después de fijar DATABASE_URL para que SQLAlchemy apunte a Neon.
    os.environ["DATABASE_URL"] = neon
    sys.path.insert(0, str(root))
    from app import app, db  # noqa: E402
    from schema_sync import sincronizar_esquema_modelos  # noqa: E402

    with app.app_context():
        r = sincronizar_esquema_modelos(app, db)
    print(
        "Neon schema sync:",
        f"tablas_creadas={r['tablas_creadas']}",
        f"columnas_agregadas={r['columnas_agregadas']}",
    )
    if r.get("errores"):
        print("Errores:")
        for e in r["errores"]:
            print(" -", e)
        sys.exit(1)
    print("Neon OK")


if __name__ == "__main__":
    main()
