#!/usr/bin/env python3
"""Resetea clave de un usuario ERP (uso local / intranet)."""
from __future__ import annotations

import argparse
import sys

from app import app, db, Usuario


def main() -> int:
    parser = argparse.ArgumentParser(description="Resetear clave usuario LhexIA ERP")
    parser.add_argument("--correo", default="admin@local.cl", help="Correo del usuario")
    parser.add_argument("--clave", required=True, help="Nueva clave (mín. 8 caracteres)")
    args = parser.parse_args()
    if len(args.clave) < 8:
        print("[ERROR] La clave debe tener al menos 8 caracteres.", file=sys.stderr)
        return 1
    with app.app_context():
        u = Usuario.query.filter_by(correo=args.correo.strip()).first()
        if not u:
            print(f"[ERROR] No existe usuario con correo: {args.correo}", file=sys.stderr)
            return 1
        u.set_password(args.clave)
        db.session.commit()
        print(f"[OK] Clave actualizada: {u.correo}")
        print("Entre en /login con el correo completo y la nueva clave.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
