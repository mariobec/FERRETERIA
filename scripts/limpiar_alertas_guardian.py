#!/usr/bin/env python3
"""
Limpia alertas del feed Guardián (Neon / BD configurada).

Uso en PC tienda:
  python scripts/limpiar_alertas_guardian.py --borrar
  python scripts/limpiar_alertas_guardian.py --cerrar

Requiere AGENTE_OPERADOR_USE_NEON=1 en .env.local para tocar la misma BD que Render.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description='Limpiar alertas operativas (Guardián vacío)')
    p.add_argument(
        '--borrar',
        action='store_true',
        help='Eliminar filas (por defecto: solo cerrar estado)',
    )
    p.add_argument(
        '--solo-operador',
        action='store_true',
        help='Solo agente_nombre=operador (por defecto: todas las alerta_operativa)',
    )
    p.add_argument('--dry-run', action='store_true', help='Solo contar, no modificar')
    args = p.parse_args()

    cargar_env_local()
    if not resolver_database_url():
        print('Falta DATABASE_URL / NEON_DATABASE_URL', file=sys.stderr)
        raise SystemExit(1)

    import app as m  # noqa: E402
    from services.agente_ejecuciones_service import (
        EST_ALERTA_ABIERTA,
        EST_ALERTA_RECONOCIDA,
        TIPO_ALERTA,
        contar_alertas_abiertas,
        limpiar_alertas_operativas,
    )

    modo = 'borrar' if args.borrar else 'cerrar'
    solo = 'operador' if args.solo_operador else None

    with m.app.app_context():
        m._asegurar_tabla_agente_ejecuciones()
        AgenteEjecucion = m.AgenteEjecucion
        q = AgenteEjecucion.query.filter(
            AgenteEjecucion.tipo == TIPO_ALERTA,
            AgenteEjecucion.estado.in_((EST_ALERTA_ABIERTA, EST_ALERTA_RECONOCIDA)),
        )
        if solo:
            q = q.filter(AgenteEjecucion.agente_nombre == solo)
        pendientes = q.count()
        print(f'Pendientes a {modo}: {pendientes} (operador abiertas: {contar_alertas_abiertas()})')

        if args.dry_run:
            raise SystemExit(0)

        if pendientes < 1:
            print('Nada que limpiar. Actualice Guardián (pull to refresh).')
            raise SystemExit(0)

        res = limpiar_alertas_operativas(modo=modo, solo_agente=solo)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if not res.get('ok'):
            raise SystemExit(1)

    print('\nListo. En Guardián: Actualizar → debe decir "Sin alertas recientes del operador".')
    print('Para probar descuadre: cierre una caja con diferencia y ejecute:')
    print('  python scripts/agente_operador_ciclo.py')


if __name__ == '__main__':
    main()
