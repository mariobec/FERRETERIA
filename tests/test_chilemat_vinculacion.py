"""Smoke — pantalla vinculación Chilemat ↔ ERP."""
import pytest


@pytest.mark.smoke
def test_chilemat_vinculacion_ruta_admin(app_client):
    r = app_client.get('/compras/chilemat/vincular', follow_redirects=False)
    assert r.status_code == 200
    assert b'Vincular cat' in r.data or b'Vincular' in r.data


@pytest.mark.smoke
def test_api_chilemat_vincular_lista(app_client):
    r = app_client.get('/api/compras/chilemat/vincular/lista?page=1&per_page=5')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'items' in data


@pytest.mark.smoke
def test_api_chilemat_vincular_buscar_erp_corta(app_client):
    r = app_client.get('/api/compras/chilemat/vincular/buscar-erp?q=A')
    assert r.status_code == 200
    assert r.get_json().get('ok') is True
