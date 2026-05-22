# -*- coding: utf-8 -*-
import pytest

from services import facturacion_caf_certificacion as caf_cert
from services import facturacion_caf_service as caf_svc
from services import facturacion_ted_service as ted


@pytest.mark.smoke
def test_generar_caf_cert_33_tiene_rsask():
    xml = caf_cert.generar_autorizacion_caf_certificacion(33, 1, 10, rut_emisor='8054120-1')
    pem = ted.extraer_rsask_pem(xml)
    assert 'BEGIN RSA PRIVATE KEY' in pem
    d = caf_svc.parse_caf_autorizacion_xml(xml)
    assert d['tipo_dte'] == 33
    assert d['rango_desde'] == 1
