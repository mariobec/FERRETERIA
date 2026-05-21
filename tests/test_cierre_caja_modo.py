"""Tests modo cierre caja — ciego vs visible (empresa config)."""
import pytest

from services.cierre_caja_config_service import es_cierre_a_ciegas, obtener_modo_cierre_caja


def test_modo_default_ciego(app_ctx, monkeypatch):
    monkeypatch.delenv('CIERRE_CAJA_MODO', raising=False)
    import app as m

    cfg = m.obtener_config_empresa()
    cfg['cierre_caja_modo'] = 'ciego'
    m.guardar_config_empresa({'cierre_caja_modo': 'ciego'})
    assert obtener_modo_cierre_caja() == 'ciego'
    assert es_cierre_a_ciegas() is True


def test_modo_visible_empresa(app_ctx, monkeypatch):
    monkeypatch.delenv('CIERRE_CAJA_MODO', raising=False)
    import app as m

    m.guardar_config_empresa({'cierre_caja_modo': 'visible'})
    assert obtener_modo_cierre_caja() == 'visible'
    assert es_cierre_a_ciegas() is False
    m.guardar_config_empresa({'cierre_caja_modo': 'ciego'})


def test_env_override_visible(app_ctx, monkeypatch):
    import app as m

    m.guardar_config_empresa({'cierre_caja_modo': 'ciego'})
    monkeypatch.setenv('CIERRE_CAJA_MODO', 'visible')
    assert obtener_modo_cierre_caja() == 'visible'
