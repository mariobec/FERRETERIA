"""
ERP LhexIA -- Generador de datos realistas de demostracion.

Crea un set coherente de datos para demos, screenshots y capacitacion:
  - 8 clientes frecuentes con credito
  - 25 ventas (efectivo, credito, anuladas, con despacho bodega)
  - 5 ordenes de compra con recepciones
  - Movimientos de caja y kardex consistentes

Uso:
    python scripts/seed_demo_data.py              # genera datos
    python scripts/seed_demo_data.py --clean      # limpia datos DEMO previos

NO interfiere con datos de produccion (todos los registros usan prefijo DEMO).
"""
import json
import os
import random
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as m

db = m.db
flask_app = m.app
DEMO_USER = 'DEMO_SEED'

# ── Catalogo demo ──────────────────────────────────────────────────
CLIENTES_DEMO = [
    dict(rut='12.345.678-9', nombre='DEMO Constructora Acme SpA', giro='Construccion',
         direccion='Av. Industrial 500, Santiago', telefono='+56911111111',
         correo='acme@demo.cl', limite_credito=2_000_000),
    dict(rut='13.456.789-0', nombre='DEMO Electro Sur Ltda', giro='Electricidad',
         direccion='Los Electricistas 120, Temuco', telefono='+56922222222',
         correo='electrosur@demo.cl', limite_credito=1_500_000),
    dict(rut='14.567.890-1', nombre='DEMO Pinturas del Centro', giro='Pinturas',
         direccion='Calle Color 45, Rancagua', telefono='+56933333333',
         correo='pinturas@demo.cl', limite_credito=800_000),
    dict(rut='15.678.901-2', nombre='DEMO Instalaciones Norte', giro='Gasfiteria',
         direccion='Av. Agua 789, Antofagasta', telefono='+56944444444',
         correo='inorte@demo.cl', limite_credito=1_200_000),
    dict(rut='16.789.012-3', nombre='DEMO Muebles Artesanos EIRL', giro='Muebles',
         direccion='Calle Madera 33, Valdivia', telefono='+56955555555',
         correo='artesanos@demo.cl', limite_credito=600_000),
    dict(rut='17.890.123-4', nombre='DEMO Inmobiliaria Los Robles', giro='Inmobiliaria',
         direccion='Av. Construccion 1200, Vina del Mar', telefono='+56966666666',
         correo='robles@demo.cl', limite_credito=5_000_000),
    dict(rut='18.901.234-5', nombre='DEMO Taller Mecanico Express', giro='Mecanica',
         direccion='Calle Motor 88, Concepcion', telefono='+56977777777',
         correo='express@demo.cl', limite_credito=400_000),
    dict(rut='19.012.345-6', nombre='DEMO Municipalidad Demo', giro='Gobierno',
         direccion='Plaza Principal s/n, Demo City', telefono='+56988888888',
         correo='muni@demo.cl', limite_credito=10_000_000),
]

PROVEEDORES_DEMO = [
    dict(nombre='DEMO Sodimac Distribucion', contacto='Carlos Proveedor',
         telefono='+56900000001', email='dist@sodimac-demo.cl'),
    dict(nombre='DEMO Ferreteria Mayorista Central', contacto='Ana Mayorista',
         telefono='+56900000002', email='central@fmc-demo.cl'),
]


def limpiar_demo():
    """Borra datos con prefijo DEMO."""
    from sqlalchemy import text as sa_text
    db.session.rollback()
    print('[DEMO] Limpiando datos previos...')
    try:
        vids = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM ventas WHERE usuario = :u"), {'u': DEMO_USER}).fetchall()]
        if vids:
            vt = tuple(vids)
            db.session.execute(sa_text("DELETE FROM ventas_cuotas_credito WHERE venta_id IN :v"), {'v': vt})
            db.session.execute(sa_text("DELETE FROM detalle_ventas WHERE id_venta IN :v"), {'v': vt})
            db.session.execute(sa_text("DELETE FROM movimiento_caja WHERE concepto LIKE :p"), {'p': '%DEMO%'})
            db.session.execute(sa_text("DELETE FROM ventas WHERE id IN :v"), {'v': vt})

        prov_ids = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM proveedores WHERE nombre LIKE 'DEMO %'")).fetchall()]
        if prov_ids:
            pt = tuple(prov_ids)
            db.session.execute(sa_text("DELETE FROM detalle_recepcion WHERE recepcion_id IN (SELECT id FROM recepciones_compra WHERE proveedor_id IN :i)"), {'i': pt})
            db.session.execute(sa_text("DELETE FROM recepciones_compra WHERE proveedor_id IN :i"), {'i': pt})
            db.session.execute(sa_text("DELETE FROM detalle_orden_compra WHERE orden_compra_id IN (SELECT id FROM ordenes_compra WHERE proveedor_id IN :i)"), {'i': pt})
            db.session.execute(sa_text("DELETE FROM ordenes_compra WHERE proveedor_id IN :i"), {'i': pt})
            db.session.execute(sa_text("DELETE FROM proveedores WHERE id IN :i"), {'i': pt})

        db.session.execute(sa_text("DELETE FROM clientes WHERE nombre LIKE 'DEMO %'"))

        try:
            db.session.execute(sa_text("DELETE FROM erp_audit_log WHERE usuario = :u"), {'u': DEMO_USER})
        except Exception:
            pass

        demo_caja = m.Caja.query.filter_by(usuario_apertura=DEMO_USER, estado='Abierta').first()
        if demo_caja:
            m.MovimientoCaja.query.filter_by(caja_id=demo_caja.id).delete(synchronize_session=False)
            demo_caja.estado = 'Cerrada'
            demo_caja.fecha_cierre = datetime.now()

        db.session.commit()
        print('[DEMO] Limpieza OK')
    except Exception as ex:
        db.session.rollback()
        print(f'[DEMO] Error limpieza: {ex}')


def seed_demo():
    """Genera datos realistas de demo."""
    random.seed(42)
    print('\n' + '=' * 50)
    print('  SEED DEMO DATA -- ERP LhexIA')
    print('=' * 50)

    limpiar_demo()

    # 1. Clientes
    clientes = []
    for data in CLIENTES_DEMO:
        cli = m.Cliente.query.filter_by(rut=data['rut']).first()
        if not cli:
            cli = m.Cliente(**data)
            db.session.add(cli)
        clientes.append(cli)
    db.session.commit()
    print(f'[DEMO] {len(clientes)} clientes creados')

    # 2. Proveedores
    proveedores = []
    for data in PROVEEDORES_DEMO:
        prov = m.Proveedor.query.filter(m.Proveedor.nombre == data['nombre']).first()
        if not prov:
            prov = m.Proveedor(**data)
            db.session.add(prov)
        proveedores.append(prov)
    db.session.commit()
    print(f'[DEMO] {len(proveedores)} proveedores creados')

    # 3. Caja demo
    caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
    if not caja:
        caja = m.Caja(monto_inicial=100000, usuario_apertura=DEMO_USER,
                      estado='Abierta', fecha_apertura=datetime.now())
        db.session.add(caja)
        db.session.commit()
    print(f'[DEMO] Caja ID={caja.id}')

    # 4. Productos existentes
    productos = m.Producto.query.filter_by(activo=True).limit(20).all()
    if not productos:
        print('[DEMO] No hay productos activos en BD. Saltando ventas.')
        return

    cf = m.obtener_o_crear_cliente_final()
    aid_t = m.id_almacen_tienda() or 1

    # 5. Ventas demo (25 variadas)
    metodos = ['Efectivo'] * 15 + ['Credito'] * 5 + ['Transferencia'] * 5
    random.shuffle(metodos)

    ventas_creadas = 0
    for i in range(25):
        try:
            n_items = random.randint(1, min(4, len(productos)))
            items = random.sample(productos, n_items)
            cliente = random.choice(clientes + [cf, cf, cf])

            venta = m.Venta(
                fecha=datetime.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12)),
                monto_total=0, usuario=DEMO_USER, estado='Abierta',
                caja_id=caja.id, cliente_id=cliente.id, punto_retiro='Tienda')
            db.session.add(venta)
            db.session.flush()

            for prod in items:
                qty = random.randint(1, 5)
                db.session.add(m.DetalleVenta(
                    id_venta=venta.id, id_producto=prod.id,
                    cantidad=qty, precio_unitario=prod.precio_venta,
                    subtotal=qty * prod.precio_venta))
            venta.recalcular_total()
            venta.estado = 'Pendiente'
            db.session.commit()

            metodo = metodos[i % len(metodos)]

            if metodo == 'Credito' and hasattr(cliente, 'cupo_disponible') and cliente != cf:
                if venta.monto_total <= (cliente.cupo_disponible or 0):
                    venta.metodo_pago = 'Credito'
                    venta.credito_plan_codigo = '30_60_90'
                    cliente.saldo_deudor = float(cliente.saldo_deudor or 0) + venta.monto_total
                    dias = m.PLANES_CUOTA_CREDITO_DIAS.get('30_60_90', (30, 60, 90))
                    mc = round(venta.monto_total / len(dias))
                    for ci, d in enumerate(dias, 1):
                        db.session.add(m.VentaCuotaCredito(
                            venta_id=venta.id, nro_cuota=ci, dias_plazo=d,
                            fecha_vencimiento=date.today() + timedelta(days=d), monto=mc))
                    db.session.commit()
                    ventas_creadas += 1
                    continue
                metodo = 'Efectivo'

            venta.estado = 'Pagado'
            venta.metodo_pago = metodo
            venta.tipo_documento = 'Boleta'
            venta.monto_recibido = venta.monto_total + random.choice([0, 10, 50, 100, 500])
            venta.vuelto = max(0, (venta.monto_recibido or 0) - venta.monto_total)

            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                if not prod:
                    continue
                factor = m._factor_venta_a_stock(prod)
                consumo = int(det.cantidad * factor)
                m.descontar_stock_venta_tienda(prod, consumo)
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='SALIDA', cantidad=consumo,
                    motivo=f'Venta DEMO #{venta.id}', usuario=DEMO_USER,
                    id_almacen=aid_t, referencia_tipo='venta', referencia_id=venta.id)

            db.session.add(m.MovimientoCaja(
                caja_id=caja.id, tipo='Ingreso',
                concepto=f'Cobro DEMO vale #{venta.id}',
                monto=venta.monto_total, usuario_registro=DEMO_USER))
            db.session.commit()
            ventas_creadas += 1
        except Exception as ex:
            db.session.rollback()
            print(f'  [WARN] Venta {i+1}: {ex}')

    print(f'[DEMO] {ventas_creadas}/25 ventas creadas')

    # 6. Ordenes de compra y recepciones
    aid_b = m.id_almacen_bodega()
    oc_count = 0
    for prov in proveedores:
        try:
            prods_oc = random.sample(productos, min(3, len(productos)))
            num = f'DEMO-OC-{prov.id}-{datetime.now():%H%M%S}'
            oc = m.OrdenCompra(
                proveedor_id=prov.id, numero=num,
                fecha_emision=date.today() - timedelta(days=random.randint(1, 15)),
                estado='Borrador', usuario_creador=DEMO_USER)
            db.session.add(oc)
            db.session.flush()
            for p in prods_oc:
                db.session.add(m.DetalleOrdenCompra(
                    orden_compra_id=oc.id, producto_id=p.id,
                    cantidad=random.randint(10, 50),
                    precio_unitario=p.precio_compra))
            oc.estado = 'Enviada'
            db.session.commit()

            recep = m.RecepcionCompra(
                proveedor_id=prov.id, orden_compra_id=oc.id,
                documento_tipo='Factura', documento_numero=f'F-{num}',
                usuario_bodega=DEMO_USER, estado='Pendiente')
            db.session.add(recep)
            db.session.flush()
            for p in prods_oc:
                qty = random.randint(5, 20)
                db.session.add(m.DetalleRecepcion(
                    recepcion_id=recep.id, producto_id=p.id,
                    cantidad_documento=qty, cantidad_recibida=qty))
                if aid_b:
                    spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
                    if spa:
                        spa.cantidad = (spa.cantidad or 0) + qty
                    else:
                        db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_b, cantidad=qty))
                    m.registrar_movimiento_kardex(
                        id_producto=p.id, tipo_movimiento='ENTRADA', cantidad=qty,
                        motivo=f'Recepcion DEMO #{recep.id}', usuario=DEMO_USER,
                        id_almacen=aid_b, referencia_tipo='recepcion', referencia_id=recep.id)
            recep.estado = 'Finalizada'
            db.session.commit()
            oc_count += 1
        except Exception as ex:
            db.session.rollback()
            print(f'  [WARN] OC prov {prov.nombre}: {ex}')

    print(f'[DEMO] {oc_count} OC + recepciones')

    print('\n' + '=' * 50)
    print('  SEED DEMO COMPLETADO')
    print(f'  Clientes: {len(clientes)} | Ventas: {ventas_creadas}')
    print(f'  OC: {oc_count} | Proveedores: {len(proveedores)}')
    print('=' * 50 + '\n')


if __name__ == '__main__':
    with flask_app.app_context():
        if '--clean' in sys.argv:
            limpiar_demo()
        else:
            seed_demo()
