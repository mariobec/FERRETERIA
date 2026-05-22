#!/usr/bin/env python3
"""Volcado Neon (o DATABASE_URL) a archivo .dump para restaurar en PC nueva.

Uso (desde raíz del repo, PC con .env.local):
  python scripts/backup_neon_dump.py
  python scripts/backup_neon_dump.py --url-key DATABASE_URL

Requiere pg_dump en PATH (instalar PostgreSQL client tools).
Salida por defecto: respaldos/neon_YYYYMMDD_HHMMSS.dump
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_env_local() -> dict[str, str]:
    p = ROOT / ".env.local"
    if not p.is_file():
        raise RuntimeError("Falta .env.local en la raíz del repo")
    env: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        env[k] = v
    return env


def parse_pg_url(url: str) -> dict[str, str]:
    u = urlparse(url)
    if u.scheme not in ("postgresql", "postgres"):
        raise ValueError("URL debe ser postgresql://...")
    db = (u.path or "").lstrip("/") or "postgres"
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": unquote(u.username or "postgres"),
        "password": unquote(u.password or ""),
        "dbname": db,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup PostgreSQL a .dump")
    parser.add_argument(
        "--url-key",
        default="NEON_DATABASE_URL",
        help="Variable en .env.local (default NEON_DATABASE_URL; fallback DATABASE_URL)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "respaldos",
        help="Carpeta de salida (default respaldos/)",
    )
    args = parser.parse_args()
    env = load_env_local()
    url = (env.get(args.url_key) or env.get("DATABASE_URL") or "").strip()
    if not url:
        print(f"ERROR: falta {args.url_key} o DATABASE_URL en .env.local", file=sys.stderr)
        return 1
    if "neon.tech" not in url and args.url_key == "NEON_DATABASE_URL":
        alt = (env.get("DATABASE_URL") or "").strip()
        if alt:
            print("AVISO: NEON_DATABASE_URL vacía; usando DATABASE_URL.", flush=True)
            url = alt
    pg = parse_pg_url(url)
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"neon_{stamp}.dump"
    host = pg["host"]
    if "-pooler" in host:
        print(
            "AVISO: host con -pooler; pg_dump suele fallar. Usa NEON_DATABASE_URL directo (sin pooler).",
            file=sys.stderr,
        )
    pg_dump = "pg_dump"
    for candidate in (
        Path(r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"),
        Path(r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"),
        Path(r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"),
    ):
        if candidate.is_file():
            pg_dump = str(candidate)
            break
    cmd = [
        pg_dump,
        "-h",
        pg["host"],
        "-p",
        pg["port"],
        "-U",
        pg["user"],
        "-d",
        pg["dbname"],
        "-Fc",
        "--no-owner",
        "--no-acl",
        "-f",
        str(out_file),
    ]
    print(f"Conectando a {pg['host']} / {pg['dbname']} …", flush=True)
    print(f"Salida: {out_file}", flush=True)
    env_run = {**__import__("os").environ, "PGPASSWORD": pg["password"]}
    try:
        subprocess.run(cmd, env=env_run, check=True)
    except FileNotFoundError:
        print("ERROR: no se encontró pg_dump. Instala PostgreSQL (client tools) y agrega al PATH.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"ERROR: pg_dump falló (código {e.returncode})", file=sys.stderr)
        return 1
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"OK: respaldo listo ({size_mb:.1f} MB)", flush=True)
    print(f"Copia a PC nueva: {out_file}", flush=True)
    print("Restaurar en local:", flush=True)
    print(
        '  pg_restore --clean --if-exists --no-owner -h localhost -U postgres -d ferreteria_local "RUTA\\al\\archivo.dump"',
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
