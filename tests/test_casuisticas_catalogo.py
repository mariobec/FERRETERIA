"""
Casuísticas documentadas en docs/CASUISTICAS_PRUEBAS.md — tests reproducibles por ID.
"""
import pytest

import app as m
from tests.conftest import crear_venta_pendiente
from tests.test_routes_criticas import _ensure_caja_abierta


def _agregar_linea_pos(app_client, codigo_barra):
    return app_client.post(
        '/api/pos/escanear-agregar',
        json={'codigo': codigo_barra},
        content_type='application/json',
    )


@pytest.mark.smoke
class TestCasuisticasPOS:
    """POS-005 / POS-006 — RUT opcional al emitir vale."""

    def test_pos_005_emitir_sin_rut_opcional(self, app_client, productos_con_stock, monkeypatch):
        """POS-005: sin RUT y flag off → emite como cliente final."""
        _ensure_caja_abierta()
        cfg = m.obtener_config_empresa()
        cfg = {**cfg, 'pos_rut_obligatorio': '0'}
        monkeypatch.setattr(m, 'obtener_config_empresa', lambda: cfg)

        app_client.get('/punto_venta')
        app_client.post(
            '/api/pos/rut-obligatorio-toggle',
            json={'obligatorio': False},
            content_type='application/json',
        )
        p = productos_con_stock[0]
        r = _agregar_linea_pos(app_client, p.codigo_barra)
        if r.status_code == 409 and r.get_json().get('error') == 'en_vale_pendiente':
            pytest.skip('Producto bloqueado por vale pendiente previo en QA')
        assert r.status_code == 200, r.get_json()

        rv = app_client.post(
            '/finalizar_venta',
            data={
                'cliente_final': '0',
                'cliente_rut': '',
                'pos_exigir_rut': '0',
                'punto_retiro': 'Tienda',
            },
            follow_redirects=False,
        )
        assert rv.status_code in (200, 302)
        assert b'punto_venta' in rv.data.lower() or rv.status_code == 302

    def test_pos_010_toggle_rut_en_pos(self, app_client):
        """POS-010: vendedora desactiva RUT obligatorio en sesión."""
        _ensure_caja_abierta()
        app_client.get('/punto_venta')
        r_on = app_client.post(
            '/api/pos/rut-obligatorio-toggle',
            json={'obligatorio': True},
            content_type='application/json',
        )
        assert r_on.status_code == 200
        assert r_on.get_json().get('obligatorio') is True
        r_off = app_client.post(
            '/api/pos/rut-obligatorio-toggle',
            json={'obligatorio': False},
            content_type='application/json',
        )
        assert r_off.status_code == 200
        assert r_off.get_json().get('obligatorio') is False
        with app_client.session_transaction() as sess:
            assert sess.get(m.POS_RUT_OBLIGATORIO_SESSION) is False

    def test_pos_006_emitir_exige_rut(self, app_client, productos_con_stock, monkeypatch):
        """POS-006: flag on + sin RUT → no emite."""
        _ensure_caja_abierta()
        cfg = {**m.obtener_config_empresa(), 'pos_rut_obligatorio': '1'}
        monkeypatch.setattr(m, 'obtener_config_empresa', lambda: cfg)
        app_client.post(
            '/api/pos/rut-obligatorio-toggle',
            json={'obligatorio': True},
            content_type='application/json',
        )

        app_client.get('/punto_venta')
        p = productos_con_stock[1]
        r_line = _agregar_linea_pos(app_client, p.codigo_barra)
        if r_line.status_code == 409 and r_line.get_json().get('error') == 'en_vale_pendiente':
            pytest.skip('Producto bloqueado por vale pendiente previo en QA')

        rv = app_client.post(
            '/finalizar_venta',
            data={
                'cliente_final': '0',
                'cliente_rut': '',
                'pos_exigir_rut': '1',
                'punto_retiro': 'Tienda',
            },
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)
        loc = (rv.location or '').lower()
        assert 'punto_venta' in loc
        with app_client.session_transaction() as sess:
            flashes = [str(msg).lower() for _cat, msg in (sess.get('_flashes') or [])]
        assert any('rut' in f for f in flashes)

    def test_pos_003_escanear_tras_vale_pendiente(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        """POS-003 — alias documentado (implementación en test_pos_live_wall)."""
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
        r = _agregar_linea_pos(app_client, p.codigo_barra)
        assert r.status_code == 409
        assert r.get_json().get('error') == 'en_vale_pendiente'
