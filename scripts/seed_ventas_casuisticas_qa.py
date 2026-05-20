#!/usr/bin/env python3
"""
Seed QA — catálogo de casuísticas venta / caja / entrega / compras.

Crea productos TEST-CAS-*, clientes (crédito, saldo a favor, obra C360),
stock tienda+bodega y opcionalmente ventas de ejemplo.

Uso:
    python scripts/seed_ventas_casuisticas_qa.py
    python scripts/seed_ventas_casuisticas_qa.py --clean
    python scripts/seed_ventas_casuisticas_qa.py --con-ventas-ejemplo
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as m
from tests.qa_catalogo_casuisticas import (
    ESCENARIOS_VENTA,
    QA_CAS_USER,
    limpiar_catalogo_casuisticas,
    upsert_catalogo_casuisticas,
)

db = m.db


def _asegurar_caja():
    caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
    if caja:
        return caja
    caja = m.Caja(
        monto_inicial=100_000,
        usuario_apertura=QA_CAS_USER,
        estado='Abierta',
        fecha_apertura=datetime.now(),
    )
    db.session.add(caja)
    db.session.commit()
    return caja


def _ventas_ejemplo(productos, clientes, caja):
    """Vales Pendiente de muestra (sin cobrar) para probar caja manualmente."""
    by = {p.codigo_barra: p for p in productos}
    cli_sf = next(c for c in clientes if c.rut == '22.222.222-2')
    cli_obra = next(c for c in clientes if c.rut == '33.333.333-3')

    # Vale tienda — cliente obra
    v1 = m.Venta(
        fecha=datetime.now(), monto_total=0, usuario=QA_CAS_USER,
        estado='Abierta', caja_id=caja.id, cliente_id=cli_obra.id, punto_retiro='Tienda')
    db.session.add(v1)
    db.session.flush()
    p_cem = by['TEST-CAS-CEM-001']
    db.session.add(m.DetalleVenta(
        id_venta=v1.id, id_producto=p_cem.id, cantidad=2,
        precio_unitario=p_cem.precio_venta, subtotal=2 * p_cem.precio_venta))
    v1.recalcular_total()
    v1.estado = 'Pendiente'

    # Vale bodega — cliente saldo favor
    v2 = m.Venta(
        fecha=datetime.now(), monto_total=0, usuario=QA_CAS_USER,
        estado='Abierta', caja_id=caja.id, cliente_id=cli_sf.id, punto_retiro='Bodega')
    db.session.add(v2)
    db.session.flush()
    p_pvc = by['TEST-CAS-PVC-001']
    db.session.add(m.DetalleVenta(
        id_venta=v2.id, id_producto=p_pvc.id, cantidad=5,
        precio_unitario=p_pvc.precio_venta, subtotal=5 * p_pvc.precio_venta,
        punto_retiro_linea='Bodega'))
    v2.recalcular_total()
    v2.estado = 'Pendiente'

    db.session.commit()
    print(f'  [OK] Vales ejemplo: #{v1.id} (Tienda/obra), #{v2.id} (Bodega/saldo favor)')


def main():
    parser = argparse.ArgumentParser(description='Seed catálogo casuísticas QA ventas')
    parser.add_argument('--clean', action='store_true', help='Borra datos TEST-CAS antes de sembrar')
    parser.add_argument('--con-ventas-ejemplo', action='store_true', help='Crea 2 vales Pendiente de muestra')
    args = parser.parse_args()

    from sqlalchemy import text as sa_text

    print('=' * 56)
    print('  SEED CASUÍSTICAS QA — venta · caja · entrega · compras')
    print('=' * 56)

    with m.app.app_context():
        if args.clean:
            print('[CAS] Limpiando TEST-CAS...')
            limpiar_catalogo_casuisticas(db, m, sa_text)

        productos, clientes = upsert_catalogo_casuisticas(db, m)
        print(f'[CAS] Productos: {len(productos)} | Clientes: {len(clientes)}')
        for p in productos:
            pre = ' [OFERTA POS]' if getattr(p, 'pos_descuento_preautorizado', False) else ''
            print(f'      {p.codigo_barra} — {p.nombre}{pre}')
        for c in clientes:
            sf = m._saldo_favor_actual(c.id)
            print(f'      {c.rut} — {c.nombre} | deuda={c.saldo_deudor:,.0f} | saldo_favor={sf:,.0f} | etapa={c.c360_etapa_actual}')

        if args.con_ventas_ejemplo:
            caja = _asegurar_caja()
            _ventas_ejemplo(productos, clientes, caja)

        print('\nEscenarios documentados (tests/test_ventas_casuisticas_flujo.py):')
        for sid, desc in ESCENARIOS_VENTA.items():
            print(f'  {sid}: {desc}')
        print('\nListo. Ejecute: pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -v')


if __name__ == '__main__':
    main()
