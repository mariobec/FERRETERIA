# -*- coding: utf-8 -*-
"""Tests unitarios cliente SOAP SII (sin llamadas reales)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from services import facturacion_sii_soap as sii


def test_split_rut():
    assert sii.split_rut('8.054.120-1') == ('8054120', '1')
    assert sii.split_rut('8054120-1') == ('8054120', '1')


def test_normalizar_ambiente():
    assert sii.normalizar_ambiente('palena') == 'produccion'
    assert sii.normalizar_ambiente('maullin') == 'certificacion'


def test_soap_habilitado_env(monkeypatch):
    monkeypatch.delenv('SII_SOAP_ENABLED', raising=False)
    assert sii.soap_habilitado() is False
    monkeypatch.setenv('SII_SOAP_ENABLED', '1')
    assert sii.soap_habilitado() is True


def test_obtener_semilla_parse_ok():
    xml = (
        '<?xml version="1.0"?><RESPUESTA><ESTADO>00</ESTADO>'
        '<SEMILLA>ABC123XYZ</SEMILLA></RESPUESTA>'
    )
    mock_client = MagicMock()
    mock_client.service.getSeed.return_value = xml
    with patch('zeep.Client', return_value=mock_client):
        r = sii.obtener_semilla('certificacion')
    assert r.ok is True
    assert r.semilla == 'ABC123XYZ'


def test_enviar_dte_deshabilitado_sin_env(monkeypatch):
    monkeypatch.delenv('SII_SOAP_ENABLED', raising=False)
    track, estado, _det = sii.enviar_dte_firmado_al_sii(
        b'<DTE/>', rut_emisor='8054120-1', ambiente='certificacion'
    )
    assert track is None
    assert estado == 'deshabilitado'


@pytest.mark.smoke
def test_diagnostico_mock_semilla():
    xml = '<?xml version="1.0"?><RESPUESTA><ESTADO>00</ESTADO><SEMILLA>S1</SEMILLA></RESPUESTA>'
    mock_client = MagicMock()
    mock_client.service.getSeed.return_value = xml
    with patch('zeep.Client', return_value=mock_client):
        d = sii.diagnostico_sii('certificacion')
    assert d['semilla_ok'] is True


def test_firmar_xml_semilla_token_algoritmos(monkeypatch, tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime as dt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'TEST SII')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pfx = tmp_path / 't.pfx'
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12

    pfx.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b'test',
            key,
            cert,
            None,
            BestAvailableEncryption(b'test'),
        )
    )

    def fake_cfg():
        return {'pfx_path': str(pfx), 'pfx_path_resolved': str(pfx), 'ambiente': 'certificacion'}

    monkeypatch.setattr(
        'services.facturacion_electronica_service.obtener_config_certificado',
        fake_cfg,
    )
    monkeypatch.setattr(
        'services.facturacion_electronica_service._leer_password_pfx_texto_plano',
        lambda _cfg: 'test',
    )

    xml_bytes = sii.firmar_xml_semilla_token('000009574333')
    assert b"encoding='ISO-8859-1'" in xml_bytes or b'encoding="ISO-8859-1"' in xml_bytes
    txt = xml_bytes.decode('iso-8859-1')
    assert '<getToken>' in txt
    assert '<Semilla>000009574333</Semilla>' in txt
    assert sii.SIG_ALG_RSA_SHA1 in txt
    assert sii.DIGEST_SHA1 in txt
    assert sii.C14N_SII in txt
    assert 'RSAKeyValue' in txt
    assert 'Modulus' in txt
    assert 'X509Certificate' in txt
