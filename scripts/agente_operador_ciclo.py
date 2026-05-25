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

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402


def main() -> None:
    cargar_env_local()
    if not resolver_database_url():
        print('Falta DATABASE_URL o NEON_DATABASE_URL en .env.local', file=sys.stderr)
        raise SystemExit(1)
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
