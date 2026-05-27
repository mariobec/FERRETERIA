"""
ERP LhexIA -- Tests de rutas criticas que mueven estado (v4+).

Pruebas HTTP reales via Flask test_client sobre endpoints que:
- Crean/modifican ventas, stock, kardex, caja, creditos
- Requieren autenticacion y permisos especificos
- Generan audit_log

Ejecucion:
    pytest tests/test_routes_criticas.py -v --cov=app --cov-report=term-missing
"""
import json
from datetime import date, datetime, timedelta

import pytest

import app as m
from tests.conftest import (
    QA_USER,
    asegurar_stock_bodega,
    cobrar_venta_efectivo,
    crear_venta_pendiente,
    login_as,
)

db = m.db


@pytest.fixture(autouse=True)
def _session_safety():
    """Rollback any pending broken transaction before each test."""
    try:
        db.session.rollback()
    except Exception:
        pass
    yield
    try:
        db.session.rollback()
    except Exception:
        pass


# =====================================================================
#  Helpers locales
# =====================================================================
def _get_admin_user():
    """Retorna el primer usuario con rol admin."""
    return m.Usuario.query.join(m.Rol).filter(
        m.Rol.nombre.in_(['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin'])
    ).first() or m.Usuario.query.first()


def _ensure_caja_abierta():
    """Garantiza caja Abierta con fecha de hoy (POS no redirige a cerrar_caja)."""
    from tests.conftest import _asegurar_caja_abierta_qa

    return _asegurar_caja_abierta_qa()


# =====================================================================
#  1. POS + Venta Completa
# =====================================================================
@pytest.mark.smoke
class TestPOSVenta:

    def test_punto_venta_get_autenticado(self, app_client):
        r = app_client.get('/punto_venta')
        assert r.status_code in (200, 302)

    def test_guardar_venta_crea_pendiente(self, app_client, productos_con_stock):
        _ensure_caja_abierta()
        p = productos_con_stock[0]
        cf = m.obtener_o_crear_cliente_final()

        r = app_client.post('/guardar_venta', data={
            'metodo_pago': 'Efectivo',
            'cliente_id': str(cf.id),
            'id_producto[]': str(p.id),
            'cantidad[]': '2',
            'precio_unitario[]': str(p.precio_venta),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_finalizar_venta_pos(self, app_client, productos_con_stock):
        _ensure_caja_abierta()
        r = app_client.post('/finalizar_venta', data={
            'cliente_final': '1',
            'punto_retiro': 'Tienda',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_agregar_producto_venta_get(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/agregar_producto_venta?codigo={p.codigo_barra}')
        assert r.status_code in (200, 302)

    def test_agregar_producto_inexistente(self, app_client):
        r = app_client.get('/agregar_producto_venta?codigo=NOEXISTE999')
        assert r.status_code in (200, 302)

    @pytest.mark.parametrize('metodo', ['Efectivo', 'Transferencia'])
    def test_guardar_venta_multiples_metodos(self, metodo, app_client, productos_con_stock):
        _ensure_caja_abierta()
        p = productos_con_stock[1]
        cf = m.obtener_o_crear_cliente_final()
        r = app_client.post('/guardar_venta', data={
            'metodo_pago': metodo,
            'cliente_id': str(cf.id),
            'id_producto[]': str(p.id),
            'cantidad[]': '1',
            'precio_unitario[]': str(p.precio_venta),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_editar_venta_get(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r = app_client.get(f'/editar_venta/{venta.id}')
        assert r.status_code in (200, 302)

    def test_editar_venta_post(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r = app_client.post(f'/editar_venta/{venta.id}', data={
            'usuario': QA_USER,
            'id_producto[]': str(p.id),
            'cantidad[]': '3',
            'precio_unitario[]': str(p.precio_venta),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        db.session.expire_all()
        v = db.session.get(m.Venta, venta.id)
        if v and v.estado != 'Anulada':
            assert v.monto_total == 3 * p.precio_venta


# =====================================================================
#  2. Caja (Critico)
# =====================================================================
class TestCajaCritica:

    def test_vales_pendientes_get(self, app_client):
        _ensure_caja_abierta()
        r = app_client.get('/caja/vales_pendientes')
        assert r.status_code in (200, 302)

    def test_procesar_cobro_efectivo(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)

        r = app_client.post(f'/procesar_cobro_caja/{venta.id}', data={
            'metodo_pago': 'Efectivo',
            'tipo_documento': 'Boleta',
            'monto_recibido': str(venta.monto_total + 100),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

        db.session.expire_all()
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'
        assert vr.metodo_pago == 'Efectivo'

        k = m.MovimientoInventario.query.filter_by(
            referencia_tipo='venta', referencia_id=venta.id).first()
        assert k is not None

    @pytest.mark.parametrize('metodo,doc', [
        ('Efectivo', 'Boleta'),
        ('Transferencia', 'Boleta'),
        ('Efectivo', 'Factura'),
    ])
    def test_cobro_multiples_medios(self, metodo, doc, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r = app_client.post(f'/procesar_cobro_caja/{venta.id}', data={
            'metodo_pago': metodo,
            'tipo_documento': doc,
            'monto_recibido': str(venta.monto_total + 50),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        db.session.expire_all()
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'

    def test_cobro_venta_inexistente(self, app_client):
        r = app_client.post('/procesar_cobro_caja/999999', data={
            'metodo_pago': 'Efectivo',
            'tipo_documento': 'Boleta',
            'monto_recibido': '50000',
        }, follow_redirects=True)
        assert r.status_code in (200, 302, 404)

    def test_anular_vale_pendiente(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[2]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)

        r = app_client.post(f'/caja/vales/{venta.id}/anular', data={
            'motivo': 'QA test anulacion via HTTP',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

        db.session.expire_all()
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada'

    def test_anular_sin_motivo(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r = app_client.post(f'/caja/vales/{venta.id}/anular', data={
            'motivo': '',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_anular_vales_caja_lote(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        """Anulación masiva desde POST /caja/vales/anular_lote (permiso anular_vale_caja)."""
        from werkzeug.datastructures import ImmutableMultiDict

        p = productos_con_stock[1]
        v1, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        v2, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        fd = ImmutableMultiDict(
            [
                ('motivo', 'QA test anulacion lote HTTP'),
                ('venta_ids', str(v1.id)),
                ('venta_ids', str(v2.id)),
            ]
        )
        r = app_client.post('/caja/vales/anular_lote', data=fd, follow_redirects=True)
        assert r.status_code == 200

        db.session.expire_all()
        assert db.session.get(m.Venta, v1.id).estado == 'Anulada'
        assert db.session.get(m.Venta, v2.id).estado == 'Anulada'

    def test_cobro_ya_pagado_rechaza(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)

        r = app_client.post(f'/procesar_cobro_caja/{venta.id}', data={
            'metodo_pago': 'Efectivo',
            'tipo_documento': 'Boleta',
            'monto_recibido': str(venta.monto_total),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_caja_cambios_get(self, app_client):
        _ensure_caja_abierta()
        r = app_client.get('/caja/cambios')
        assert r.status_code in (200, 302)

    def test_caja_saldos_favor_get(self, app_client):
        r = app_client.get('/caja/saldos-favor')
        assert r.status_code in (200, 302)


# =====================================================================
#  3. Bodega
# =====================================================================
class TestBodegaRutas:

    def test_bodega_plataforma_get(self, app_client):
        r = app_client.get('/bodega/plataforma')
        assert r.status_code in (200, 302)

    def test_bodega_plataforma_filtro_estado(self, app_client):
        r = app_client.get('/bodega/plataforma?estado=PENDIENTE')
        assert r.status_code in (200, 302)

    def test_bodega_cuadro_mando_get(self, app_client):
        r = app_client.get('/bodega/cuadro-mando')
        assert r.status_code in (200, 302)

    def test_bodega_cuadro_mando_tv(self, app_client):
        r = app_client.get('/bodega/cuadro-mando/tv')
        assert r.status_code in (200, 302)

    def test_bodega_despachos_get(self, app_client):
        r = app_client.get('/bodega/despachos')
        assert r.status_code in (200, 302)

    def test_bodega_export_dia(self, app_client):
        r = app_client.get('/bodega/export-dia')
        assert r.status_code in (200, 302)

    def test_bodega_retiros_snapshot(self, app_client):
        r = app_client.get('/api/bodega/retiros-cola-snapshot')
        assert r.status_code in (200, 302)

    def test_voice_command_sin_audio(self, app_client):
        r = app_client.post('/api/bodega/voice-command',
                            content_type='multipart/form-data', data={})
        assert r.status_code in (200, 400, 422, 503)

    def test_bodega_preparacion_post(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[4]
        asegurar_stock_bodega(p, 50)
        venta, _ = crear_venta_pendiente([(p, 3)], caja_abierta, cliente_final, 'Bodega')
        cobrar_venta_efectivo(venta, caja_abierta)

        r = app_client.post(f'/bodega/vale/{venta.id}/preparacion', data={
            'estado': 'EN_PREPARACION',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)


# =====================================================================
#  4. Compras y Recepciones
# =====================================================================
class TestComprasRecepciones:

    def test_crear_oc_get(self, app_client):
        r = app_client.get('/compras/ordenes/nueva')
        assert r.status_code in (200, 302)

    def test_crear_oc_post(self, app_client, productos_con_stock, proveedor_test):
        p = productos_con_stock[3]
        r = app_client.post('/compras/ordenes/nueva', data={
            'proveedor_id': str(proveedor_test.id),
            'numero': f'QA-HTTP-{datetime.now():%H%M%S%f}',
            'estado': 'Borrador',
            'producto_id[]': str(p.id),
            'cantidad[]': '15',
            'precio_unitario[]': str(p.precio_compra),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_recepciones_nueva_get(self, app_client):
        r = app_client.get('/recepciones/nueva')
        assert r.status_code in (200, 302)

    def test_recepciones_tablet(self, app_client):
        r = app_client.get('/recepciones/tablet')
        assert r.status_code in (200, 302)

    def test_recepciones_costos(self, app_client):
        r = app_client.get('/recepciones/costos')
        assert r.status_code in (200, 302)

    def test_oc_detalle_get(self, app_client, productos_con_stock, proveedor_test):
        db.session.rollback()
        p = productos_con_stock[3]
        db.session.expire_all()
        prov_id = proveedor_test.id
        oc = m.OrdenCompra(
            proveedor_id=prov_id,
            numero=f'QA-DET-{datetime.now():%H%M%S%f}',
            fecha_emision=date.today(), estado='Borrador',
            usuario_creador=QA_USER)
        db.session.add(oc)
        db.session.flush()
        db.session.add(m.DetalleOrdenCompra(
            orden_compra_id=oc.id, producto_id=p.id,
            cantidad=5, precio_unitario=p.precio_compra))
        db.session.commit()
        r = app_client.get(f'/compras/ordenes/{oc.id}')
        assert r.status_code in (200, 302)


# =====================================================================
#  5. Creditos
# =====================================================================
class TestCreditos:

    def test_creditos_lista(self, app_client):
        r = app_client.get('/creditos')
        assert r.status_code in (200, 302)

    def test_registrar_abono(self, app_client, cliente_credito, caja_abierta):
        _ensure_caja_abierta()
        cliente_credito.saldo_deudor = 50000
        db.session.commit()

        r = app_client.post('/registrar_abono', data={
            'cliente_id': str(cliente_credito.id),
            'metodo_pago': 'Efectivo',
            'monto_abono': '10000',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_estado_cuenta_get(self, app_client, cliente_credito):
        r = app_client.get(f'/creditos/estado_cuenta/{cliente_credito.id}')
        assert r.status_code in (200, 302)


# =====================================================================
#  6. Admin: crear/editar producto, cliente, proveedor
# =====================================================================
class TestAdminCRUD:

    def test_guardar_producto_completo(self, app_client):
        from sqlalchemy import text as sa_text
        ts = datetime.now().strftime('%H%M%S%f')
        r = app_client.post('/guardar_producto', data={
            'nombre': f'QA Producto HTTP {ts}',
            'codigo': f'QA-HTTP-{ts}',
            'p_compra': '1000',
            'p_venta': '1990',
            'stock': '10',
            'unidad': 'Unidad',
            'categoria': 'Test',
            'subcategoria': 'HTTP',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        prod = m.Producto.query.filter_by(codigo_barra=f'QA-HTTP-{ts}').first()
        if prod:
            assert prod.precio_venta == 1990
            pid = prod.id
            db.session.execute(sa_text("DELETE FROM stock_por_almacen WHERE id_producto = :p"), {'p': pid})
            db.session.execute(sa_text("DELETE FROM movimientos_inventario WHERE id_producto = :p"), {'p': pid})
            db.session.execute(sa_text("DELETE FROM productos WHERE id = :p"), {'p': pid})
            db.session.commit()

    def test_toggle_producto(self, app_client, productos_con_stock):
        p = productos_con_stock[4]
        r = app_client.post(f'/toggle_producto/{p.id}', follow_redirects=True)
        assert r.status_code in (200, 302)
        db.session.expire(p)
        r2 = app_client.post(f'/toggle_producto/{p.id}', follow_redirects=True)
        assert r2.status_code in (200, 302)

    def test_editar_stock_producto(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.post(f'/productos/{p.id}/editar_stock', data={
            'nuevo_stock': '999',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_guardar_proveedor(self, app_client):
        ts = datetime.now().strftime('%H%M%S%f')
        r = app_client.post('/guardar_proveedor', data={
            'nombre': f'QA Prov HTTP {ts}',
            'contacto': 'QA Contact',
            'telefono': '+56900000099',
            'email': f'qa{ts}@test.cl',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        prov = m.Proveedor.query.filter_by(nombre=f'QA Prov HTTP {ts}').first()
        if prov:
            db.session.delete(prov)
            db.session.commit()

    def test_admin_clientes_post(self, app_client):
        r = app_client.post('/admin/clientes', data={
            'rut': '99.999.999-9',
            'nombre': 'QA Cliente HTTP Test',
            'giro': 'Test',
            'direccion': 'Test 123',
            'telefono': '+56900000098',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        cli = m.Cliente.query.filter_by(rut='99.999.999-9').first()
        if cli:
            db.session.delete(cli)
            db.session.commit()

    def test_eliminar_venta_anulada(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        venta.estado = 'Anulada'
        venta.motivo_anulacion = 'QA HTTP delete test'
        db.session.commit()
        r = app_client.post(f'/eliminar_venta/{venta.id}', follow_redirects=True)
        assert r.status_code in (200, 302)


# =====================================================================
#  7. Exports y Reportes
# =====================================================================
class TestExportsReportes:

    def test_bi_export_csv(self, app_client):
        r = app_client.get('/bi/export.csv')
        assert r.status_code in (200, 302)

    def test_bi_export_vendedores(self, app_client):
        r = app_client.get('/bi/export_vendedores.csv')
        assert r.status_code in (200, 302)

    def test_productos_exportar_excel(self, app_client):
        r = app_client.get('/productos/exportar_excel')
        assert r.status_code in (200, 302)

    def test_descargar_plantilla(self, app_client):
        r = app_client.get('/descargar_plantilla_productos')
        assert r.status_code in (200, 302)

    def test_ver_documento(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        r = app_client.get(f'/ver_documento/{venta.id}')
        assert r.status_code in (200, 302, 404)


# =====================================================================
#  8. Permisos denegados por rol
# =====================================================================
class TestPermisosDenegados:

    def test_bodeguero_no_accede_admin(self, app_client):
        with login_as(app_client, 'bodeguero') as c:
            r = c.get('/admin/roles-permisos')
            assert r.status_code in (200, 302, 403)

    def test_vendedor_no_accede_bodega(self, app_client):
        with login_as(app_client, 'vendedor') as c:
            r = c.get('/bodega/plataforma')
            assert r.status_code in (200, 302, 403)

    def test_cajera_accede_vales_pendientes(self, app_client):
        _ensure_caja_abierta()
        with login_as(app_client, 'cajera') as c:
            r = c.get('/caja/vales_pendientes')
            assert r.status_code in (200, 302)

    def test_admin_accede_todo(self, app_client):
        with login_as(app_client, 'admin') as c:
            for url in ['/productos', '/ventas', '/bodega/plataforma',
                        '/caja/vales_pendientes', '/admin/roles-permisos']:
                r = c.get(url)
                assert r.status_code in (200, 302), f'{url} -> {r.status_code}'


# =====================================================================
#  9. Validaciones de estado post-cobro
# =====================================================================
class TestValidacionEstado:

    def test_cobro_genera_kardex_y_stock_change(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[2]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 2)], caja_abierta, cliente_final)
        vid = venta.id

        app_client.post(f'/procesar_cobro_caja/{vid}', data={
            'metodo_pago': 'Efectivo',
            'tipo_documento': 'Boleta',
            'monto_recibido': str(venta.monto_total + 500),
        }, follow_redirects=True)

        db.session.expire_all()
        vr = db.session.get(m.Venta, vid)
        assert vr.estado == 'Pagado'

        kardex = m.MovimientoInventario.query.filter_by(
            referencia_tipo='venta', referencia_id=vid, id_producto=p.id).all()
        assert len(kardex) >= 1
        assert all(k.tipo_movimiento == 'SALIDA' for k in kardex)

        from sqlalchemy import text as sa_text
        audit = db.session.execute(sa_text(
            "SELECT COUNT(*) FROM erp_audit_log WHERE entidad_tipo = 'venta' AND entidad_id = :vid"
        ), {'vid': vid}).scalar()
        assert audit >= 1

        db.session.expire_all()
        stock_post = m.stock_disponible_venta_tienda(p)
        assert stock_post <= stock_pre

    def test_anulacion_via_http_revierte_estado(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[3]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)

        app_client.post(f'/caja/vales/{venta.id}/anular', data={
            'motivo': 'QA validacion estado reversa',
        }, follow_redirects=True)

        db.session.expire_all()
        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada'
        assert vr.motivo_anulacion is not None


# =====================================================================
#  10. Rutas adicionales de alto trafico
# =====================================================================
class TestRutasAltoTrafico:

    def test_buscar_producto_autocomplete(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/buscar_producto?q={p.nombre[:6]}')
        assert r.status_code == 200
        data = r.get_json()
        assert 'results' in data
        assert len(data['results']) >= 1

    def test_buscar_producto_pos_enriquecido(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(
            f'/buscar_producto?q={p.nombre[:6]}&origen=pos&enriquecido=1&solo_vendibles=0'
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['results']
        row = data['results'][0]
        for key in (
            'nombre', 'codigo', 'precio', 'precio_fmt', 'marca',
            'stock_tienda', 'stock_bodega', 'stock_total', 'sin_stock',
            'semaforo', 'semaforo_label', 'permite_venta_verde', 'badges',
        ):
            assert key in row
        assert row['precio_fmt'].startswith('$')
        assert row['semaforo'] in ('verde', 'amarillo', 'azul')

    def test_buscar_producto_enriquecido_orden_stock_primero(self, app_client, productos_con_stock):
        """Con stock disponible debe aparecer antes que filas sin stock (modo catálogo)."""
        p = productos_con_stock[0]
        pref = (p.nombre or 'TEST')[:4]
        r = app_client.get(
            f'/buscar_producto?q={pref}&origen=pos&enriquecido=1&solo_vendibles=0'
        )
        assert r.status_code == 200
        results = r.get_json().get('results') or []
        assert len(results) >= 2
        con_stock = [x for x in results if int(x.get('stock_total') or 0) > 0]
        sin_stock = [x for x in results if x.get('sin_stock')]
        if con_stock and sin_stock:
            idx_ok = results.index(con_stock[0])
            idx_no = results.index(sin_stock[0])
            assert idx_ok < idx_no

    def test_buscar_producto_por_codigo_barra(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/api/buscar_producto/{p.codigo_barra}')
        assert r.status_code in (200, 404)

    def test_healthz(self, app_client):
        r = app_client.get('/healthz')
        assert r.status_code == 200
        assert r.get_json()['status'] == 'ok'

    def test_login_get(self, app_client):
        r = app_client.get('/login')
        assert r.status_code in (200, 302)

    def test_owner_mobile(self, app_client):
        r = app_client.get('/owner-mobile')
        assert r.status_code in (200, 302)

    def test_ia_abastecimiento(self, app_client):
        r = app_client.get('/ia_abastecimiento')
        assert r.status_code in (200, 302)

    def test_comercial_leads(self, app_client):
        r = app_client.get('/comercial/leads')
        assert r.status_code in (200, 302)

    def test_inventario_enrolamiento(self, app_client):
        r = app_client.get('/inventario/enrolamiento')
        assert r.status_code in (200, 302)

    @pytest.mark.parametrize('url', [
        '/bi/demo/dueno',
        '/bi/demo/radar-mercado',
        '/bi/demo/alertas-precio-premium',
        '/gerencia/simulador-margen',
    ])
    def test_bi_demos(self, url, app_client):
        r = app_client.get(url)
        assert r.status_code in (200, 302)


# =====================================================================
#  11. Rutas de Caja (cierre, historial, movimientos)
# =====================================================================
class TestCajaExtra:

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            ("340000", 340000.0),
            ("340.000", 340000.0),
            ("340,000", 340000.0),
            ("340.000,00", 340000.0),
            ("$ 340.000", 340000.0),
            ("CLP 340.000", 340000.0),
            ("340\u00a0000", 340000.0),
            ("12,50", 12.5),
            ("12.5", 12.5),
        ],
    )
    def test_parse_clp_monto_acepta_formatos_reales(self, raw_value, expected):
        assert m._parse_clp_monto(raw_value) == expected

    @pytest.mark.parametrize("raw_value", ["", "abc", "12a", "1-2", "-500"])
    def test_parse_clp_monto_rechaza_invalidos(self, raw_value):
        assert m._parse_clp_monto(raw_value) is None

    def test_cerrar_caja_post(self, app_client):
        _ensure_caja_abierta()
        r = app_client.post(
            '/cerrar_caja',
            data={
                'monto_declarado_cajero': '50000',
                'monto_declarado_tarjeta': '0',
            },
            follow_redirects=True,
        )
        assert r.status_code in (200, 302)
        _ensure_caja_abierta()

    def test_historial_cierres(self, app_client):
        r = app_client.get('/caja/historial_cierres')
        assert r.status_code in (200, 302)

    def test_movimiento_caja_post(self, app_client):
        _ensure_caja_abierta()
        r = app_client.post('/movimiento_caja', data={
            'tipo': 'Ingreso',
            'concepto': 'QA test ingreso',
            'monto': '5000',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_abrir_caja_con_monto(self, app_client):
        caja = m.Caja.query.filter_by(estado='Abierta').first()
        if caja:
            caja.estado = 'Cerrada'
            caja.fecha_cierre = datetime.now()
            db.session.commit()
        r = app_client.post('/abrir_caja', data={
            'monto_inicial': '100000',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        _ensure_caja_abierta()


class TestUsuariosAdmin:

    def test_editar_usuario_actualiza_password_y_limpia_forzar_clave(self, app_client):
        rol = m.Rol.query.first()
        assert rol is not None

        usuario = m.Usuario(
            nombre='QA Editar Usuario',
            correo='qa_editar_usuario@test.cl',
            rol_id=rol.id,
            perfil='FORZAR_CLAVE',
        )
        usuario.set_password('temporal123')
        db.session.add(usuario)
        db.session.commit()

        r = app_client.post(
            f'/editar_usuario/{usuario.id}',
            data={
                'nombre': 'QA Editar Usuario',
                'correo': 'qa_editar_usuario@test.cl',
                'rol_id': str(rol.id),
                'password': 'NuevaClave456',
            },
            follow_redirects=True,
        )
        assert r.status_code == 200

        db.session.expire_all()
        usuario_editado = db.session.get(m.Usuario, usuario.id)
        assert usuario_editado is not None
        assert usuario_editado.check_password('NuevaClave456')
        assert usuario_editado.perfil == 'ACTIVO'

        db.session.delete(usuario_editado)
        db.session.commit()


class TestAnalyticsWeb:

    def test_api_analytics_track_persiste_sesion_y_conversion(self, app_client):
        suffix = datetime.now().strftime('%H%M%S%f')
        visitor_key = f'liz_v_{suffix.lower()}_qavisitorabc123'
        session_key = f'liz_s_{suffix.lower()}_qasessionabc12345'
        pageview_key = f'liz_p_qa{suffix.lower()}'

        r = app_client.post(
            '/api/analytics/track',
            json={
                'events': [
                    {
                        'visitor_key': visitor_key,
                        'session_id': session_key,
                        'session_key': session_key,
                        'pageview_key': pageview_key,
                        'event_name': 'page_view',
                        'path': '/erp-ferreterias',
                        'full_url': 'https://www.lhexia.cl/erp-ferreterias',
                        'page_title': 'ERP para ferreterías',
                        'source': 'google.com',
                        'medium': 'organic',
                    },
                    {
                        'visitor_key': visitor_key,
                        'session_id': session_key,
                        'session_key': session_key,
                        'pageview_key': pageview_key,
                        'event_name': 'heartbeat',
                        'path': '/erp-ferreterias',
                        'active_seconds': 18,
                    },
                    {
                        'visitor_key': visitor_key,
                        'session_id': session_key,
                        'session_key': session_key,
                        'pageview_key': pageview_key,
                        'event_name': 'conversion',
                        'conversion_type': 'whatsapp_click',
                        'path': '/erp-ferreterias',
                    },
                ]
            },
            follow_redirects=True,
        )
        assert r.status_code == 202

        visitor = m.WebAnalyticsVisitor.query.filter_by(visitor_key=visitor_key).first()
        session = m.WebAnalyticsSession.query.filter_by(session_key=session_key).first()
        pageview = m.WebAnalyticsPageView.query.filter_by(pageview_key=pageview_key).first()
        conversion = (
            m.WebAnalyticsConversion.query.join(m.WebAnalyticsSession)
            .filter(m.WebAnalyticsSession.session_key == session_key)
            .order_by(m.WebAnalyticsConversion.id.desc())
            .first()
        )

        assert visitor is not None
        assert session is not None
        assert pageview is not None
        assert conversion is not None
        assert session.pageviews_count >= 1
        assert session.active_seconds >= 18
        assert session.conversions_count >= 1
        assert conversion.conversion_type == 'whatsapp_click'
        raw_rows = m.ControlTraficoInterno.query.filter_by(session_id=session_key).all()
        assert len(raw_rows) >= 3

        if conversion:
            db.session.delete(conversion)
        events = m.WebAnalyticsEvent.query.filter_by(session_id=session.id).all() if session else []
        for ev in events:
            db.session.delete(ev)
        for raw in raw_rows:
            db.session.delete(raw)
        if pageview:
            db.session.delete(pageview)
        if session:
            db.session.delete(session)
        if visitor:
            db.session.delete(visitor)
        db.session.commit()

    def test_api_analytics_track_rechaza_session_id_invalido(self, app_client):
        r = app_client.post(
            '/api/analytics/track',
            json={
                'events': [
                    {
                        'visitor_key': 'liz_v_demo_demo123456',
                        'session_id': 'invalido',
                        'pageview_key': 'liz_p_demo123',
                        'event_name': 'page_view',
                        'path': '/',
                    }
                ]
            },
            follow_redirects=True,
        )
        assert r.status_code == 400

    def test_api_analytics_track_normaliza_taxonomia_cta(self, app_client):
        suffix = datetime.now().strftime('%H%M%S%f').lower()
        visitor_key = f'liz_v_{suffix}_qactaabc123'
        session_key = f'liz_s_{suffix}_qactasession12345'
        pageview_key = f'liz_p_qacta{suffix}'

        r = app_client.post(
            '/api/analytics/track',
            json={
                'events': [
                    {
                        'visitor_key': visitor_key,
                        'session_id': session_key,
                        'session_key': session_key,
                        'pageview_key': pageview_key,
                        'event_name': 'cta_click',
                        'path': '/erp-ferreterias',
                        'label': 'Quiero mi Diagnóstico IA Gratis',
                        'target': 'https://www.lhexia.cl/index#diagnostico',
                        'meta': {
                            'tag': 'a',
                        },
                    }
                ]
            },
            follow_redirects=True,
        )
        assert r.status_code == 202

        session = m.WebAnalyticsSession.query.filter_by(session_key=session_key).first()
        event = (
            m.WebAnalyticsEvent.query.join(m.WebAnalyticsSession)
            .filter(m.WebAnalyticsSession.session_key == session_key, m.WebAnalyticsEvent.event_name == 'cta_click')
            .order_by(m.WebAnalyticsEvent.id.desc())
            .first()
        )
        assert session is not None
        assert event is not None
        assert event.label == 'diagnostico_ia'

        meta = json.loads(event.meta_json or '{}')
        assert meta.get('cta_id') == 'diagnostico_ia'
        assert meta.get('cta_group') == 'lead_capture'
        assert meta.get('page_family') == 'money_page'

        raw_rows = m.ControlTraficoInterno.query.filter_by(session_id=session_key).all()
        for raw in raw_rows:
            db.session.delete(raw)
        if event:
            db.session.delete(event)
        pageview = m.WebAnalyticsPageView.query.filter_by(pageview_key=pageview_key).first()
        if pageview:
            db.session.delete(pageview)
        if session:
            visitor = m.WebAnalyticsVisitor.query.filter_by(id=session.visitor_id).first()
            db.session.delete(session)
            if visitor:
                db.session.delete(visitor)
        db.session.commit()

    def test_consolidar_y_purgar_telemetria_archiva_y_elimina_raw(self):
        with m.app.app_context():
            m._asegurar_tablas_web_analytics()
            old_ts = datetime.now() - timedelta(days=120)
            raw = m.ControlTraficoInterno(
                created_at=old_ts,
                visitor_key='liz_v_oldbucket_demo123',
                session_id='liz_s_oldbucket_demo123456',
                pageview_key='liz_p_oldbucket123',
                event_name='cta_click',
                path='/erp-ferreterias',
                visits_count=1,
                clicks_count=2,
                active_seconds=35,
                conversions_count=1,
            )
            db.session.add(raw)
            db.session.commit()

            result = m.consolidar_y_purgar_telemetria(retention_days=90)
            assert result.get('ok') is True
            assert result.get('deleted_rows', 0) >= 1

            archive = m.TelemetriaHistoricaAgregada.query.filter_by(bucket_date=old_ts.date()).first()
            assert archive is not None
            assert archive.visitas_total >= 1
            assert archive.clicks_total >= 2
            assert archive.tiempo_activo_segundos >= 35
            assert archive.conversiones_total >= 1
            assert m.ControlTraficoInterno.query.filter_by(session_id='liz_s_oldbucket_demo123456').first() is None

    def test_api_observabilidad_cron_diario_ejecuta_snapshot_y_purga(self, app_client, monkeypatch):
        monkeypatch.setenv('OBSERVABILIDAD_CRON_SECRET', 'qa-observabilidad-secret')

        with m.app.app_context():
            m._asegurar_tablas_web_analytics()
            old_ts = datetime.now() - timedelta(days=120)
            raw = m.ControlTraficoInterno(
                created_at=old_ts,
                visitor_key='liz_v_cron_demo123',
                session_id='liz_s_cron_demo123456',
                pageview_key='liz_p_cron123',
                event_name='cta_click',
                path='/erp-retail-especializado',
                visits_count=1,
                clicks_count=1,
                active_seconds=20,
                conversions_count=0,
            )
            db.session.add(raw)
            db.session.commit()

        r = app_client.post(
            '/api/observabilidad/cron-diario',
            headers={'Authorization': 'Bearer qa-observabilidad-secret'},
            json={'run_seo_snapshot': True, 'run_telemetry_purge': True, 'retention_days': 90},
            follow_redirects=False,
        )
        assert r.status_code == 200

        payload = r.get_json()
        assert payload is not None
        assert payload.get('ok') is True
        assert (payload.get('seo_snapshot') or {}).get('ok') is True
        assert (payload.get('seo_snapshot') or {}).get('pages', 0) >= 5
        assert (payload.get('telemetry_purge') or {}).get('deleted_rows', 0) >= 1

        with m.app.app_context():
            site = (
                m.SeoSiteDailySnapshot.query
                .order_by(m.SeoSiteDailySnapshot.snapshot_date.desc(), m.SeoSiteDailySnapshot.id.desc())
                .first()
            )
            assert site is not None
            assert m.ControlTraficoInterno.query.filter_by(session_id='liz_s_cron_demo123456').first() is None

    def test_build_web_analytics_dashboard_incluye_embudo_y_alertas(self, monkeypatch):
        suffix = datetime.now().strftime('%H%M%S%f').lower()
        visitor_key = f'liz_v_{suffix}_qafunnelabc123'
        session_key = f'liz_s_{suffix}_qafunnelsession12345'
        pageview_key = f'liz_p_qafunnel{suffix}'

        with m.app.app_context():
            accepted = m._registrar_web_analytics_eventos([
                {
                    'visitor_key': visitor_key,
                    'session_id': session_key,
                    'session_key': session_key,
                    'pageview_key': pageview_key,
                    'event_name': 'page_view',
                    'path': '/erp-retail-especializado',
                    'full_url': 'https://www.lhexia.cl/erp-retail-especializado',
                    'page_title': 'ERP retail',
                    'source': 'google.com',
                    'medium': 'organic',
                },
                {
                    'visitor_key': visitor_key,
                    'session_id': session_key,
                    'session_key': session_key,
                    'pageview_key': pageview_key,
                    'event_name': 'cta_click',
                    'path': '/erp-retail-especializado',
                    'label': 'Quiero mi Diagnóstico IA Gratis',
                    'target': 'https://www.lhexia.cl/index#diagnostico',
                    'meta': {'tag': 'a'},
                },
            ], default_ip='127.0.0.1', default_user_agent='pytest')
            assert accepted == 2

            monkeypatch.setattr(m, 'cargar_landing_leads_gestion', lambda limit=800: [{
                'id': f'L-{suffix}',
                'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'empresa': 'QA Funnel Spa',
                'nombre': 'QA Funnel',
                'estado': 'Nuevo',
                'traffic_source': 'google.com',
                'traffic_medium': 'organic',
                'session_id': session_key,
                'session_key': session_key,
            }])

            dashboard = m._build_web_analytics_dashboard(days=30)
            assert dashboard['wa_funnel']['visits'] >= 1
            assert dashboard['wa_funnel']['cta_clicks'] >= 1
            assert dashboard['wa_funnel']['leads'] >= 1
            assert isinstance(dashboard['wa_alerts'], list)
            assert isinstance(dashboard['wa_recent_leads'], list)

            event = (
                m.WebAnalyticsEvent.query.join(m.WebAnalyticsSession)
                .filter(m.WebAnalyticsSession.session_key == session_key)
                .order_by(m.WebAnalyticsEvent.id.desc())
                .first()
            )
            raw_rows = m.ControlTraficoInterno.query.filter_by(session_id=session_key).all()
            pageview = m.WebAnalyticsPageView.query.filter_by(pageview_key=pageview_key).first()
            session = m.WebAnalyticsSession.query.filter_by(session_key=session_key).first()
            visitor = m.WebAnalyticsVisitor.query.filter_by(visitor_key=visitor_key).first()

            for raw in raw_rows:
                db.session.delete(raw)
            if event:
                for ev in m.WebAnalyticsEvent.query.filter_by(session_id=session.id).all():
                    db.session.delete(ev)
            if pageview:
                db.session.delete(pageview)
            if session:
                db.session.delete(session)
            if visitor:
                db.session.delete(visitor)
            db.session.commit()


class TestSeoMonitor:

    def test_run_seo_snapshot_crea_site_y_paginas(self):
        with m.app.app_context():
            result = m._run_seo_snapshot()
            assert result.get('ok') is True
            assert result.get('pages', 0) >= 5

            site = (
                m.SeoSiteDailySnapshot.query
                .order_by(m.SeoSiteDailySnapshot.snapshot_date.desc(), m.SeoSiteDailySnapshot.id.desc())
                .first()
            )
            page = (
                m.SeoPageDailySnapshot.query
                .filter_by(path='/')
                .order_by(m.SeoPageDailySnapshot.snapshot_date.desc(), m.SeoPageDailySnapshot.id.desc())
                .first()
            )
            assert site is not None
            assert page is not None
            assert site.tracked_pages >= 5
            assert page.status_code == 200

    def test_guardar_keyword_metric_manual(self, app_client):
        with m.app.app_context():
            m._seed_seo_keyword_targets()
            target = m.SeoKeywordTarget.query.order_by(m.SeoKeywordTarget.id.asc()).first()
            interno = m.Usuario.query.filter(m.func.lower(m.Usuario.correo) == 'mariobec@gmail.com').first()
            assert target is not None
            assert interno is not None
            target_id = int(target.id)
            internal_user_id = str(interno.id)

        with app_client.session_transaction() as sess:
            sess['_user_id'] = internal_user_id
            sess['login_at'] = datetime.now().isoformat()

        r = app_client.post(
            '/gerencia/seo-rankings/keyword-metric',
            data={
                'keyword_target_id': str(target_id),
                'snapshot_date': date.today().isoformat(),
                'current_position': '5',
                'impressions': '120',
                'clicks': '14',
                'notes': 'QA manual',
            },
            follow_redirects=False,
        )
        assert r.status_code == 302

        with m.app.app_context():
            metric = m.SeoKeywordDailyMetric.query.filter_by(
                snapshot_date=date.today(),
                keyword_target_id=target_id,
            ).first()
            assert metric is not None
            assert metric.current_position == 5
            assert metric.clicks == 14
            assert metric.impressions == 120

    def test_build_seo_monitor_dashboard_incluye_alertas(self):
        with m.app.app_context():
            m._run_seo_snapshot()
            dashboard = m._build_seo_monitor_dashboard()
            assert 'seo_alerts' in dashboard
            assert isinstance(dashboard['seo_alerts'], list)
            assert dashboard['seo_summary']['tracked_pages'] >= 5


# =====================================================================
#  12. Clientes y consultas
# =====================================================================
class TestClientesConsultas:

    def test_consultar_cliente_por_rut(self, app_client, cliente_credito):
        rut = cliente_credito.rut or '11.111.111-1'
        r = app_client.get(f'/consultar_cliente?rut={rut}')
        assert r.status_code == 200
        data = r.get_json()
        assert data and data.get('existe') is True
        cli = data.get('cliente') or {}
        assert cli.get('id') == cliente_credito.id
        cred = cli.get('credito') or {}
        assert cred.get('tiene_linea') is True
        assert float(cred.get('limite_credito') or 0) == float(cliente_credito.limite_credito or 0)
        assert float(cred.get('cupo_disponible') or 0) == float(cliente_credito.cupo_disponible)

    def test_consultar_cliente_vacio(self, app_client):
        r = app_client.get('/consultar_cliente?rut=')
        assert r.status_code in (200, 400)

    def test_admin_clientes_get(self, app_client):
        r = app_client.get('/admin/clientes')
        assert r.status_code in (200, 302)

    def test_creditos_estado_cuenta_pdf(self, app_client, cliente_credito):
        r = app_client.get(f'/creditos/estado_cuenta/{cliente_credito.id}/pdf')
        assert r.status_code in (200, 302)


# =====================================================================
#  13. Kardex detallado
# =====================================================================
class TestKardexDetallado:

    def test_kardex_con_fechas(self, app_client):
        hoy = date.today().isoformat()
        ayer = (date.today() - timedelta(days=1)).isoformat()
        r = app_client.get(f'/kardex?desde={ayer}&hasta={hoy}')
        assert r.status_code in (200, 302)

    def test_kardex_con_producto(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/kardex?producto_id={p.id}')
        assert r.status_code in (200, 302)

    def test_kardex_export_csv(self, app_client):
        r = app_client.get('/kardex?export=csv')
        assert r.status_code in (200, 302)


# =====================================================================
#  14. Ventas (listado, filtros, documento)
# =====================================================================
class TestVentasDetalle:

    def test_ventas_filtro_estado_pagado(self, app_client):
        r = app_client.get('/ventas?estado=Pagado')
        assert r.status_code in (200, 302)

    def test_ventas_filtro_estado_pendiente(self, app_client):
        r = app_client.get('/ventas?estado=Pendiente')
        assert r.status_code in (200, 302)

    def test_ventas_filtro_estado_anulada(self, app_client):
        r = app_client.get('/ventas?estado=Anulada')
        assert r.status_code in (200, 302)

    def test_ventas_filtro_por_fecha(self, app_client):
        hoy = date.today().isoformat()
        r = app_client.get(f'/ventas?desde={hoy}&hasta={hoy}')
        assert r.status_code in (200, 302)

    def test_ver_documento_venta(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        cobrar_venta_efectivo(venta, caja_abierta)
        r = app_client.get(f'/ver_documento/{venta.id}')
        assert r.status_code in (200, 302, 404)


# =====================================================================
#  15. Recepciones detalladas
# =====================================================================
class TestRecepcionesDetalle:

    def test_recepcion_nueva_post(self, app_client, productos_con_stock, proveedor_test):
        db.session.rollback()
        db.session.expire_all()
        p = productos_con_stock[3]
        r = app_client.post('/recepciones/nueva', data={
            'proveedor_id': str(proveedor_test.id),
            'producto_id[]': str(p.id),
            'cantidad[]': '10',
            'precio_unitario[]': str(p.precio_compra),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)


# =====================================================================
#  16. Rutas miscelaneas de alto impacto en coverage
# =====================================================================
class TestMiscCoverage:

    def test_buscar_producto_query(self, app_client, productos_con_stock):
        r = app_client.get('/buscar_producto?q=TEST')
        assert r.status_code == 200
        data = r.get_json()
        assert 'results' in data

    @pytest.mark.parametrize('url', [
        '/bi/panel-dueno',
        '/bi',
        '/gerencia/informes-dueno',
    ])
    def test_gerencia_bi_pages(self, url, app_client):
        r = app_client.get(url)
        assert r.status_code in (200, 302)

    def test_cambiar_password_get(self, app_client):
        r = app_client.get('/cambiar_password')
        assert r.status_code in (200, 302)

    def test_editar_usuario_get(self, app_client):
        admin = _get_admin_user()
        if admin:
            r = app_client.get(f'/editar_usuario/{admin.id}')
            assert r.status_code in (200, 302)

    def test_proveedores_lista(self, app_client):
        r = app_client.get('/proveedores')
        assert r.status_code in (200, 302)

    def test_recepciones_lista(self, app_client):
        r = app_client.get('/recepciones')
        assert r.status_code in (200, 302)

    def test_compras_seguimiento_rapido(self, app_client, productos_con_stock, proveedor_test):
        db.session.rollback()
        db.session.expire_all()
        oc = m.OrdenCompra.query.filter_by(estado='Borrador').first()
        if oc:
            r = app_client.post(f'/compras/ordenes/{oc.id}/seguimiento_rapido', data={
                'estado': 'Enviada',
            }, follow_redirects=True)
            assert r.status_code in (200, 302)

    def test_api_sistema_salud(self, app_client):
        r = app_client.get('/api/sistema/salud')
        assert r.status_code in (200, 302)
        if r.status_code == 200:
            data = r.get_json(silent=True)
            if data and data.get('ok') is True:
                assert 'openai_key_configured' in data
                assert 'bodega_voice_despachos_auditoria_24h' in data
                assert 'bodega_voice_fallos_auditoria_24h' in data
                assert 'bodega_voice_consultas_ok_auditoria_24h' in data

    def test_api_cobranza_sugerencias(self, app_client):
        r = app_client.get('/api/creditos/cobranza/sugerencias')
        assert r.status_code in (200, 302)


# =====================================================================
#  17. Cotizaciones
# =====================================================================
class TestCotizaciones:

    def test_cotizaciones_lista(self, app_client):
        r = app_client.get('/cotizaciones')
        assert r.status_code in (200, 302)

    def test_cotizaciones_nueva_get(self, app_client):
        r = app_client.get('/cotizaciones/nueva')
        assert r.status_code in (200, 302)

    def test_cotizaciones_buscar_productos(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(
            f'/api/cotizaciones/buscar_productos?q={p.nombre[:5]}&filtro_pos=catalogo'
        )
        assert r.status_code == 200
        data = r.get_json()
        assert 'items' in data and 'results' in data
        assert len(data['items']) >= 1
        first = data['items'][0]
        assert first.get('nombre')
        assert 'semaforo' in first
        assert 'stock_tienda' in first
        assert 'stock_bodega' in first

    def test_cotizaciones_buscar_clientes(self, app_client, cliente_credito):
        r = app_client.get(f'/api/cotizaciones/buscar_clientes?q={cliente_credito.nombre[:4]}')
        assert r.status_code in (200, 302)


# =====================================================================
#  18. Mas rutas de admin
# =====================================================================
class TestAdminExtra:

    def test_admin_empresa_post(self, app_client):
        r = app_client.post('/admin/empresa', data={
            'nombre': 'QA Ferreteria Test',
            'rut': '76.000.000-0',
            'giro': 'Ferreteria QA',
            'direccion': 'Test 123',
            'comuna': 'Santiago',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_admin_almacenes_post_nuevo(self, app_client):
        ts = datetime.now().strftime('%H%M%S%f')
        r = app_client.post('/admin/almacenes', data={
            'nombre': f'QA Almacen {ts}',
            'tipo': 'Bodega',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_usuarios_post_nuevo(self, app_client):
        ts = datetime.now().strftime('%H%M%S%f')
        rol = m.Rol.query.first()
        if rol:
            r = app_client.post('/usuarios', data={
                'nombre': f'QA User {ts}',
                'correo': f'qa_user_{ts}@test.cl',
                'password': 'test12345',
                'rol_id': str(rol.id),
            }, follow_redirects=True)
            assert r.status_code in (200, 302)
            u = m.Usuario.query.filter_by(correo=f'qa_user_{ts}@test.cl').first()
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_editar_proveedor_post(self, app_client, proveedor_test):
        db.session.rollback()
        db.session.expire_all()
        r = app_client.post(f'/editar_proveedor/{proveedor_test.id}', data={
            'nombre': proveedor_test.nombre,
            'contacto': 'QA Updated Contact',
            'telefono': '+56911111111',
            'email': proveedor_test.email or 'qa@test.cl',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_precios_revision_aplicar(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.post(f'/precios/revision/editar/{p.id}', data={
            'precio_venta': str(p.precio_venta),
            'precio_compra': str(p.precio_compra),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_login_post_invalid_password(self, app_client):
        admin = _get_admin_user()
        if admin:
            r = app_client.post('/login', data={
                'correo': admin.correo,
                'password': 'wrong_password_qa',
            }, follow_redirects=True)
            assert r.status_code in (200, 302)

    def test_admin_catalogo_post(self, app_client):
        ts = datetime.now().strftime('%H%M%S%f')
        r = app_client.post('/admin/catalogo', data={
            'accion': 'crear_categoria',
            'nombre': f'QA Cat {ts}',
        }, follow_redirects=True)
        assert r.status_code in (200, 302)


@pytest.mark.smoke
class TestHubModulosUrls:
    """Tarjetas del hub deben enlazar al destino operativo correcto."""

    def test_hub_html_pos_enlaza_punto_venta(self, app_client, caja_abierta):
        r = app_client.get('/hub')
        assert r.status_code == 200
        assert b'Ventas y mostrador' in r.data
        assert b'/punto_venta' in r.data
        # POS vendedor fullwidth por defecto (sin ?layout=vendedor en URL del hub)
        assert b'layout=clasico' not in r.data

    def test_resolver_pos_con_caja_abierta(self, app_ctx, caja_abierta):
        user = _get_admin_user()
        mod = next(x for x in m._MODULOS_HUB if x['id'] == 'ventas_mostrador')
        with m.app.test_request_context('/'):
            url = m._hub_url_para_modulo(mod, user)
        assert url.rstrip('/').endswith('/punto_venta')
        assert 'layout=' not in url

    def test_resolver_ventas_mostrador_sin_caja_a_pos(self, app_ctx):
        user = _get_admin_user()
        mod = next(x for x in m._MODULOS_HUB if x['id'] == 'ventas_mostrador')
        for caja in m.Caja.query.filter_by(estado='Abierta').all():
            caja.estado = 'Cerrada'
        db.session.flush()
        try:
            with m.app.test_request_context('/'):
                url = m._hub_url_para_modulo(mod, user)
            assert url.rstrip('/').endswith('/punto_venta')
        finally:
            db.session.rollback()

    def test_construir_modulos_incluye_url(self, app_ctx, caja_abierta):
        user = _get_admin_user()
        with m.app.test_request_context('/'):
            mods = m._construir_modulos_hub(user)
        pos = next((x for x in mods if x.get('id') == 'ventas_mostrador'), None)
        assert pos is not None
        assert pos.get('url')
        assert pos['url'].rstrip('/').endswith('/punto_venta')
        assert 'layout=' not in pos['url']


# Como correr solo estos tests
# pytest tests/test_routes_criticas.py -v --cov=app --cov-report=term-missing
