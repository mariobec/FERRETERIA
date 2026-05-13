# -*- coding: utf-8 -*-
"""
Inserta CAF de laboratorio (XML mock) para tipos 33, 39 y 61 — rango folios 1..100.

Uso:
    python scripts/seed_caf_certificacion_sii.py
    python scripts/seed_caf_certificacion_sii.py --reemplazar

Reemplaza solo filas cuyo caf_xml contiene el marcador de mock (no borra CAF real del SII).
El XML mock no incluye FRMA firmada: sustituir por el CAF oficial de certificación cuando lo tengan.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as m
from services.facturacion_sii_certificacion import mock_caf_xml

db = m.db
flask_app = m.app
Caf = m.Caf

MOCK_MARK = 'MOCK CERTIFICACION SII'
TIPOS = (33, 39, 61)
DESDE, HASTA = 1, 100


def _rut_emisor() -> str:
    cfg = m.obtener_config_empresa()
    return (os.getenv('EMPRESA_RUT') or cfg.get('rut_emisor') or '76.192.028-5').strip()


def main() -> None:
    ap = argparse.ArgumentParser(description='Semilla tabla cafs para certificación SII (mock).')
    ap.add_argument(
        '--reemplazar',
        action='store_true',
        help='Elimina CAF mock previos (marcador interno) e inserta de nuevo.',
    )
    args = ap.parse_args()
    rut = _rut_emisor()

    with flask_app.app_context():
        if args.reemplazar:
            q = db.session.query(Caf).filter(Caf.caf_xml.like('%' + MOCK_MARK + '%'))
            n = q.delete(synchronize_session=False)
            db.session.commit()
            print('[CAF] Eliminados registros mock previos: %s' % n)

        for td in TIPOS:
            re_caf = rut.replace('.', '').strip()
            xml = mock_caf_xml(td, DESDE, HASTA, rut_emisor=re_caf or '761920285')
            row = Caf(
                tipo_dte=int(td),
                rango_desde=DESDE,
                rango_hasta=HASTA,
                caf_xml=xml,
                fecha_autorizacion=date.today(),
                usado_hasta=0,
            )
            db.session.add(row)
        db.session.commit()
        print('[CAF] Insertados tipos %s rango %s..%s RUT emisor %s' % (TIPOS, DESDE, HASTA, rut))


if __name__ == '__main__':
    main()
