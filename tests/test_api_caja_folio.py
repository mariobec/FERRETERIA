"""Smoke — API folio caja (sin cola real)."""
import pytest


@pytest.mark.smoke
def test_api_caja_vale_por_folio_invalido(app_client, caja_abierta):
    r = app_client.get('/api/caja/vale-por-folio?q=XYZ')
    assert r.status_code == 400
    data = r.get_json()
    assert data.get('ok') is False
