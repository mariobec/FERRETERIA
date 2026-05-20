#!/usr/bin/env python3
"""Aplica un archivo .sql en Neon (NEON_DATABASE_URL en .env.local). Uso:
  python scripts/apply_sql_neon.py sql/2026_05_21_rendimiento_sd1_postgresql.sql
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

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


def split_sql_statements(sql_text: str) -> list[str]:
    lines: list[str] = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    return [p.strip() for p in body.split(";") if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sql_file", type=Path, help="Ruta al archivo SQL")
    parser.add_argument(
        "--url-key",
        default="NEON_DATABASE_URL",
        help="Variable en .env.local (default NEON_DATABASE_URL)",
    )
    args = parser.parse_args()
    sql_path = args.sql_file if args.sql_file.is_absolute() else ROOT / args.sql_file
    if not sql_path.is_file():
        print(f"ERROR: no existe {sql_path}", file=sys.stderr)
        return 1

    env = load_env_local()
    url = (env.get(args.url_key) or env.get("DATABASE_URL") or "").strip()
    if not url:
        print(f"ERROR: falta {args.url_key} o DATABASE_URL en .env.local", file=sys.stderr)
        return 1
    if "neon.tech" not in url and "render.com" not in url:
        print(
            "ADVERTENCIA: la URL no parece Neon/Render; abortando por seguridad.",
            file=sys.stderr,
        )
        return 2

    statements = split_sql_statements(sql_path.read_text(encoding="utf-8"))
    print(f"Conectando ({args.url_key})… {len(statements)} sentencias", flush=True)

    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for i, stmt in enumerate(statements, 1):
                preview = stmt.replace("\n", " ")[:72]
                print(f"  [{i}/{len(statements)}] {preview}…", flush=True)
                cur.execute(stmt)
        print("OK: SQL aplicado.", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
