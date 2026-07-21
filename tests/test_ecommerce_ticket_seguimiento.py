"""Tickets ecom Pagado + seguimiento público PED-WEB."""
import pytest

from services import ecommerce_pedidos_service as ecom
from services.vitrina_tienda_service import (
    ASISTENTE_USUARIO_WEB,
    TIENDA_SLUG_SD,
    codigo_pedido_web,
    parse_codigo_pedido_web,
    token_seguimiento_pedido,
    validar_token_seguimiento,
)


@pytest.mark.smoke
def test_token_seguimiento_pedido_web():
    assert parse_codigo_pedido_web('PED-WEB-003527') == 3527
    assert parse_codigo_pedido_web('mal') is None
    tok = token_seguimiento_pedido(3527)
    assert len(tok) >= 16
    assert validar_token_seguimiento(3527, tok) is True
    assert validar_token_seguimiento(3527, '00000000000000000000') is False
    assert codigo_pedido_web(3527) == 'PED-WEB-003527'


@pytest.mark.smoke
def test_detalle_pedido_pagado_muestra_ticket_cobro(app_client, app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[0]
    v = Venta(
        estado='Pagado',
        metodo_pago='Webpay',
        usuario=f'{ASISTENTE_USUARIO_WEB} (Nombre: TicketQA; Tel: 911111111)',
        monto_total=float(p.precio_venta or 1990),
        punto_retiro='Tienda',
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=p.id,
            cantidad=1,
            precio_unitario=int(p.precio_venta or 1990),
            subtotal=int(p.precio_venta or 1990),
            punto_retiro_linea='Tienda',
        )
    )
    v.bodega_preparacion_estado = 'LISTO_RETIRO'
    db.session.commit()

    r = app_client.get(f'/ecommerce/pedidos/{v.id}')
    assert r.status_code == 200
    body = r.data.decode('utf-8', errors='ignore')
    assert f'/caja/vale_retiro/{v.id}' in body


@pytest.mark.smoke
def test_seguimiento_publico_pedido(app_client, app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[1]
    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=f'{ASISTENTE_USUARIO_WEB} (Nombre: SegQA; Tel: 922222222)',
        monto_total=float(p.precio_venta or 2990),
        punto_retiro='Tienda',
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=p.id,
            cantidad=1,
            precio_unitario=int(p.precio_venta or 2990),
            subtotal=int(p.precio_venta or 2990),
        )
    )
    v.bodega_preparacion_estado = 'EN_PREPARACION'
    db.session.commit()

    codigo = codigo_pedido_web(int(v.id))
    tok = token_seguimiento_pedido(int(v.id))
    r_bad = app_client.get(f'/tienda/{TIENDA_SLUG_SD}/pedido/{codigo}')
    assert r_bad.status_code == 403
    r = app_client.get(f'/tienda/{TIENDA_SLUG_SD}/pedido/{codigo}?t={tok}')
    assert r.status_code == 200
    assert codigo.encode() in r.data
    assert ecom.es_pedido_web(v)
    # Pendiente → QR de seguimiento
    assert b'data:image/png;base64,' in r.data or b'QR' in r.data


@pytest.mark.smoke
def test_mensaje_whatsapp_pedido_pagado_incluye_codigo(app_ctx, productos_con_stock, caja_abierta):
    from app import Venta, db

    v = Venta(
        estado='Pagado',
        metodo_pago='Webpay',
        usuario=f'{ASISTENTE_USUARIO_WEB} (Nombre: WA QA; Tel: 933333333)',
        monto_total=1990,
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.commit()
    msg = ecom.mensaje_whatsapp_pedido_pagado(v, url_seguimiento='https://ejemplo.cl/seg', metodo_pago='Webpay')
    assert 'PED-WEB-' in msg
    assert 'https://ejemplo.cl/seg' in msg
    assert 'pago recibido' in msg.lower() or 'Pago' in msg
