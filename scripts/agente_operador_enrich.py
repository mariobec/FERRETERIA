#!/usr/bin/env python3
"""
Worker LhexIA Operador v0.2 — enriquecimiento semántico vía Ollama local.

Ejecutar en el PC de sucursal (cron cada 5–15 min). Requiere:
  DATABASE_URL o NEON_DATABASE_URL → Neon
  AGENTE_OLLAMA_ENABLED=1
  OLLAMA_BASE_URL=http://127.0.0.1:11434

No afecta el POS en Render.
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

    from services.agente_operador_service import ejecutar_lote_enriquecimiento

    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()
        res = ejecutar_lote_enriquecimiento()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if not res.get('ok'):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
