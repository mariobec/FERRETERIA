# -*- coding: utf-8 -*-
"""TED / FRMT con CAF de laboratorio (clave RSA 512 generada en test)."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from services import facturacion_electronica_service as fe
from services import facturacion_ted_service as ted


# Clave RSA 512 bits de ejemplo (documentación SII / CryptoSys) — solo tests.
_RSASK_PEM_TEST = """-----BEGIN RSA PRIVATE KEY-----
MIIBOwIBAAJBANGuDuim8fEI9yuIlkj+MOyp3mWHifoP6a4oWLSBKJSrd3MpEsZd
czvL0l7t/e0IU5rF+0gRLnU1Mfvtsw1wYWcCAQMCQQCLyV9FxKFLW09yWw7bVCCd
xpRDr7FRX/EexZB4VhsNxm/vtJfDZyYle0Lfy42LlcsXxPm1w6Q6NnjuW+AeBy67
AiEA7iMi5q5xjswqq+49RP55o//jqdZL/pC9rdnUKxsNRMMCIQDhaHdIctErN2hC
IP9knS3+9zra4R+5jSXOvI+3xVhWjQIhAJ7CF0R0S7SIHHKe04NUURf/7RvkMqm1
08k74sdnXi3XAiEAlkWk2vc2HM+a1sCqQxNz/098ketqe7NuidMKeoOQObMCIQCk
FAMS9IcPcMjk7zI2r/4EEW63PSXyN7MFAX7TYe25mw==
-----END RSA PRIVATE KEY-----"""
_M_B64 = '0a4O6Kbx8Qj3K4iWSP4w7KneZYeJ+g/prihYtIEolKt3cykSxl1zO8vSXu397QhTmsX7SBEudTUx++2zDXBhZw=='
_E_B64 = 'Aw=='


def _caf_autorizacion_test_xml() -> bytes:
    pem = _RSASK_PEM_TEST
    key = serialization.load_pem_private_key(pem.encode('ascii'), password=None)
    pub = key.public_key().public_numbers()
    m_b64 = _M_B64
    e_b64 = _E_B64
    dd_bytes = (
        b'<DD><RE>8054120-1</RE><TD>39</TD><F>1</F><FE>2026-05-20</FE>'
        b'<RR>66666666-6</RR><RSR>CLI</RSR><MNT>1190</MNT><IT1>Item</IT1>'
        b'<CAF version="1.0"><DA><RE>8054120-1</RE><TD>39</TD>'
        b'<RNG><D>1</D><H>10</H></RNG><FA>2026-05-20</FA>'
        b'<RSAPK><M>%s</M><E>%s</E></RSAPK></DA>'
        b'<FRMA algoritmo="SHA1withRSA">dGVzdA==</FRMA></CAF>'
        b'<TSTED>2026-05-20T12:00:00</TSTED></DD>'
    ) % (m_b64.encode(), e_b64.encode())
    sig = key.sign(dd_bytes, padding.PKCS1v15(), hashes.SHA1())
    frma = base64.b64encode(sig).decode('ascii')
    xml_txt = (
        '<?xml version="1.0"?><AUTORIZACION><CAF version="1.0"><DA>'
        '<RE>8054120-1</RE><RS>TEST</RS><TD>39</TD><RNG><D>1</D><H>10</H></RNG>'
        '<FA>2026-05-20</FA><RSAPK><M>%s</M><E>%s</E></RSAPK><IDK>100</IDK></DA>'
        '<FRMA algoritmo="SHA1withRSA">%s</FRMA></CAF><RSASK>%s</RSASK></AUTORIZACION>'
    ) % (m_b64, e_b64, frma, pem)
    return xml_txt.encode('utf-8')


@pytest.mark.smoke
def test_extraer_rsask_y_firmar_frmt():
    caf = _caf_autorizacion_test_xml()
    pem = ted.extraer_rsask_pem(caf)
    assert 'BEGIN RSA PRIVATE KEY' in pem
    ctx = fe.construir_contexto_dte_prueba(39, folio=1)
    caf_el = ted.extraer_elemento_caf(caf)
    dd = ted.construir_elemento_dd(ctx, caf_el)
    sig = ted.firmar_frmt_dd(ted.aplanar_dd_para_firma(dd), pem)
    assert len(sig) > 20


@pytest.mark.smoke
def test_generar_xml_con_ted():
    caf = _caf_autorizacion_test_xml()
    ctx = fe.construir_contexto_dte_prueba(39, folio=42)
    xml = fe.generar_xml_dte_prueba_lxml(ctx, caf_autorizacion_xml=caf)
    assert b'<TED' in xml or b'TED' in xml
    assert b'FRMT' in xml
    assert b'StubFase1' not in xml
