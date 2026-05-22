#!/usr/bin/env python3
"""
Purga operativa en Neon (PRD) antes del debut SD-1 — deja catálogo y transacciones en cero.

CONSERVA: recepciones_compra (cabeceras RCV), proveedores, usuarios/roles/permisos, almacenes.
NO toca la BD local salvo --neon ausente y URL explícita de Neon en DATABASE_URL (bloqueado por defecto).

Uso:
  python scripts/purge_maestro_productos_neon.py --neon --dry-run
  set CONFIRMAR_PURGA_MAESTRO=SI
  python scripts/purge_maestro_productos_neon.py --neon
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]

# Orden: hijas primero (FK). No incluir recepciones_compra ni proveedores.
TABLAS_PURGA: tuple[str, ...] = (
    'agente_ejecuciones',
    'cobranza_recordatorio_whatsapp',
    'reabasto_cliente_wa_log',
    'ventas_cuotas_credito',
    'ventas_a_pedido',
    'detalle_ventas',
    'abonos_credito',
    'movimiento_caja',
    'ventas',
    'caja',
    'cotizacion_detalles',
    'cotizaciones',
    'detalle_recepcion',
    'bitacora_costos_compra',
    'detalle_orden_compra',
    'ordenes_compra',
    'detalle_auditoria',
    'auditorias_inventario',
    'enrolamiento_toma_linea',
    'enrolamiento_toma_sesion',
    'cambios_detalle',
    'cambios_operacion',
    'movimientos_inventario',
    'stock_por_almacen',
    'bitacora_precios_venta',
    'movimientos_saldo_favor',
    'clientes_saldos_favor',
    'cliente_prediccion_log',
    'c360_proactiva_ofertas',
    'c360_llamadas_snapshot_dia',
    'clientes',
    'productos',
)

TABLAS_CONSERVAR: tuple[str, ...] = (
    'recepciones_compra',
    'proveedores',
    'usuarios',
    'roles',
    'permisos',
    'rol_permisos',
    'almacenes',
    'unidades_medida',
    'conversiones_unidad',
    'catalogo_categorias',
    'catalogo_subcategorias',
)


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


def _resolver_url(*, usar_neon: bool) -> str:
    env = _load_env_local()
    if usar_neon:
        url = (env.get('NEON_DATABASE_URL') or '').strip()
        if not url:
            raise SystemExit('ERROR: falta NEON_DATABASE_URL en .env.local')
    else:
        url = (env.get('DATABASE_URL') or '').strip()
        if not url:
            raise SystemExit('ERROR: use --neon para PRD o configure DATABASE_URL')

    low = url.lower()
    if 'localhost' in low or '127.0.0.1' in low or '@localhost:' in low:
        raise SystemExit(
            'BLOQUEADO: esta URL es Postgres LOCAL. Use --neon para PRD '
            '(la BD local del prototipo no se purga con este script).'
        )
    if usar_neon and 'neon.tech' not in low and 'render.com' not in low:
        print(
            'ADVERTENCIA: NEON_DATABASE_URL no parece Neon/Render; revise .env.local',
            file=sys.stderr,
        )
    return url


def _tabla_existe(cur, nombre: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (nombre,),
    )
    return cur.fetchone() is not None


def _contar(cur, nombre: str) -> int | None:
    if not _tabla_existe(cur, nombre):
        return None
    cur.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(nombre)))
    return int(cur.fetchone()[0])


def _host_snippet(url: str) -> str:
    if '@' in url:
        return url.split('@', 1)[1].split('/')[0][:80]
    return url[:40]


def dry_run(conn, url: str) -> int:
    print('=== PURGA MAESTRO — SIMULACION (--dry-run) ===')
    with conn.cursor() as cur:
        print(f'\nDestino: {_host_snippet(url)}')
        print('\n--- Tablas que quedarán en CERO (purga) ---')
        total_purge = 0
        for t in TABLAS_PURGA:
            n = _contar(cur, t)
            if n is None:
                print(f'  {t}: (no existe en BD)')
            else:
                print(f'  {t}: {n:,}')
                total_purge += n

        print('\n--- Tablas CONSERVADAS (no se borran) ---')
        for t in TABLAS_CONSERVAR:
            n = _contar(cur, t)
            if n is None:
                print(f'  {t}: (no existe)')
            else:
                print(f'  {t}: {n:,} filas')

        rcv = _contar(cur, 'recepciones_compra')
        prod = _contar(cur, 'productos')
        print('\n--- Verificación SD-1 ---')
        print(f'  productos después de purga (simulado): 0 (actual: {prod or 0:,})')
        print(f'  recepciones_compra intactas: {rcv or 0:,} (objetivo: ~2.300 cabeceras RCV)')

    print('\nOK dry-run. Para ejecutar:')
    print('  set CONFIRMAR_PURGA_MAESTRO=SI   (PowerShell: $env:CONFIRMAR_PURGA_MAESTRO="SI")')
    print('  python scripts/purge_maestro_productos_neon.py --neon')
    return 0


def ejecutar_purga(conn) -> int:
    confirm = (os.environ.get('CONFIRMAR_PURGA_MAESTRO') or '').strip().upper()
    if confirm != 'SI':
        raise SystemExit(
            'Abortado: defina CONFIRMAR_PURGA_MAESTRO=SI para purga real en PRD.'
        )

    print('=== PURGA MAESTRO — EJECUCION PRD ===')
    with conn.cursor() as cur:
        existentes = [t for t in TABLAS_PURGA if _tabla_existe(cur, t)]
        omitidas = [t for t in TABLAS_PURGA if t not in existentes]
        if omitidas:
            print('Tablas omitidas (no existen):', ', '.join(omitidas))

        for t in existentes:
            antes = _contar(cur, t)
            cur.execute(
                sql.SQL('TRUNCATE TABLE {} RESTART IDENTITY CASCADE').format(
                    sql.Identifier(t)
                )
            )
            print(f'  TRUNCATE {t} (había {antes or 0:,} filas)')

        conn.commit()

        prod = _contar(cur, 'productos')
        rcv = _contar(cur, 'recepciones_compra')
        prov = _contar(cur, 'proveedores')
        ventas = _contar(cur, 'ventas')
        caja = _contar(cur, 'caja')

        print('\n--- Post-purga ---')
        print(f'  productos: {prod or 0}')
        print(f'  ventas: {ventas or 0}')
        print(f'  caja: {caja or 0}')
        print(f'  recepciones_compra: {rcv or 0}')
        print(f'  proveedores: {prov or 0}')

        if (prod or 0) != 0:
            print('ERROR: productos no quedó en 0', file=sys.stderr)
            return 1
        if (ventas or 0) != 0:
            print('ERROR: ventas no quedó en 0', file=sys.stderr)
            return 1

    print('\nOK: purga completada. Siguiente: homologar --maestro + carga masiva en ERP.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Purga catálogo y operación en Neon (PRD SD-1).')
    parser.add_argument(
        '--neon',
        action='store_true',
        help='Usar NEON_DATABASE_URL (obligatorio para PRD; no purga local)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo muestra conteos; no borra datos',
    )
    args = parser.parse_args()

    if not args.neon:
        print(
            'ERROR: indique --neon para apuntar a producción Neon. '
            'La BD local del prototipo no se modifica.',
            file=sys.stderr,
        )
        return 2

    url = _resolver_url(usar_neon=True)
    print(f'Conectando PRD ({_host_snippet(url)})…', flush=True)

    conn = psycopg2.connect(url)
    try:
        if args.dry_run:
            return dry_run(conn, url)
        return ejecutar_purga(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
