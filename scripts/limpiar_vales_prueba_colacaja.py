#!/usr/bin/env python3
"""
Elimina de la BD vales en cola (Pendiente sin metodo de pago, o borrador Abierta)
creados por pruebas automatizadas o seed demo.

Criterios (solo estos documentos):
  - usuario IN ('QA_TEST', 'DEMO_SEED', '__qa_runner__'), o
  - tienen al menos una linea con producto codigo_barra LIKE 'TEST-%'

Por que pueden quedar Pendiente aunque el flujo POS/caja este bien:
  - Los tests crean vales y a veces no ejecutan el POST de cobro en caja.
  - seed_demo_data.py genera vales demo en Pendiente.
  - Pruebas manuales con productos TEST-* dejan documentos sin cobrar.

Seguridad:
  - Aborta si DATABASE_URL apunta a host tipo produccion (misma lista que tests/conftest.py).
  - En BD remota no-localhost exige ademas ALLOW_LIMPIEZA_COLA_PRUEBA=1.

Uso:
  set ALLOW_LIMPIEZA_COLA_PRUEBA=1
  python scripts/limpiar_vales_prueba_colacaja.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_HOSTS_PRODUCCION = (
    'neon.tech', 'render.com', 'railway.app', 'supabase.co',
    'amazonaws.com', 'azure.com', 'elephantsql.com',
)


def _uri() -> str:
    return (os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI') or '').lower()


def _aborto_produccion() -> bool:
    u = _uri()
    if os.getenv('ALLOW_TESTS_ON_REMOTE') == '1':
        return False
    return any(h in u for h in _HOSTS_PRODUCCION)


def _requiere_flag_explicita() -> bool:
    u = _uri()
    if 'localhost' in u or '127.0.0.1' in u:
        return False
    return True


def main() -> int:
    if _aborto_produccion():
        print('ABORTADO: DATABASE_URL parece produccion cloud. No se ejecuta limpieza.')
        return 2
    if _requiere_flag_explicita() and os.getenv('ALLOW_LIMPIEZA_COLA_PRUEBA') != '1':
        print('En esta BD no-localhost defina ALLOW_LIMPIEZA_COLA_PRUEBA=1')
        return 2

    import app as m
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload

    Venta = m.Venta
    DetalleVenta = m.DetalleVenta
    Producto = m.Producto

    usuarios_prueba = ('QA_TEST', 'DEMO_SEED', '__qa_runner__')

    with m.app.app_context():
        q_usuario = (
            m.db.session.query(Venta.id)
            .filter(
                Venta.estado.in_(('Pendiente', 'Abierta')),
                or_(Venta.metodo_pago.is_(None), Venta.metodo_pago == ''),
                Venta.usuario.in_(usuarios_prueba),
            )
        )
        q_test_prod = (
            m.db.session.query(Venta.id)
            .join(DetalleVenta, DetalleVenta.id_venta == Venta.id)
            .join(Producto, Producto.id == DetalleVenta.id_producto)
            .filter(
                Venta.estado.in_(('Pendiente', 'Abierta')),
                or_(Venta.metodo_pago.is_(None), Venta.metodo_pago == ''),
                Producto.codigo_barra.like('TEST-%'),
            )
            .distinct()
        )
        ids = {row[0] for row in q_usuario.all()}
        ids.update(row[0] for row in q_test_prod.all())
        if not ids:
            print('No hay vales/borradores de prueba en cola que coincidan con los criterios.')
            return 0

        ventas = (
            Venta.query.options(joinedload(Venta.detalles), joinedload(Venta.cuotas_credito))
            .filter(Venta.id.in_(ids))
            .order_by(Venta.id.asc())
            .all()
        )
        borrados = 0
        for v in ventas:
            try:
                with m.db.session.begin_nested():
                    ok, err = m._revertir_operaciones_venta_antes_borrar(v, 'limpiar_vales_prueba_colacaja')
                    if not ok:
                        raise ValueError(err or 'reversa fallida')
                    m.db.session.delete(v)
                borrados += 1
            except ValueError as ex:
                print(f'  Saltado venta #{v.id}: {ex}')
                continue
        try:
            m.db.session.commit()
        except Exception as ex:
            m.db.session.rollback()
            print(f'Error commit: {ex}')
            return 1
        print(f'Listo: eliminadas {borrados} venta(s) de prueba en cola (ids candidatos: {len(ids)}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
