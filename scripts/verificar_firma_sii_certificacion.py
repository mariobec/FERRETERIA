# -*- coding: utf-8 -*-
"""
Verificación DevOps: .pfx + firmar_xml_dte + set certificación SII + ZIP.

Uso (desde la raíz del proyecto):
    python scripts/verificar_firma_sii_certificacion.py
    python scripts/verificar_firma_sii_certificacion.py --http

Requiere instance/certs/emisor.pfx y variables SII_CERT_* (p. ej. en .env.local).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--http', action='store_true', help='Además llama al endpoint admin con test_client (sesión admin).')
    args = ap.parse_args()

    import app as m

    # Igual que emitir-prueba set: releer credenciales desde archivos locales
    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception:
        traceback.print_exc()
        return 2

    from services import facturacion_electronica_service as fe
    from services import facturacion_sii_certificacion as cert

    root = m.app.root_path
    pfx_resolved = fe.obtener_config_certificado().get('pfx_path_resolved') or ''
    print('--- Config certificado ---')
    print('SII_CERT_PFX_PATH (raw):', (os.getenv('SII_CERT_PFX_PATH') or '(vacío)')[:120])
    print('Ruta resuelta:', pfx_resolved or '(vacía)')
    print('Archivo existe:', bool(pfx_resolved and os.path.isfile(pfx_resolved)))
    print('SII_AMBIENTE:', fe.obtener_config_certificado().get('ambiente'))
    print('--- Prueba firmar_xml_dte (XML mínimo DTE) ---')

    ctx = fe.construir_contexto_dte_prueba(39, folio=999001)
    xml_raw = fe.generar_xml_dte_prueba_lxml(ctx)
    xml_sig, st = fe.firmar_xml_dte(xml_raw)
    print('estado_firma:', st)
    if st.startswith('ERROR_FIRMA'):
        print('--- Traceback último error (si aplica) revisar logs arriba ---')
        traceback.print_exc()
    has_sig = b'Signature' in xml_sig or b'ds:Signature' in xml_sig or b'xmldsig' in xml_sig.lower()
    print('XML contiene nodo Signature:', has_sig)

    print('--- Set certificación (39, 33, 61) ---')
    cfg = m.obtener_config_empresa()
    rut = (os.getenv('EMPRESA_RUT') or cfg.get('rut_emisor') or '76.192.028-5').strip()
    rs = (cfg.get('razon_social') or cfg.get('nombre_comercial') or 'EMPRESA').strip()
    casos, paths = cert.ejecutar_set_certificacion_sii(
        root, rut_emisor=rut, razon_emisor=rs, folio_39=1, folio_33=1, folio_61=1
    )
    for c in casos:
        print(' ', c)
    all_firmado = all(c.get('estado_firma') == 'FIRMADO' for c in casos)
    xml_ok = True
    for p in paths:
        if not os.path.isfile(p):
            print('FALTA archivo:', p)
            xml_ok = False
            continue
        with open(p, 'rb') as fh:
            data = fh.read()
        ok = b'Signature' in data or b'ds:Signature' in data
        print(os.path.basename(p), 'bytes=', len(data), 'Signature=', ok)
        xml_ok = xml_ok and ok

    zip_path = os.path.join(cert.directorio_pruebas_sii(root), 'pruebas_sii_dte_verificacion.zip')
    buf = cert.crear_zip_pruebas_sii(paths)
    with open(zip_path, 'wb') as zf:
        zf.write(buf.getvalue())
    print('ZIP escrito:', zip_path, 'bytes=', os.path.getsize(zip_path))

    if args.http:
        print('--- HTTP test_client (mismo flujo que ?modo=set_certificacion&zip=1) ---')
        m.app.config['TESTING'] = True
        m.app.config['WTF_CSRF_ENABLED'] = False
        with m.app.app_context():
            admin = m.Usuario.query.join(m.Rol).filter(
                m.Rol.nombre.in_(['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin'])
            ).first()
            if not admin:
                admin = m.Usuario.query.first()
            client = m.app.test_client()
            if admin:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(admin.id)
            rv = client.get(
                '/api/admin/facturacion/emitir-prueba'
                '?modo=set_certificacion&zip=1&reload_env=1'
            )
        print('HTTP status:', rv.status_code, 'content-type:', rv.headers.get('Content-Type'))
        if rv.status_code == 200 and 'zip' in (rv.headers.get('Content-Type') or '').lower():
            p2 = os.path.join(cert.directorio_pruebas_sii(root), 'pruebas_sii_dte_http.zip')
            with open(p2, 'wb') as fh:
                fh.write(rv.data)
            print('ZIP HTTP guardado en:', p2)
        else:
            print(rv.get_data(as_text=True)[:2000])

    ok_all = st == 'FIRMADO' and all_firmado and xml_ok
    print('--- RESULTADO ---', 'OK' if ok_all else 'REVISAR (stub, error de clave o XML sin Signature)')
    return 0 if ok_all else 1


if __name__ == '__main__':
    raise SystemExit(main())
