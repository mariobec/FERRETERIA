"""Explorador catálogo Chilemat — rutas y API."""
import pytest


@pytest.mark.smoke
def test_chilemat_explorador_ruta_admin(app_client):
    r = app_client.get('/compras/chilemat/explorador', follow_redirects=False)
    assert r.status_code == 200
    assert b'Universo Chilemat' in r.data


@pytest.mark.smoke
def test_api_chilemat_catalogo_json(app_client):
    r = app_client.get('/api/compras/chilemat/catalogo?page=1&per_page=5')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'items' in data
    assert data.get('total', 0) >= 0
