"""
ERP LhexIA -- Tests de rutas HTTP (Flask test_client).

Objetivo: cubrir las rutas criticas GET/POST para subir coverage de 17% a 35-45%.
No requiere autenticacion real (LOGIN_DISABLED=True en fixture app_client).

Ejecucion:
    pytest tests/test_routes.py -v
    pytest tests/test_routes.py -v -m smoke
    pytest tests/test_routes.py -v --cov=app --cov-report=term-missing
"""
import json
from datetime import datetime

import pytest

import app as m

db = m.db


# ── GET routes (paginas principales) ────────────────────────────────
@pytest.mark.smoke
class TestRutasPublicas:

    def test_healthz(self, app_client):
        r = app_client.get('/healthz')
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'ok'

    def test_login_page(self, app_client):
        r = app_client.get('/login')
        assert r.status_code in (200, 302)

    def test_index_redirect(self, app_client):
        r = app_client.get('/')
        assert r.status_code in (200, 302)


@pytest.mark.smoke
class TestRutasDashboard:

    def test_inicio(self, app_client):
        r = app_client.get('/inicio')
        assert r.status_code in (200, 302)

    def test_catalogo(self, app_client):
        r = app_client.get('/catalogo')
        assert r.status_code in (200, 302)

    def test_consulta_stock(self, app_client):
        r = app_client.get('/consulta-stock')
        assert r.status_code in (200, 302)


@pytest.mark.smoke
class TestRutasProductos:

    def test_lista_productos(self, app_client):
        r = app_client.get('/productos')
        assert r.status_code in (200, 302)

    def test_productos_filtro_activos(self, app_client):
        r = app_client.get('/productos/filtro/activos')
        assert r.status_code in (200, 302)

    def test_productos_filtro_inactivos(self, app_client):
        r = app_client.get('/productos/filtro/inactivos')
        assert r.status_code in (200, 302)

    def test_stock_critico(self, app_client):
        r = app_client.get('/stock/critico')
        assert r.status_code in (200, 302)

    def test_productos_api_catalogo_subs(self, app_client):
        r = app_client.get('/productos/api/catalogo_subs')
        assert r.status_code in (200, 302)


class TestRutasVentas:

    def test_lista_ventas(self, app_client):
        r = app_client.get('/ventas')
        assert r.status_code in (200, 302)

    def test_ventas_con_filtros(self, app_client):
        r = app_client.get('/ventas?estado=Pagado&page=1')
        assert r.status_code in (200, 302)


class TestRutasPOS:

    def test_punto_venta_get(self, app_client):
        r = app_client.get('/punto_venta')
        assert r.status_code in (200, 302)


class TestRutasCaja:

    def test_abrir_caja_get(self, app_client):
        r = app_client.get('/abrir_caja')
        assert r.status_code in (200, 302)

    def test_cerrar_caja_get(self, app_client):
        r = app_client.get('/cerrar_caja')
        assert r.status_code in (200, 302)

    def test_movimiento_caja_get(self, app_client):
        r = app_client.get('/movimiento_caja')
        assert r.status_code in (200, 302)


class TestRutasKardex:

    def test_kardex_sin_filtro(self, app_client):
        r = app_client.get('/kardex')
        assert r.status_code in (200, 302)

    def test_kardex_con_producto(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/kardex?producto_id={p.id}')
        assert r.status_code in (200, 302)


class TestRutasCompras:

    def test_ordenes_compra(self, app_client):
        r = app_client.get('/compras/ordenes')
        assert r.status_code in (200, 302)

    def test_ordenes_nueva_get(self, app_client):
        r = app_client.get('/compras/ordenes/nueva')
        assert r.status_code in (200, 302)


class TestRutasRecepciones:

    def test_recepciones_lista(self, app_client):
        r = app_client.get('/recepciones')
        assert r.status_code in (200, 302)

    def test_recepciones_costos(self, app_client):
        r = app_client.get('/recepciones/costos')
        assert r.status_code in (200, 302)


class TestRutasProveedores:

    def test_proveedores_lista(self, app_client):
        r = app_client.get('/proveedores')
        assert r.status_code in (200, 302)


class TestRutasCreditos:

    def test_creditos_lista(self, app_client):
        r = app_client.get('/creditos')
        assert r.status_code in (200, 302)


class TestRutasAdmin:

    def test_usuarios_lista(self, app_client):
        r = app_client.get('/usuarios')
        assert r.status_code in (200, 302)

    def test_admin_empresa(self, app_client):
        r = app_client.get('/admin/empresa')
        assert r.status_code in (200, 302)

    def test_admin_almacenes(self, app_client):
        r = app_client.get('/admin/almacenes')
        assert r.status_code in (200, 302)

    def test_admin_clientes(self, app_client):
        r = app_client.get('/admin/clientes')
        assert r.status_code in (200, 302)

    def test_admin_roles_permisos(self, app_client):
        r = app_client.get('/admin/roles-permisos')
        assert r.status_code in (200, 302)

    def test_admin_unidades(self, app_client):
        r = app_client.get('/admin/unidades')
        assert r.status_code in (200, 302)

    def test_admin_catalogo(self, app_client):
        r = app_client.get('/admin/catalogo')
        assert r.status_code in (200, 302)


class TestRutasBI:

    def test_bi_dashboard(self, app_client):
        r = app_client.get('/bi')
        assert r.status_code in (200, 302)

    def test_bi_panel_dueno(self, app_client):
        r = app_client.get('/bi/panel-dueno')
        assert r.status_code in (200, 302)


class TestRutasInventario:

    def test_inventario_dashboard_premium(self, app_client):
        r = app_client.get('/inventario/dashboard-premium')
        assert r.status_code in (200, 302)

    def test_inventario_salud(self, app_client):
        r = app_client.get('/inventario/salud')
        assert r.status_code in (200, 302)

    def test_auditorias(self, app_client):
        r = app_client.get('/ver_auditorias')
        assert r.status_code in (200, 302)

    def test_precios_revision(self, app_client):
        r = app_client.get('/precios/revision')
        assert r.status_code in (200, 302)


class TestRutasMisc:

    def test_ayuda(self, app_client):
        r = app_client.get('/ayuda')
        assert r.status_code in (200, 302)

    def test_consultar_cliente(self, app_client):
        r = app_client.get('/consultar_cliente?rut=11.111.111-1')
        assert r.status_code in (200, 302, 400)


# ── API endpoints ───────────────────────────────────────────────────
@pytest.mark.smoke
class TestAPIs:

    def test_buscar_producto_api(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/buscar_producto?q={p.nombre[:4]}')
        assert r.status_code == 200
        data = r.get_json()
        assert 'results' in data

    def test_buscar_producto_api_corto(self, app_client):
        r = app_client.get('/buscar_producto?q=x')
        assert r.status_code == 200
        data = r.get_json()
        assert data['results'] == []

    def test_buscar_producto_por_codigo(self, app_client, productos_con_stock):
        p = productos_con_stock[0]
        r = app_client.get(f'/api/buscar_producto/{p.codigo_barra}')
        assert r.status_code in (200, 404)


# ── POST con validaciones ──────────────────────────────────────────
class TestPOSTRoutes:

    def test_login_post_invalido(self, app_client):
        r = app_client.post('/login', data={
            'correo': 'noexiste@test.cl', 'password': 'mala123'
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_guardar_producto_minimo(self, app_client):
        from sqlalchemy import text as sa_text
        ts = datetime.now().strftime('%H%M%S%f')
        r = app_client.post('/guardar_producto', data={
            'nombre': f'QA Minimal {ts}', 'codigo': f'QAMIN-{ts}',
            'p_venta': '100', 'stock': '0',
            'p_compra': '50', 'unidad': 'Unidad', 'categoria': '', 'subcategoria': '',
        }, follow_redirects=True)
        assert r.status_code in (200, 302, 400)
        prod = m.Producto.query.filter_by(codigo_barra=f'QAMIN-{ts}').first()
        if prod:
            pid = prod.id
            db.session.execute(sa_text("DELETE FROM stock_por_almacen WHERE id_producto = :p"), {'p': pid})
            db.session.execute(sa_text("DELETE FROM movimientos_inventario WHERE id_producto = :p"), {'p': pid})
            db.session.execute(sa_text("DELETE FROM productos WHERE id = :p"), {'p': pid})
            db.session.commit()

    def test_guardar_proveedor_sin_datos(self, app_client):
        r = app_client.post('/guardar_proveedor', data={
            'nombre': '', 'contacto': '', 'telefono': ''
        }, follow_redirects=True)
        assert r.status_code in (200, 302, 400)

    def test_toggle_producto_inexistente(self, app_client):
        r = app_client.post('/toggle_producto/999999', follow_redirects=True)
        assert r.status_code in (200, 302, 404)

    def test_abrir_caja_post(self, app_client):
        r = app_client.post('/abrir_caja', data={
            'monto_inicial': '50000'
        }, follow_redirects=True)
        assert r.status_code in (200, 302)


# ── Rutas con export ────────────────────────────────────────────────
class TestExports:

    def test_productos_exportar_excel(self, app_client):
        r = app_client.get('/productos/exportar_excel')
        assert r.status_code in (200, 302)

    def test_descargar_plantilla(self, app_client):
        r = app_client.get('/descargar_plantilla_productos')
        assert r.status_code in (200, 302)

    def test_bi_export_csv(self, app_client):
        r = app_client.get('/bi/export.csv')
        assert r.status_code in (200, 302)


@pytest.mark.smoke
class TestFacturacionElectronicaAdminApi:

    def test_emitir_prueba_boleta_get(self, app_client):
        r = app_client.get('/api/admin/facturacion/emitir-prueba?dte_tipo=39')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('dte_tipo') == 39
        assert data.get('xml_valido') is True
        assert '<DTE' in (data.get('xml_utf8') or '')

    def test_emitir_prueba_factura_post(self, app_client):
        r = app_client.post(
            '/api/admin/facturacion/emitir-prueba',
            data=json.dumps({'dte_tipo': 33, 'folio': 7}),
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('dte_tipo') == 33
        assert data.get('folio') == 7
