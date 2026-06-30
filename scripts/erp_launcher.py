#!/usr/bin/env python3
"""
Punto de entrada LhexIA ERP — desarrollo y PyInstaller (frozen).

Subcomandos admin (mismo binario, sin .py sueltos en cliente):
  LhexIA_ERP.exe --reset-clave --correo admin@local.cl --clave MiClave123
  LhexIA_ERP.exe --url-red --mostrar
  LhexIA_ERP.exe --url-red http://192.168.1.2:5000
  LhexIA_ERP.exe --crear-usuario-test [--reset-password]

Sin argumentos: arranca el servidor Flask (puerto 5000).
"""
from __future__ import annotations

import argparse
import os
import sys


def _repo_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_local_file(root: str) -> None:
    path = os.path.join(root, ".env.local")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            if k:
                os.environ.setdefault(k, v)


def _require_database_config(root: str) -> None:
    if os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI"):
        return
    _load_env_local_file(root)
    if os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI"):
        return
    if getattr(sys, "frozen", False):
        print(
            "[ERROR] Falta erp\\.env.local con DATABASE_URL (PostgreSQL).\n"
            "  Ejecute 00_Instalar_servidor_completo.bat (pasos 1 y 4).\n"
            "  O cree erp\\.env.local con:\n"
            "    DATABASE_URL=postgresql://postgres:CLAVE@localhost:5432/ferreteria_local\n"
            "    ERP_PG_DRIVER=pg8000",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _prepare_env() -> str:
    root = _repo_root()
    os.chdir(root)
    os.environ.setdefault("LHEXIA_SKIP_VENV_BOOTSTRAP", "1")
    os.environ.setdefault("LHEXIA_RUNTIME_MODE", "exe" if getattr(sys, "frozen", False) else "")
    os.environ.setdefault("PGCLIENTENCODING", "UTF8")
    if root not in sys.path:
        sys.path.insert(0, root)
    _require_database_config(root)
    return root


def _cmd_reset_clave(args: argparse.Namespace) -> int:
    from app import Usuario, app, db

    with app.app_context():
        u = Usuario.query.filter_by(correo=args.correo.strip()).first()
        if not u:
            print(f"[ERROR] No existe usuario: {args.correo}", file=sys.stderr)
            return 1
        u.set_password(args.clave)
        db.session.commit()
        print(f"[OK] Clave actualizada: {u.correo}")
    return 0


def _cmd_url_red(args: argparse.Namespace) -> int:
    import json

    ruta = os.path.join(_repo_root(), "data", "empresa_config.json")
    cfg = {}
    if os.path.isfile(ruta):
        with open(ruta, encoding="utf-8") as f:
            cfg = json.load(f) or {}

    if args.mostrar:
        print(cfg.get("url_red_erp") or "(sin URL fija configurada)")
        return 0

    if args.borrar:
        cfg["url_red_erp"] = ""
    elif args.url:
        url = args.url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        cfg["url_red_erp"] = url.rstrip("/")
    else:
        print("[ERROR] Indique URL o --mostrar / --borrar", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("[OK] URL red guardada en data/empresa_config.json")
    return 0


def _cmd_crear_usuario_test(args: argparse.Namespace) -> int:
    from scripts.crear_usuario_test_piso import main as crear_main

    argv = ["crear_usuario_test_piso.py"]
    if args.reset_password:
        argv.append("--reset-password")
    old = sys.argv
    try:
        sys.argv = argv
        crear_main()
    finally:
        sys.argv = old
    return 0


def _cmd_servidor(_args: argparse.Namespace) -> int:
    import app as erp_app

    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    host = (os.getenv("FLASK_RUN_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = int((os.getenv("FLASK_RUN_PORT") or "5000").strip() or "5000")
    erp_app.app.run(host=host, port=port, debug=debug_mode)
    return 0


def main() -> int:
    _prepare_env()

    parser = argparse.ArgumentParser(description="LhexIA ERP")
    sub = parser.add_subparsers(dest="cmd")

    p_reset = sub.add_parser("reset-clave", help="Resetear clave usuario")
    p_reset.add_argument("--correo", default="admin@local.cl")
    p_reset.add_argument("--clave", required=True)

    p_url = sub.add_parser("url-red", help="URL fija intranet")
    p_url.add_argument("url", nargs="?", default="")
    p_url.add_argument("--mostrar", action="store_true")
    p_url.add_argument("--borrar", action="store_true")

    p_test = sub.add_parser("crear-usuario-test", help="Usuario prueba piso")
    p_test.add_argument("--reset-password", action="store_true")

    # Compat: flags legacy sin subcomando
    if len(sys.argv) >= 2 and sys.argv[1] == "--reset-clave":
        p = argparse.ArgumentParser()
        p.add_argument("--reset-clave", action="store_true")
        p.add_argument("--correo", default="admin@local.cl")
        p.add_argument("--clave", required=True)
        a = p.parse_args()
        return _cmd_reset_clave(a)

    args = parser.parse_args()
    if args.cmd == "reset-clave":
        return _cmd_reset_clave(args)
    if args.cmd == "url-red":
        return _cmd_url_red(args)
    if args.cmd == "crear-usuario-test":
        return _cmd_crear_usuario_test(args)
    return _cmd_servidor(args)


if __name__ == "__main__":
    raise SystemExit(main())
