# -*- coding: utf-8 -*-
"""
CAF de laboratorio para Ambiente de Certificación SII (Maullín).

Incluye RSASK para timbrar TED en desarrollo. **No válido ante el SII real**;
sirve para set de simulación, pruebas locales y carga en tabla `cafs` de QA.

Para certificación oficial: descargar AUTORIZACION desde Maullín tras postular software.
"""
from __future__ import annotations

import base64
import os
from datetime import date
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Clave RSA 512 de ejemplo (documentación SII / CryptoSys) — solo certificación local.
_RSASK_PEM_CERT = """-----BEGIN RSA PRIVATE KEY-----
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

# Rangos sugeridos Maullín / set simulación (no solapan con prod)
RANGO_CERT_BOLETA_39 = (1, 500)
RANGO_CERT_FACTURA_33 = (1, 500)
RANGO_CERT_NC_61 = (1, 100)


def generar_autorizacion_caf_certificacion(
    tipo_dte: int,
    rango_desde: int,
    rango_hasta: int,
    *,
    rut_emisor: str = '8054120-1',
    razon_social: str = 'CERTIFICACION MAULLIN LHEXIA',
    fecha_autorizacion: Optional[str] = None,
) -> bytes:
    """
    Genera XML AUTORIZACION completo con CAF + RSASK para timbrado TED en QA.
    """
    fa = (fecha_autorizacion or date.today().isoformat())[:10]
    td = int(tipo_dte)
    r0, r1 = int(rango_desde), int(rango_hasta)
    re = (rut_emisor or '8054120-1').strip()
    rs = (razon_social or 'CERT MAULLIN')[:80]

    key = serialization.load_pem_private_key(_RSASK_PEM_CERT.encode('ascii'), password=None)
    da_for_frma = (
        '<DA><RE>%s</RE><RS>%s</RS><TD>%s</TD><RNG><D>%s</D><H>%s</H></RNG>'
        '<FA>%s</FA><RSAPK><M>%s</M><E>%s</E></RSAPK><IDK>100</IDK></DA>'
    ) % (re, rs, td, r0, r1, fa, _M_B64, _E_B64)
    frma_sig = base64.b64encode(
        key.sign(da_for_frma.encode('iso-8859-1', errors='replace'), padding.PKCS1v15(), hashes.SHA1())
    ).decode('ascii')

    xml_txt = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n<AUTORIZACION>\n'
        '<CAF version="1.0">\n%s\n'
        '<FRMA algoritmo="SHA1withRSA">%s</FRMA>\n</CAF>\n<RSASK>\n%s\n</RSASK>\n</AUTORIZACION>\n'
    ) % (da_for_frma, frma_sig, _RSASK_PEM_CERT.strip())
    return xml_txt.encode('utf-8')


def directorio_caf_certificacion(app_root: str) -> str:
    d = os.path.join(app_root, 'storage', 'dtes', 'caf_certificacion')
    os.makedirs(d, exist_ok=True)
    return d


def guardar_cafs_certificacion(
    app_root: str,
    *,
    rut_emisor: str = '8054120-1',
    razon_social: str = 'CERTIFICACION MAULLIN LHEXIA',
) -> Dict[int, str]:
    """Escribe CAF_cert_33.xml, CAF_cert_39.xml (y opcional 61) en disco."""
    out: Dict[int, str] = {}
    d = directorio_caf_certificacion(app_root)
    specs = (
        (39, RANGO_CERT_BOLETA_39),
        (33, RANGO_CERT_FACTURA_33),
        (61, RANGO_CERT_NC_61),
    )
    for td, (r0, r1) in specs:
        xml_b = generar_autorizacion_caf_certificacion(
            td, r0, r1, rut_emisor=rut_emisor, razon_social=razon_social
        )
        path = os.path.join(d, 'CAF_cert_%s.xml' % td)
        with open(path, 'wb') as fh:
            fh.write(xml_b)
        out[int(td)] = path
    return out


def insertar_cafs_certificacion_bd(
    db_session: Any,
    caf_model: Any,
    *,
    rut_emisor: str = '8054120-1',
    razon_social: str = 'CERTIFICACION MAULLIN LHEXIA',
    reemplazar: bool = True,
) -> Dict[int, Any]:
    """
    Inserta CAF 33 y 39 de certificación en `cafs`.
    Si `reemplazar`, borra CAF previos de esos tipos en los rangos de cert.
    """
    from sqlalchemy import text

    from services import facturacion_caf_service as caf_svc

    if reemplazar:
        for td, (r0, r1) in ((39, RANGO_CERT_BOLETA_39), (33, RANGO_CERT_FACTURA_33)):
            db_session.execute(
                text(
                    'DELETE FROM cafs WHERE tipo_dte = :td AND rango_desde = :r0 AND rango_hasta = :r1'
                ),
                {'td': td, 'r0': r0, 'r1': r1},
            )
        db_session.flush()

    rows: Dict[int, Any] = {}
    for td, (r0, r1) in ((39, RANGO_CERT_BOLETA_39), (33, RANGO_CERT_FACTURA_33)):
        xml_b = generar_autorizacion_caf_certificacion(
            td, r0, r1, rut_emisor=rut_emisor, razon_social=razon_social
        )
        row, _info = caf_svc.insertar_caf_desde_xml(db_session, caf_model, xml_b)
        rows[int(td)] = row
    return rows
