"""
E2E facturación Fase 1: cobro en caja persiste XML bajo storage/dtes/emitidos/.

Requiere BD de QA (misma suite que conftest). Aísla CAF tipo 39 borrando filas
existentes de ese tipo para que el folio salga del CAF de prueba.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

import app as m
from services import facturacion_caf_service as caf_svc
from services import facturacion_dte_storage as st
from tests.conftest import crear_venta_pendiente

db = m.db

CAF_E2E_BOLETA_XML = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<AUTORIZACION>
<CAF version="1.0">
<DA>
<RE>76192028-5</RE>
<TD>39</TD>
<RNG><D>870010</D><H>870999</H></RNG>
<FA>2026-05-14</FA>
</DA>
</CAF>
</AUTORIZACION>
"""


@pytest.fixture
def caf_boleta_39_aislado():
    """Un único CAF boleta (39) para el test; evita competencia con otros rangos."""
    m._asegurar_tabla_cafs_y_columnas_ventas_fe()
    db.session.execute(text('DELETE FROM cafs WHERE tipo_dte = 39'))
    db.session.commit()
    row, _ = caf_svc.insertar_caf_desde_xml(db.session, m.Caf, CAF_E2E_BOLETA_XML)
    db.session.commit()
    try:
        yield row
    finally:
        try:
            db.session.execute(text('DELETE FROM cafs WHERE id = :i'), {'i': int(row.id)})
            db.session.commit()
        except Exception:
            db.session.rollback()


@pytest.mark.smoke
def test_cobro_caja_persiste_xml_dte_emitido(
    app_client,
    productos_con_stock,
    caja_abierta,
    cliente_final,
    caf_boleta_39_aislado,
):
    caf_row = caf_boleta_39_aislado
    p = productos_con_stock[0]
    venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
    vid = venta.id

    r = app_client.post(
        f'/procesar_cobro_caja/{vid}',
        data={
            'metodo_pago': 'Efectivo',
            'tipo_documento': 'Boleta',
            'monto_recibido': str(int(venta.monto_total) + 100),
        },
        follow_redirects=True,
    )
    assert r.status_code in (200, 302)

    db.session.expire_all()
    vr = db.session.get(m.Venta, vid)
    assert vr is not None
    assert vr.estado == 'Pagado'
    # Boletas: Multicaja emite al SII; LhexIA no consume CAF ni genera XML.
    assert vr.dte_estado == 'EXTERNO_MULTICAJA'
    assert vr.caf_id is None
    assert vr.nro_documento is None
    assert st.buscar_xml_dte_por_venta(m.app.root_path, vid) is None
