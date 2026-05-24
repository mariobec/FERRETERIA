#!/usr/bin/env python3
"""Smoke POST /api/agente/operador/dispatch-scan (cron Render o cron-job.org)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    p = argparse.ArgumentParser(description='Smoke cron LhexIA Operador scan')
    p.add_argument('--base-url', default=os.getenv('PUBLIC_SITE_URL') or 'http://127.0.0.1:5000')
    p.add_argument(
        '--secret',
        default=os.getenv('AGENTE_OPERADOR_CRON_SECRET')
        or os.getenv('COBRANZA_DISPATCH_CRON_SECRET')
        or os.getenv('CRON_SECRET')
        or '',
    )
    args = p.parse_args()
    if not args.secret:
        print('Defina AGENTE_OPERADOR_CRON_SECRET o COBRANZA_DISPATCH_CRON_SECRET', file=sys.stderr)
        raise SystemExit(1)

    url = args.base_url.rstrip('/') + '/api/agente/operador/dispatch-scan'
    req = urllib.request.Request(
        url,
        data=b'{}',
        method='POST',
        headers={
            'Authorization': f'Bearer {args.secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            print(body)
            if resp.status != 200:
                raise SystemExit(1)
    except urllib.error.HTTPError as e:
        print(e.read().decode('utf-8', errors='replace'), file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == '__main__':
    main()
