#!/usr/bin/env python3
"""
Preflight cierre SD-1 — comprobaciones rápidas en BD y rutas críticas.

Uso:
  python scripts/sd1_cierre_preflight.py
  python scripts/sd1_cierre_preflight.py --min-almacenes 3

Requiere app Flask y DATABASE_URL (local/QA). No ejecutar contra prod sin cuidado.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main() -> int:
    parser = argparse.ArgumentParser(description='Preflight cierre SD-1')
    parser.add_argument('--min-almacenes', type=int, default=3, help='Mínimo almacenes activos')
    args = parser.parse_args()

    import app as m  # noqa: E402

    with m.app.app_context():
        ok = True
        lines: list[str] = []
        lines.append('=== SD-1 Preflight (LhexIA VERTEX - Fase 1) ===\n')

        # Almacenes
        activos = m.Almacen.query.filter_by(activo=True).count()
        lines.append(f'Almacenes activos: {activos} (mínimo {args.min_almacenes})')
        if activos < args.min_almacenes:
            ok = False
            lines.append('  FAIL - configurar sucursales en Admin > Almacenes')
        else:
            for a in m.Almacen.query.filter_by(activo=True).order_by(m.Almacen.id).all():
                lines.append(f'  - [{a.id}] {a.codigo} - {a.nombre}')

        # Caja abierta (informativo)
        caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
        lines.append(f'\nCaja abierta: {"sí #" + str(caja.id) if caja else "no (abrir para piloto POS)"}')

        # Rutas críticas HTTP (test client)
        client = m.app.test_client()
        rutas = [
            ('GET', '/api/sistema/salud'),
            ('GET', '/login'),
            ('GET', '/inventario/enrolamiento'),
            ('GET', '/inventario/salud'),
            ('GET', '/punto_venta'),
            ('GET', '/owner-mobile'),
            ('GET', '/api/v1/owner/dashboard'),
        ]
        lines.append('\nRutas (sin sesión — esperado 200 o 302/401):')
        for method, path in rutas:
            fn = getattr(client, method.lower())
            r = fn(path)
            st = r.status_code
            good = st in (200, 302, 401, 403)
            if path == '/api/v1/owner/dashboard' and st == 401:
                good = True
            if not good:
                ok = False
            mark = 'OK' if good else 'FAIL'
            lines.append(f'  [{mark}] {method} {path} -> {st}')

        # Productos activos con código (muestra)
        n_prod = m.Producto.query.filter_by(activo=True).count()
        n_barra = (
            m.db.session.query(m.Producto)
            .filter(m.Producto.activo == True, m.Producto.codigo_barra.isnot(None))
            .filter(m.Producto.codigo_barra != '')
            .count()
        )
        lines.append(f'\nProductos activos: {n_prod} | con codigo de barras: {n_barra}')
        if n_prod < 10:
            lines.append('  WARN — catálogo muy pequeño para ferretería')

        lines.append('\n' + ('RESULTADO: OK — listo para checklist piso' if ok else 'RESULTADO: REVISAR ítems FAIL'))
        print('\n'.join(lines))
        return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
