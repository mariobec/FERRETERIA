"""Visor recepciones + rango DTE — smoke."""
from datetime import date

import pytest

from services.dte_correo_carga_service import rango_anio, rango_mes
from services.recepciones_lista_service import query_lista_recepciones


@pytest.mark.smoke
def test_rango_mes_2026_enero():
    d1, d2 = rango_mes(2026, 1)
    assert d1 == date(2026, 1, 1)
    assert d2 == date(2026, 2, 1)


@pytest.mark.smoke
def test_rango_anio_2026():
    d1, d2 = rango_anio(2026)
    assert d1 == date(2026, 1, 1)
    assert d2 == date(2027, 1, 1)


@pytest.mark.smoke
def test_query_recepciones_fecha_desde(app_ctx):
    q = query_lista_recepciones(fecha_desde=date(2026, 1, 1), fecha_hasta=date(2026, 12, 31))
    assert q is not None
    q.count()


@pytest.mark.smoke
def test_api_limpiar_documentales_dry_run(app_client):
    r = app_client.post(
        '/api/recepciones/limpiar-documentales',
        json={'anio': 2026, 'origen': 'rcv_sii', 'solo_sin_lineas': True, 'dry_run': True},
    )
    assert r.status_code == 200
    assert r.is_json
    data = r.get_json()
    assert data.get('ok') is True
    assert 'candidatas' in data


@pytest.mark.smoke
def test_api_visor_detalle(app_client):
    r = app_client.get('/recepciones/visor')
    assert r.status_code == 200

    r2 = app_client.get('/recepciones/cargador-dte')
    assert r2.status_code == 200
