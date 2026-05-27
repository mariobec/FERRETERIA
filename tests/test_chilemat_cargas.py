"""Smoke: pantalla y API cargas Chilemat."""
import json


def test_chilemat_cargas_pagina(app_client):
    r = app_client.get('/compras/chilemat/cargas', follow_redirects=True)
    assert r.status_code == 200
    assert b'Cargas Chilemat' in r.data


def test_api_chilemat_cargas_preview(app_client):
    r = app_client.post(
        '/api/compras/chilemat/cargas/ejecutar',
        data=json.dumps({
            'accion': 'cargar_productos',
            'sin_sync': True,
            'preview': True,
            'limit': 3,
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('accion') == 'cargar_productos'
    assert 'carga' in data
