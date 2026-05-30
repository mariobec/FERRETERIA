"""Módulo cliente Fábrica de Color — lab preview + sesión caja."""
import pytest

from services import fabrica_color_service as fc
from services import modulo_pinturas_session_service as ms


@pytest.mark.smoke
def test_modulo_pinturas_lab_404_sin_preview(app_client):
    r = app_client.get('/modulos/pinturas/lab')
    assert r.status_code == 404


@pytest.mark.smoke
def test_modulo_pinturas_lab_ok_con_preview(app_client, monkeypatch):
    monkeypatch.setenv('VITRINA_FABRICA_COLOR_PREVIEW', '1')
    r = app_client.get('/modulos/pinturas/lab')
    assert r.status_code == 200
    assert b'Preview lab' in r.data
    assert b'lab/iniciar' in r.data


@pytest.mark.smoke
def test_modulo_pinturas_wizard_lab(app_client, monkeypatch):
    monkeypatch.setenv('VITRINA_FABRICA_COLOR_PREVIEW', '1')
    r = app_client.get('/modulos/pinturas/lab/iniciar')
    assert r.status_code == 200
    assert b'F' in r.data and b'brica de Color' in r.data
    assert b'fabrica-color.js' in r.data


@pytest.mark.smoke
def test_modulo_pinturas_cotizar_lab(app_client, monkeypatch):
    monkeypatch.setenv('VITRINA_FABRICA_COLOR_PREVIEW', '1')
    r = app_client.post(
        '/api/modulos/pinturas/lab/cotizar',
        json={
            'ambiente_id': 'living',
            'color_id': 'b-001',
            'brillo_id': 'mate',
            'm2': 15,
            'calidad_id': 'standard',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('cantidad', {}).get('galones_sugeridos', 0) >= 1


@pytest.mark.smoke
def test_tienda_sin_link_fabrica(app_client):
    r = app_client.get('/tienda/ferreteria-santo-domingo')
    assert r.status_code == 200
    assert b'fabrica-de-color' not in r.data
    assert b'tienda-nav-fabrica' not in r.data


@pytest.mark.smoke
def test_legacy_fabrica_vitrina_404(app_client):
    r = app_client.get('/tienda/ferreteria-santo-domingo/fabrica-de-color')
    assert r.status_code == 404


def test_caja_habilitar_modulo_pinturas(app_client):
    r = app_client.post('/api/caja/modulo-pinturas/habilitar')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('token')
    assert data.get('path', '').startswith('/modulos/pinturas/')


def test_caja_token_abre_wizard(app_client):
    r = app_client.post('/api/caja/modulo-pinturas/habilitar')
    assert r.status_code == 200
    token = r.get_json().get('token')
    rw = app_client.get(f'/modulos/pinturas/{token}')
    assert rw.status_code == 200
    assert b'Sesi' in rw.data and b'mostrador' in rw.data


def test_fabrica_calcular_cantidad():
    c = fc.calcular_cantidad(m2=35, manos=2)
    assert c['m2'] == 35
    assert c['galones_sugeridos'] >= 1


def test_sesion_preview_flag(monkeypatch):
    monkeypatch.setenv('VITRINA_FABRICA_COLOR_PREVIEW', '1')
    assert ms.preview_habilitado() is True
    assert ms.validar_acceso('lab') is not None
    monkeypatch.setenv('VITRINA_FABRICA_COLOR_PREVIEW', '0')
    assert ms.preview_habilitado() is False
