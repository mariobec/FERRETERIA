#!/usr/bin/env python3
"""
Datos de prueba — arqueo / cierre a ciegas para vendedor@local.cl

Uso:
  python scripts/seed_arqueo_demo_vendedor.py
  python scripts/seed_arqueo_demo_vendedor.py --clean   # borra turnos SEED-ARQUEO previos

Deja:
  - 1 caja ABIERTA del vendedor con ventas Pagado (efectivo + tarjeta) para cerrar en UI
  - 1 caja CERRADA de ejemplo con arqueo persistido (panel admin)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as m  # noqa: E402
from app import (  # noqa: E402
    Caja,
    Cliente,
    DetalleVenta,
    MovimientoCaja,
    Usuario,
    Venta,
    db,
)
from services.cuadratura_arqueo_service import (  # noqa: E402
    aplicar_indicadores_sii_caja,
    calcular_monto_teorico_gaveta_turno,
)

VENDEDOR_EMAIL = 'vendedor@local.cl'
SEED_TAG = 'SEED-ARQUEO'
FONDO_APERTURA = 100_000


def _vendedor() -> Usuario:
    u = Usuario.query.filter_by(correo=VENDEDOR_EMAIL).first()
    if not u:
        raise SystemExit(f'No existe usuario {VENDEDOR_EMAIL}. Créalo en Admin → Usuarios.')
    return u


def _productos_demo(n: int = 4):
    productos = (
        m.Producto.query.filter(m.Producto.codigo_barra.like('TEST-%'), m.Producto.activo == True)  # noqa: E712
        .order_by(m.Producto.id.asc())
        .limit(n)
        .all()
    )
    if len(productos) < 2:
        productos = m.Producto.query.filter_by(activo=True).order_by(m.Producto.id.asc()).limit(n).all()
    if not productos:
        raise SystemExit('No hay productos activos en BD.')
    return productos


def _cliente_final():
    return m.obtener_o_crear_cliente_final()


def _limpiar_seed():
    cajas = Caja.query.filter(Caja.usuario_apertura.like(f'{SEED_TAG}%')).all()
    ids = [c.id for c in cajas]
    if ids:
        venta_ids = [r[0] for r in db.session.query(Venta.id).filter(Venta.caja_id.in_(ids)).all()]
        if venta_ids:
            DetalleVenta.query.filter(DetalleVenta.id_venta.in_(venta_ids)).delete(
                synchronize_session=False
            )
            Venta.query.filter(Venta.id.in_(venta_ids)).delete(synchronize_session=False)
        MovimientoCaja.query.filter(MovimientoCaja.caja_id.in_(ids)).delete(synchronize_session=False)
        Caja.query.filter(Caja.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
    print(f'Limpieza: {len(ids)} caja(s) {SEED_TAG}.')


def _crear_venta_pagada(
    *,
    caja: Caja,
    vendedor: Usuario,
    cliente: Cliente,
    producto,
    cantidad: int,
    metodo_pago: str,
    dte_estado: str | None = None,
    folio: int | None = None,
    track: str | None = None,
) -> Venta:
    subtotal = int(round(float(producto.precio_venta or 0) * cantidad))
    v = Venta(
        fecha=datetime.now(),
        monto_total=float(subtotal),
        usuario=vendedor.nombre,
        estado='Pagado',
        metodo_pago=metodo_pago,
        tipo_documento='Boleta',
        caja_id=caja.id,
        cliente_id=cliente.id,
        punto_retiro='Tienda',
        dte_estado=dte_estado,
        nro_documento=folio,
        dte_track_id=track,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=producto.id,
            cantidad=cantidad,
            precio_unitario=float(producto.precio_venta or 0),
            subtotal=float(subtotal),
            punto_retiro_linea='Tienda',
        )
    )
    return v


def _cerrar_caja_demo(caja: Caja, ventas_cuadre, *, declarado_efectivo: int, declarado_tarjeta: int):
    from services.cuadratura_arqueo_service import calcular_indicadores_sii_turno

    ctx = _totales_turno(caja, ventas_cuadre)
    monto_teorico_int = int(round(ctx['monto_teorico']))
    caja.fecha_cierre = datetime.now()
    caja.monto_declarado_cajero = declarado_efectivo
    caja.monto_declarado_tarjeta = declarado_tarjeta
    caja.monto_final = declarado_efectivo
    caja.monto_teorico_cierre = monto_teorico_int
    caja.monto_contado_cierre = declarado_efectivo
    caja.diferencia_cierre = declarado_efectivo - monto_teorico_int
    caja.estado = 'Cerrada'
    caja.usuario_cierre = caja.usuario_apertura
    caja.observacion_cierre = f'{SEED_TAG} turno demo cerrado para panel admin'
    aplicar_indicadores_sii_caja(caja, ventas_cuadre)


def _totales_turno(caja: Caja, ventas_cuadre):
    def _mp(v):
        return (v.metodo_pago or '').strip()

    def _m(v):
        return max(0.0, float(v.monto_total or 0) - float(getattr(v, 'saldo_favor_usado', 0) or 0))

    te = sum(_m(v) for v in ventas_cuadre if _mp(v) == 'Efectivo') or 0
    return {
        'monto_teorico': calcular_monto_teorico_gaveta_turno(
            monto_inicial=float(caja.monto_inicial or 0),
            total_efectivo=te,
            total_abonos_efectivo=0,
            cambios_efectivo_recibido=0,
            ingresos_manuales=0,
            cambios_efectivo_devuelto=0,
            egresos=0,
        )
    }


def seed():
    m._asegurar_columnas_caja_cuadratura()
    vendedor = _vendedor()
    nombre_op = vendedor.nombre or 'Vendedor'
    tag_user = f'{SEED_TAG} {nombre_op}'
    productos = _productos_demo()
    cliente = _cliente_final()

    # Una sola caja abierta en el sistema (la del vendedor para /cerrar_caja)
    for c in Caja.query.filter_by(estado='Abierta').all():
        c.estado = 'Cerrada'
        c.fecha_cierre = datetime.now()
        c.observacion_cierre = ((c.observacion_cierre or '') + ' [auto-cierre seed]')[:255]

    # --- Turno ABIERTO (para probar /cerrar_caja a ciegas) ---
    caja_abierta = Caja(
        monto_inicial=float(FONDO_APERTURA),
        usuario_apertura=tag_user,
        estado='Abierta',
        fecha_apertura=datetime.now(),
    )
    db.session.add(caja_abierta)
    db.session.flush()

    _crear_venta_pagada(
        caja=caja_abierta,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[0],
        cantidad=2,
        metodo_pago='Efectivo',
        dte_estado='ENVIADO',
        folio=90001,
        track='SEED-TRACK-001',
    )
    _crear_venta_pagada(
        caja=caja_abierta,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[1],
        cantidad=1,
        metodo_pago='Debito',
        dte_estado='ENVIADO',
        folio=90002,
        track='SEED-TRACK-002',
    )
    _crear_venta_pagada(
        caja=caja_abierta,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[2] if len(productos) > 2 else productos[0],
        cantidad=1,
        metodo_pago='Efectivo',
    )

    ventas_abierta = Venta.query.filter_by(caja_id=caja_abierta.id, estado='Pagado').all()
    teo_abierta = int(round(_totales_turno(caja_abierta, ventas_abierta)['monto_teorico']))
    tarjeta_ventas = sum(
        max(0, int(round(float(v.monto_total or 0))))
        for v in ventas_abierta
        if (v.metodo_pago or '').strip() in ('Debito', 'TarjetaCredito', 'Transferencia')
    )

    # --- Turno CERRADO (panel admin con descuadre leve) ---
    caja_cerrada = Caja(
        monto_inicial=float(FONDO_APERTURA),
        usuario_apertura=tag_user,
        estado='Abierta',
        fecha_apertura=datetime.now() - timedelta(hours=8),
    )
    db.session.add(caja_cerrada)
    db.session.flush()

    _crear_venta_pagada(
        caja=caja_cerrada,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[0],
        cantidad=3,
        metodo_pago='Efectivo',
        dte_estado='ENVIADO',
        folio=90010,
        track='SEED-TRACK-010',
    )
    _crear_venta_pagada(
        caja=caja_cerrada,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[1],
        cantidad=2,
        metodo_pago='TarjetaCredito',
        dte_estado='ENVIADO',
        folio=90011,
        track='SEED-TRACK-011',
    )
    _crear_venta_pagada(
        caja=caja_cerrada,
        vendedor=vendedor,
        cliente=cliente,
        producto=productos[2] if len(productos) > 2 else productos[0],
        cantidad=1,
        metodo_pago='Efectivo',
        dte_estado='PENDIENTE_ENVIO',
        folio=90012,
    )

    ventas_cerrada = Venta.query.filter_by(caja_id=caja_cerrada.id, estado='Pagado').all()
    teo_cerrada = int(round(_totales_turno(caja_cerrada, ventas_cerrada)['monto_teorico']))
    declarado_efectivo_cerrada = teo_cerrada - 5_850  # descuadre demo
    declarado_tarjeta_cerrada = sum(
        max(0, int(round(float(v.monto_total or 0))))
        for v in ventas_cerrada
        if (v.metodo_pago or '').strip() in ('Debito', 'TarjetaCredito', 'Transferencia')
    )
    _cerrar_caja_demo(
        caja_cerrada,
        ventas_cerrada,
        declarado_efectivo=declarado_efectivo_cerrada,
        declarado_tarjeta=declarado_tarjeta_cerrada,
    )

    db.session.commit()

    print('')
    print('=== Seed arqueo vendedor@local.cl ===')
    print(f'Usuario: {vendedor.nombre} ({VENDEDOR_EMAIL})')
    print('')
    print('TURNO ABIERTO (cierre a ciegas):')
    print(f'  Caja #{caja_abierta.id}  ->  http://127.0.0.1:5000/cerrar_caja')
    print(f'  Teorico gaveta (referencia QA, NO mostrar al cajero): ${teo_abierta:,}'.replace(',', '.'))
    print(f'  Sugerido declarar efectivo: ${teo_abierta:,}'.replace(',', '.'))
    print(f'  Sugerido declarar tarjetas: ${tarjeta_ventas:,}'.replace(',', '.'))
    print('')
    print('TURNO CERRADO (panel admin):')
    print(f'  Caja #{caja_cerrada.id}  ->  http://127.0.0.1:5000/admin/caja/arqueo/{caja_cerrada.id}')
    print(f'  Historial  ->  http://127.0.0.1:5000/caja/historial_cierres')
    print('')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true', help='Borra cajas anteriores SEED-ARQUEO')
    args = parser.parse_args()
    with m.app.app_context():
        if args.clean:
            _limpiar_seed()
        seed()


if __name__ == '__main__':
    main()
