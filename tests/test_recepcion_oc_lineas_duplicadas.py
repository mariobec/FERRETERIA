"""OC con varias líneas del mismo SKU — suma al cargar stock."""
from datetime import date, datetime

import pytest

from app import (
    DetalleOrdenCompra,
    DetalleRecepcion,
    OrdenCompra,
    RecepcionCompra,
    StockPorAlmacen,
    db,
    id_almacen_tienda,
)


@pytest.mark.smoke
def test_workflow_fifo_lineas_mismo_producto(app_client, proveedor_test, productos_con_stock):
    """Pendiente y REC se reparten FIFO entre líneas OC duplicadas."""
    p = productos_con_stock[0]
    oc = OrdenCompra(
        proveedor_id=proveedor_test.id,
        numero=f'TEST-OC-DUP-001-{datetime.now():%H%M%S%f}',
        fecha_emision=date.today(),
        estado='Enviada',
        usuario_creador='QA',
    )
    db.session.add(oc)
    db.session.flush()
    for qty in (30, 30, 40):
        db.session.add(
            DetalleOrdenCompra(
                orden_compra_id=oc.id,
                producto_id=p.id,
                cantidad=qty,
                precio_unitario=1000.0,
            )
        )
    rec = RecepcionCompra(
        proveedor_id=proveedor_test.id,
        orden_compra_id=oc.id,
        documento_tipo='Factura',
        documento_numero='TEST-FAC-DUP',
        usuario_bodega='QA',
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()

    r = app_client.get(f'/api/recepciones/{rec.id}/workflow')
    assert r.status_code == 200
    data = r.get_json()
    lineas = [ln for ln in data['lineas'] if ln['producto_id'] == p.id]
    assert len(lineas) == 3
    assert [ln['cantidad_pendiente'] for ln in lineas] == [30, 30, 40]
    assert [ln['cantidad_recibida_oc'] for ln in lineas] == [0, 0, 0]

    _cleanup_oc_recepcion(rec, oc)


def _cleanup_oc_recepcion(rec, oc):
    db.session.expire_all()
    rid = getattr(rec, 'id', None)
    oid = getattr(oc, 'id', None)
    if rid:
        DetalleRecepcion.query.filter_by(recepcion_id=rid).delete(synchronize_session=False)
        RecepcionCompra.query.filter_by(id=rid).delete(synchronize_session=False)
    if oid:
        DetalleOrdenCompra.query.filter_by(orden_compra_id=oid).delete(synchronize_session=False)
        OrdenCompra.query.filter_by(id=oid).delete(synchronize_session=False)
    db.session.commit()


@pytest.mark.smoke
def test_aplicar_lineas_oc_suma_mismo_producto(app_client, proveedor_test, productos_con_stock):
    """Seleccionar 3 filas mismo SKU suma cantidades (no solo la primera)."""
    p = productos_con_stock[1]
    stock_pre = p.stock or 0
    aid_t = id_almacen_tienda()
    spa_pre = 0
    if aid_t:
        spa = StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_t).first()
        spa_pre = int(spa.cantidad or 0) if spa else 0

    oc = OrdenCompra(
        proveedor_id=proveedor_test.id,
        numero=f'TEST-OC-DUP-002-{datetime.now():%H%M%S%f}',
        fecha_emision=date.today(),
        estado='Enviada',
        usuario_creador='QA',
    )
    db.session.add(oc)
    db.session.flush()
    for qty in (30, 30, 40):
        db.session.add(
            DetalleOrdenCompra(
                orden_compra_id=oc.id,
                producto_id=p.id,
                cantidad=qty,
                precio_unitario=1500.0,
            )
        )
    rec = RecepcionCompra(
        proveedor_id=proveedor_test.id,
        orden_compra_id=oc.id,
        documento_tipo='Factura',
        documento_numero='TEST-FAC-DUP-2',
        usuario_bodega='QA',
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()

    payload = {
        'lineas': [
            {'producto_id': p.id, 'cantidad': 30, 'destino': 'tienda', 'costo_unitario': 1500},
            {'producto_id': p.id, 'cantidad': 30, 'destino': 'tienda', 'costo_unitario': 1500},
            {'producto_id': p.id, 'cantidad': 10, 'destino': 'tienda', 'costo_unitario': 1500},
        ],
        'comision_chilemat': 0,
    }
    r = app_client.post(f'/api/recepciones/{rec.id}/aplicar_lineas_oc', json=payload)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('aplicados') == 1
    assert data['detalle'][0]['cantidad'] == 70
    assert data['detalle'][0]['delta'] == 70

    det = DetalleRecepcion.query.filter_by(recepcion_id=rec.id, producto_id=p.id).first()
    assert det is not None
    assert int(det.cantidad_recibida) == 70

    db.session.refresh(p)
    assert (p.stock or 0) == stock_pre + 70
    if aid_t:
        spa = StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_t).first()
        assert int(spa.cantidad or 0) == spa_pre + 70

    # Tras 70 recibidas (30+30+10), FIFO: línea 3 queda con 30 pendientes de 40 OC
    r2 = app_client.get(f'/api/recepciones/{rec.id}/workflow')
    lineas = [ln for ln in r2.get_json()['lineas'] if ln['producto_id'] == p.id]
    assert [ln['cantidad_pendiente'] for ln in lineas] == [0, 0, 30]
    assert [ln['cantidad_recibida_oc'] for ln in lineas] == [30, 30, 10]

    _cleanup_oc_recepcion(rec, oc)
