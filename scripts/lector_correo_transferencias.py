#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI — sincroniza avisos transferencia bancaria desde IMAP (misma config que DTE)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description='Lector IMAP transferencias bancarias → bandeja caja')
    parser.add_argument('--limite', type=int, default=80)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--solo-no-leidos', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    from app import app
    from services.transferencia_correo_carga_service import sincronizar_correo_transferencias

    with app.app_context():
        res = sincronizar_correo_transferencias(
            limite=args.limite,
            offset=args.offset,
            solo_no_leidos=args.solo_no_leidos,
            usuario='CLI',
            dry_run=args.dry_run,
        )
    if not res.get('ok'):
        print('ERROR:', res.get('error'))
        return 1
    print(res.get('mensaje') or 'OK')
    print('stats:', res.get('stats'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
