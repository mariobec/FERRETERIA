#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico integral FE facturas (33) — LhexIA ERP.

Uso:
    python scripts/fe_resolver_facturas.py
    python scripts/fe_resolver_facturas.py --reintentar 3040
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description='Resolver FE facturas LhexIA')
    ap.add_argument('--reintentar', type=int, metavar='VENTA_ID', help='Reintentar envío SII de una venta')
    args = ap.parse_args()

    import app as m
    from services import facturacion_electronica_service as fe
    from services import facturacion_sii_soap as sii

    m._load_env_archivos(force_local_overwrite=True)
    with m.app.app_context():
        m._asegurar_tabla_cafs_y_columnas_ventas_fe()

        print('=== Resolver facturas LhexIA (tipo 33) ===\n')

        # CAF 33
        caf33 = (
            m.db.session.query(m.Caf)
            .filter(m.Caf.tipo_dte == 33)
            .order_by(m.Caf.id.desc())
            .first()
        )
        if caf33:
            disp = int(caf33.rango_hasta) - int(caf33.usado_hasta or 0)
            if int(caf33.usado_hasta or 0) < int(caf33.rango_desde):
                disp = int(caf33.rango_hasta) - int(caf33.rango_desde) + 1
            print(
                f'CAF 33: id={caf33.id} rango {caf33.rango_desde}-{caf33.rango_hasta} '
                f'usado_hasta={caf33.usado_hasta} (~{max(0, disp)} folios libres)'
            )
        else:
            print('CAF 33: NO CARGADO — reobtener en Maullín y cargar_caf_real.py')

        # Cola
        pend = (
            m.Venta.query.filter(
                m.Venta.dte_tipo == 33,
                m.Venta.dte_estado == fe.DTE_ESTADO_PENDIENTE_ENVIO,
            )
            .count()
        )
        print(f'Cola facturas PENDIENTE_ENVIO: {pend}')

        # SII
        diag = sii.diagnostico_sii()
        print(f"\nSII ambiente: {diag.get('ambiente')} ({diag.get('url_base')})")
        print(f"PFX: {diag.get('pfx_configurado')} | RUT coincide: {diag.get('rut_coincide')}")
        print(f"Semilla: {diag.get('semilla_ok')} estado={diag.get('semilla_estado')}")
        print(f"Token:   {diag.get('token_ok')} estado={diag.get('token_estado')}")
        if diag.get('token_nota'):
            print(f"  Nota: {diag.get('token_nota')}")
        if not diag.get('token_ok'):
            print(
                '\n--- ACCIONES PORTAL (Maullín) ---\n'
                '1. Certificado: mismo .pfx que entra al portal (8054120-1).\n'
                '2. Menu certificacion - Sistema facturacion de mercado -\n'
                '   Actualizacion datos empresa autorizada - software LhexIA + URL lhexia.cl\n'
                '   (La pantalla Multicaja es solo para BOLETAS Klap.)\n'
                '3. Modificar Usuarios: RUT del certificado autorizado.\n'
                '4. SII 227175600 si sigue ESTADO 10.\n'
                '5. En .env.local: SII_FCH_RESOLUCION=2021-03-24  SII_NRO_RESOLUCION=0\n'
            )

        if args.reintentar:
            vid = int(args.reintentar)
            print(f'\nReintentando venta #{vid}...')
            r = fe.reintentar_emision_fe_venta(
                m.db.session,
                vid,
                m.Venta,
                m.Caf,
                m.obtener_config_empresa,
                m.app.logger,
                erp_root=m.app.root_path,
            )
            if r.get('ok'):
                m.db.session.commit()
            else:
                m.db.session.rollback()
            print(json.dumps(r, indent=2, ensure_ascii=False))
            v = m.db.session.get(m.Venta, vid)
            if v:
                print(
                    f"Estado final: dte_estado={v.dte_estado} folio={v.nro_documento} "
                    f"track={v.dte_track_id}"
                )

        print('\n=== Fin ===')
        return 0 if diag.get('token_ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
