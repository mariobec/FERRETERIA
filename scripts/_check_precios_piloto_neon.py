"""Verifica esquema piloto precios en Neon (NEON_DATABASE_URL en .env.local)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def _parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def main() -> int:
    neon = (_parse_env(ROOT / ".env.local").get("NEON_DATABASE_URL") or "").strip()
    if not neon:
        print("ERROR: falta NEON_DATABASE_URL en .env.local")
        return 1
    os.environ["DATABASE_URL"] = neon
    from sqlalchemy import inspect, text

    from app import app, db

    with app.app_context():
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        ok = True
        for name in ("bitacora_piloto_mostrador",):
            present = name in tables
            print(f"tabla {name}:", "OK" if present else "FALTA")
            ok = ok and present
        if "productos" in tables:
            cols = {c["name"] for c in insp.get_columns("productos")}
            has_sd = "precio_venta_sd" in cols
            print("columna productos.precio_venta_sd:", "OK" if has_sd else "FALTA")
            ok = ok and has_sd
        if "detalle_ventas" in tables:
            dv = {c["name"] for c in insp.get_columns("detalle_ventas")}
            has_ap = "a_pedido" in dv
            print("columna detalle_ventas.a_pedido:", "OK" if has_ap else "FALTA")
            ok = ok and has_ap
        if "bitacora_piloto_mostrador" in tables:
            n = db.session.execute(text("SELECT COUNT(*) FROM bitacora_piloto_mostrador")).scalar()
            print("filas bitacora_piloto_mostrador:", int(n or 0))
        sd = db.session.execute(
            text(
                "SELECT COUNT(*) FROM productos "
                "WHERE precio_venta_sd IS NOT NULL AND precio_venta_sd > 0"
            )
        ).scalar()
        print("productos con precio_venta_sd > 0:", int(sd or 0))
    print("RESULTADO:", "LISTO PRD" if ok else "FALTA MIGRAR")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
