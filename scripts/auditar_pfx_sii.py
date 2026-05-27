# -*- coding: utf-8 -*-
"""
Compara uno o más archivos .pfx para FE SII (Maullín/Palena).

Uso:
    python scripts/auditar_pfx_sii.py ruta\cert1.pfx ruta\cert2.pfx
    python scripts/auditar_pfx_sii.py cert1.pfx --password "clave" --probar-token

No sube certificados al repo; solo lee rutas locales.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Usuarios con Firmar+Enviar en Maullín (8054120-1) — actualizar si cambia el portal.
USUARIOS_FIRMAR_ENVIAR_MAULLIN = {
    '8054120-1': 'LUIS GASTON RIVERA PEREZ (titular empresa, recomendado)',
    '9788569-9': 'LADISLAO ROBERTO CORTES TOBAR',
}


def _cargar_pfx(path: str, password: Optional[str]) -> Tuple[Any, Any]:
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(path, 'rb') as fh:
        raw = fh.read()
    intentos: List[Optional[bytes]] = []
    if password:
        intentos.append(password.encode('utf-8'))
    intentos.extend([None, b''])
    last_err: Optional[Exception] = None
    for pw in intentos:
        try:
            pk, cert, _x = pkcs12.load_key_and_certificates(raw, pw)
            if pk is not None and cert is not None:
                return pk, cert
        except ValueError as ex:
            last_err = ex
    if last_err:
        raise last_err
    raise ValueError('pfx_sin_clave_valida')


def _subject_cn(cert: Any) -> str:
    try:
        from cryptography.x509.oid import NameOID

        for attr in cert.subject:
            if attr.oid == NameOID.COMMON_NAME:
                return str(attr.value or '').strip()
    except Exception:
        pass
    return ''


def _vigencia(cert: Any) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    nb = cert.not_valid_before_utc
    na = cert.not_valid_after_utc
    return {
        'desde': nb.isoformat() if nb else None,
        'hasta': na.isoformat() if na else None,
        'vigente': bool(nb and na and nb <= now <= na),
    }


def inspeccionar_pfx(
    path: str,
    *,
    password: Optional[str],
    rut_empresa: str,
) -> Dict[str, Any]:
    from services import facturacion_sii_soap as sii

    out: Dict[str, Any] = {
        'archivo': path,
        'existe': os.path.isfile(path),
        'ok': False,
        'error': None,
    }
    if not out['existe']:
        out['error'] = 'archivo_no_encontrado'
        return out

    try:
        _pk, cert = _cargar_pfx(path, password)
        rut_cert = sii.extraer_rut_desde_certificado(cert)
        cuerpo_e, dv_e = sii.split_rut(rut_empresa)
        rut_emp_norm = f'{cuerpo_e}-{dv_e}'
        coincide_empresa = False
        if rut_cert:
            c, d = sii.split_rut(rut_cert)
            coincide_empresa = c == cuerpo_e and d == dv_e

        vig = _vigencia(cert)
        autorizado_maullin = rut_cert in USUARIOS_FIRMAR_ENVIAR_MAULLIN

        veredicto: List[str] = []
        if not vig.get('vigente'):
            veredicto.append('DESCARTAR: certificado vencido o aún no vigente')
        if coincide_empresa:
            veredicto.append('RECOMENDADO: RUT = empresa 8054120-1 (mismo que portal con todos los permisos)')
        elif autorizado_maullin:
            veredicto.append(
                f'POSIBLE: RUT {rut_cert} está en Maullín con Firmar/Enviar — '
                f'{USUARIOS_FIRMAR_ENVIAR_MAULLIN[rut_cert]}'
            )
        elif rut_cert:
            veredicto.append(
                f'DESCARTAR para token empresa: RUT {rut_cert} no es 8054120-1 '
                'ni usuario con Firmar+Enviar en Maullín'
            )
        else:
            veredicto.append('REVISAR: no se pudo leer RUT del certificado')

        out.update(
            {
                'ok': True,
                'rut_certificado': rut_cert,
                'nombre_cn': _subject_cn(cert),
                'rut_empresa': rut_emp_norm,
                'coincide_empresa': coincide_empresa,
                'autorizado_maullin_firmar': autorizado_maullin,
                'vigencia': vig,
                'veredicto': veredicto,
            }
        )
    except Exception as ex:
        out['error'] = f'{type(ex).__name__}:{str(ex)[:300]}'
        if 'password' in str(ex).lower() or 'invalid' in str(ex).lower():
            out['veredicto'] = ['DESCARTAR o reintentar: clave .pfx incorrecta']
    return out


def _probar_token_con_pfx(path: str, password: Optional[str]) -> Dict[str, Any]:
    """Prueba semilla+token usando este .pfx (sin cambiar emisor.pfx del proyecto)."""
    from unittest.mock import patch

    import services.facturacion_sii_soap as sii_mod

    def _loader():
        return _cargar_pfx(path, password)

    with patch.object(sii_mod, '_cargar_clave_certificado_pfx', _loader):
        sem = sii_mod.obtener_semilla('certificacion')
        if not sem.ok or not sem.semilla:
            return {
                'semilla_ok': sem.ok,
                'semilla_estado': sem.estado,
                'token_ok': False,
                'token_estado': None,
                'error': sem.error,
            }
        tok = sii_mod.obtener_token(sem.semilla, 'certificacion')
        return {
            'semilla_ok': True,
            'semilla_estado': sem.estado,
            'token_ok': tok.ok,
            'token_estado': tok.estado,
            'error': tok.error,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description='Auditar .pfx para SII / LhexIA')
    ap.add_argument('pfx', nargs='+', help='Rutas a archivos .pfx')
    ap.add_argument('--password', '-p', help='Clave del .pfx (si no, prueba vacía y la de SII_CERT_PASSWORD)')
    ap.add_argument('--rut-empresa', default=os.getenv('EMPRESA_RUT', '8054120-1'))
    ap.add_argument(
        '--probar-token',
        action='store_true',
        help='Llama Maullín semilla+token con cada .pfx (lento, requiere red)',
    )
    args = ap.parse_args()

    pw = args.password
    if not pw:
        try:
            import app as m

            m._load_env_archivos(force_local_overwrite=True)
            from services import facturacion_electronica_service as fe

            pw = fe._leer_password_pfx_texto_plano(fe.obtener_config_certificado())
        except Exception:
            pw = None

    print(f'Empresa configurada: {args.rut_empresa}\n')
    mejor: Optional[str] = None

    for ruta in args.pfx:
        print('=' * 60)
        print('Archivo:', os.path.abspath(ruta))
        info = inspeccionar_pfx(ruta, password=pw, rut_empresa=args.rut_empresa)
        if info.get('ok'):
            print('  RUT certificado:', info.get('rut_certificado'))
            print('  Nombre (CN):', info.get('nombre_cn'))
            print('  Coincide empresa:', info.get('coincide_empresa'))
            print('  Vigente:', info.get('vigencia', {}).get('vigente'))
            print('  Válido hasta:', info.get('vigencia', {}).get('hasta'))
            for v in info.get('veredicto') or []:
                print('  ->', v)
            if info.get('coincide_empresa') and info.get('vigencia', {}).get('vigente'):
                mejor = ruta
        else:
            print('  Error:', info.get('error'))
            for v in info.get('veredicto') or []:
                print('  ->', v)

        if args.probar_token and info.get('ok'):
            print('  --- Prueba token Maullín ---')
            tok = _probar_token_con_pfx(ruta, pw)
            print('  Semilla:', tok.get('semilla_estado'))
            print('  Token:', tok.get('token_estado'), tok.get('error') or 'OK')
            if tok.get('token_ok'):
                mejor = ruta
                print('  -> ESTE .pfx obtuvo TOKEN 00')
        print()

    if mejor:
        print('Sugerencia: usar como emisor.pfx ->', os.path.abspath(mejor))
        print('Copiar a instance/certs/emisor.pfx y ajustar SII_CERT_PASSWORD si la clave difiere.')
    else:
        print('Ningún .pfx cumplió RUT empresa + vigencia. Revise claves y usuarios Maullín.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
