#!/usr/bin/env python3
"""
Demo Guardián — ventas hoy, 1 caja con descuadre, 2 alertas inventario (Neon).

Uso (PC tienda, .env.local con NEON + AGENTE_OPERADOR_USE_NEON=1):
  python scripts/seed_guardian_demo_hoy.py
  python scripts/seed_guardian_demo_hoy.py --clean
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._agente_env import cargar_env_local, resolver_database_url  # noqa: E402

TAG = 'GUARDIAN-DEMO-HOY'
DEDUPE_CAJA = f'operador:{TAG}:caja_descuadre'
DEDUPE_INV1 = f'operador:{TAG}:inv_1'
DEDUPE_INV2 = f'operador:{TAG}:inv_2'


def _limpiar(m):
    from app import AgenteEjecucion, Caja, DetalleVenta, MovimientoCaja, Venta, db

    cajas = Caja.query.filter(Caja.usuario_apertura.like(f'{TAG}%')).all()
    cids = [c.id for c in cajas]
    if cids:
        vids = [r[0] for r in db.session.query(Venta.id).filter(Venta.caja_id.in_(cids)).all()]
        if vids:
            DetalleVenta.query.filter(DetalleVenta.id_venta.in_(vids)).delete(synchronize_session=False)
            Venta.query.filter(Venta.id.in_(vids)).delete(synchronize_session=False)
        MovimientoCaja.query.filter(MovimientoCaja.caja_id.in_(cids)).delete(synchronize_session=False)
        Caja.query.filter(Caja.id.in_(cids)).delete(synchronize_session=False)

    AgenteEjecucion.query.filter(AgenteEjecucion.dedupe_key.like(f'%{TAG}%')).delete(
        synchronize_session=False
    )
    db.session.commit()


def _productos(m, n=3):
    ps = (
        m.Producto.query.filter(m.Producto.codigo_barra.like('TEST-%'), m.Producto.activo.is_(True))
        .order_by(m.Producto.id.asc())
        .limit(n)
        .all()
    )
    if len(ps) < 2:
        ps = m.Producto.query.filter_by(activo=True).order_by(m.Producto.id.asc()).limit(n).all()
    if not ps:
        raise SystemExit('No hay productos activos en BD.')
    return ps


def seed():
    import app as m
    from app import Caja, Cliente, DetalleVenta, Venta, db
    from services.agente_ejecuciones_service import (
        EST_ALERTA_ABIERTA,
        TIPO_ALERTA,
        crear_registro,
        existe_dedupe_abierta,
    )
    from services.agente_operador_service import (
        ejecutar_lote_enriquecimiento,
        escanear_y_registrar_alertas,
    )

    m._asegurar_columnas_caja_cuadratura()
    m._asegurar_tabla_agente_ejecuciones()

    ahora = datetime.now()
    hoy = ahora.date()
    cliente = m.obtener_o_crear_cliente_final()
    productos = _productos(m)
    usuario = 'Admin'

    # --- Caja cerrada hoy con descuadre (+$12.500) ---
    fondo = 80_000
    venta_ef = 45_000
    venta_db = 32_000
    teorico = fondo + venta_ef
    declarado = teorico + 12_500

    caja = Caja(
        monto_inicial=float(fondo),
        usuario_apertura=f'{TAG} Admin',
        estado='Cerrada',
        fecha_apertura=datetime.combine(hoy, datetime.min.time().replace(hour=8, minute=30)),
        fecha_cierre=ahora - timedelta(minutes=20),
        monto_declarado_cajero=float(declarado),
        monto_declarado_tarjeta=float(venta_db),
        monto_final=float(declarado),
        monto_teorico_cierre=float(teorico),
        monto_contado_cierre=float(declarado),
        diferencia_cierre=float(declarado - teorico),
        observacion_cierre=f'{TAG} cierre demo con descuadre',
        modo_cierre_arqueo='visible',
    )
    db.session.add(caja)
    db.session.flush()

    ventas = []
    for i, (prod, monto, mp) in enumerate(
        (
            (productos[0], venta_ef, 'Efectivo'),
            (productos[1], venta_db, 'Debito'),
            (productos[2] if len(productos) > 2 else productos[0], 28_500, 'Efectivo'),
        )
    ):
        v = Venta(
            fecha=ahora - timedelta(hours=2 - i * 0.3),
            monto_total=float(monto),
            usuario=usuario,
            estado='Pagado',
            metodo_pago=mp,
            tipo_documento='Boleta',
            caja_id=caja.id,
            cliente_id=cliente.id,
            punto_retiro='Tienda',
        )
        db.session.add(v)
        db.session.flush()
        db.session.add(
            DetalleVenta(
                id_venta=v.id,
                id_producto=prod.id,
                cantidad=1,
                precio_unitario=float(monto),
                subtotal=float(monto),
                punto_retiro_linea='Tienda',
            )
        )
        ventas.append(v)

    db.session.commit()

    # --- 2 alertas inventario en feed (no dependen del catálogo masivo) ---
    inv_specs = [
        (productos[0], 2, 'warning'),
        (productos[1], 0, 'critical'),
    ]
    inv_ids = []
    for idx, (prod, stk, sev) in enumerate(inv_specs):
        dedupe = DEDUPE_INV1 if idx == 0 else DEDUPE_INV2
        if existe_dedupe_abierta(dedupe):
            continue
        titulo = f'Stock bajo: {(prod.nombre or "SKU")[:60]}'
        cuerpo = (
            f'{TAG} — Quedan {stk} u. en tienda (umbral piloto <5). '
            f'Código {(prod.codigo_barra or prod.id)}.'
        )
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=titulo[:255],
            cuerpo=cuerpo,
            severidad=sev,
            codigo='sku_bajo_minimo',
            dedupe_key=dedupe,
            payload={
                'producto_id': prod.id,
                'stock_actual': stk,
                'cuerpo_base_v01': cuerpo,
                'enriquecido_semantico': False,
                'demo_guardian': True,
            },
        )
        if rid:
            inv_ids.append(rid)

    scan = escanear_y_registrar_alertas()
    enrich = ejecutar_lote_enriquecimiento(limite=5)

    out = {
        'tag': TAG,
        'caja_id': caja.id,
        'diferencia_clp': int(caja.diferencia_cierre or 0),
        'ventas_hoy': len(ventas),
        'ventas_ids': [v.id for v in ventas],
        'alertas_inventario': inv_ids,
        'scan': scan,
        'enrich': enrich,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--clean', action='store_true', help='Borrar datos previos con tag GUARDIAN-DEMO-HOY')
    args = p.parse_args()

    cargar_env_local()
    if not resolver_database_url():
        raise SystemExit('Falta DATABASE_URL / NEON_DATABASE_URL')

    import app as m

    with m.app.app_context():
        if args.clean:
            _limpiar(m)
            print('Limpieza OK')
            return
        seed()


if __name__ == '__main__':
    main()
