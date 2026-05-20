"""Live Wall: snapshot staff/cliente y token firmado (POS segundo monitor / TV).

Los tests autenticados van primero. Para rutas anónimas se usa
`test_client(use_cookies=False)` y no arrastrar cookies del `app_client`.
El snapshot staff exige `session['_user_id']` además de `current_user`.
"""
import pytest

import app as m
from tests.conftest import crear_venta_pendiente
from tests.test_routes_criticas import _ensure_caja_abierta


@pytest.mark.smoke
class TestPosLiveWall:
    def test_staff_html_y_snapshot_kpis(self, app_client):
        _ensure_caja_abierta()
        r = app_client.get('/pos/live-wall/staff', follow_redirects=True)
        assert r.status_code == 200
        assert b'Live Wall' in r.data
        rs = app_client.get('/api/pos/live-wall/snapshot')
        assert rs.status_code == 200
        j = rs.get_json()
        assert j.get('ok') is True
        assert j.get('modo') == 'staff'
        assert 'tienda_kpis' in j
        tk = j['tienda_kpis']
        assert 'ventas_hoy_monto' in tk
        assert 'ventas_hoy_documentos' in tk
        assert 'bodega_retiro_cola' in tk

    def test_cliente_snapshot_con_token(self, app_client):
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        rs = app_client.get('/api/pos/live-wall/snapshot')
        assert rs.status_code == 200
        vid = rs.get_json().get('venta_id')
        if not vid:
            pytest.skip('Sin vale Abierta para el usuario de prueba')
        tok = m.pos_live_wall_token_create(vid)
        assert tok
        anon = m.app.test_client()
        rc = anon.get('/api/pos/live-wall/snapshot', query_string={'token': tok})
        assert rc.status_code == 200
        cj = rc.get_json()
        assert cj.get('modo') == 'cliente'
        assert 'tienda_kpis' not in cj
        if cj.get('estado') == 'abierta':
            assert 'mensaje_cliente' not in cj
            assert 'recomendaciones' in cj

    def test_snapshot_sin_auth_401(self):
        c = m.app.test_client(use_cookies=False)
        r = c.get('/api/pos/live-wall/snapshot')
        assert r.status_code == 401
        assert r.get_json().get('error') == 'no_auth'

    def test_snapshot_token_invalido_403(self):
        c = m.app.test_client(use_cookies=False)
        r = c.get('/api/pos/live-wall/snapshot?token=__invalid__')
        assert r.status_code == 403
        assert r.get_json().get('error') == 'token_invalido'

    def test_command_deck_html(self, app_client):
        _ensure_caja_abierta()
        r = app_client.get('/pos/command-deck', follow_redirects=True)
        assert r.status_code == 200
        assert b'Command Deck' in r.data
        assert b'pos-command-deck.js' in r.data
        assert b'posBarcodeWedge' in r.data

    def test_experience_wall_alias(self, app_client):
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        rs = app_client.get('/api/pos/live-wall/snapshot')
        vid = rs.get_json().get('venta_id')
        if not vid:
            pytest.skip('Sin vale Abierta para el usuario de prueba')
        tok = m.pos_live_wall_token_create(vid)
        anon = m.app.test_client()
        r = anon.get('/pos/experience-wall', query_string={'token': tok})
        assert r.status_code == 200

    def test_token_legacy_sigue_nueva_venta_abierta(self, app_client):
        """Tras emitir vale, la TV con token viejo debe mostrar el nuevo carrito Abierta."""
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        rs = app_client.get('/api/pos/live-wall/snapshot')
        v1 = m.Venta.query.get(rs.get_json().get('venta_id'))
        if not v1:
            pytest.skip('Sin vale Abierta para el usuario de prueba')
        tok_legacy = m.pos_live_wall_token_create(v1.id)
        v1.estado = 'Pendiente'
        v2 = m.Venta(
            usuario=v1.usuario,
            estado='Abierta',
            monto_total=0,
            caja_id=v1.caja_id,
            fecha=m.db.func.current_timestamp(),
        )
        m.db.session.add(v2)
        m.db.session.commit()
        anon = m.app.test_client()
        rc = anon.get('/api/pos/live-wall/snapshot', query_string={'token': tok_legacy})
        assert rc.status_code == 200
        cj = rc.get_json()
        assert cj.get('ok') is True
        assert cj.get('venta_id') == v2.id
        assert cj.get('estado') == 'abierta'
        assert cj.get('nuevo_token')

    def test_vincular_cliente_y_snapshot_vitrina(self, app_client, cliente_credito):
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        rut = cliente_credito.rut
        rv = app_client.post(
            '/api/pos/vincular-cliente',
            json={'cliente_rut': rut},
            content_type='application/json',
        )
        assert rv.status_code == 200
        j = rv.get_json()
        assert j.get('ok') is True
        cv = j.get('cliente_vitrina')
        assert cv and cv.get('nombre_publico')
        assert 'rut' not in cv

        rs = app_client.get('/api/pos/live-wall/snapshot')
        sk = rs.get_json()
        assert sk.get('cliente_vitrina', {}).get('nombre_publico')

        vid = sk.get('venta_id')
        assert vid
        tok = m.pos_live_wall_token_create(vid)
        anon = m.app.test_client()
        rc = anon.get('/api/pos/live-wall/snapshot', query_string={'token': tok})
        assert rc.status_code == 200
        cj = rc.get_json()
        assert cj.get('cliente_vitrina', {}).get('nombre_publico')

    def test_vincular_registrar_cliente_nuevo(self, app_client):
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        rut = '55.555.555-5'
        prev = m.Cliente.query.filter_by(rut=rut).first()
        if prev:
            m.Venta.query.filter_by(cliente_id=prev.id).update({'cliente_id': None})
            m.db.session.delete(prev)
            m.db.session.commit()
        rv = app_client.post(
            '/api/pos/vincular-cliente',
            json={
                'cliente_rut': rut,
                'registrar': True,
                'nombre': 'QA Cliente Nuevo POS',
                'telefono': '+56911112222',
            },
            content_type='application/json',
        )
        assert rv.status_code == 200, rv.get_json()
        j = rv.get_json()
        assert j.get('ok') is True
        assert j.get('cliente', {}).get('nombre') == 'QA Cliente Nuevo POS'
        assert j.get('cliente_vitrina', {}).get('nombre_publico')
        cli = m.Cliente.query.filter_by(rut=rut).first()
        assert cli is not None
        m.Venta.query.filter_by(cliente_id=cli.id).update({'cliente_id': None})
        m.db.session.delete(cli)
        m.db.session.commit()

    def test_vale_emitido_en_snapshot_tv(self, app_client, productos_con_stock):
        """Tras emitir vale, la TV cliente recibe vale_emitido para animación incrustada."""
        _ensure_caja_abierta()
        caja = m.obtener_caja_activa()
        app_client.get('/punto_venta')
        with m.app.test_request_context():
            from flask_login import login_user
            admin = m.Usuario.query.join(m.Rol).filter(
                m.Rol.nombre.in_(['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin'])
            ).first()
            if admin:
                login_user(admin)
            u = m._nombre_usuario_pos_actual()
        tok = m.pos_live_wall_token_create_station(caja.id, u)
        p = productos_con_stock[0]
        app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': p.codigo_barra},
            content_type='application/json',
        )
        rv = app_client.post(
            '/finalizar_venta',
            data={
                'cliente_final': '1',
                'punto_retiro': 'Tienda',
                'pos_exigir_rut': '1',
            },
            follow_redirects=False,
        )
        assert rv.status_code in (200, 302)
        anon = m.app.test_client()
        rc = anon.get('/api/pos/live-wall/snapshot', query_string={'token': tok})
        assert rc.status_code == 200
        cj = rc.get_json()
        ve = cj.get('vale_emitido')
        assert ve and ve.get('venta_id')
        assert ve.get('total', 0) > 0
        assert cj.get('estado') in ('sin_venta', 'abierta', 'pendiente')

    def test_token_estacion_sin_venta_abierta(self, app_client):
        _ensure_caja_abierta()
        caja = m.obtener_caja_activa()
        u = m._nombre_usuario_pos_actual()
        tok = m.pos_live_wall_token_create_station(caja.id, u)
        anon = m.app.test_client()
        rc = anon.get('/api/pos/live-wall/snapshot', query_string={'token': tok})
        assert rc.status_code == 200
        cj = rc.get_json()
        assert cj.get('estado') in ('abierta', 'sin_venta')

    def test_escanear_incrementa_misma_linea(self, app_client, productos_con_stock):
        _ensure_caja_abierta()
        p = productos_con_stock[0]
        aid = m.id_almacen_tienda()
        if aid:
            m.fijar_stock_almacen(p.id, aid, 10)
            m.db.session.commit()
        app_client.get('/punto_venta')
        codigo = p.codigo_barra
        r1 = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': codigo},
            content_type='application/json',
        )
        if r1.status_code == 409 and r1.get_json().get('error') == 'en_vale_pendiente':
            pytest.skip('Producto bloqueado por vale pendiente previo en QA')
        assert r1.status_code == 200, r1.get_json()
        j1 = r1.get_json()
        assert j1.get('ok') is True
        assert j1.get('linea_incrementada') is False
        r2 = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': codigo},
            content_type='application/json',
        )
        assert r2.status_code == 200, r2.get_json()
        j2 = r2.get_json()
        assert j2.get('ok') is True
        assert j2.get('linea_incrementada') is True
        assert j2.get('cantidad_en_vale') == 2
        vid = j2.get('venta_id')
        lineas = m.DetalleVenta.query.filter_by(id_venta=vid, id_producto=p.id).all()
        assert len(lineas) == 1
        assert lineas[0].cantidad == 2

    def test_escanear_bloquea_si_supera_stock_en_vale(self, app_client, productos_con_stock):
        _ensure_caja_abierta()
        p = productos_con_stock[3]
        aid = m.id_almacen_tienda()
        bid = m.id_almacen_bodega()
        if aid:
            m.fijar_stock_almacen(p.id, aid, 1)
        if bid:
            m.fijar_stock_almacen(p.id, bid, 0)
        if aid or bid:
            m.db.session.commit()
        app_client.get('/punto_venta')
        codigo = p.codigo_barra
        r1 = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': codigo},
            content_type='application/json',
        )
        if r1.status_code == 409 and r1.get_json().get('error') == 'en_vale_pendiente':
            pytest.skip('Producto bloqueado por vale pendiente previo en QA')
        assert r1.status_code == 200, r1.get_json()
        assert r1.get_json().get('ok') is True
        r2 = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': codigo},
            content_type='application/json',
        )
        assert r2.status_code == 409
        j2 = r2.get_json()
        assert j2.get('ok') is False
        assert j2.get('error') == 'sin_stock'
        vid = r1.get_json().get('venta_id')
        lineas = m.DetalleVenta.query.filter_by(id_venta=vid, id_producto=p.id).all()
        assert len(lineas) == 1
        assert lineas[0].cantidad == 1

    def test_escanear_avisa_si_producto_en_vale_pendiente(
        self, app_client, productos_con_stock, caja_abierta, cliente_final
    ):
        """Tras emitir un vale, no debe poder re-escanear lo mismo en venta nueva sin aviso."""
        _ensure_caja_abierta()
        p = productos_con_stock[4]
        aid = m.id_almacen_tienda()
        if aid:
            m.fijar_stock_almacen(p.id, aid, 1)
            m.db.session.commit()
        venta_pend, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        venta_pend.prioridad = 1
        m.db.session.commit()
        app_client.get('/punto_venta')
        r = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': p.codigo_barra},
            content_type='application/json',
        )
        assert r.status_code == 409, r.get_json()
        j = r.get_json()
        assert j.get('ok') is False
        assert j.get('error') == 'en_vale_pendiente'
        assert 'pendiente en caja' in (j.get('mensaje') or '').lower()
        assert 'Vale N°' in (j.get('mensaje') or '')

    def test_snapshot_total_coincide_suma_lineas_dos_productos(self, app_client, productos_con_stock):
        """TV cliente: total del JSON debe coincidir con la suma de subtotales (no monto_total stale)."""
        _ensure_caja_abierta()
        p0, p1 = productos_con_stock[2], productos_con_stock[3]
        aid = m.id_almacen_tienda()
        if aid:
            m.fijar_stock_almacen(p0.id, aid, 30)
            m.fijar_stock_almacen(p1.id, aid, 30)
            m.db.session.commit()
        app_client.get('/punto_venta')
        for p, resp in (
            (p0, 'r0'),
            (p1, 'r1'),
        ):
            r = app_client.post(
                '/api/pos/escanear-agregar',
                json={'codigo': p.codigo_barra},
                content_type='application/json',
            )
            if r.status_code == 409 and r.get_json().get('error') == 'en_vale_pendiente':
                pytest.skip('Producto bloqueado por vale pendiente previo en QA')
            assert r.status_code == 200, (resp, r.get_json())
        rs = app_client.get('/api/pos/live-wall/snapshot')
        assert rs.status_code == 200
        j = rs.get_json()
        if j.get('estado') != 'abierta' or not j.get('lineas'):
            pytest.skip('Sin vale Abierta con dos líneas')
        suma = sum(float(x.get('subtotal') or 0) for x in j['lineas'])
        assert suma > 0
        assert abs(float(j.get('total') or 0) - suma) < 1.0
        vid = j.get('venta_id')
        v = m.Venta.query.get(vid)
        assert v is not None
        v.monto_total = float(p0.precio_venta or 0) * 0.25
        m.db.session.commit()
        rs2 = app_client.get('/api/pos/live-wall/snapshot')
        j2 = rs2.get_json()
        suma2 = sum(float(x.get('subtotal') or 0) for x in (j2.get('lineas') or []))
        assert abs(float(j2.get('total') or 0) - suma2) < 1.0
        assert abs(float(j2.get('total') or 0) - suma) < 1.0
