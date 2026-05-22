# -*- coding: utf-8 -*-
"""
CAF de certificación Maullín (33 + 39) con RSASK — archivos en disco y opcional BD QA.

Uso:
    python scripts/fe_setup_caf_certificacion_maullin.py
    python scripts/fe_setup_caf_certificacion_maullin.py --bd
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--bd', action='store_true', help='Insertar CAF en tabla cafs (requiere BD QA local).')
    args = ap.parse_args()

    import app as m

    m._load_env_archivos(force_local_overwrite=True)
    os.environ.setdefault('SII_AMBIENTE', 'certificacion')

    from services import facturacion_caf_certificacion as caf_cert

    cfg = m.obtener_config_empresa()
    rut = (os.getenv('EMPRESA_RUT') or cfg.get('rut_emisor') or '8054120-1').strip()
    rs = (os.getenv('EMPRESA_RAZON_SOCIAL') or cfg.get('razon_social') or 'CERT MAULLIN LHEXIA').strip()

    paths = caf_cert.guardar_cafs_certificacion(m.app.root_path, rut_emisor=rut, razon_social=rs)
    print('CAF certificación guardados:')
    for td, p in sorted(paths.items()):
        print('  tipo', td, '->', p)

    if args.bd:
        with m.app.app_context():
            m._asegurar_tabla_cafs_y_columnas_ventas_fe()
            rows = caf_cert.insertar_cafs_certificacion_bd(
                m.db.session, m.Caf, rut_emisor=rut, razon_social=rs, reemplazar=True
            )
            m.db.session.commit()
            info = {str(k): {'id': v.id, 'tipo_dte': v.tipo_dte} for k, v in rows.items()}
            print('BD cafs:', json.dumps(info, indent=2))

    print('SII_AMBIENTE recomendado: certificacion (Maullín)')
    print('Set SII: GET /api/admin/facturacion/emitir-prueba?modo=set_certificacion&reload_env=1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
