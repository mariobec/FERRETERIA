#!/usr/bin/env python3
"""Diagnóstico rápido: BD Operador + Ollama local (PC Santo Domingo)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402


def main() -> None:
    cargar_env_local()
    db_url = resolver_database_url()
    import os

    use_neon = (os.environ.get('AGENTE_OPERADOR_USE_NEON') or '').lower() in (
        '1',
        'true',
        'yes',
        'on',
    )
    os.environ.setdefault('AGENTE_OLLAMA_ENABLED', '1')

    from services.ollama_client import ollama_disponible, ollama_habilitado, ollama_model

    informe = {
        'database_url_configurada': bool(db_url),
        'usa_neon_operador': use_neon,
        'ollama_habilitado': ollama_habilitado(),
        'ollama_disponible': ollama_disponible(),
        'ollama_modelo': ollama_model(),
    }

    if not db_url:
        print(json.dumps({**informe, 'error': 'sin_database_url'}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    import app as m  # noqa: E402
    from services.agente_operador_service import ejecutar_lote_enriquecimiento, escanear_y_registrar_alertas

    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()
        informe['scan'] = escanear_y_registrar_alertas()
        informe['enrich'] = ejecutar_lote_enriquecimiento()

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    if not informe.get('ollama_disponible'):
        print(
            '\nOllama no responde: instale desde https://ollama.com y ejecute scripts/setup_ollama_sd.ps1',
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not informe['scan'].get('ok'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
