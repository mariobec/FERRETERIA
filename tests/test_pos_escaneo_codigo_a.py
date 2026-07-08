"""Entrega A POS: variantes EAN al escanear y ofrecer venta a pedido sin stock."""
from __future__ import annotations

import pytest

import app as m
from services.pos_codigo_escaneo_service import variantes_codigo_barras_escaneo
from tests.conftest import db


@pytest.mark.smoke
def test_variantes_ean13_agrega_cero_final():
    v = variantes_codigo_barras_escaneo('7806179608053')
    assert '7806179608053' in v
    assert '78061796080530' in v


@pytest.mark.smoke
def test_variantes_pistola_apostrofo_como_guion():
    v = variantes_codigo_barras_escaneo("FERRE'009868")
    assert "FERRE'009868" in v
    assert "FERRE-009868" in v


@pytest.mark.smoke
def test_variantes_pistola_tilde_como_guion():
    v = variantes_codigo_barras_escaneo('FERRE~009873')
    assert 'FERRE~009873' in v
    assert 'FERRE-009873' in v
    v2 = variantes_codigo_barras_escaneo('FERRE-009873')
    assert "FERRE'009873" in v2 or 'FERRE~009873' in v2


@pytest.mark.smoke
def test_variantes_ean14_quita_cero_final():
    v = variantes_codigo_barras_escaneo('78061796080530')
    assert '78061796080530' in v
    assert '7806179608053' in v


def test_dos_productos_ean13_ean14_no_se_colapsan(app_ctx, productos_con_stock):
    """Dos SKUs distintos (13 vs 14 dígitos) deben resolverse por coincidencia exacta."""
    from services.catalogo_resolucion_codigo_service import resolver_codigo_escaneado

    p1, p2 = productos_con_stock[0], productos_con_stock[1]
    old1, old2 = p1.codigo_barra, p2.codigo_barra
    ean13 = f'88877766{(int(p1.id) % 100000):05d}'
    ean14 = ean13 + '0'
    p1.codigo_barra = ean13
    p2.codigo_barra = ean14
    db.session.commit()
    try:
        r13 = resolver_codigo_escaneado(
            ean13,
            Producto=m.Producto,
            ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
            db=db,
            app=m.app,
            buscar_chilemat_fn=m._producto_por_codigo_chilemat_escaneo,
        )
        r14 = resolver_codigo_escaneado(
            ean14,
            Producto=m.Producto,
            ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
            db=db,
            app=m.app,
            buscar_chilemat_fn=m._producto_por_codigo_chilemat_escaneo,
        )
        assert r13.get('ambiguo') is False
        assert r14.get('ambiguo') is False
        assert int(r13['producto'].id) == int(p1.id)
        assert int(r14['producto'].id) == int(p2.id)
        via_pos_13 = m._pos_buscar_producto_por_codigo(ean13)
        via_pos_14 = m._pos_buscar_producto_por_codigo(ean14)
        assert int(via_pos_13.id) == int(p1.id)
        assert int(via_pos_14.id) == int(p2.id)
    finally:
        p1.codigo_barra = old1
        p2.codigo_barra = old2
        db.session.commit()


def test_homologacion_ean_solo_si_un_producto(app_ctx, productos_con_stock):
    """EAN-13 escaneado puede resolver maestro EAN-14 solo cuando no hay par 13/14 distinto."""
    from services.catalogo_resolucion_codigo_service import resolver_codigo_escaneado

    p = productos_con_stock[0]
    old = p.codigo_barra
    ean13 = '9998887776053'
    p.codigo_barra = ean13 + '0'
    db.session.commit()
    try:
        r = resolver_codigo_escaneado(
            ean13,
            Producto=m.Producto,
            ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
            db=db,
            app=m.app,
            buscar_chilemat_fn=m._producto_por_codigo_chilemat_escaneo,
        )
        assert r.get('ambiguo') is False
        assert int(r['producto'].id) == int(p.id)
    finally:
        p.codigo_barra = old
        db.session.commit()


def test_pos_buscar_resuelve_ean13_vs_maestro_14(app_ctx, productos_con_stock):
    p = productos_con_stock[0]
    old = p.codigo_barra
    p.codigo_barra = '99988877760530'
    db.session.commit()
    try:
        found = m._pos_buscar_producto_por_codigo('9998887776053')
        assert found is not None
        assert int(found.id) == int(p.id)
    finally:
        p.codigo_barra = old
        db.session.commit()


@pytest.mark.smoke
def test_api_escanear_con_stock_tienda_no_ofrece_apedido(app_client, productos_con_stock, caja_abierta):
    """Con stock en tienda debe agregar al vale, no modal a pedido."""
    p = productos_con_stock[3]
    old = p.codigo_barra
    scan_code = f'88877766{(int(p.id) % 100000):05d}'
    master_code = scan_code + '0'
    p.codigo_barra = master_code
    p.precio_venta_sd = 1990
    aid_t = m.id_almacen_tienda()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 1)
    db.session.commit()
    for dv in m.DetalleVenta.query.filter_by(id_producto=p.id).all():
        v = m.Venta.query.get(dv.id_venta)
        if v and (v.estado or '').strip() in ('Pendiente', 'Abierta'):
            db.session.delete(dv)
    db.session.commit()
    try:
        r = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': scan_code},
            content_type='application/json',
        )
        data = r.get_json()
        assert r.status_code == 200, data
        assert data.get('ok') is True
        assert data.get('error') != 'ofrecer_apedido'
    finally:
        p.codigo_barra = old
        db.session.commit()


@pytest.mark.smoke
def test_api_escanear_ofrecer_apedido_sin_stock(app_client, productos_con_stock, caja_abierta):
    p = productos_con_stock[4]
    old = p.codigo_barra
    scan_code = f'99988877{(int(p.id) % 100000):05d}'
    master_code = scan_code + '0'
    p.codigo_barra = master_code
    p.precio_venta_sd = 2500
    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 0)
    if aid_b:
        m.fijar_stock_almacen(p.id, aid_b, 0)
    db.session.commit()
    # Quitar líneas pendientes previas del mismo producto (re-ejecución QA).
    for dv in m.DetalleVenta.query.filter_by(id_producto=p.id).all():
        v = m.Venta.query.get(dv.id_venta)
        if v and (v.estado or '').strip() in ('Pendiente', 'Abierta'):
            db.session.delete(dv)
    db.session.commit()
    try:
        r = app_client.post(
            '/api/pos/escanear-agregar',
            json={'codigo': scan_code},
            content_type='application/json',
        )
        data = r.get_json()
        assert r.status_code == 409, data
        assert data.get('error') == 'ofrecer_apedido'
        assert data.get('producto', {}).get('id') == p.id
        assert data.get('codigo_homologado') is True

        r2 = app_client.post(
            '/api/pos/escanear-agregar',
            json={'producto_id': p.id, 'a_pedido': True},
            content_type='application/json',
        )
        if r2.status_code == 409 and r2.get_json().get('error') == 'en_vale_pendiente':
            pytest.skip('vale pendiente previo en QA')
        assert r2.status_code == 200, r2.get_json()
        assert r2.get_json().get('ok') is True
    finally:
        p.codigo_barra = old
        db.session.commit()
