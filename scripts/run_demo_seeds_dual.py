"""
Ejecuta los seeds de demostración contra la base LOCAL y contra NEON.

Lee DATABASE_URL y NEON_DATABASE_URL desde .env.local en la raíz del proyecto.
Por cada destino corre un subproceso con DATABASE_URL acorde (evita que SQLAlchemy
quede enganchado a la primera URI importada).

Orden:
  1) seed_ferreteria_curado_chile_demo.py  (DEMO-CUR-*)
  2) seed_madera_chile_demo.py             (MADERA-CHL-*)
  3) seed_demo_data.py                     (DEMO-* masivo + clientes/ventas)
  4) patch_demo_credito_cartera.py         (RUT 77%: saldos, cuotas, abonos demo coherentes)

Uso (desde la raíz del proyecto):
    python scripts/run_demo_seeds_dual.py
    python scripts/run_demo_seeds_dual.py --solo NEON
    python scripts/run_demo_seeds_dual.py --solo LOCAL

Requiere en .env.local:
    DATABASE_URL=postgresql://usuario:clave@host:5432/nombre_bd
    NEON_DATABASE_URL=postgresql://...neon... ?sslmode=require (según tu proyecto)

Si falla LOCAL con "no password supplied", completá usuario/clave en DATABASE_URL o
levantá Postgres con trust sólo en desarrollo.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
ENV_LOCAL = ROOT / ".env.local"

SEEDS = [
    "scripts/seed_ferreteria_curado_chile_demo.py",
    "scripts/seed_madera_chile_demo.py",
    "scripts/seed_demo_data.py",
    "scripts/patch_demo_credito_cartera.py",
]


def _parse_env_local() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_LOCAL.is_file():
        return out
    for raw in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k] = v
    return out


def _child_env(database_url: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() != "SQLALCHEMY_DATABASE_URI"}
    env["DATABASE_URL"] = database_url
    env.setdefault("PGCLIENTENCODING", "UTF8")
    return env


def _run_seed(rel_script: str, database_url: str, tag: str) -> None:
    cmd = [sys.executable, str(ROOT / rel_script)]
    print(f"\n=== [{tag}] {rel_script} ===", flush=True)
    r = subprocess.run(cmd, cwd=str(ROOT), env=_child_env(database_url))
    if r.returncode != 0:
        raise SystemExit(f"Fallo [{tag}] {rel_script} (exit {r.returncode})")


def _sqlalchemy_uri(database_url: str) -> str:
    uri = database_url.strip()
    if uri.startswith("postgres://"):
        uri = "postgresql+psycopg2://" + uri[len("postgres://") :]
    elif uri.startswith("postgresql://") and "+psycopg2" not in uri.split("://", 1)[0]:
        uri = "postgresql+psycopg2://" + uri[len("postgresql://") :]
    return uri


def repair_serial_sequences_postgres(database_url: str) -> None:
    """Evita INSERT con id duplicado cuando la secuencia quedó atrás (p. ej. tras pg_restore)."""
    if not database_url.lower().startswith("postgresql"):
        return
    os.environ.setdefault("PGCLIENTENCODING", "UTF8")
    uri = _sqlalchemy_uri(database_url).lower()
    neon_pool = "neon.tech" in uri and "pooler" in uri
    connect_args = {
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8")),
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "client_encoding": "utf8",
    }
    if not neon_pool:
        connect_args["options"] = "-c lc_messages=C"

    engine = create_engine(
        _sqlalchemy_uri(database_url),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )
    sql_tables = text(
        """
        SELECT DISTINCT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND NOT a.attisdropped
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND a.attname = 'id' AND a.attnum > 0
        ORDER BY 1;
        """
    )
    fixed = 0
    with engine.connect() as conn:
        for (tname,) in conn.execute(sql_tables).fetchall():
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"),
                {"t": tname},
            ).scalar()
            if not seq:
                continue
            mx = conn.execute(text(f'SELECT MAX(id) FROM "{tname}"')).scalar()
            if mx is None:
                conn.execute(text(f"SELECT setval('{seq}', 1, false)"))
            else:
                conn.execute(text(f"SELECT setval('{seq}', :mx, true)"), {"mx": int(mx)})
            fixed += 1
        conn.commit()
    engine.dispose()
    print(f"secuencias_serial_reparadas: tablas_con_id_serial={fixed}", flush=True)


def _resumen_uri(uri: str) -> str:
    try:
        p = urlparse(uri.split()[0])
        db = (p.path or "").lstrip("/") or "?"
        return f"{p.scheme or '?'}://{p.hostname or '?'}:{p.port or '?'}/{db}"
    except Exception:
        return "(URI no válida)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Seeds demo en LOCAL y/o NEON.")
    ap.add_argument(
        "--solo",
        choices=("LOCAL", "NEON", "AMBOS"),
        default="AMBOS",
        help="Por defecto corre ambas bases leídas de .env.local.",
    )
    args = ap.parse_args()

    os.chdir(ROOT)
    env_file = _parse_env_local()
    local_url = (env_file.get("DATABASE_URL") or "").strip()
    neon_url = (env_file.get("NEON_DATABASE_URL") or "").strip()

    targets: list[tuple[str, str]] = []
    if args.solo in ("LOCAL", "AMBOS"):
        if not local_url:
            raise SystemExit(f"No hay DATABASE_URL en {ENV_LOCAL}")
        targets.append(("LOCAL", local_url))
    if args.solo in ("NEON", "AMBOS"):
        if not neon_url:
            raise SystemExit(f"No hay NEON_DATABASE_URL en {ENV_LOCAL}")
        targets.append(("NEON", neon_url))

    print(f"Raiz proyecto: {ROOT}")
    print(f"Archivo env: {ENV_LOCAL} ({'existe' if ENV_LOCAL.is_file() else 'NO existe'})")
    for tag, url in targets:
        print(f"  -> {tag}: {_resumen_uri(url)}")

    for tag, url in targets:
        repair_serial_sequences_postgres(url)
        for script in SEEDS:
            _run_seed(script, url, tag)
        print(f"\n>>> Seeds demo terminados en {tag}", flush=True)


if __name__ == "__main__":
    main()
