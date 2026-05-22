"""Config operación un local vs red multi-sucursal."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.smoke
def test_es_operacion_un_local_default():
    with patch('app.obtener_config_empresa', return_value={}):
        from services.empresa_operacion_service import es_operacion_un_local

        assert es_operacion_un_local() is True


@pytest.mark.smoke
def test_es_operacion_multi_desde_empresa_json():
    cfg = {'operacion_un_local': '0', 'operacion_sucursales_red_n': '5'}
    with patch('app.obtener_config_empresa', return_value=cfg):
        from services.empresa_operacion_service import (
            es_operacion_un_local,
            obtener_sucursales_red_n,
        )

        assert es_operacion_un_local() is False
        assert obtener_sucursales_red_n() == 5


@pytest.mark.smoke
def test_env_override_un_local(monkeypatch):
    monkeypatch.setenv('OWNER_GUARDIAN_UN_LOCAL', '0')
    with patch('app.obtener_config_empresa', return_value={'operacion_un_local': '1'}):
        from services.empresa_operacion_service import es_operacion_un_local

        assert es_operacion_un_local() is False


@pytest.mark.smoke
def test_env_override_sucursales_n(monkeypatch):
    monkeypatch.setenv('OWNER_GUARDIAN_SUCURSALES_N', '7')
    with patch('app.obtener_config_empresa', return_value={'operacion_sucursales_red_n': '3'}):
        from services.empresa_operacion_service import obtener_sucursales_red_n

        assert obtener_sucursales_red_n() == 7
