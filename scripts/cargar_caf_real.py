#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carga un CAF XML oficial del SII en la tabla `cafs` (Postgres local o Neon).

Uso:
    python scripts/cargar_caf_real.py --input "C:\\ruta\\CAF_39.xml"
    python scripts/cargar_caf_real.py --input CAF_39.xml --tipo-esperado 39 --dry-run
    python scripts/cargar_caf_real.py --input CAF_39.xml --reemplazar-tipo 39
    python scripts/cargar_caf_real.py --input CAF_39.xml --copiar-storage

Requisitos:
    - DATABASE_URL en env_qa.txt / .env.local (misma BD que usa el ERP).
    - XML completo <AUTORIZACION> descargado del portal SII (con bloque CAF/DA/TD/RNG).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    import app as m

    try:
        m._load_env_archivos(force_local_overwrite=True)
    except Exception as ex:
        print('AVISO: no se pudo cargar .env:', ex)


def _normalizar_rut(rut: str) -> str:
    s = (rut or '').strip().upper().replace('.', '')
    if '-' not in s:
        return s
    cuerpo, dv = s.rsplit('-', 1)
    return f'{re.sub(r"\\D", "", cuerpo)}-{dv}'


def _rut_desde_caf_xml(xml_bytes: bytes) -> str | None:
    txt = xml_bytes.decode('utf-8', errors='replace')
    m = re.search(r'<RE>\s*([^<]+)\s*</RE>', txt, re.IGNORECASE)
    if not m:
        return None
    return _normalizar_rut(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description='Cargar CAF real SII → tabla cafs')
    ap.add_argument('--input', '-i', required=True, help='Ruta al XML del CAF')
    ap.add_argument(
        '--tipo-esperado',
        type=int,
        default=39,
        help='Validar que TD en el XML sea este tipo (default 39 boleta)',
    )
    ap.add_argument(
        '--rut-esperado',
        default='8054120-1',
        help='Validar RUT emisor <RE> en el CAF (default 8054120-1)',
    )
    ap.add_argument(
        '--reemplazar-tipo',
        type=int,
        metavar='TD',
        help='Antes de insertar, borra CAF existentes de ese tipo_dte (ej. 39)',
    )
    ap.add_argument(
        '--copiar-storage',
        action='store_true',
        help='Copia el XML a storage/dtes/caf/CAF_tipo{N}_{desde}-{hasta}.xml',
    )
    ap.add_argument('--dry-run', action='store_true', help='Solo validar, no escribe en BD')
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print('ERROR: no existe archivo:', in_path)
        return 2

    xml_bytes = in_path.read_bytes()
    if not xml_bytes.strip():
        print('ERROR: archivo vacío')
        return 2

    _load_env()
    from services import facturacion_caf_service as caf_svc
    import app as m

    try:
        parsed = caf_svc.parse_caf_autorizacion_xml(xml_bytes)
    except ValueError as ex:
        print('ERROR parseo CAF:', ex)
        return 2

    rut_xml = _rut_desde_caf_xml(xml_bytes)
    rut_ok = _normalizar_rut(args.rut_esperado)
    print('=== CAF parseado ===')
    print(f"  tipo_dte (TD):     {parsed['tipo_dte']}")
    print(f"  rango:             {parsed['rango_desde']} — {parsed['rango_hasta']}")
    print(f"  fecha_autorizacion:{parsed['fecha_autorizacion']}")
    print(f"  RUT <RE> en XML:   {rut_xml or '(no encontrado)'}")
    print(f"  RUT esperado:      {rut_ok}")
    folios_disp = parsed['rango_hasta'] - parsed['rango_desde'] + 1
    print(f"  folios disponibles: {folios_disp}")

    if int(parsed['tipo_dte']) != int(args.tipo_esperado):
        print(f"ERROR: TD={parsed['tipo_dte']} distinto de --tipo-esperado {args.tipo_esperado}")
        return 2
    if rut_xml and rut_xml != rut_ok:
        print('ERROR: RUT del CAF no coincide con --rut-esperado')
        return 2

    amb = (os.getenv('SII_AMBIENTE') or 'certificacion').strip().lower()
    print(f"\n  SII_AMBIENTE actual: {amb}")
    if amb in ('prod', 'produccion', 'palena', 'production'):
        print('  >> CAF de PRODUCCION (Palena): coherente con ambiente.')
    else:
        print('  >> Ambiente CERTIFICACION (Maullin): use CAF del set de')
        print('     certificacion en maullin.sii.cl, no el de produccion Palena.')

    if args.dry_run:
        print('\n[DRY-RUN] No se escribió en la base de datos.')
        return 0

    with m.app.app_context():
        m._asegurar_tabla_cafs_y_columnas_ventas_fe()
        if args.reemplazar_tipo is not None:
            td = int(args.reemplazar_tipo)
            n = (
                m.db.session.query(m.Caf)
                .filter(m.Caf.tipo_dte == td)
                .delete(synchronize_session=False)
            )
            m.db.session.commit()
            print(f'\n[CAF] Eliminados {n} registro(s) previos tipo_dte={td}')

        if caf_svc.caf_duplicado_rango(
            m.db.session,
            m.Caf,
            parsed['tipo_dte'],
            parsed['rango_desde'],
            parsed['rango_hasta'],
        ):
            print('ERROR: ya existe un CAF con el mismo tipo y rango en cafs.')
            print('       Use --reemplazar-tipo 39 o borre el duplicado manualmente.')
            return 2

        row, info = caf_svc.insertar_caf_desde_xml(m.db.session, m.Caf, xml_bytes)
        m.db.session.commit()

        if args.copiar_storage:
            dest_dir = ROOT / 'storage' / 'dtes' / 'caf'
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / (
                f"CAF_tipo{parsed['tipo_dte']}_{parsed['rango_desde']}-{parsed['rango_hasta']}.xml"
            )
            shutil.copy2(in_path, dest)
            print(f'  Copia en: {dest}')

        print('\n=== CAF registrado ===')
        print(f"  id:          {row.id}")
        print(f"  usado_hasta: {row.usado_hasta} (primer folio al cobrar: {parsed['rango_desde']})")
        print(f"  info:        {info}")
        print('\nVerifique en el ERP: /admin/facturacion/caf')
        print('Próximo cobro con Boleta asignará folio', parsed['rango_desde'], 'si es el único CAF 39 activo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
