"""Smoke — Enrolador Bodega tablet + instalador QR."""
import pytest


@pytest.mark.smoke
class TestBodegaEnroladorTablet:
    def test_bodega_enrolador_setup(self, app_client):
        r = app_client.get('/bodega/enrolador')
        assert r.status_code == 200
        assert b'Instalador Enrolador Bodega' in r.data
        assert b'/inventario/enrolamiento/tablet' in r.data

    def test_enrolamiento_tablet(self, app_client):
        r = app_client.get('/inventario/enrolamiento/tablet')
        assert r.status_code == 200
        assert b'Enrolador bodega' in r.data or b'enrol-tablet-kiosk' in r.data

    def test_bodega_enrolador_manifest(self, app_client):
        r = app_client.get('/bodega-enrolador/manifest.webmanifest')
        assert r.status_code == 200
        data = r.get_json()
        assert data['short_name'] == 'Enrolador'
        assert '/inventario/enrolamiento/tablet' in data['start_url']

    def test_bodega_enrolador_sw(self, app_client):
        r = app_client.get('/bodega-enrolador/sw.js')
        assert r.status_code == 200
        assert b'serviceWorker' in r.data or b'fetch' in r.data

    def test_lan_url_resolver(self):
        from services.bodega_enrolador_service import detectar_ipv4_lan, resolver_base_lan

        class _Req:
            host = '127.0.0.1:5000'
            url_root = 'http://127.0.0.1:5000/'

        base = resolver_base_lan(_Req())
        assert base.startswith('http://')
        assert ':5000' in base
        ip = detectar_ipv4_lan()
        if ip:
            assert ip.count('.') == 3
