"""Ingreso DTE correo → recepción documental sin stock — smoke."""
from pathlib import Path

import pytest

from app import DetalleRecepcion, Producto, Proveedor, RecepcionCompra, RecepcionLineaDocumento, db
from services.ingreso_dte_correo_service import (
    ORIGEN_DTE_CORREO,
    persistir_recepcion_desde_xml_dte,
)
from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS

FIXTURE = Path(__file__).resolve().parents[0] / 'fixtures' / 'dte_compra_ejemplo.xml'
RUT_CHILEMAT = '96516560-5'
FOLIO = '5005433'


@pytest.mark.smoke
def test_ingreso_dte_correo_sin_stock(app_ctx, productos_con_stock):
    prov = Proveedor.query.filter_by(rut=RUT_CHILEMAT).first()
    if not prov:
        prov = Proveedor(nombre='CHILEMAT TEST', rut=RUT_CHILEMAT)
        db.session.add(prov)
        db.session.commit()

    from app import guardar_producto_codigo_proveedor

    p = Producto.query.filter(Producto.codigo_chilemat == '110109').first()
    if not p:
        p = Producto.query.filter(Producto.nombre.ilike('%TEST%')).first()
    assert p is not None
    guardar_producto_codigo_proveedor(prov.id, 'INT-110109', p.id, usuario='QA', commit=True)

    stock_antes = int(p.stock or 0)

    RecepcionCompra.query.filter_by(
        proveedor_id=prov.id,
        documento_numero=FOLIO,
    ).delete(synchronize_session=False)
    db.session.commit()

    res = persistir_recepcion_desde_xml_dte(FIXTURE, usuario_bodega='QA-TEST')
    assert res.ok is True, res.errores
    assert res.recepcion_id
    assert res.recepcion_creada is True
    assert res.lineas_documentales >= 2

    rec = RecepcionCompra.query.get(res.recepcion_id)
    assert rec.estado == ESTADO_PENDIENTE_ITEMS
    assert rec.origen_importacion == ORIGEN_DTE_CORREO
    assert rec.documento_numero == FOLIO
    assert float(rec.monto_neto or 0) == 58160.0

    docs = RecepcionLineaDocumento.query.filter_by(recepcion_id=rec.id).order_by(RecepcionLineaDocumento.nro_linea).all()
    assert len(docs) == 2
    assert docs[0].nombre.startswith('ALAMBRE')
    assert float(docs[0].precio_unitario or 0) == 1498.0
    assert docs[1].producto_id is None  # clavo sin código — sin match catálogo

    dets = DetalleRecepcion.query.filter_by(recepcion_id=rec.id).all()
    assert len(dets) >= 1
    assert all(int(d.cantidad_recibida or 0) == 0 for d in dets)
    assert any(int(d.cantidad_documento or 0) == 10 for d in dets)

    db.session.refresh(p)
    assert int(p.stock or 0) == stock_antes

    # cleanup
    RecepcionLineaDocumento.query.filter_by(recepcion_id=rec.id).delete()
    DetalleRecepcion.query.filter_by(recepcion_id=rec.id).delete()
    db.session.delete(rec)
    db.session.commit()
