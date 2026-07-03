"""Limpieza recepciones RCV vacías — smoke."""
from datetime import datetime

import pytest

from app import Proveedor, RecepcionCompra, db
from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS, ORIGEN_RCV_SII
from services.recepciones_lista_service import limpiar_recepciones_documentales


@pytest.mark.smoke
def test_limpiar_rcv_sin_lineas(app_ctx):
    prov = Proveedor.query.filter(Proveedor.nombre.ilike('%TEST%')).first()
    if not prov:
        prov = Proveedor(nombre='PROV TEST LIMPIAR', rut='11.111.111-1')
        db.session.add(prov)
        db.session.commit()

    folio = 'LIMPIAR-TEST-001'
    RecepcionCompra.query.filter_by(proveedor_id=prov.id, documento_numero=folio).delete(
        synchronize_session=False
    )
    db.session.commit()

    rec = RecepcionCompra(
        proveedor_id=prov.id,
        documento_tipo='Factura',
        documento_numero=folio,
        usuario_bodega='QA',
        estado=ESTADO_PENDIENTE_ITEMS,
        origen_importacion=ORIGEN_RCV_SII,
        monto_total=1000.0,
        fecha_documento=datetime(2026, 5, 1).date(),
    )
    db.session.add(rec)
    db.session.commit()
    rid = rec.id

    prev = limpiar_recepciones_documentales(anio=2026, origen='rcv_sii', dry_run=True)
    assert prev['ok'] is True
    assert prev['candidatas'] >= 1

    res = limpiar_recepciones_documentales(anio=2026, origen='rcv_sii', ids=[rid], dry_run=False)
    assert res['ok'] is True
    assert res['eliminadas'] == 1
    assert RecepcionCompra.query.get(rid) is None
