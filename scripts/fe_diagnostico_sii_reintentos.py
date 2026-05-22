# -*- coding: utf-8 -*-
"""
Diagnóstico SII Maullín/Palena con reintentos; si token ESTADO 00, sube Factura 33 del set.

Uso:
    py scripts/fe_diagnostico_sii_reintentos.py
    py scripts/fe_diagnostico_sii_reintentos.py --intentos 5 --pausa 10
    py scripts/fe_diagnostico_sii_reintentos.py --sin-subir   # solo semilla/token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _subir_factura_33_set(app_root: str, ambiente: str) -> dict:
    from services import facturacion_electronica_service as fe

    print('\n>>> Token OK — enviando DTE_33_FOLIO_1.xml del set de certificación al SII…')
    return fe.enviar_xml_prueba_sii_desde_storage(
        app_root,
        dte_tipo=33,
        folio=1,
        ambiente=ambiente,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description='Diagnóstico SII con reintentos (semilla + token + upload 33)')
    ap.add_argument(
        '--ambiente',
        choices=('certificacion', 'produccion'),
        default='certificacion',
    )
    ap.add_argument('--intentos', type=int, default=3, help='Número de intentos (default: 3)')
    ap.add_argument('--pausa', type=float, default=5.0, help='Segundos entre intentos (default: 5)')
    ap.add_argument(
        '--sin-subir',
        action='store_true',
        help='No subir DTE 33 aunque el token sea 00',
    )
    args = ap.parse_args()

    import app as m

    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception as ex:
        print('ERROR cargando .env:', ex)
        return 2

    os.environ.setdefault('SII_SOAP_ENABLED', '1')
    os.environ['SII_AMBIENTE'] = args.ambiente

    from services import facturacion_sii_soap as sii

    intentos = max(1, int(args.intentos))
    pausa = max(0.0, float(args.pausa))
    token_ok = False
    upload_ok = False
    ultimo_token_est = None

    print(
        'Diagnóstico SII: %d intento(s), pausa %.1fs, ambiente=%s, soap=%s, subir_33=%s'
        % (intentos, pausa, args.ambiente, sii.soap_habilitado(), not args.sin_subir)
    )

    for n in range(1, intentos + 1):
        print('\n--- Intento %d/%d ---' % (n, intentos))
        diag = sii.diagnostico_sii(args.ambiente)
        print(json.dumps(diag, indent=2, ensure_ascii=False))

        sem_ok = diag.get('semilla_ok')
        tok_est = diag.get('token_estado')
        ultimo_token_est = tok_est

        if sem_ok and tok_est == '00' and diag.get('token_ok'):
            print('\nOK: semilla y token (ESTADO 00)')
            token_ok = True
            if not args.sin_subir:
                up = _subir_factura_33_set(m.app.root_path, args.ambiente)
                print(json.dumps(up, indent=2, ensure_ascii=False))
                upload_ok = bool(up.get('ok'))
                if upload_ok:
                    print('\nÉXITO: Track ID = %s' % up.get('track_id'))
                elif up.get('token_estado') == '10':
                    print('\nREPORTE: Token rechazado en upload (estado 10) — revisar Transforms/firma semilla')
                elif up.get('estado_envio') == 'error_token':
                    print('\nREPORTE: Falló token en flujo upload — %s' % up.get('error'))
                else:
                    print(
                        '\nREPORTE: Upload sin track (estado_envio=%s, upload_status=%s)'
                        % (up.get('estado_envio'), up.get('upload_status'))
                    )
            break

        if sem_ok and tok_est and tok_est != '00':
            print('\nSemilla OK; token rechazado SII (estado %s)' % tok_est)
            if tok_est == '10':
                print('REPORTE: ESTADO 10 — ajustar Transforms/firma getToken (manual SII cap. 8)')

        if not sem_ok:
            print('\nSemilla no disponible (503 u otro error SII)')

        if n < intentos and pausa > 0:
            print('Esperando %.1fs…' % pausa)
            time.sleep(pausa)

    if upload_ok:
        return 0
    if token_ok and args.sin_subir:
        return 0
    if token_ok:
        return 2

    if ultimo_token_est == '10':
        print('\nSin token 00; último estado token=10 (firma semilla no aceptada por SII).')
        return 3

    print('\nSin éxito tras %d intento(s). Maullín inestable (503) o token pendiente.' % intentos)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
