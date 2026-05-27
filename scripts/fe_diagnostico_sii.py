# -*- coding: utf-8 -*-
"""
Diagnóstico FE SII: semilla + token (sin subir DTE).

Uso:
    python scripts/fe_diagnostico_sii.py
    python scripts/fe_diagnostico_sii.py --ambiente produccion
    python scripts/fe_diagnostico_sii.py --intentos 3 --espera 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _es_reintentable(error: str | None) -> bool:
    if not error:
        return False
    e = error.upper()
    return any(
        x in e
        for x in (
            '503',
            '502',
            '504',
            'TIMEOUT',
            'CONNECTION',
            'SEMILLA_NO',
            'TOKEN_NO',
            'HTTPERROR',
            'TRANSPORT',
        )
    )


def _obtener_semilla_con_reintentos(sii, ambiente, intentos: int, espera_seg: float):
    ultimo = None
    for n in range(1, intentos + 1):
        if n > 1:
            pausa = espera_seg * (2 ** (n - 2))
            print(f'  Reintento semilla {n}/{intentos} (espera {pausa:.0f}s)…')
            time.sleep(pausa)
        ultimo = sii.obtener_semilla(ambiente)
        if ultimo.ok:
            return ultimo, n
        if not _es_reintentable(ultimo.error):
            break
    return ultimo, intentos


def _obtener_token_con_reintentos(sii, semilla: str, ambiente, intentos: int, espera_seg: float):
    ultimo = None
    for n in range(1, intentos + 1):
        if n > 1:
            pausa = espera_seg * (2 ** (n - 2))
            print(f'  Reintento token {n}/{intentos} (espera {pausa:.0f}s)…')
            time.sleep(pausa)
        ultimo = sii.obtener_token(semilla, ambiente)
        if ultimo.ok:
            return ultimo, n
        if not _es_reintentable(ultimo.error) and (ultimo.estado or '') not in ('', None):
            if (ultimo.estado or '') not in ('10', '12'):
                break
    return ultimo, intentos


def _imprimir_bloque(titulo: str, contenido: str | None) -> None:
    if not contenido:
        return
    print(f'\n--- {titulo} ---')
    print(contenido)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '--ambiente',
        choices=('certificacion', 'produccion'),
        default=None,
        help='Override SII_AMBIENTE para esta ejecución',
    )
    ap.add_argument(
        '--intentos',
        type=int,
        default=3,
        help='Reintentos ante 503 / fallos transitorios (default 3)',
    )
    ap.add_argument(
        '--espera',
        type=float,
        default=5.0,
        help='Segundos base entre reintentos; backoff x2 (default 5)',
    )
    args = ap.parse_args()

    import app as m

    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception as ex:
        print('ERROR cargando .env:', ex)
        return 2

    from services import facturacion_electronica_service as fe
    from services import facturacion_sii_soap as sii

    if args.ambiente:
        os.environ['SII_AMBIENTE'] = args.ambiente

    cfg = fe.obtener_config_certificado()
    path = cfg.get('pfx_path_resolved') or ''
    pfx_ok = bool((cfg.get('pfx_path') or '').strip() and path and os.path.isfile(path))
    amb = sii.normalizar_ambiente(args.ambiente or cfg.get('ambiente'))

    print(f'Ambiente: {amb} ({sii.url_base_sii(amb)})')
    print(f'SOAP habilitado: {sii.soap_habilitado()}')
    print(f'PFX: {cfg.get("pfx_path")} (existe: {pfx_ok})')

    rut_audit = sii.auditar_rut_certificado_vs_empresa()
    print(
        f'RUT empresa config: {rut_audit.get("rut_empresa_config")} | '
        f'RUT certificado: {rut_audit.get("rut_certificado")} | '
        f'coincide: {rut_audit.get("rut_coincide")}'
    )
    if rut_audit.get('error'):
        print('  Aviso certificado:', rut_audit['error'])
    if rut_audit.get('rut_coincide') is False:
        print('  REVISAR: el .pfx no pertenece al RUT configurado en EMPRESA_RUT.')

    print(f'\nSolicitando semilla (hasta {args.intentos} intentos)…')
    sem, n_sem = _obtener_semilla_con_reintentos(sii, amb, args.intentos, args.espera)
    print(f'Semilla: ok={sem.ok} estado={sem.estado} intento={n_sem}')

    tok = None
    n_tok = 0
    if sem.ok and sem.semilla:
        print(f'Solicitando token (hasta {args.intentos} intentos)…')
        tok, n_tok = _obtener_token_con_reintentos(
            sii, sem.semilla, amb, args.intentos, args.espera
        )
        print(f'Token: ok={tok.ok} estado={tok.estado} intento={n_tok}')
    elif not sem.ok:
        tok = sii.ResultadoToken(ok=False, error=sem.error or 'semilla_fallo', estado=sem.estado)

    diag = sii.diagnostico_sii(args.ambiente)
    diag['semilla_intentos'] = n_sem
    diag['token_intentos'] = n_tok
    diag['rut_certificado_audit'] = rut_audit

    print('\n=== Resumen JSON ===')
    resumen = {k: v for k, v in diag.items() if not k.endswith('_cruda') and k != 'token_xml_firmado_enviado'}
    print(json.dumps(resumen, indent=2, ensure_ascii=False))

    if not sem.ok:
        _imprimir_bloque('XML crudo SII — semilla (error)', sem.raw)
        print('\nREVISAR: Maullín/Palena no entregó semilla (503, mantenimiento o firewall).')
        return 1

    if pfx_ok and tok and not tok.ok:
        _imprimir_bloque('XML crudo SII — getToken (respuesta completa)', tok.raw)
        inner = sii._extraer_xml_interno_soap(tok.raw)
        if inner and inner != (tok.raw or ''):
            _imprimir_bloque('XML interno parseado (getTokenReturn)', inner)
        try:
            xml_firmado = sii.firmar_xml_semilla_token(sem.semilla or '')
            _imprimir_bloque(
                'XML firmado enviado a GetTokenFromSeed',
                xml_firmado.decode('iso-8859-1', errors='replace'),
            )
        except Exception as ex:
            print('\n--- Error al generar XML firmado local ---')
            print(ex)
        print('\nREVISAR: semilla OK pero token falló.')
        if tok.estado:
            print(f'  Código ESTADO SII: {tok.estado}')
        if tok.error:
            print(f'  Detalle: {tok.error}')
        if diag.get('token_nota'):
            print(f'  Nota: {diag["token_nota"]}')
        return 1

    if pfx_ok and tok and tok.ok:
        print('\nOK: semilla + token obtenidos correctamente.')
        return 0

    if not pfx_ok:
        print('\nPFX no configurado: solo se validó semilla.')
        return 0

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
