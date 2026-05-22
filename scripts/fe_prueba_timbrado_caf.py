# -*- coding: utf-8 -*-
"""
Genera XML boleta 39 con TED usando un archivo AUTORIZACION del SII (con RSASK).

Uso:
    python scripts/fe_prueba_timbrado_caf.py ruta/al/caf_tipo39.xml
    python scripts/fe_prueba_timbrado_caf.py ruta/caf.xml --folio 100
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('caf_xml', help='Archivo AUTORIZACION descargado del portal SII')
    ap.add_argument('--folio', type=int, default=1)
    ap.add_argument('--dte-tipo', type=int, default=39)
    args = ap.parse_args()

    import app as m

    m._load_env_archivos(force_local_overwrite=True)
    from services import facturacion_electronica_service as fe
    from services import facturacion_ted_service as ted

    path = args.caf_xml
    if not os.path.isfile(path):
        print('No existe:', path)
        return 1
    with open(path, 'rb') as fh:
        caf_bytes = fh.read()

    try:
        ted.extraer_rsask_pem(caf_bytes)
        print('OK: CAF contiene RSASK')
    except ValueError as ex:
        print('ERROR CAF:', ex)
        print('El XML del SII debe incluir bloque <RSASK> con clave privada PEM.')
        return 1

    ctx = fe.construir_contexto_dte_prueba(args.dte_tipo, folio=args.folio)
    xml = fe.generar_xml_dte_prueba_lxml(ctx, caf_autorizacion_xml=caf_bytes)
    out_dir = os.path.join(m.app.root_path, 'storage', 'dtes', 'pruebas_sii')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'DTE_%s_FOLIO_%s_TIMBRADO.xml' % (args.dte_tipo, args.folio))
    with open(out, 'wb') as fh:
        fh.write(xml)

    has_ted = b'TED' in xml and b'FRMT' in xml
    print('Archivo:', out)
    print('TED+FRMT:', has_ted, 'bytes:', len(xml))
    if not has_ted:
        print('REVISAR: timbrado no insertó TED (ver logs)')
        return 1

    xml_sig, st_firma = fe.firmar_xml_dte(xml)
    out_sig = out.replace('.xml', '_firmado.xml')
    with open(out_sig, 'wb') as fh:
        fh.write(xml_sig)
    print('Firma emisor:', st_firma, '->', out_sig)
    return 0 if st_firma == 'FIRMADO' else 1


if __name__ == '__main__':
    raise SystemExit(main())
