"""Resolver línea OC COMPRA-HIST-MAESTRA → producto real — smoke."""
from datetime import date

import pytest

from app import (
    DetalleOrdenCompra,
    OrdenCompra,
    Producto,
    Proveedor,
    RecepcionCompra,
    db,
    guardar_producto_codigo_proveedor,
)

CODIGO_GENERICO = 'COMPRA-HIST-MAESTRA'


def _producto_generico():
    p = Producto.query.filter_by(codigo_interno=CODIGO_GENERICO).first()
    if p:
        return p
    p = Producto(
        codigo_interno=CODIGO_GENERICO,
        codigo_barra=CODIGO_GENERICO,
        nombre='[Histórico] Compras maestra sin ficha SKU',
        activo=False,
        precio_compra=0,
        precio_venta=0,
        stock=0,
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.mark.smoke
def test_resolver_linea_oc_generica(app_client, proveedor_test, productos_con_stock):
    from app import _producto_es_generico_oc

    gen = _producto_generico()
    real = productos_con_stock[0]
    prov = proveedor_test

    oc = OrdenCompra(
        proveedor_id=prov.id,
        numero='TEST-OC-GEN-001',
        fecha_emision=date.today(),
        estado='Enviada',
        usuario_creador='QA',
    )
    db.session.add(oc)
    db.session.flush()
    det_gen = DetalleOrdenCompra(
        orden_compra_id=oc.id,
        producto_id=gen.id,
        cantidad=30,
        precio_unitario=5623.0,
    )
    db.session.add(det_gen)

    rec = RecepcionCompra(
        proveedor_id=prov.id,
        orden_compra_id=oc.id,
        documento_tipo='Factura',
        documento_numero='TEST-FAC-GEN',
        usuario_bodega='QA',
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()

    cod_fac = 'INT-TEST-GEN-OC-01'
    guardar_producto_codigo_proveedor(prov.id, cod_fac, real.id, usuario='QA', commit=True)

    r = app_client.post(
        f'/api/recepciones/{rec.id}/resolver_linea_oc_generica',
        json={
            'detalle_oc_id': det_gen.id,
            'codigo_factura': cod_fac,
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('producto_id') == real.id

    db.session.refresh(det_gen)
    assert det_gen.producto_id == real.id
    assert not _producto_es_generico_oc(det_gen.producto)

    r2 = app_client.post(
        f'/api/recepciones/{rec.id}/preview_match_codigo_oc',
        json={'codigo_factura': cod_fac},
    )
    assert r2.status_code == 200
    prev = r2.get_json()
    assert prev.get('encontrado') is True
    assert prev.get('producto_id') == real.id

    # cleanup (FK: detalle antes que recepción/OC)
    DetalleOrdenCompra.query.filter_by(orden_compra_id=oc.id).delete(synchronize_session=False)
    db.session.delete(rec)
    db.session.delete(oc)
    db.session.commit()


@pytest.mark.smoke
def test_preview_match_codigo_sin_equivalencia(app_client, proveedor_test):
    rec = RecepcionCompra(
        proveedor_id=proveedor_test.id,
        documento_tipo='Factura',
        documento_numero='TEST-FAC-PREV',
        usuario_bodega='QA',
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()
    r = app_client.post(
        f'/api/recepciones/{rec.id}/preview_match_codigo_oc',
        json={'codigo_factura': 'CODIGO-INEXISTENTE-XYZ'},
    )
    assert r.status_code == 200
    assert r.get_json().get('encontrado') is False
    db.session.delete(rec)
    db.session.commit()
