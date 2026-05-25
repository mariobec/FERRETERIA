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

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402


def main() -> None:
    cargar_env_local()
    if not resolver_database_url():
        print('Falta DATABASE_URL o NEON_DATABASE_URL en .env.local', file=sys.stderr)
        raise SystemExit(1)
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
