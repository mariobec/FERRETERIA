#!/usr/bin/env python3
"""
Smoke del build PyInstaller LhexIA_ERP.

1. No hay .py sueltos en INSTALACION/erp (fuera de _internal)
2. El exe arranca y responde GET /login (requiere Postgres local + .env.local)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ERP = ROOT / "INSTALACION" / "erp"
DEFAULT_EXE = DEFAULT_ERP / "LhexIA_ERP.exe"


def check_no_loose_py(erp_dir: Path) -> list[str]:
    bad = []
    for py in erp_dir.rglob("*.py"):
        if "_internal" in py.parts:
            continue
        bad.append(str(py.relative_to(erp_dir)))
    return bad


def check_login(port: int, timeout: float = 90.0) -> tuple[bool, str]:
    url = f"http://127.0.0.1:{port}/login"
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                body = resp.read(8000).decode("utf-8", errors="replace")
                if resp.status == 200 and ("login" in body.lower() or "correo" in body.lower()):
                    return True, f"HTTP {resp.status} OK"
                return False, f"HTTP {resp.status} sin formulario login"
        except Exception as e:
            last_err = str(e)
            time.sleep(2)
    return False, last_err or "timeout"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--erp-dir", type=Path, default=DEFAULT_ERP)
    parser.add_argument("--exe", type=Path, default=None)
    parser.add_argument("--port", type=int, default=5098)
    parser.add_argument("--skip-http", action="store_true", help="Solo chequear archivos")
    args = parser.parse_args()

    erp_dir = args.erp_dir.resolve()
    exe = (args.exe or erp_dir / "LhexIA_ERP.exe").resolve()

    print("=== Validacion build PyInstaller ===")
    print(f"  Carpeta: {erp_dir}")
    print(f"  Exe:     {exe}")

    if not exe.is_file():
        print("[FALLO] No existe LhexIA_ERP.exe", file=sys.stderr)
        return 1

    loose = check_no_loose_py(erp_dir)
    if loose:
        print("[FALLO] .py sueltos en cliente (no debe haber):")
        for p in loose[:20]:
            print(f"  - {p}")
        return 1
    print("[OK] Sin .py sueltos fuera de _internal")

    internal = erp_dir / "_internal"
    if not internal.is_dir():
        print("[FALLO] Falta carpeta _internal", file=sys.stderr)
        return 1
    print("[OK] _internal presente")

    if args.skip_http:
        print("[OK] Validacion estructura completada (--skip-http)")
        return 0

    env = os.environ.copy()
    env["LHEXIA_SKIP_VENV_BOOTSTRAP"] = "1"
    env["FLASK_DEBUG"] = "0"
    env["FLASK_RUN_HOST"] = "127.0.0.1"
    env["FLASK_RUN_PORT"] = str(args.port)
    env["ERP_PG_DRIVER"] = env.get("ERP_PG_DRIVER", "pg8000")

  # Cargar .env.local del repo si existe
    for env_file in (ROOT / ".env.local", erp_dir / ".env.local"):
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    if not env.get("DATABASE_URL") and not env.get("SQLALCHEMY_DATABASE_URI"):
        print("[AVISO] Sin DATABASE_URL — omitiendo prueba HTTP (use --skip-http o .env.local)")
        return 0

    print(f"[...] Arrancando exe en puerto {args.port} (max 90s)...")
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(erp_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        ok, msg = check_login(args.port)
        if ok:
            print(f"[OK] Servidor responde /login: {msg}")
            return 0
        print(f"[FALLO] /login: {msg}", file=sys.stderr)
        if proc.stdout and proc.poll() is not None:
            tail = proc.stdout.read(4000) or ""
            if tail:
                print("--- salida exe ---")
                print(tail[-2000:])
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
