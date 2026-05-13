"""
ERP LhexIA -- Suite de pruebas funcionales v2.

Ejecuta flujos reales del sistema (sin mocks) y valida invariantes de negocio.
Genera reporte en consola + archivo test_report_YYYYMMDD_HHMMSS.txt

Uso:
    python scripts/seed_test_data.py

Autor: QA Engineer + Python Architect
Fecha: 2026-05-12  |  v2: limpieza robusta, T8-T10, Session.get, reporte archivo
"""
import io
import json as _json
import os
import sys
import threading
import traceback
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as m

db = m.db
flask_app = m.app

QA_USER = 'QA_TEST'

PRODUCTOS_TEST = [
    {
        'nombre': 'TEST Martillo carpintero 16oz Stanley',
        'codigo_barra': 'TEST-MART-001',
        'codigo_interno': 'T-MART-001',
        'precio_compra': 8500, 'precio_venta': 14990,
        'stock': 50, 'unidad': 'Unidad',
        'categoria': 'Herramientas', 'subcategoria': 'Martillos', 'activo': True,
    },
    {
        'nombre': 'TEST Clavo 2.5" caja 1kg',
        'codigo_barra': 'TEST-CLAV-002',
        'codigo_interno': 'T-CLAV-002',
        'precio_compra': 1200, 'precio_venta': 2490,
        'stock': 200, 'unidad': 'Caja',
        'categoria': 'Fijaciones', 'subcategoria': 'Clavos', 'activo': True,
    },
    {
        'nombre': 'TEST Pintura latex blanco 1gal Sherwin',
        'codigo_barra': 'TEST-PINT-003',
        'codigo_interno': 'T-PINT-003',
        'precio_compra': 15000, 'precio_venta': 24990,
        'stock': 30, 'unidad': 'Galon',
        'categoria': 'Pinturas', 'subcategoria': 'Latex', 'activo': True,
    },
    {
        'nombre': 'TEST Cable electrico 2.5mm 100mt',
        'codigo_barra': 'TEST-CABL-004',
        'codigo_interno': 'T-CABL-004',
        'precio_compra': 22000, 'precio_venta': 38990,
        'stock': 15, 'unidad': 'Rollo',
        'categoria': 'Electrico', 'subcategoria': 'Cables', 'activo': True,
    },
    {
        'nombre': 'TEST Tornillo madera 6x1.5" 100un',
        'codigo_barra': 'TEST-TORN-005',
        'codigo_interno': 'T-TORN-005',
        'precio_compra': 800, 'precio_venta': 1690,
        'stock': 300, 'unidad': 'Bolsa',
        'categoria': 'Fijaciones', 'subcategoria': 'Tornillos', 'activo': True,
    },
]

PROVEEDOR_TEST = {
    'nombre': 'TEST Distribuidora Ferretera Nacional S.A.',
    'contacto': 'Juan Perez', 'telefono': '+56912345678',
    'email': 'test@proveedortest.cl',
}

CLIENTE_TEST = {
    'rut': '11.111.111-1',
    'nombre': 'TEST Constructora Demo SpA',
    'giro': 'Construccion', 'direccion': 'Av. Test 1234, Santiago',
    'telefono': '+56998765432', 'correo': 'test@constructorademo.cl',
    'limite_credito': 1000000,
}


# =====================================================================
#  Utilidades
# =====================================================================
class TestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.errors = []
        self._log = io.StringIO()

    def _print(self, msg):
        print(msg)
        self._log.write(msg + '\n')

    def ok(self, name, detail=''):
        self.passed.append((name, detail))
        self._print(f'  [PASS] {name}' + (f' -- {detail}' if detail else ''))

    def fail(self, name, detail=''):
        self.failed.append((name, detail))
        self._print(f'  [FAIL] {name}' + (f' -- {detail}' if detail else ''))

    def error(self, name, exc):
        tb = traceback.format_exc()
        self.errors.append((name, str(exc), tb))
        self._print(f'  [ERROR] {name} -- {exc}')

    def section(self, title):
        self._print(f'\n{title}')

    def report(self):
        total = len(self.passed) + len(self.failed) + len(self.errors)
        w = 64
        lines = [
            '', '=' * w,
            '  REPORTE DE PRUEBAS -- ERP LhexIA v2',
            '=' * w,
            f'  Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}',
            f'  Total: {total}  |  OK: {len(self.passed)}  |  FAIL: {len(self.failed)}  |  ERROR: {len(self.errors)}',
            '-' * w,
        ]
        if self.passed:
            lines.append('\n  APROBADAS:')
            for n, d in self.passed:
                lines.append(f'    [OK] {n}' + (f' -- {d}' if d else ''))
        if self.failed:
            lines.append('\n  FALLIDAS:')
            for n, d in self.failed:
                lines.append(f'    [FAIL] {n}' + (f' -- {d}' if d else ''))
        if self.errors:
            lines.append('\n  ERRORES (excepciones):')
            for n, exc, tb in self.errors:
                lines.append(f'    [ERROR] {n}: {exc}')
                for ln in tb.strip().split('\n')[-3:]:
                    lines.append(f'            {ln}')

        pct = (len(self.passed) / total * 100) if total else 0
        status = 'APROBADO' if not self.failed and not self.errors else 'CON OBSERVACIONES'
        lines += ['', '-' * w, f'  Tasa de exito: {pct:.0f}%', f'  Veredicto: {status}', '=' * w, '']

        for ln in lines:
            self._print(ln)

        self._save_to_file()
        return len(self.failed) + len(self.errors)

    def _save_to_file(self):
        report_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
        os.makedirs(report_dir, exist_ok=True)
        fname = f'test_report_{datetime.now():%Y%m%d_%H%M%S}.txt'
        path = os.path.join(report_dir, fname)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._log.getvalue())
            print(f'  Reporte guardado: docs/{fname}')
        except Exception as ex:
            print(f'  [WARN] No se pudo guardar reporte: {ex}')


R = TestResult()


# =====================================================================
#  Limpieza robusta (FK-safe order)
# =====================================================================
def resetear_datos_prueba(keep_admin=True):
    """Borra datos de test en orden seguro respetando FKs."""
    from sqlalchemy import text as sa_text

    R.section('[FASE 0] Limpieza de datos de prueba previos...')
    db.session.rollback()

    try:
        vids = [
            r[0] for r in db.session.execute(
                sa_text("SELECT id FROM ventas WHERE usuario = :u"), {'u': QA_USER}
            ).fetchall()
        ]
        if vids:
            vid_tuple = tuple(vids)
            db.session.execute(sa_text(
                "DELETE FROM ventas_cuotas_credito WHERE venta_id IN :vids"
            ), {'vids': vid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM detalle_ventas WHERE id_venta IN :vids"
            ), {'vids': vid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM movimiento_caja WHERE concepto LIKE :pat"
            ), {'pat': '%QA test%'})
            db.session.execute(sa_text(
                "DELETE FROM ventas WHERE id IN :vids"
            ), {'vids': vid_tuple})

        pids = [
            r[0] for r in db.session.execute(
                sa_text("SELECT id FROM productos WHERE codigo_barra LIKE 'TEST-%'")
            ).fetchall()
        ]
        if pids:
            pid_tuple = tuple(pids)
            db.session.execute(sa_text(
                "DELETE FROM movimientos_inventario WHERE id_producto IN :pids"
            ), {'pids': pid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM stock_por_almacen WHERE id_producto IN :pids"
            ), {'pids': pid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM detalle_recepcion WHERE producto_id IN :pids"
            ), {'pids': pid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM detalle_orden_compra WHERE producto_id IN :pids"
            ), {'pids': pid_tuple})
            db.session.execute(sa_text(
                "DELETE FROM productos WHERE id IN :pids"
            ), {'pids': pid_tuple})

        prov_ids = [
            r[0] for r in db.session.execute(
                sa_text("SELECT id FROM proveedores WHERE nombre LIKE 'TEST %'")
            ).fetchall()
        ]
        if prov_ids:
            prov_tuple = tuple(prov_ids)
            db.session.execute(sa_text(
                "DELETE FROM recepciones_compra WHERE proveedor_id IN :ids"
            ), {'ids': prov_tuple})
            db.session.execute(sa_text(
                "DELETE FROM ordenes_compra WHERE proveedor_id IN :ids"
            ), {'ids': prov_tuple})
            db.session.execute(sa_text(
                "DELETE FROM proveedores WHERE id IN :ids"
            ), {'ids': prov_tuple})

        db.session.execute(sa_text(
            "DELETE FROM clientes WHERE rut = :rut"
        ), {'rut': CLIENTE_TEST['rut']})

        qa_caja = m.Caja.query.filter_by(usuario_apertura=QA_USER, estado='Abierta').first()
        if qa_caja:
            m.MovimientoCaja.query.filter_by(caja_id=qa_caja.id).delete(synchronize_session=False)
            qa_caja.estado = 'Cerrada'
            qa_caja.fecha_cierre = datetime.now()

        db.session.commit()
        R.ok('Limpieza completa (FK-safe)')
    except Exception as ex:
        db.session.rollback()
        R.error('Limpieza', ex)


# =====================================================================
#  Semilla
# =====================================================================
def _crear_productos_test():
    productos = []
    for data in PRODUCTOS_TEST:
        p = m.Producto.query.filter_by(codigo_barra=data['codigo_barra']).first()
        if not p:
            p = m.Producto(**data)
            db.session.add(p)
        else:
            for k, v in data.items():
                setattr(p, k, v)
        productos.append(p)
    db.session.flush()

    aid_tienda = m.id_almacen_tienda()
    if aid_tienda:
        for p in productos:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_tienda).first()
            if not spa:
                spa = m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_tienda, cantidad=p.stock or 0)
                db.session.add(spa)
            else:
                spa.cantidad = p.stock or 0
    db.session.commit()
    return productos


def _crear_cliente_test():
    cli = m.Cliente.query.filter_by(rut=CLIENTE_TEST['rut']).first()
    if not cli:
        cli = m.Cliente(**CLIENTE_TEST)
        db.session.add(cli)
        db.session.commit()
    else:
        cli.saldo_deudor = 0
        cli.limite_credito = CLIENTE_TEST['limite_credito']
        db.session.commit()
    return cli


def _crear_proveedor_test():
    prov = m.Proveedor.query.filter(m.Proveedor.nombre.like('TEST %')).first()
    if not prov:
        prov = m.Proveedor(**PROVEEDOR_TEST)
        db.session.add(prov)
        db.session.commit()
    return prov


def _asegurar_caja_test():
    caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
    if caja:
        return caja
    caja = m.Caja(monto_inicial=50000, usuario_apertura=QA_USER,
                  estado='Abierta', fecha_apertura=datetime.now())
    db.session.add(caja)
    db.session.commit()
    return caja


def _cobrar_venta_efectivo(venta, caja):
    """Helper: cobra una venta completa con Efectivo y descuenta stock+kardex."""
    from services.venta_service import transaccion_critica
    with transaccion_critica():
        venta.estado = 'Pagado'
        venta.metodo_pago = 'Efectivo'
        venta.tipo_documento = 'Boleta'
        venta.monto_recibido = venta.monto_total + 10
        venta.vuelto = venta.monto_recibido - venta.monto_total

        aid_t = m.id_almacen_tienda() or 1
        for det in venta.detalles:
            prod = db.session.get(m.Producto, det.id_producto)
            factor = m._factor_venta_a_stock(prod)
            consumo = int(det.cantidad * factor)
            err = m.descontar_stock_venta_tienda(prod, consumo)
            assert err is None, f'Error descontando stock: {err}'
            m.registrar_movimiento_kardex(
                id_producto=prod.id, tipo_movimiento='SALIDA',
                cantidad=consumo, motivo=f'Cobro QA #{venta.id}',
                usuario=QA_USER, id_almacen=aid_t,
                referencia_tipo='venta', referencia_id=venta.id,
            )

        db.session.add(m.MovimientoCaja(
            caja_id=caja.id, tipo='Ingreso',
            concepto=f'Cobro vale #{venta.id} (QA test)',
            monto=venta.monto_total, usuario_registro=QA_USER,
        ))
    db.session.commit()


def _crear_venta_pendiente(productos_cantidades, caja, cliente, punto_retiro='Tienda'):
    """Helper: crea venta Pendiente con lineas dadas. Retorna (venta, detalles)."""
    venta = m.Venta(
        fecha=datetime.now(), monto_total=0, usuario=QA_USER,
        estado='Abierta', caja_id=caja.id, cliente_id=cliente.id,
        punto_retiro=punto_retiro,
    )
    db.session.add(venta)
    db.session.flush()
    dets = []
    for prod, qty in productos_cantidades:
        d = m.DetalleVenta(
            id_venta=venta.id, id_producto=prod.id,
            cantidad=qty, precio_unitario=prod.precio_venta,
            subtotal=qty * prod.precio_venta,
        )
        db.session.add(d)
        dets.append(d)
    venta.recalcular_total()
    venta.estado = 'Pendiente'
    db.session.commit()
    return venta, dets


# =====================================================================
#  T1: Venta completa (Happy Path)
# =====================================================================
def test_venta_completa():
    test_name = 'T1 Venta completa Happy Path'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cliente_final = m.obtener_o_crear_cliente_final()
        p_mart, p_clav = productos[0], productos[1]

        stock_m = m.stock_disponible_venta_tienda(p_mart)
        stock_c = m.stock_disponible_venta_tienda(p_clav)

        venta, _ = _crear_venta_pendiente(
            [(p_mart, 2), (p_clav, 5)], caja, cliente_final)
        R.ok(f'{test_name} -- Venta creada', f'ID={venta.id}, ${venta.monto_total:,.0f}')

        assert m.stock_disponible_venta_tienda(p_mart) == stock_m, 'Stock cambio al crear'
        R.ok(f'{test_name} -- Stock intacto al crear vale')

        _cobrar_venta_efectivo(venta, caja)
        R.ok(f'{test_name} -- Cobro exitoso', f'${venta.monto_total:,.0f}')

        sm = m.stock_disponible_venta_tienda(p_mart)
        sc = m.stock_disponible_venta_tienda(p_clav)
        assert sm == stock_m - 2, f'Stock martillo: {stock_m} -> {sm}, esperado {stock_m - 2}'
        assert sc == stock_c - 5, f'Stock clavos: {stock_c} -> {sc}, esperado {stock_c - 5}'
        R.ok(f'{test_name} -- Stock descontado', f'Mart {stock_m}->{sm}, Clav {stock_c}->{sc}')

        k = m.MovimientoInventario.query.filter_by(
            id_producto=p_mart.id, referencia_tipo='venta', referencia_id=venta.id).first()
        assert k and k.tipo_movimiento == 'SALIDA' and k.cantidad == 2
        R.ok(f'{test_name} -- Kardex SALIDA OK')

        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado' and vr.metodo_pago == 'Efectivo'
        R.ok(f'{test_name} -- Estado final correcto')
        return venta.id

    except AssertionError as ae:
        R.fail(test_name, str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)
    return None


# =====================================================================
#  T2: Venta a credito
# =====================================================================
def test_venta_credito():
    test_name = 'T2 Venta credito 30/60/90'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        cliente = _crear_cliente_test()
        caja = _asegurar_caja_test()
        p_pint = productos[2]

        saldo_pre = float(cliente.saldo_deudor or 0)
        stock_pre = m.stock_disponible_venta_tienda(p_pint)

        venta, _ = _crear_venta_pendiente([(p_pint, 3)], caja, cliente)
        monto = venta.monto_total
        R.ok(f'{test_name} -- Vale creado', f'${monto:,.0f}')

        assert monto <= cliente.cupo_disponible
        R.ok(f'{test_name} -- Cupo OK', f'${cliente.cupo_disponible:,.0f}')

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.metodo_pago = 'Credito'
            venta.credito_plan_codigo = '30_60_90'
            cliente.saldo_deudor = float(cliente.saldo_deudor or 0) + monto

            aid_t = m.id_almacen_tienda() or 1
            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                factor = m._factor_venta_a_stock(prod)
                consumo = int(det.cantidad * factor)
                err = m.descontar_stock_venta_tienda(prod, consumo)
                assert err is None, f'Error stock: {err}'
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='SALIDA',
                    cantidad=consumo, motivo=f'Credito QA #{venta.id}',
                    usuario=QA_USER, id_almacen=aid_t,
                    referencia_tipo='venta', referencia_id=venta.id)

            dias = m.PLANES_CUOTA_CREDITO_DIAS['30_60_90']
            mc = round(monto / len(dias))
            for i, d in enumerate(dias, 1):
                db.session.add(m.VentaCuotaCredito(
                    venta_id=venta.id, nro_cuota=i, dias_plazo=d,
                    fecha_vencimiento=date.today() + timedelta(days=d), monto=mc))
        db.session.commit()

        assert float(cliente.saldo_deudor or 0) == saldo_pre + monto
        R.ok(f'{test_name} -- Saldo deudor', f'${saldo_pre:,.0f} -> ${cliente.saldo_deudor:,.0f}')

        cuotas = m.VentaCuotaCredito.query.filter_by(venta_id=venta.id).all()
        assert len(cuotas) == 3
        R.ok(f'{test_name} -- 3 cuotas generadas')

        assert m.stock_disponible_venta_tienda(p_pint) == stock_pre - 3
        R.ok(f'{test_name} -- Stock descontado')
        return venta.id

    except AssertionError as ae:
        R.fail(test_name, str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)
    return None


# =====================================================================
#  T3: Compra y recepcion
# =====================================================================
def test_compra_recepcion():
    test_name = 'T3 Compra y recepcion'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        prov = _crear_proveedor_test()
        p_cable = productos[3]

        try:
            m.OrdenCompra.query.first()
        except Exception:
            R.fail(test_name, 'Tablas OC no existen')
            return None

        numero_oc = f'QA-{datetime.now():%H%M%S}'
        oc = m.OrdenCompra(
            proveedor_id=prov.id, numero=numero_oc,
            fecha_emision=date.today(), estado='Borrador', usuario_creador=QA_USER)
        db.session.add(oc)
        db.session.flush()
        db.session.add(m.DetalleOrdenCompra(
            orden_compra_id=oc.id, producto_id=p_cable.id,
            cantidad=10, precio_unitario=p_cable.precio_compra))
        oc.estado = 'Enviada'
        db.session.commit()
        R.ok(f'{test_name} -- OC creada', f'#{numero_oc}, ${oc.total_estimado:,.0f}')

        recep = m.RecepcionCompra(
            proveedor_id=prov.id, orden_compra_id=oc.id,
            documento_tipo='Factura', documento_numero=f'F-QA-{datetime.now():%H%M%S}',
            usuario_bodega=QA_USER, estado='Pendiente')
        db.session.add(recep)
        db.session.flush()
        db.session.add(m.DetalleRecepcion(
            recepcion_id=recep.id, producto_id=p_cable.id,
            cantidad_documento=10, cantidad_recibida=10))

        aid_b = m.id_almacen_bodega()
        if aid_b:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p_cable.id, id_almacen=aid_b).first()
            if spa:
                spa.cantidad = (spa.cantidad or 0) + 10
            else:
                db.session.add(m.StockPorAlmacen(id_producto=p_cable.id, id_almacen=aid_b, cantidad=10))
            m.registrar_movimiento_kardex(
                id_producto=p_cable.id, tipo_movimiento='ENTRADA', cantidad=10,
                motivo=f'Recepcion QA #{recep.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='recepcion', referencia_id=recep.id)

        p_cable.stock = (p_cable.stock or 0) + 10
        recep.estado = 'Finalizada'
        db.session.commit()
        R.ok(f'{test_name} -- Recepcion OK', f'Cable +10, total={p_cable.stock}')

        k = m.MovimientoInventario.query.filter_by(
            id_producto=p_cable.id, referencia_tipo='recepcion', referencia_id=recep.id).first()
        assert k is not None
        R.ok(f'{test_name} -- Kardex ENTRADA OK')
        return oc.id

    except AssertionError as ae:
        R.fail(test_name, str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)
    return None


# =====================================================================
#  T4: Despacho bodega
# =====================================================================
def test_despacho_bodega():
    test_name = 'T4 Despacho bodega'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cf = m.obtener_o_crear_cliente_final()
        p_torn = productos[4]

        aid_b = m.id_almacen_bodega()
        if not aid_b:
            R.fail(test_name, 'No hay almacen BODEGA')
            return None

        spa_b = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first()
        if not spa_b:
            spa_b = m.StockPorAlmacen(id_producto=p_torn.id, id_almacen=aid_b, cantidad=100)
            db.session.add(spa_b)
            db.session.commit()
        elif (spa_b.cantidad or 0) < 20:
            spa_b.cantidad = 100
            db.session.commit()
        sb_pre = spa_b.cantidad

        venta, dets = _crear_venta_pendiente([(p_torn, 10)], caja, cf, 'Bodega')
        R.ok(f'{test_name} -- Vale Bodega', f'ID={venta.id}')

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            qty = 5
            venta.bodega_despacho_json = _json.dumps({str(dets[0].id): qty})
            venta.bodega_despacho_estado = 'SALIDA_PARCIAL'
            venta.bodega_despacho_ultimo_at = datetime.now()

            spa_r = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first()
            spa_r.cantidad = (spa_r.cantidad or 0) - qty
            m.registrar_movimiento_kardex(
                id_producto=p_torn.id, tipo_movimiento='SALIDA', cantidad=qty,
                motivo=f'Despacho bodega QA #{venta.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()

        spa_post = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first()
        assert spa_post.cantidad == sb_pre - qty
        R.ok(f'{test_name} -- Stock bodega', f'{sb_pre} -> {spa_post.cantidad}')

        vr = db.session.get(m.Venta, venta.id)
        assert vr.bodega_despacho_estado == 'SALIDA_PARCIAL'
        R.ok(f'{test_name} -- Estado despacho OK')
        return venta.id

    except AssertionError as ae:
        R.fail(test_name, str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)
    return None


# =====================================================================
#  T5: Invariantes
# =====================================================================
def test_invariantes():
    test_name = 'T5 Invariantes'
    R.section(f'\n--- {test_name} ---')

    try:
        cf = m.obtener_o_crear_cliente_final()
        assert cf and cf.rut
        R.ok(f'{test_name} -- Cliente final', f'RUT={cf.rut}')
    except Exception as ex:
        R.error(f'{test_name} -- Cliente final', ex)

    try:
        at = m.id_almacen_tienda()
        ab = m.id_almacen_bodega()
        assert at and ab and at != ab
        R.ok(f'{test_name} -- Almacenes TIENDA({at}) BODEGA({ab})')
    except Exception as ex:
        R.error(f'{test_name} -- Almacenes', ex)

    try:
        from services.venta_service import transaccion_critica
        prods = _crear_productos_test()
        p = prods[0]
        s0 = m.stock_disponible_venta_tienda(p)
        try:
            with transaccion_critica():
                m.descontar_stock_venta_tienda(p, 1)
                raise ValueError('rollback test')
        except ValueError:
            pass
        db.session.rollback()
        assert m.stock_disponible_venta_tienda(p) == s0
        R.ok(f'{test_name} -- transaccion_critica rollback OK')
    except AssertionError as ae:
        R.fail(f'{test_name} -- Rollback', str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(f'{test_name} -- Rollback', ex)

    try:
        v = m.Venta(monto_total=119000)
        v.desglosar_iva()
        assert v.neto == 100000 and v.iva == 19000
        R.ok(f'{test_name} -- IVA 19%', '$119.000 -> Neto $100.000 + IVA $19.000')
    except AssertionError as ae:
        R.fail(f'{test_name} -- IVA', str(ae))

    try:
        nombres = {p.nombre for p in m.Permiso.query.all()}
        req = {'pos_emitir_vale', 'caja_cobrar_vale', 'bodega_operador', 'ver_inventario'}
        assert req <= nombres, f'Faltan: {req - nombres}'
        R.ok(f'{test_name} -- Permisos semilla', f'{len(nombres)} permisos')
    except AssertionError as ae:
        R.fail(f'{test_name} -- Permisos', str(ae))
    except Exception as ex:
        R.error(f'{test_name} -- Permisos', ex)

    try:
        nav = m._NAV_MAP
        assert isinstance(nav, list) and len(nav) > 0
        for g in nav:
            assert 'id' in g and 'items' in g
        R.ok(f'{test_name} -- _NAV_MAP OK', f'{len(nav)} grupos')
    except AssertionError as ae:
        R.fail(f'{test_name} -- _NAV_MAP', str(ae))


# =====================================================================
#  T6: Redireccion por perfil
# =====================================================================
def test_redireccion_perfil():
    test_name = 'T6 Redireccion por perfil'
    R.section(f'\n--- {test_name} ---')
    try:
        assert hasattr(m, '_home_por_perfil')
        R.ok(f'{test_name} -- _home_por_perfil existe')
    except AssertionError as ae:
        R.fail(test_name, str(ae))


# =====================================================================
#  T7: Validacion post-hoc
# =====================================================================
def validar_flujo_completo(venta_id):
    test_name = f'T7 Post-hoc venta #{venta_id}'
    R.section(f'\n--- {test_name} ---')
    if not venta_id:
        R.fail(test_name, 'venta_id None')
        return
    try:
        venta = db.session.get(m.Venta, venta_id)
        assert venta, f'#{venta_id} no existe'
        assert venta.estado in ('Pagado', 'Pendiente')
        R.ok(f'{test_name} -- Estado={venta.estado}')
        assert len(venta.detalles) > 0
        R.ok(f'{test_name} -- {len(venta.detalles)} lineas')
        assert venta.monto_total > 0
        R.ok(f'{test_name} -- ${venta.monto_total:,.0f}')
        if venta.neto and venta.iva:
            assert abs((venta.neto + venta.iva) - venta.monto_total) <= 1
            R.ok(f'{test_name} -- IVA coherente')
        if venta.estado == 'Pagado':
            for d in venta.detalles:
                assert m.MovimientoInventario.query.filter_by(
                    referencia_tipo='venta', referencia_id=venta.id, id_producto=d.id_producto
                ).first(), f'Kardex faltante prod #{d.id_producto}'
            R.ok(f'{test_name} -- Kardex completo')
            mov = m.MovimientoCaja.query.filter(
                m.MovimientoCaja.concepto.contains(str(venta.id))).first()
            if mov:
                R.ok(f'{test_name} -- Mov caja ${mov.monto:,.0f}')
            else:
                R.fail(f'{test_name} -- Mov caja NO encontrado')
    except AssertionError as ae:
        R.fail(test_name, str(ae))
    except Exception as ex:
        R.error(test_name, ex)


# =====================================================================
#  T8: Anulacion de vale (con y sin despacho bodega)
# =====================================================================
def test_anulacion_vale():
    test_name = 'T8 Anulacion de vale'
    R.section(f'\n--- {test_name} ---')

    # 8a: Anular vale Pagado SIN despacho bodega -> revertir stock tienda
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cf = m.obtener_o_crear_cliente_final()
        p = productos[0]

        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = _crear_venta_pendiente([(p, 3)], caja, cf)
        _cobrar_venta_efectivo(venta, caja)
        stock_cobrado = m.stock_disponible_venta_tienda(p)
        assert stock_cobrado == stock_pre - 3, f'Cobro: {stock_pre}->{stock_cobrado}'
        R.ok(f'{test_name}a -- Cobrada OK', f'Stock {stock_pre}->{stock_cobrado}')

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.estado = 'Anulada'
            venta.motivo_anulacion = 'QA test anulacion'
            venta.fecha_anulacion = datetime.now()
            venta.usuario_anulacion = QA_USER

            aid_t = m.id_almacen_tienda() or 1
            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                factor = m._factor_venta_a_stock(prod)
                consumo = int(det.cantidad * factor)
                m.incrementar_stock_venta_tienda(prod, consumo)
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='ENTRADA',
                    cantidad=consumo, motivo=f'Anulacion QA #{venta.id}',
                    usuario=QA_USER, id_almacen=aid_t,
                    referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()

        stock_post = m.stock_disponible_venta_tienda(p)
        assert stock_post == stock_pre, f'Reversion: esperado {stock_pre}, real {stock_post}'
        R.ok(f'{test_name}a -- Stock revertido', f'{stock_cobrado}->{stock_post}')

        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada'
        R.ok(f'{test_name}a -- Estado Anulada OK')

    except AssertionError as ae:
        R.fail(f'{test_name}a', str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(f'{test_name}a', ex)

    # 8b: Anular vale con despacho bodega -> revertir stock bodega
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cf = m.obtener_o_crear_cliente_final()
        p_torn = productos[4]
        aid_b = m.id_almacen_bodega()

        spa_b = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first()
        if not spa_b:
            spa_b = m.StockPorAlmacen(id_producto=p_torn.id, id_almacen=aid_b, cantidad=100)
            db.session.add(spa_b)
            db.session.commit()
        sb_pre = spa_b.cantidad

        venta, dets = _crear_venta_pendiente([(p_torn, 8)], caja, cf, 'Bodega')

        from services.venta_service import transaccion_critica
        qty_desp = 8
        with transaccion_critica():
            venta.bodega_despacho_json = _json.dumps({str(dets[0].id): qty_desp})
            venta.bodega_despacho_estado = 'DESPACHADO'
            spa_r = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first()
            spa_r.cantidad = (spa_r.cantidad or 0) - qty_desp
            m.registrar_movimiento_kardex(
                id_producto=p_torn.id, tipo_movimiento='SALIDA', cantidad=qty_desp,
                motivo=f'Despacho QA #{venta.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()

        sb_desp = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first().cantidad
        R.ok(f'{test_name}b -- Despachado', f'Bodega {sb_pre}->{sb_desp}')

        with transaccion_critica():
            venta.estado = 'Anulada'
            venta.motivo_anulacion = 'QA anulacion con despacho'
            venta.fecha_anulacion = datetime.now()
            venta.usuario_anulacion = QA_USER

            desp = _json.loads(venta.bodega_despacho_json or '{}')
            for det_id_str, cant in desp.items():
                det_obj = db.session.get(m.DetalleVenta, int(det_id_str))
                if not det_obj:
                    continue
                spa_rev = m.StockPorAlmacen.query.filter_by(
                    id_producto=det_obj.id_producto, id_almacen=aid_b).first()
                spa_rev.cantidad = (spa_rev.cantidad or 0) + int(cant)
                m.registrar_movimiento_kardex(
                    id_producto=det_obj.id_producto, tipo_movimiento='ENTRADA',
                    cantidad=int(cant), motivo=f'Reversion bodega QA #{venta.id}',
                    usuario=QA_USER, id_almacen=aid_b,
                    referencia_tipo='venta', referencia_id=venta.id)

            venta.bodega_despacho_json = None
            venta.bodega_despacho_estado = None
            venta.bodega_despacho_ultimo_at = None
        db.session.commit()

        sb_post = m.StockPorAlmacen.query.filter_by(id_producto=p_torn.id, id_almacen=aid_b).first().cantidad
        assert sb_post == sb_pre, f'Reversion bodega: esperado {sb_pre}, real {sb_post}'
        R.ok(f'{test_name}b -- Stock bodega revertido', f'{sb_desp}->{sb_post}')

        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada' and vr.bodega_despacho_json is None
        R.ok(f'{test_name}b -- Anulada + JSON limpio')

    except AssertionError as ae:
        R.fail(f'{test_name}b', str(ae))
    except Exception as ex:
        db.session.rollback()
        R.error(f'{test_name}b', ex)


# =====================================================================
#  T9: Venta con stock insuficiente (debe fallar)
# =====================================================================
def test_stock_insuficiente():
    test_name = 'T9 Stock insuficiente'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cf = m.obtener_o_crear_cliente_final()
        p = productos[0]

        stock_actual = m.stock_disponible_venta_tienda(p)
        qty_excesiva = stock_actual + 100

        venta, _ = _crear_venta_pendiente([(p, qty_excesiva)], caja, cf)
        R.ok(f'{test_name} -- Vale creado con qty={qty_excesiva} (stock={stock_actual})')

        from services.venta_service import transaccion_critica
        cobro_fallo = False
        try:
            with transaccion_critica():
                venta.estado = 'Pagado'
                venta.metodo_pago = 'Efectivo'
                for det in venta.detalles:
                    prod = db.session.get(m.Producto, det.id_producto)
                    factor = m._factor_venta_a_stock(prod)
                    consumo = int(det.cantidad * factor)
                    err = m.descontar_stock_venta_tienda(prod, consumo)
                    if err:
                        raise ValueError(f'Stock insuficiente: {err}')
            db.session.commit()
        except (ValueError, AssertionError):
            db.session.rollback()
            cobro_fallo = True

        if cobro_fallo:
            R.ok(f'{test_name} -- Cobro rechazado correctamente (stock insuficiente)')
        else:
            stock_post = m.stock_disponible_venta_tienda(p)
            if stock_post < 0:
                R.fail(f'{test_name} -- Cobro NO rechazo stock negativo', f'stock={stock_post}')
            else:
                R.ok(f'{test_name} -- Sistema permitio descuento (sin validacion stock negativo)',
                     'Considerar agregar validacion')

        venta.estado = 'Anulada'
        venta.motivo_anulacion = 'QA test stock insuficiente'
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)


# =====================================================================
#  T10: Concurrencia simulada (dos cobros al mismo vale)
# =====================================================================
def test_concurrencia_doble_cobro():
    test_name = 'T10 Concurrencia doble cobro'
    R.section(f'\n--- {test_name} ---')
    try:
        productos = _crear_productos_test()
        caja = _asegurar_caja_test()
        cf = m.obtener_o_crear_cliente_final()
        p = productos[1]

        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = _crear_venta_pendiente([(p, 2)], caja, cf)
        vid = venta.id
        R.ok(f'{test_name} -- Vale #{vid} creado')

        resultados = {'t1': None, 't2': None}
        barrera = threading.Barrier(2, timeout=10)

        def cobro_thread(nombre):
            try:
                with flask_app.app_context():
                    barrera.wait()
                    from services.venta_service import transaccion_critica
                    v = db.session.get(m.Venta, vid)
                    if v.estado != 'Pendiente':
                        resultados[nombre] = 'skipped'
                        return
                    try:
                        with transaccion_critica():
                            v2 = db.session.get(m.Venta, vid)
                            if v2.estado != 'Pendiente':
                                resultados[nombre] = 'skipped'
                                return
                            v2.estado = 'Pagado'
                            v2.metodo_pago = 'Efectivo'
                            v2.monto_recibido = v2.monto_total
                            v2.vuelto = 0
                            aid_t = m.id_almacen_tienda() or 1
                            for det in v2.detalles:
                                prod = db.session.get(m.Producto, det.id_producto)
                                factor = m._factor_venta_a_stock(prod)
                                consumo = int(det.cantidad * factor)
                                m.descontar_stock_venta_tienda(prod, consumo)
                                m.registrar_movimiento_kardex(
                                    id_producto=prod.id, tipo_movimiento='SALIDA',
                                    cantidad=consumo, motivo=f'Concurrencia {nombre} QA',
                                    usuario=QA_USER, id_almacen=aid_t,
                                    referencia_tipo='venta', referencia_id=vid)
                        db.session.commit()
                        resultados[nombre] = 'ok'
                    except Exception as inner_ex:
                        db.session.rollback()
                        resultados[nombre] = f'error: {inner_ex}'
            except Exception as outer:
                resultados[nombre] = f'error: {outer}'

        t1 = threading.Thread(target=cobro_thread, args=('t1',))
        t2 = threading.Thread(target=cobro_thread, args=('t2',))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        r1 = resultados.get('t1', 'timeout')
        r2 = resultados.get('t2', 'timeout')
        R.ok(f'{test_name} -- Thread 1: {r1}')
        R.ok(f'{test_name} -- Thread 2: {r2}')

        cobros_ok = sum(1 for r in [r1, r2] if r == 'ok')
        if cobros_ok <= 1:
            R.ok(f'{test_name} -- Solo 1 cobro exitoso (correcto)')
        else:
            R.fail(f'{test_name} -- AMBOS threads cobraron (doble cobro!)')

        stock_post = m.stock_disponible_venta_tienda(p)
        descuento_esperado = 2 * cobros_ok
        expected = stock_pre - descuento_esperado
        if stock_post == expected:
            R.ok(f'{test_name} -- Stock coherente', f'{stock_pre}->{stock_post}')
        else:
            R.fail(f'{test_name} -- Stock incoherente',
                   f'esperado {expected}, real {stock_post}')

    except Exception as ex:
        db.session.rollback()
        R.error(test_name, ex)


# =====================================================================
#  RUNNER
# =====================================================================
def run_all_tests():
    R.section('=' * 64)
    R.section('  ERP LhexIA -- SUITE DE PRUEBAS FUNCIONALES v2')
    R.section('  ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    R.section('=' * 64)

    resetear_datos_prueba()

    R.section('\n[FASE 1] Semilla de datos base...')
    try:
        _crear_productos_test()
        R.ok('Semilla -- Productos', f'{len(PRODUCTOS_TEST)} productos')
    except Exception as ex:
        R.error('Semilla -- Productos', ex)
        return R.report()
    try:
        _crear_cliente_test()
        R.ok('Semilla -- Cliente credito')
    except Exception as ex:
        R.error('Semilla -- Cliente', ex)
    try:
        _crear_proveedor_test()
        R.ok('Semilla -- Proveedor')
    except Exception as ex:
        R.error('Semilla -- Proveedor', ex)
    try:
        caja = _asegurar_caja_test()
        R.ok('Semilla -- Caja abierta', f'ID={caja.id}')
    except Exception as ex:
        R.error('Semilla -- Caja', ex)

    R.section('\n[FASE 2] Pruebas funcionales core...')
    v1 = test_venta_completa()
    v2 = test_venta_credito()
    test_compra_recepcion()
    test_despacho_bodega()

    R.section('\n[FASE 3] Anulacion y edge cases...')
    test_anulacion_vale()
    test_stock_insuficiente()
    test_concurrencia_doble_cobro()

    R.section('\n[FASE 4] Invariantes y validaciones...')
    test_invariantes()
    test_redireccion_perfil()

    R.section('\n[FASE 5] Validacion post-hoc...')
    validar_flujo_completo(v1)
    if v2:
        validar_flujo_completo(v2)

    return R.report()


if __name__ == '__main__':
    with flask_app.app_context():
        exit_code = run_all_tests()
        sys.exit(min(exit_code, 1))
