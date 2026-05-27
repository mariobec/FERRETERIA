"""Match híbrido factura Chilemat y tabla puente producto_codigo_proveedor."""
import pytest

from app import (
    Producto,
    ProductoCodigoProveedor,
    _asegurar_tabla_producto_codigo_proveedor,
    _matchear_producto_linea_factura,
    guardar_producto_codigo_proveedor,
)


@pytest.fixture
def producto_chilemat_codigo(app_ctx):
    from app import db

    p = Producto(
        nombre='SOPLETE PORTATIL PG-400M C/PIEZA PROVIDUS',
        codigo_chilemat='FERSOLPIS043',
        codigo_barra='PEND-FERSOLPIS043',
        codigo_interno='CHM-FERSOLPIS043',
        precio_compra=0,
        precio_venta=1000,
        stock=0,
        activo=True,
    )
    db.session.add(p)
    db.session.commit()
    yield p
    try:
        ProductoCodigoProveedor.query.filter_by(producto_id=p.id).delete(
            synchronize_session=False
        )
        db.session.delete(p)
        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.mark.smoke
def test_match_int_sin_prefijo_en_chilemat(producto_chilemat_codigo, proveedor_test):
    p, how = _matchear_producto_linea_factura(
        'INT-FERSOLPIS043',
        'SOPLETE PORTATIL PG400M',
        proveedor_test.id,
    )
    assert p is not None
    assert p.id == producto_chilemat_codigo.id
    assert how == 'codigo_chilemat_sin_prefijo'


@pytest.mark.smoke
def test_match_tabla_puente_codigo_proveedor(app_ctx, producto_chilemat_codigo, proveedor_test):
    _asegurar_tabla_producto_codigo_proveedor()
    ok, err = guardar_producto_codigo_proveedor(
        proveedor_test.id,
        'INT-AGRHACCHI021',
        producto_chilemat_codigo.id,
        usuario='QA',
    )
    assert ok is True
    assert err is None
    p, how = _matchear_producto_linea_factura(
        'INT-AGRHACCHI021',
        'HACHA C/MANGO 1000 GRS',
        proveedor_test.id,
    )
    assert p is not None
    assert how == 'codigo_proveedor'
    row = ProductoCodigoProveedor.query.filter_by(
        proveedor_id=proveedor_test.id,
        codigo_factura_proveedor='INT-AGRHACCHI021',
    ).first()
    assert row is not None
    assert row.producto_id == producto_chilemat_codigo.id


@pytest.mark.smoke
def test_match_descripcion_exacta(app_ctx, proveedor_test):
    from app import db

    p = Producto(
        nombre='BURLETE DOBLE PARA PUERTAS GRIS 95 CM RAYUN',
        codigo_chilemat='FERBURRAY001',
        codigo_barra='PEND-FERBURRAY001',
        precio_compra=0,
        precio_venta=500,
        stock=0,
        activo=True,
    )
    db.session.add(p)
    db.session.commit()
    try:
        found, how = _matchear_producto_linea_factura(
            'INT-OTRO-CODIGO-999',
            'BURLETE DOBLE PARA PUERTAS GRIS 95 CM RAYUN',
            proveedor_test.id,
        )
        assert found is not None
        assert found.id == p.id
        assert how == 'descripcion_exacta'
    finally:
        db.session.delete(p)
        db.session.commit()


@pytest.mark.smoke
def test_api_vincular_codigo_proveedor(app_client, proveedor_test, productos_con_stock):
    from app import RecepcionCompra, db

    prod = productos_con_stock[0]
    rec = RecepcionCompra(
        proveedor_id=proveedor_test.id,
        documento_tipo='Factura',
        documento_numero='TEST-VINC-COD',
        usuario_bodega='QA',
        estado='Pendiente',
    )
    db.session.add(rec)
    db.session.commit()
    r = app_client.post(
        f'/recepciones/{rec.id}/codigo-proveedor/vincular',
        json={'codigo_factura': 'INT-TEST-XYZ99', 'producto_id': prod.id},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    p, how = _matchear_producto_linea_factura('INT-TEST-XYZ99', '', proveedor_test.id)
    assert p is not None
    assert p.id == prod.id
    assert how == 'codigo_proveedor'
