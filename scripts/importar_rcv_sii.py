#!/usr/bin/env python3
"""Importa compras del RCV SII → borradores RecepcionCompra (Pendiente de Items)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_env_local() -> dict[str, str]:
    p = ROOT / '.env.local'
    env: dict[str, str] = {}
    if not p.is_file():
        return env
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        env[k] = v
    return env


def _parse_tipos(raw: str):
    from services.rcv_sii_import_service import TIPOS_DOC_COMPRA_DEFAULT

    out = set()
    for part in (raw or '').split(','):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return frozenset(out) if out else TIPOS_DOC_COMPRA_DEFAULT


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Importar Registro de Compras SII → recepciones borrador en LhexIA ERP.',
    )
    parser.add_argument('--input', '-i', required=True, help='CSV/TXT exportado del RCV (compras)')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo simula: no escribe en base de datos',
    )
    parser.add_argument(
        '--neon',
        action='store_true',
        help='Usar NEON_DATABASE_URL de .env.local (misma BD que www.lhexia.cl / Render)',
    )
    parser.add_argument(
        '--tipos',
        default='33,34,46',
        help='Tipos documento SII a importar (default: 33,34,46 facturas compra)',
    )
    parser.add_argument(
        '--usuario',
        default='RCV-SII',
        help='Texto usuario_bodega en la recepción',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Salida JSON (para automatización)',
    )
    args = parser.parse_args()

    if args.neon:
        env = _load_env_local()
        url = (env.get('NEON_DATABASE_URL') or '').strip()
        if not url:
            print('ERROR: falta NEON_DATABASE_URL en .env.local', file=sys.stderr)
            raise SystemExit(1)
        os.environ['DATABASE_URL'] = url
        os.environ['SQLALCHEMY_DATABASE_URI'] = url
        dest = 'Neon/produccion (NEON_DATABASE_URL)'
    else:
        dest = 'DATABASE_URL de .env.local (suele ser Postgres local)'

    import app as m  # noqa: E402
    from services.rcv_sii_import_service import importar_archivo_rcv  # noqa: E402

    tipos = _parse_tipos(args.tipos)

    with m.app.app_context():
        m._asegurar_columnas_recepcion_rcv()
        res = importar_archivo_rcv(
            args.input,
            dry_run=args.dry_run,
            tipos_doc=tipos,
            usuario_bodega=args.usuario,
        )

    if args.json:
        print(
            json.dumps(
                {
                    'ok': res.ok,
                    'dry_run': res.dry_run,
                    'destino': dest,
                    'archivo': res.archivo,
                    'filas_compra': res.filas_compra,
                    'creadas': res.creadas,
                    'omitidas_duplicado': res.omitidas_duplicado,
                    'proveedores_creados': res.proveedores_creados,
                    'muestra_ids': res.muestra_ids,
                    'errores': res.errores,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        modo = 'SIMULACION' if res.dry_run else 'IMPORTACION'
        print(f'=== RCV SII — {modo} ===')
        print(f'Destino BD: {dest}')
        print(f'Archivo: {res.archivo}')
        print(f'Lineas compra detectadas: {res.filas_compra}')
        print(f'Recepciones {"que se crearian" if res.dry_run else "creadas"}: {res.creadas}')
        print(f'Omitidas (ya existian folio+proveedor): {res.omitidas_duplicado}')
        print(f'Proveedores nuevos: {res.proveedores_creados}')
        if res.muestra_ids:
            print(f'IDs muestra: {", ".join(f"#{i}" for i in res.muestra_ids)}')
        if res.errores:
            print('Errores:')
            for e in res.errores[:30]:
                print(f'  - {e}')
            if len(res.errores) > 30:
                print(f'  ... y {len(res.errores) - 30} mas')

    if not res.ok:
        raise SystemExit(1)
    if res.creadas == 0 and not res.errores:
        print('AVISO: no se creo ninguna recepcion (revisar tipos doc o duplicados).', file=sys.stderr)


if __name__ == '__main__':
    main()
