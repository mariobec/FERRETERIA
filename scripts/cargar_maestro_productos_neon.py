#!/usr/bin/env python3
"""Carga masiva maestro productos (CSV homologado) directo a Neon — lotes, sin timeout HTTP."""
from __future__ import annotations

import argparse
import csv
import io
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


def _clip(v, max_len: int) -> str:
    return str(v or '').strip()[:max_len]


def _to_float(v, default=0.0) -> float:
    try:
        if v is None or str(v).strip() == '':
            return float(default)
        return float(str(v).replace(',', '.'))
    except Exception:
        return float(default)


def main() -> None:
    parser = argparse.ArgumentParser(description='Carga CSV maestro Chilemat a Neon (lotes).')
    parser.add_argument(
        '--input',
        '-i',
        default=str(ROOT / 'CARGA DE DATOS' / 'productos_homologados_sd.csv'),
        help='CSV homologado (--maestro)',
    )
    parser.add_argument('--neon', action='store_true', help='Usar NEON_DATABASE_URL de .env.local')
    parser.add_argument('--dry-run', action='store_true', help='Solo contar filas, no escribe')
    parser.add_argument('--lote', type=int, default=400, help='Commit cada N filas')
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        raise SystemExit(f'No existe: {in_path}')

    if args.neon:
        env = _load_env_local()
        url = (env.get('NEON_DATABASE_URL') or '').strip()
        if not url:
            raise SystemExit('ERROR: falta NEON_DATABASE_URL en .env.local')
        os.environ['DATABASE_URL'] = url
        os.environ['SQLALCHEMY_DATABASE_URI'] = url
        if 'neon.tech' in url.lower():
            os.environ.pop('PGOPTIONS', None)
        dest = 'Neon (NEON_DATABASE_URL)'
    else:
        dest = 'DATABASE_URL de .env.local'

    texto = None
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            texto = in_path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise SystemExit('No se pudo leer el CSV (UTF-8 / Latin-1)')

    reader = csv.DictReader(io.StringIO(texto))
    filas = list(reader)
    print(f'Destino: {dest}')
    print(f'Archivo: {in_path} ({len(filas)} filas)')

    if args.dry_run:
        print('DRY-RUN: sin cambios en BD.')
        return

    import app as m
    from app import Producto, db
    from services.venta_service import transaccion_critica

    creados = actualizados = omitidos = 0
    lote = max(50, min(args.lote, 1000))

    with m.app.app_context():
        for batch_start in range(0, len(filas), lote):
            batch = filas[batch_start:batch_start + lote]
            with transaccion_critica():
                for row in batch:
                    codigo = _clip(row.get('codigo_barra') or row.get('codigo') or '', 50)
                    interno = _clip(row.get('codigo_interno') or '', 32)
                    nombre = _clip(row.get('nombre') or '', 100)
                    if not nombre or (not codigo and not interno):
                        omitidos += 1
                        continue

                    prod = None
                    if codigo:
                        prod = Producto.query.filter_by(codigo_barra=codigo).first()
                    if prod is None and interno:
                        prod = Producto.query.filter_by(codigo_interno=interno).first()
                    es_nuevo = prod is None
                    if es_nuevo:
                        if not codigo:
                            omitidos += 1
                            continue
                        prod = Producto(codigo_barra=codigo, activo=True)
                        db.session.add(prod)

                    prod.nombre = nombre
                    cm = _clip(row.get('codigo_chilemat') or '', 80)
                    if cm:
                        prod.codigo_chilemat = cm
                    ci = _clip(row.get('codigo_interno') or '', 32)
                    if ci:
                        prod.codigo_interno = ci
                    prod.precio_compra = _to_float(row.get('precio_compra'), 0)
                    pv = row.get('precio_venta')
                    if pv is not None and str(pv).strip() != '':
                        prod.precio_venta = _to_float(pv, 0)
                    prod.precio_mayoreo = _to_float(row.get('precio_mayoreo'), 0)
                    prod.stock = 0
                    prod.unidad = _clip(row.get('unidad_venta') or row.get('unidad') or 'Unidad', 20)
                    prod.unidad_compra = _clip(
                        row.get('unidad_compra') or row.get('unidad_venta') or 'Unidad', 20
                    )
                    prod.unidad_venta = _clip(row.get('unidad_venta') or 'Unidad', 20)
                    prod.factor_conversion = _to_float(row.get('factor_conversion'), 1) or 1.0
                    cat = _clip(row.get('categoria') or '', 50)
                    prod.categoria = cat or None
                    sub = _clip(row.get('subcategoria') or '', 50)
                    prod.subcategoria = sub or None
                    prod.activo = True

                    if es_nuevo:
                        creados += 1
                    else:
                        actualizados += 1

            db.session.commit()
            print(f'  Lote {batch_start + 1}-{batch_start + len(batch)} OK')

        total = Producto.query.filter_by(activo=True).count()
        print('=== FIN ===')
        print(f'Creados: {creados} | Actualizados: {actualizados} | Omitidos: {omitidos}')
        print(f'Productos activos en BD: {total}')


if __name__ == '__main__':
    main()
