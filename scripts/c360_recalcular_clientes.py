"""
Recalcula perfiles Customer 360 para clientes activos (CLI, sin HTTP).
Uso desde la raíz del proyecto:
  python scripts/c360_recalcular_clientes.py
  python scripts/c360_recalcular_clientes.py --max 150
"""
from __future__ import annotations

import argparse
import os
import sys

# Raíz del repo
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    p = argparse.ArgumentParser(description='Worker local C360 (recalcular clientes)')
    p.add_argument('--max', type=int, default=400, help='Máximo de clientes activos a procesar')
    args = p.parse_args()

    os.chdir(ROOT)
    from app import (  # noqa: E402
        app,
        c360_worker_recalcular_clientes,
        _asegurar_columnas_customer_360_legacy,
    )

    with app.app_context():
        if not _asegurar_columnas_customer_360_legacy():
            print('ERROR: no se pudieron asegurar columnas C360', file=sys.stderr)
            sys.exit(1)
        out = c360_worker_recalcular_clientes(args.max)
        print(out)
        sys.exit(0 if out.get('ok') else 1)


if __name__ == '__main__':
    main()
