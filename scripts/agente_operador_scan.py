#!/usr/bin/env python3
"""CLI — LhexIA Operador v0.1: escaneo SQL de vales y descuadres (sin GPU)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as m  # noqa: E402


def main() -> None:
    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()
        from services.agente_operador_service import escanear_y_registrar_alertas

        res = escanear_y_registrar_alertas()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if not res.get('ok'):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
