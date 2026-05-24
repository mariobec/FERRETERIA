#!/usr/bin/env python3
"""
LhexIA Operador — ciclo completo en PC sucursal: scan SQL + enrich Ollama.

Uso (después de instalar Ollama):
  python scripts/agente_operador_ciclo.py

Requiere en .env.local:
  DATABASE_URL o NEON_DATABASE_URL
  AGENTE_OLLAMA_ENABLED=1
  OLLAMA_BASE_URL=http://127.0.0.1:11434
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _cargar_env():
    for name in ('.env.local', '.env'):
        p = ROOT / name
        if not p.is_file():
            continue
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def main() -> None:
    _cargar_env()
    if not os.environ.get('DATABASE_URL') and os.environ.get('NEON_DATABASE_URL'):
        os.environ['DATABASE_URL'] = os.environ['NEON_DATABASE_URL']
    os.environ.setdefault('AGENTE_OLLAMA_ENABLED', '1')

    import app as m  # noqa: E402
    from services.agente_operador_service import (
        ejecutar_lote_enriquecimiento,
        escanear_y_registrar_alertas,
    )

    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()
        scan = escanear_y_registrar_alertas()
        enrich = ejecutar_lote_enriquecimiento()
        out = {'scan': scan, 'enrich': enrich}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if not scan.get('ok'):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
