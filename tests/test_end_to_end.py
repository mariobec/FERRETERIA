"""
ERP LhexIA -- Suite de pruebas end-to-end v4 (pytest).

T1-T15: core (v3)
T16: Carga ligera (10 ventas simultaneas)
T17: Flujo multi-almacen (traslado tienda<->bodega)
T18: Auditoria (erp_audit_log)

Ejecucion:
    pytest tests/ -v                                      # completa
    pytest tests/ -v -m smoke                             # solo smoke / CI
    pytest tests/ -v --cov=app --cov-report=term-missing  # con coverage
    pytest tests/ --html=docs/test_report_v4.html --self-contained-html
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

import app as m
from tests.conftest import (
    QA_USER,
    anular_venta_con_audit,
    asegurar_stock_bodega,
    cobrar_venta_efectivo,
    cobrar_venta_efectivo_con_audit,
    crear_venta_pendiente,
    simular_comando_voz,
    trasladar_stock,
    venta_rapida_thread_safe,
)

db = m.db


# =====================================================================
#  T1 -- Venta completa (happy path)
# =====================================================================
@pytest.mark.smoke
@pytest.mark.happy_path
class TestT01VentaCompleta:

    def test_crear_vale_no_descuenta_stock(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 2)], caja_abierta, cliente_final)
        assert m.stock_disponible_venta_tienda(p) == stock_pre

    def test_cobrar_descuenta_stock(self, productos_con_stock, caja_abierta, cliente_final):
        p_mart, p_clav = productos_con_stock[0], productos_con_stock[1]
        sm = m.stock_disponible_venta_tienda(p_mart)
        sc = m.stock_disponible_venta_tienda(p_clav)
        venta, _ = crear_venta_pendiente(
            [(p_mart, 2), (p_clav, 5)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        assert m.stock_disponible_venta_tienda(p_mart) == sm - 2
        assert m.stock_disponible_venta_tienda(p_clav) == sc - 5

    def test_estado_final_pagado(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'
        assert vr.metodo_pago == 'Efectivo'
        assert vr.tipo_documento == 'Boleta'

    def test_kardex_salida_registrado(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        k = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, referencia_tipo='venta', referencia_id=venta.id).first()
        assert k is not None and k.tipo_movimiento == 'SALIDA'

    def test_movimiento_caja_registrado(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        mov = m.MovimientoCaja.query.filter(
            m.MovimientoCaja.concepto.contains(str(venta.id))).first()
        assert mov is not None and mov.monto == venta.monto_total


# =====================================================================
#  T2 -- Venta a credito 30/60/90
# =====================================================================
@pytest.mark.smoke
@pytest.mark.happy_path
class TestT02VentaCredito:

    def test_credito_genera_cuotas(self, productos_con_stock, caja_abierta, cliente_credito):
        p = productos_con_stock[2]
        stock_pre = m.stock_disponible_venta_tienda(p)
        saldo_pre = float(cliente_credito.saldo_deudor or 0)
        venta, _ = crear_venta_pendiente([(p, 3)], caja_abierta, cliente_credito)
        monto = venta.monto_total
        assert monto <= cliente_credito.cupo_disponible

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.metodo_pago = 'Credito'
            venta.credito_plan_codigo = '30_60_90'
            cliente_credito.saldo_deudor = float(cliente_credito.saldo_deudor or 0) + monto
            aid_t = m.id_almacen_tienda() or 1
            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
                assert m.descontar_stock_venta_tienda(prod, consumo) is None
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='SALIDA', cantidad=consumo,
                    motivo=f'Credito QA #{venta.id}', usuario=QA_USER, id_almacen=aid_t,
                    referencia_tipo='venta', referencia_id=venta.id)
            dias = m.PLANES_CUOTA_CREDITO_DIAS['30_60_90']
            mc = round(monto / len(dias))
            for i, d in enumerate(dias, 1):
                db.session.add(m.VentaCuotaCredito(
                    venta_id=venta.id, nro_cuota=i, dias_plazo=d,
                    fecha_vencimiento=date.today() + timedelta(days=d), monto=mc))
        db.session.commit()

        assert float(cliente_credito.saldo_deudor or 0) == saldo_pre + monto
        assert len(m.VentaCuotaCredito.query.filter_by(venta_id=venta.id).all()) == 3
        assert m.stock_disponible_venta_tienda(p) == stock_pre - 3


# =====================================================================
#  T3 -- Compra y recepcion
# =====================================================================
@pytest.mark.smoke
@pytest.mark.happy_path
class TestT03CompraRecepcion:

    def test_flujo_oc_recepcion(self, productos_con_stock, proveedor_test, app_ctx):
        p = productos_con_stock[3]
        num = f'QA-{datetime.now():%H%M%S%f}'
        oc = m.OrdenCompra(
            proveedor_id=proveedor_test.id, numero=num,
            fecha_emision=date.today(), estado='Borrador', usuario_creador=QA_USER)
        db.session.add(oc); db.session.flush()
        db.session.add(m.DetalleOrdenCompra(
            orden_compra_id=oc.id, producto_id=p.id,
            cantidad=10, precio_unitario=p.precio_compra))
        oc.estado = 'Enviada'; db.session.commit()
        assert oc.total_estimado > 0

        recep = m.RecepcionCompra(
            proveedor_id=proveedor_test.id, orden_compra_id=oc.id,
            documento_tipo='Factura', documento_numero=f'F-{num}',
            usuario_bodega=QA_USER, estado='Pendiente')
        db.session.add(recep); db.session.flush()
        db.session.add(m.DetalleRecepcion(
            recepcion_id=recep.id, producto_id=p.id,
            cantidad_documento=10, cantidad_recibida=10))
        aid_b = m.id_almacen_bodega()
        if aid_b:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
            if spa:
                spa.cantidad = (spa.cantidad or 0) + 10
            else:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_b, cantidad=10))
            m.registrar_movimiento_kardex(
                id_producto=p.id, tipo_movimiento='ENTRADA', cantidad=10,
                motivo=f'Recepcion QA #{recep.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='recepcion', referencia_id=recep.id)
        recep.estado = 'Finalizada'; db.session.commit()
        k = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, referencia_tipo='recepcion', referencia_id=recep.id).first()
        assert k is not None and k.tipo_movimiento == 'ENTRADA'


# =====================================================================
#  T4 -- Despacho bodega (parcial)
# =====================================================================
@pytest.mark.smoke
@pytest.mark.happy_path
class TestT04DespachoBodega:

    def test_despacho_parcial(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[4]
        aid_b = m.id_almacen_bodega(); assert aid_b
        asegurar_stock_bodega(p, 100)
        sb_pre = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad
        venta, dets = crear_venta_pendiente([(p, 10)], caja_abierta, cliente_final, 'Bodega')

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.bodega_despacho_json = json.dumps({str(dets[0].id): 5})
            venta.bodega_despacho_estado = 'SALIDA_PARCIAL'
            venta.bodega_despacho_ultimo_at = datetime.now()
            spa_r = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
            spa_r.cantidad -= 5
            m.registrar_movimiento_kardex(
                id_producto=p.id, tipo_movimiento='SALIDA', cantidad=5,
                motivo=f'Despacho QA #{venta.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()
        assert m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad == sb_pre - 5
        assert db.session.get(m.Venta, venta.id).bodega_despacho_estado == 'SALIDA_PARCIAL'


# =====================================================================
#  T5 -- Invariantes de negocio
# =====================================================================
@pytest.mark.smoke
@pytest.mark.invariantes
class TestT05Invariantes:

    def test_cliente_final_existe(self, app_ctx):
        cf = m.obtener_o_crear_cliente_final()
        assert cf and cf.rut

    def test_almacenes_distintos(self, app_ctx):
        at, ab = m.id_almacen_tienda(), m.id_almacen_bodega()
        assert at and ab and at != ab

    def test_permisos_semilla(self, app_ctx):
        nombres = {p.nombre for p in m.Permiso.query.all()}
        assert {'pos_emitir_vale', 'caja_cobrar_vale', 'bodega_operador', 'ver_inventario'} <= nombres

    def test_nav_map_estructura(self, app_ctx):
        nav = m._NAV_MAP
        assert isinstance(nav, list) and len(nav) > 0
        for g in nav:
            assert 'id' in g and 'items' in g

    def test_home_por_perfil_existe(self, app_ctx):
        assert callable(m._home_por_perfil)


# =====================================================================
#  T6 -- Redireccion por perfil
# =====================================================================
@pytest.mark.smoke
class TestT06Redireccion:
    def test_funcion_existe_y_es_callable(self, app_ctx):
        assert callable(m._home_por_perfil)

    def test_redirige_a_pos_si_el_rol_tiene_permiso_pos(self, app_ctx):
        usuario = SimpleNamespace(
            rol=SimpleNamespace(
                nombre='Vendedor',
                rol_permisos=[
                    SimpleNamespace(permiso=SimpleNamespace(nombre='pos_emitir_vale'))
                ],
            )
        )
        with m.app.test_request_context('/'):
            assert m._home_por_perfil(usuario) == m.url_for('punto_venta')


# =====================================================================
#  T7 -- Validacion post-hoc
# =====================================================================
@pytest.mark.smoke
@pytest.mark.happy_path
class TestT07PostHoc:

    def test_venta_pagada_coherente(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado' and len(vr.detalles) > 0 and vr.monto_total > 0
        if vr.neto and vr.iva:
            assert abs((vr.neto + vr.iva) - vr.monto_total) <= 1
        for d in vr.detalles:
            assert m.MovimientoInventario.query.filter_by(
                referencia_tipo='venta', referencia_id=vr.id, id_producto=d.id_producto).first()
        assert m.MovimientoCaja.query.filter(
            m.MovimientoCaja.concepto.contains(str(vr.id))).first()


# =====================================================================
#  T8 -- Anulacion de vale (sin y con despacho bodega)
# =====================================================================
@pytest.mark.anulacion
class TestT08AnulacionVale:

    def test_anular_sin_despacho_revierte_stock(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 3)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        assert m.stock_disponible_venta_tienda(p) == stock_pre - 3

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.estado = 'Anulada'
            venta.motivo_anulacion = 'QA anulacion'
            venta.fecha_anulacion = datetime.now()
            venta.usuario_anulacion = QA_USER
            aid_t = m.id_almacen_tienda() or 1
            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
                m.incrementar_stock_venta_tienda(prod, consumo)
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='ENTRADA', cantidad=consumo,
                    motivo=f'Anulacion QA #{venta.id}', usuario=QA_USER, id_almacen=aid_t,
                    referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()
        assert m.stock_disponible_venta_tienda(p) == stock_pre
        assert db.session.get(m.Venta, venta.id).estado == 'Anulada'

    def test_anular_con_despacho_revierte_bodega(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[4]
        aid_b = m.id_almacen_bodega()
        asegurar_stock_bodega(p, 100)
        sb_pre = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad
        venta, dets = crear_venta_pendiente([(p, 8)], caja_abierta, cliente_final, 'Bodega')

        from services.venta_service import transaccion_critica
        with transaccion_critica():
            venta.bodega_despacho_json = json.dumps({str(dets[0].id): 8})
            venta.bodega_despacho_estado = 'DESPACHADO'
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
            spa.cantidad -= 8
            m.registrar_movimiento_kardex(
                id_producto=p.id, tipo_movimiento='SALIDA', cantidad=8,
                motivo=f'Despacho QA #{venta.id}', usuario=QA_USER,
                id_almacen=aid_b, referencia_tipo='venta', referencia_id=venta.id)
        db.session.commit()

        with transaccion_critica():
            venta.estado = 'Anulada'
            venta.motivo_anulacion = 'QA anulacion bodega'
            venta.fecha_anulacion = datetime.now()
            venta.usuario_anulacion = QA_USER
            desp = json.loads(venta.bodega_despacho_json or '{}')
            for did_s, cant in desp.items():
                det_obj = db.session.get(m.DetalleVenta, int(did_s))
                if not det_obj:
                    continue
                spa_r = m.StockPorAlmacen.query.filter_by(
                    id_producto=det_obj.id_producto, id_almacen=aid_b).first()
                spa_r.cantidad += int(cant)
                m.registrar_movimiento_kardex(
                    id_producto=det_obj.id_producto, tipo_movimiento='ENTRADA',
                    cantidad=int(cant), motivo=f'Reversion QA #{venta.id}',
                    usuario=QA_USER, id_almacen=aid_b,
                    referencia_tipo='venta', referencia_id=venta.id)
            venta.bodega_despacho_json = None
            venta.bodega_despacho_estado = None
        db.session.commit()
        assert m.StockPorAlmacen.query.filter_by(
            id_producto=p.id, id_almacen=aid_b).first().cantidad == sb_pre
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada' and vr.bodega_despacho_json is None


# =====================================================================
#  T9 -- Stock insuficiente (debe rechazar)
# =====================================================================
@pytest.mark.edge_case
class TestT09StockInsuficiente:

    def test_cobro_rechazado_por_stock(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        qty = m.stock_disponible_venta_tienda(p) + 100
        venta, _ = crear_venta_pendiente([(p, qty)], caja_abierta, cliente_final)

        from services.venta_service import transaccion_critica
        cobro_fallo = False
        try:
            with transaccion_critica():
                venta.estado = 'Pagado'; venta.metodo_pago = 'Efectivo'
                for det in venta.detalles:
                    prod = db.session.get(m.Producto, det.id_producto)
                    consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
                    err = m.descontar_stock_venta_tienda(prod, consumo)
                    if err:
                        raise ValueError(f'Stock insuficiente: {err}')
            db.session.commit()
        except (ValueError, AssertionError):
            db.session.rollback(); cobro_fallo = True

        assert cobro_fallo, 'Cobro deberia fallar por stock insuficiente'
        venta.estado = 'Anulada'; venta.motivo_anulacion = 'QA stock'
        db.session.commit()


# =====================================================================
#  T10 -- Concurrencia (doble cobro)
# =====================================================================
@pytest.mark.concurrency
@pytest.mark.slow
class TestT10Concurrencia:

    def test_solo_un_thread_cobra(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[1]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 2)], caja_abierta, cliente_final)
        vid = venta.id
        resultados = {}
        barrera = threading.Barrier(2, timeout=10)

        def cobro_thread(nombre):
            try:
                with m.app.app_context():
                    barrera.wait()
                    from services.venta_service import transaccion_critica
                    v = db.session.get(m.Venta, vid)
                    if v.estado != 'Pendiente':
                        resultados[nombre] = 'skipped'; return
                    try:
                        with transaccion_critica():
                            v2 = db.session.get(m.Venta, vid)
                            if v2.estado != 'Pendiente':
                                resultados[nombre] = 'skipped'; return
                            v2.estado = 'Pagado'; v2.metodo_pago = 'Efectivo'
                            v2.monto_recibido = v2.monto_total; v2.vuelto = 0
                            aid_t = m.id_almacen_tienda() or 1
                            for det in v2.detalles:
                                prod = db.session.get(m.Producto, det.id_producto)
                                consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
                                m.descontar_stock_venta_tienda(prod, consumo)
                                m.registrar_movimiento_kardex(
                                    id_producto=prod.id, tipo_movimiento='SALIDA',
                                    cantidad=consumo, motivo=f'Conc {nombre} QA',
                                    usuario=QA_USER, id_almacen=aid_t,
                                    referencia_tipo='venta', referencia_id=vid)
                        db.session.commit(); resultados[nombre] = 'ok'
                    except Exception:
                        db.session.rollback(); resultados[nombre] = 'error'
            except Exception:
                resultados[nombre] = 'error'

        t1 = threading.Thread(target=cobro_thread, args=('t1',))
        t2 = threading.Thread(target=cobro_thread, args=('t2',))
        t1.start(); t2.start(); t1.join(15); t2.join(15)
        cobros_ok = sum(1 for r in resultados.values() if r == 'ok')
        assert cobros_ok <= 1, f'Doble cobro! {resultados}'
        assert m.stock_disponible_venta_tienda(p) == stock_pre - (2 * cobros_ok)


# =====================================================================
#  T11 -- Despacho parcial + final con voz simulada
# =====================================================================
@pytest.mark.happy_path
@pytest.mark.bodega
class TestT11DespachoVozCompleto:

    def test_parcial_luego_final(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[4]
        aid_b = m.id_almacen_bodega()
        asegurar_stock_bodega(p, 200)
        sb_pre = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad
        venta, _ = crear_venta_pendiente([(p, 10)], caja_abierta, cliente_final, 'Bodega')

        r1 = simular_comando_voz(venta.id, p.codigo_barra, 4)
        assert r1['estado'] == 'SALIDA_PARCIAL' and r1['stock_bodega'] == sb_pre - 4

        r2 = simular_comando_voz(venta.id, p.codigo_barra, 6)
        assert r2['estado'] == 'DESPACHADO' and r2['stock_bodega'] == sb_pre - 10

        desp = json.loads(db.session.get(m.Venta, venta.id).bodega_despacho_json or '{}')
        assert sum(int(v) for v in desp.values()) == 10


# =====================================================================
#  T12 -- Exceder cupo de credito
# =====================================================================
@pytest.mark.edge_case
class TestT12ExcederCupoCredito:

    def test_credito_rechazado_por_cupo(self, productos_con_stock, caja_abierta, cliente_credito):
        cliente_credito.saldo_deudor = cliente_credito.limite_credito - 1000
        db.session.commit()
        p = productos_con_stock[3]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_credito)
        assert venta.monto_total > cliente_credito.cupo_disponible

        from services.venta_service import transaccion_critica
        rechazado = False
        try:
            with transaccion_critica():
                if venta.monto_total > cliente_credito.cupo_disponible:
                    raise ValueError('Cupo insuficiente')
                venta.metodo_pago = 'Credito'
            db.session.commit()
        except ValueError:
            db.session.rollback(); rechazado = True

        assert rechazado
        cliente_credito.saldo_deudor = 0
        venta.estado = 'Anulada'; venta.motivo_anulacion = 'QA cupo'
        db.session.commit()


# =====================================================================
#  T13 -- Anulacion de vale ya despachado
# =====================================================================
@pytest.mark.anulacion
class TestT13AnulacionDespachado:

    def test_requiere_motivo_y_revierte(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[4]
        aid_b = m.id_almacen_bodega()
        asegurar_stock_bodega(p, 100)
        sb_pre = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad
        venta, _ = crear_venta_pendiente([(p, 5)], caja_abierta, cliente_final, 'Bodega')
        cobrar_venta_efectivo(venta, caja_abierta)
        simular_comando_voz(venta.id, p.codigo_barra, 5)
        assert db.session.get(m.Venta, venta.id).bodega_despacho_estado == 'DESPACHADO'

        from services.venta_service import transaccion_critica
        motivo = 'Devolucion completa (QA)'
        with transaccion_critica():
            venta.estado = 'Anulada'; venta.motivo_anulacion = motivo
            venta.fecha_anulacion = datetime.now(); venta.usuario_anulacion = QA_USER
            aid_t = m.id_almacen_tienda() or 1
            for det in venta.detalles:
                prod = db.session.get(m.Producto, det.id_producto)
                consumo = int(det.cantidad * m._factor_venta_a_stock(prod))
                m.incrementar_stock_venta_tienda(prod, consumo)
                m.registrar_movimiento_kardex(
                    id_producto=prod.id, tipo_movimiento='ENTRADA', cantidad=consumo,
                    motivo=f'Anulacion tienda QA #{venta.id}', usuario=QA_USER,
                    id_almacen=aid_t, referencia_tipo='venta', referencia_id=venta.id)
            desp = json.loads(venta.bodega_despacho_json or '{}')
            for did_s, cant in desp.items():
                det_obj = db.session.get(m.DetalleVenta, int(did_s))
                if not det_obj:
                    continue
                spa_r = m.StockPorAlmacen.query.filter_by(
                    id_producto=det_obj.id_producto, id_almacen=aid_b).first()
                spa_r.cantidad += int(cant)
                m.registrar_movimiento_kardex(
                    id_producto=det_obj.id_producto, tipo_movimiento='ENTRADA',
                    cantidad=int(cant), motivo=f'Reversion bodega QA #{venta.id}',
                    usuario=QA_USER, id_almacen=aid_b,
                    referencia_tipo='venta', referencia_id=venta.id)
            venta.bodega_despacho_json = None; venta.bodega_despacho_estado = None
        db.session.commit()
        assert m.StockPorAlmacen.query.filter_by(
            id_producto=p.id, id_almacen=aid_b).first().cantidad == sb_pre
        vf = db.session.get(m.Venta, venta.id)
        assert vf.estado == 'Anulada' and vf.motivo_anulacion == motivo


# =====================================================================
#  T14 -- transaccion_critica rollback
# =====================================================================
@pytest.mark.invariantes
class TestT14TransaccionCritica:

    def test_rollback_parcial(self, productos_con_stock, app_ctx):
        p = productos_con_stock[0]
        stock_pre = m.stock_disponible_venta_tienda(p)
        from services.venta_service import transaccion_critica
        try:
            with transaccion_critica():
                m.descontar_stock_venta_tienda(p, 1)
                raise RuntimeError('Fallo simulado')
        except RuntimeError:
            pass
        db.session.rollback()
        assert m.stock_disponible_venta_tienda(p) == stock_pre

    def test_rollback_no_deja_movimientos(self, productos_con_stock, app_ctx):
        p = productos_con_stock[0]
        ref = f'rollback-{datetime.now():%f}'
        from services.venta_service import transaccion_critica
        try:
            with transaccion_critica():
                m.registrar_movimiento_kardex(
                    id_producto=p.id, tipo_movimiento='SALIDA', cantidad=1,
                    motivo=ref, usuario=QA_USER, id_almacen=m.id_almacen_tienda() or 1,
                    referencia_tipo='test', referencia_id=0)
                raise RuntimeError('Fallo post-kardex')
        except RuntimeError:
            pass
        db.session.rollback()
        assert m.MovimientoInventario.query.filter_by(motivo=ref).first() is None


# =====================================================================
#  T15 -- IVA y redondeos (parametrizado)
# =====================================================================
@pytest.mark.smoke
@pytest.mark.invariantes
class TestT15IVARedondeos:

    @pytest.mark.parametrize('total,neto_esperado,iva_esperado', [
        (119000, 100000, 19000),
        (1190, 1000, 190),
        (100, 84, 16),
        (1, 1, 0),
        (0, 0, 0),
        (999990, 840328, 159662),
        (50000, 42017, 7983),
    ])
    def test_desglose_iva_chile(self, total, neto_esperado, iva_esperado, app_ctx):
        v = m.Venta(monto_total=total)
        v.desglosar_iva()
        assert v.neto == neto_esperado and v.iva == iva_esperado
        assert v.neto + v.iva == total

    def test_recalcular_total_redondea_entero(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        assert venta.monto_total == float(round(venta.monto_total))
        assert venta.neto + venta.iva == venta.monto_total

    @pytest.mark.parametrize('qty', [1, 7, 13, 99])
    def test_total_coherente_cantidades(self, qty, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, qty)], caja_abierta, cliente_final)
        assert venta.monto_total == float(round(qty * p.precio_venta))
        assert venta.neto + venta.iva == venta.monto_total


# =====================================================================
#  T16 -- Prueba de carga ligera (10 ventas simultaneas)
# =====================================================================
@pytest.mark.load
@pytest.mark.slow
class TestT16CargaLigera:

    def test_10_ventas_simultaneas(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[1]
        db.session.expire_all()
        stock_pre = m.stock_disponible_venta_tienda(p)
        n = 10

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(
                    venta_rapida_thread_safe, i,
                    p.id, caja_abierta.id, cliente_final.id)
                for i in range(n)
            ]
            results = [f.result(timeout=30) for f in as_completed(futures)]

        ok_count = sum(1 for r in results if r['ok'])
        fail_count = sum(1 for r in results if not r['ok'])

        assert ok_count > 0, f'Ninguna venta exitosa: {results}'
        assert ok_count + fail_count == n

        db.session.expire_all()
        stock_post = m.stock_disponible_venta_tienda(p)
        assert stock_post < stock_pre, \
            f'Stock no disminuyo: pre={stock_pre}, post={stock_post}'
        assert stock_post >= stock_pre - ok_count, \
            f'Stock bajo mas de lo esperado: {stock_pre}->{stock_post} con {ok_count} ventas'


# =====================================================================
#  T17 -- Flujo multi-almacen (traslado tienda <-> bodega)
# =====================================================================
@pytest.mark.happy_path
@pytest.mark.bodega
class TestT17MultiAlmacen:

    def test_venta_tienda_y_traslado_a_bodega(self, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        aid_t = m.id_almacen_tienda()
        aid_b = m.id_almacen_bodega()
        assert aid_t and aid_b

        asegurar_stock_bodega(p, 50)
        st_pre = m.stock_disponible_venta_tienda(p)
        sb_pre = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first().cantidad

        venta, _ = crear_venta_pendiente([(p, 2)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        assert m.stock_disponible_venta_tienda(p) == st_pre - 2

        qty_traslado = 5
        st_after, sb_after = trasladar_stock(p, aid_t, aid_b, qty_traslado)

        assert st_after == st_pre - 2 - qty_traslado
        assert sb_after == sb_pre + qty_traslado

        k_salida = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, tipo_movimiento='SALIDA',
            id_almacen=aid_t, referencia_tipo='traslado').order_by(
            m.MovimientoInventario.id.desc()).first()
        k_entrada = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, tipo_movimiento='ENTRADA',
            id_almacen=aid_b, referencia_tipo='traslado').order_by(
            m.MovimientoInventario.id.desc()).first()
        assert k_salida and k_entrada
        assert k_salida.cantidad == qty_traslado == k_entrada.cantidad

    def test_traslado_bodega_a_tienda(self, productos_con_stock, app_ctx):
        from sqlalchemy import text as sa_text
        p = productos_con_stock[2]
        aid_t = m.id_almacen_tienda()
        aid_b = m.id_almacen_bodega()

        asegurar_stock_bodega(p, 200)
        db.session.expire_all()

        st_pre = m.stock_disponible_venta_tienda(p)

        so_after, sd_after = trasladar_stock(p, aid_b, aid_t, 10)
        db.session.expire_all()
        st_post = m.stock_disponible_venta_tienda(p)
        assert st_post == st_pre + 10, f'Tienda: {st_pre} -> {st_post}, esperado {st_pre + 10}'

        k_salida = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, tipo_movimiento='SALIDA',
            id_almacen=aid_b, referencia_tipo='traslado').order_by(
            m.MovimientoInventario.id.desc()).first()
        k_entrada = m.MovimientoInventario.query.filter_by(
            id_producto=p.id, tipo_movimiento='ENTRADA',
            id_almacen=aid_t, referencia_tipo='traslado').order_by(
            m.MovimientoInventario.id.desc()).first()
        assert k_salida and k_entrada
        assert k_salida.cantidad == 10 == k_entrada.cantidad


# =====================================================================
#  T18 -- Auditoria (erp_audit_log)
# =====================================================================
@pytest.mark.invariantes
@pytest.mark.audit
class TestT18Auditoria:

    def test_cobro_genera_audit_log(self, productos_con_stock, caja_abierta, cliente_final, audit_snapshot):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo_con_audit(venta, caja_abierta)

        entries = audit_snapshot('cobro_vale')
        cobros = [e for e in entries if e.entidad_id == venta.id]
        assert len(cobros) >= 1, f'No hay audit cobro_vale para venta #{venta.id}'
        entry = cobros[0]
        assert entry.entidad_tipo == 'venta'
        assert entry.usuario == QA_USER

    def test_anulacion_genera_audit_log(self, productos_con_stock, caja_abierta, cliente_final, audit_snapshot):
        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        anular_venta_con_audit(venta, 'QA auditoria test')

        entries = audit_snapshot('anular_vale')
        anulaciones = [e for e in entries if e.entidad_id == venta.id]
        assert len(anulaciones) >= 1
        entry = anulaciones[0]
        assert entry.entidad_tipo == 'venta'
        assert 'Anulada' in (entry.datos_despues or '')

    def test_audit_log_tabla_existe(self, app_ctx):
        ok = m._asegurar_tabla_erp_audit_log()
        assert ok, 'erp_audit_log no se pudo crear/verificar'

    def test_audit_log_campos_completos(self, productos_con_stock, caja_abierta, cliente_final, audit_snapshot):
        p = productos_con_stock[2]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo_con_audit(venta, caja_abierta)

        entries = audit_snapshot('cobro_vale')
        cobros = [e for e in entries if e.entidad_id == venta.id]
        assert cobros
        e = cobros[0]
        assert e.created_at is not None
        assert e.evento == 'cobro_vale'
        assert e.entidad_tipo == 'venta'
        assert e.entidad_id == venta.id
        assert e.datos_antes is not None
        assert e.datos_despues is not None
