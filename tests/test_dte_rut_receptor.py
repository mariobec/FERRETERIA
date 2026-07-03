"""Filtro RUT receptor DTE — smoke."""
import pytest

from services.dte_rut_receptor_service import (
    etiqueta_gmail_para_rut,
    normalizar_rut,
    rut_receptor_permitido,
)


@pytest.mark.smoke
def test_normalizar_rut():
    assert normalizar_rut('8054120-1') == '8054120-1'
    assert normalizar_rut('80541201') == '8054120-1'


@pytest.mark.smoke
def test_rut_permitido_sin_env(monkeypatch):
    monkeypatch.delenv('DTE_RUT_RECEPTOR', raising=False)
    monkeypatch.delenv('EMPRESA_RUT', raising=False)
    assert rut_receptor_permitido('99999999-9') is True


@pytest.mark.smoke
def test_rut_permitido_con_env(monkeypatch):
    monkeypatch.setenv('DTE_RUT_RECEPTOR', '8054120-1')
    assert rut_receptor_permitido('8054120-1') is True
    assert rut_receptor_permitido('96516560-5') is False
    assert etiqueta_gmail_para_rut('8054120-1') == 'DTE-8054120-1'
    assert etiqueta_gmail_para_rut('96516560-5') == 'DTE-Otra-Sociedad'
