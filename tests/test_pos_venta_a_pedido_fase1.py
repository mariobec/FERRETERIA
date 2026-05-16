"""Fase 1 POS venta en verde: agregar a_pedido y emitir vale sin bloqueo de stock."""
from __future__ import annotations

from datetime import datetime

import pytest

import app as m
from services import stock_service
from tests.conftest import QA_USER, db
from tests.test_routes_criticas import _ensure_caja_abierta


@pytest.mark.happy_path
def test_consumo_agrupado_omite_lineas_a_pedido(app_ctx, productos_con_stock, caja_abierta, cliente_final):
    p1, p2 = productos_con_stock[0], productos_con_stock[1]
    aid = m.id_almacen_tienda()
    if aid:
        m.fijar_stock_almacen(p1.id, aid, 0)
        m.fijar_stock_almacen(p2.id, aid, 5)
        db.session.commit()

    venta = m.Venta(
        fecha=datetime.now(),
        monto_total=0,
        usuario=QA_USER,
        estado='Abierta',
        caja_id=caja_abierta.id,
        cliente_id=cliente_final.id,
    )
    db.session.add(venta)
    db.session.flush()
    db.session.add(
        m.DetalleVenta(
            id_venta=venta.id,
            id_producto=p1.id,
            cantidad=3,
            precio_unitario=p1.precio_venta,
            subtotal=3 * p1.precio_venta,
            a_pedido=True,
        )
    )
    db.session.add(
        m.DetalleVenta(
            id_venta=venta.id,
            id_producto=p2.id,
            cantidad=1,
            precio_unitario=p2.precio_venta,
            subtotal=p2.precio_venta,
            a_pedido=False,
        )
    )
    db.session.commit()

    agrupado = stock_service.consumo_tienda_agrupado_por_producto(venta)
    assert p1.id not in agrupado

    faltantes = stock_service.venta_validar_stock_tienda(venta)
    assert not any((p1.nombre or '') in (msg or '') for msg in faltantes)


@pytest.mark.happy_path
def test_finalizar_venta_con_solo_linea_a_pedido(app_client, productos_con_stock):
    _ensure_caja_abierta()
    p = productos_con_stock[4]
    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 0)
    if aid_b:
        m.fijar_stock_almacen(p.id, aid_b, 0)
    db.session.commit()

    app_client.get('/punto_venta')
    r_add = app_client.post(
        '/api/pos/escanear-agregar',
        json={'producto_id': p.id, 'a_pedido': True},
        content_type='application/json',
    )
    if r_add.status_code == 409 and r_add.get_json().get('error') == 'en_vale_pendiente':
        pytest.skip('Producto bloqueado por vale pendiente previo en QA')
    assert r_add.status_code == 200, r_add.get_json()
    body = r_add.get_json()
    assert body.get('ok') is True
    assert body.get('a_pedido') is True

    vid = body.get('venta_id')
    det = m.DetalleVenta.query.filter_by(id_venta=vid, id_producto=p.id).first()
    assert det is not None
    assert bool(getattr(det, 'a_pedido', False)) is True

    from services.pos_compromiso_entrega_service import fecha_entrega_estimada

    rv = app_client.post(
        '/finalizar_venta',
        data={
            'cliente_final': '1',
            'punto_retiro': 'Tienda',
            'compromiso_confirmado': '1',
            'fecha_entrega_prometida': fecha_entrega_estimada().isoformat(),
            'compromiso_retiro_tienda': '1',
        },
        follow_redirects=False,
    )
    assert rv.status_code in (200, 302), (rv.status_code, rv.get_data(as_text=True)[:500])
    venta = m.Venta.query.get(vid)
    assert venta is not None
    assert venta.estado == 'Pendiente'
