#!/usr/bin/env python3
"""
Ejercicio end-to-end LhexIA Operador (PC tienda):
  1) Alerta demo en Neon (si no hay vales reales)
  2) Scan SQL
  3) Enrich Ollama
  4) Vista tipo Guardián (feed + mensaje_ia)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402

DEDUPE_EJERCICIO = 'operador:ejercicio_sd_ollama_v1'


def main() -> None:
    cargar_env_local()
    if not resolver_database_url():
        print('Falta DATABASE_URL / NEON_DATABASE_URL en .env.local', file=sys.stderr)
        raise SystemExit(1)

    import app as m  # noqa: E402
    from services.agente_ejecuciones_service import (
        EST_ALERTA_ABIERTA,
        TIPO_ALERTA,
        crear_registro,
        existe_dedupe_abierta,
        listar_alertas_sin_enriquecer,
        obtener_por_id,
        parse_payload_json,
    )
    from services.agente_operador_service import (
        ejecutar_lote_enriquecimiento,
        escanear_y_registrar_alertas,
    )
    from services.owner_dashboard_service import (
        _feed_preview,
        _mensaje_ia,
        construir_owner_dashboard,
        detectar_perfil_guardian,
    )

    informe: dict = {'pasos': []}

    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()

        # Paso 0: semilla demo (Neon sin vales pendientes reales)
        if not existe_dedupe_abierta(DEDUPE_EJERCICIO):
            rid = crear_registro(
                agente_nombre='operador',
                tipo=TIPO_ALERTA,
                estado=EST_ALERTA_ABIERTA,
                titulo='[Ejercicio] Vale demo pendiente 4.2 h',
                cuerpo=(
                    'Vale de prueba piloto SD. Estado Pendiente simulado para demo Ollama. '
                    'Monto $45.990. Vendedor: mostrador.'
                ),
                severidad='warning',
                codigo='vale_pendiente_horas',
                dedupe_key=DEDUPE_EJERCICIO,
                payload={
                    'venta_id': None,
                    'horas': 4.2,
                    'monto_clp': 45990,
                    'cuerpo_base_v01': 'Ejercicio Operador + Ollama en PC tienda.',
                    'enriquecido_semantico': False,
                    'ejercicio': True,
                },
            )
            informe['pasos'].append({'semilla_demo': rid})
        else:
            informe['pasos'].append({'semilla_demo': 'ya_existia'})

        informe['scan'] = escanear_y_registrar_alertas()
        informe['enrich'] = ejecutar_lote_enriquecimiento(limite=3)

        row = None
        for candidata in listar_alertas_sin_enriquecer(limite=10):
            if parse_payload_json(candidata.payload_json).get('ejercicio'):
                row = candidata
                break
        if row is None:
            ej = obtener_por_id(informe['pasos'][0].get('semilla_demo')) if isinstance(
                informe['pasos'][0].get('semilla_demo'), int
            ) else None
            if ej:
                row = ej
        if row:
            pj = parse_payload_json(row.payload_json)
            informe['alerta_ejercicio'] = {
                'id': row.id,
                'titulo': row.titulo,
                'enriquecido': pj.get('enriquecido_semantico'),
                'cuerpo_ui': (row.cuerpo or '')[:500],
            }

        perfil = detectar_perfil_guardian(None)
        feed = _feed_preview(perfil=perfil, limite=5)
        informe['feed_guardian'] = feed
        dash = construir_owner_dashboard(
            calcular_ctx_caja=m._calcular_contexto_turno_caja,
            usuario=None,
        )
        informe['mensaje_ia_guardian'] = dash.get('mensaje_ia', '')
        informe['feed_enriquecidos'] = sum(1 for f in feed if f.get('enriquecido'))

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    enrich = informe.get('enrich') or {}
    ya_enriquecido = (informe.get('feed_enriquecidos') or 0) > 0 or bool(
        (informe.get('alerta_ejercicio') or {}).get('enriquecido')
    )
    if enrich.get('enriquecidas', 0) < 1 and not ya_enriquecido:
        print(
            '\nEnrich no completó: revise Ollama en bandeja y OLLAMA_MODEL en .env.local',
            file=sys.stderr,
        )
        raise SystemExit(2)
    print('\n--- Abra en el navegador de esta PC ---')
    print('  http://127.0.0.1:5000/owner-mobile')
    print('  Pulso operativo: badge IA local + texto enriquecido')


if __name__ == '__main__':
    main()
