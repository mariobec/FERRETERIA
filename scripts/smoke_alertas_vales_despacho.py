#!/usr/bin/env python3
"""
Smoke test del cron de alertas de vales con despacho bodega sin cobro.

Requiere: servidor Flask en ejecución, variables en entorno o .env cargadas manualmente.

  set BASE_URL=http://127.0.0.1:5000
  set CRON_SECRET=tu_secreto (VALE_DESPACHO_ALERTAS_CRON_SECRET o COBRANZA_DISPATCH_CRON_SECRET)

  python scripts/smoke_alertas_vales_despacho.py
  python scripts/smoke_alertas_vales_despacho.py --use-view

Por defecto usa dry_run=true (no envía). Use --send-all para enviar WA/Slack de verdad.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser(description='POST /api/ventas/alertas-despachos-pendientes')
    p.add_argument('--base-url', default=os.getenv('BASE_URL', 'http://127.0.0.1:5000').rstrip('/'))
    p.add_argument('--secret', default=os.getenv('CRON_SECRET') or os.getenv('COBRANZA_DISPATCH_CRON_SECRET') or '')
    p.add_argument('--send-all', action='store_true', help='dry_run=false y send_wa/send_wa_interno/notify_slack true (¡envía de verdad!)')
    p.add_argument('--use-view', action='store_true')
    args = p.parse_args()

    secret = (args.secret or '').strip()
    if not secret:
        print('Defina CRON_SECRET o COBRANZA_DISPATCH_CRON_SECRET', file=sys.stderr)
        return 2

    dry_run = not args.send_all
    body = {
        'dry_run': dry_run,
        'max': 20,
        'use_view': bool(args.use_view),
        'send_wa': False if dry_run else True,
        'send_wa_interno': False if dry_run else True,
        'notify_slack': False if dry_run else True,
    }

    url = f'{args.base_url}/api/ventas/alertas-despachos-pendientes'
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {secret}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print(f'HTTP {e.code}: {err_body}', file=sys.stderr)
        return 1
    except Exception as ex:
        print(str(ex), file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
