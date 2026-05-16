"""CAF SII: parseo XML e inserción."""
import pytest

from sqlalchemy import text

import app as m
from services import facturacion_caf_service as caf_svc

db = m.db

CAF_XML_MIN = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<AUTORIZACION>
<CAF version="1.0">
<DA>
<RE>76192028-5</RE>
<TD>39</TD>
<RNG><D>990001</D><H>990010</H></RNG>
<FA>2026-01-15</FA>
</DA>
</CAF>
</AUTORIZACION>
"""


def test_parse_caf_xml():
    d = caf_svc.parse_caf_autorizacion_xml(CAF_XML_MIN)
    assert d['tipo_dte'] == 39
    assert d['rango_desde'] == 990001
    assert d['rango_hasta'] == 990010
    assert d['fecha_autorizacion'].year == 2026


@pytest.mark.smoke
def test_api_admin_cafs_post_get(app_client):
    """Admin inserta CAF vía API y aparece en GET."""
    db.session.execute(text('DELETE FROM cafs WHERE tipo_dte = 39 AND rango_desde = 990001'))
    db.session.commit()
    r = app_client.post(
        '/api/admin/facturacion/cafs',
        data=CAF_XML_MIN.decode('utf-8'),
        content_type='text/plain',
    )
    if r.status_code == 403:
        pytest.skip('Sin permiso API facturación')
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.get_json()
    assert j.get('ok') is True
    cid = j.get('caf', {}).get('id')
    assert cid
    try:
        rg = app_client.get('/api/admin/facturacion/cafs')
        assert rg.status_code == 200
        lst = rg.get_json().get('cafs') or []
        ids = [x['id'] for x in lst]
        assert cid in ids
    finally:
        try:
            db.session.execute(text('DELETE FROM cafs WHERE id = :i'), {'i': int(cid)})
            db.session.commit()
        except Exception:
            db.session.rollback()
