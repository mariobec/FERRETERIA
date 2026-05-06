"""
Crea o actualiza los almacenes TIENDA y BODEGA (códigos que usa el ERP por defecto).

  py crear_almacenes_tienda_bodega.py

Idempotente: si ya existen por código, solo renombra / reactiva.
Tras ejecutar, reiniciá Flask si está corriendo (caché de ids tienda/bodega).
"""
from __future__ import annotations

import sys

from app import Almacen, app, db, _invalidar_cache_ids_almacen


def _upsert_almacen(codigo: str, nombre: str) -> tuple[str, int]:
    c = (codigo or '').strip().upper()[:20]
    row = (
        Almacen.query.filter(db.func.upper(db.func.trim(Almacen.codigo)) == c).first()
    )
    if row:
        row.nombre = (nombre or '').strip()[:100]
        row.activo = True
        db.session.flush()
        return 'actualizado', int(row.id)
    row = Almacen(codigo=c, nombre=(nombre or '').strip()[:100], activo=True)
    db.session.add(row)
    db.session.flush()
    return 'creado', int(row.id)


def main() -> int:
    with app.app_context():
        try:
            t_acc, tid = _upsert_almacen('TIENDA', 'Tienda / Mostrador')
            b_acc, bid = _upsert_almacen('BODEGA', 'Bodega')
            db.session.commit()
            _invalidar_cache_ids_almacen()
            print(f'TIENDA  ({t_acc}) -> id {tid}')
            print(f'BODEGA  ({b_acc}) -> id {bid}')
            print('Listo. Reinicia el servidor Flask si estaba en ejecucion.')
            return 0
        except Exception as ex:
            db.session.rollback()
            print(f'Error: {ex}', file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
