# -*- coding: utf-8 -*-
"""
Diagnóstico FE SII: semilla + token (sin subir DTE).

Uso:
    python scripts/fe_diagnostico_sii.py
    python scripts/fe_diagnostico_sii.py --ambiente produccion
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '--ambiente',
        choices=('certificacion', 'produccion'),
        default=None,
        help='Override SII_AMBIENTE para esta ejecución',
    )
    args = ap.parse_args()

    import app as m

    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception as ex:
        print('ERROR cargando .env:', ex)
        return 2

    from services import facturacion_sii_soap as sii

    if args.ambiente:
        os.environ['SII_AMBIENTE'] = args.ambiente

    diag = sii.diagnostico_sii(args.ambiente)
    print(json.dumps(diag, indent=2, ensure_ascii=False))

    ok = diag.get('semilla_ok') and (not diag.get('pfx_configurado') or diag.get('token_ok'))
    if not diag.get('soap_habilitado'):
        print('\nNota: SII_SOAP_ENABLED no está activo; el cobro seguirá en STUB_NO_ENVIO hasta activarlo.')
    if not diag.get('semilla_ok'):
        print('\nREVISAR: Maullín/Palena no entregó semilla (503 mantenimiento, firewall o URL SII)')
        return 1
    if diag.get('pfx_configurado') and not diag.get('token_ok'):
        print('\nREVISAR: semilla OK pero token falló (.pfx/contraseña o GetTokenFromSeed 503)')
        return 1
    print('\nOK: conexión SII (semilla' + (' + token' if diag.get('token_ok') else '') + ')')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
