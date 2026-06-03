"""Bandeja e-commerce — pedidos PED-WEB / Maylen-Web."""
import pytest

from services import ecommerce_pedidos_service as ecom
from services.vitrina_tienda_service import ASISTENTE_USUARIO_WEB, codigo_pedido_web


@pytest.mark.smoke
def test_ecommerce_bandeja_lista_pedido_maylen_web(app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[0]
    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=f'{ASISTENTE_USUARIO_WEB} (Nombre: QA; Tel: 912345678)',
        monto_total=float(p.precio_venta or 1990),
        punto_retiro='Tienda',
        caja_id=caja_abierta.id,
        cliente_id=None,
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
    v.bodega_preparacion_estado = 'PENDIENTE'
    db.session.commit()

    assert ecom.es_pedido_web(v)
    rows = ecom.listar_pedidos_web(estado='ACTIVOS')
    ids = {int(x.id) for x in rows}
    assert int(v.id) in ids
    cnt = ecom.contadores_bandeja()
    assert cnt['total'] >= 1
    assert codigo_pedido_web(int(v.id)).startswith('PED-WEB-')


@pytest.mark.smoke
def test_ecommerce_bandeja_http(app_client, app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[1]
    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=ASISTENTE_USUARIO_WEB,
        monto_total=5000,
        punto_retiro='Tienda',
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=p.id,
            cantidad=2,
            precio_unitario=2500,
            subtotal=5000,
        )
    )
    v.bodega_preparacion_estado = 'PENDIENTE'
    db.session.commit()

    r = app_client.get('/ecommerce/pedidos')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert codigo_pedido_web(int(v.id)) in body
    assert 'PED-WEB' in body


@pytest.mark.smoke
def test_parse_contacto_pedido_web():
    d = ecom.parse_contacto_pedido_web(f'{ASISTENTE_USUARIO_WEB} (Nombre: Juan; Tel: 912345678)')
    assert d['nombre'] == 'Juan'
    assert '912345678' in d['telefono']
    d_legacy = ecom.parse_contacto_liz_web('Liz-Web (Nombre: Ana; Tel: 911111111)')
    assert d_legacy['nombre'] == 'Ana'


@pytest.mark.smoke
def test_anular_pedido_web(app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[0]
    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=ASISTENTE_USUARIO_WEB,
        monto_total=float(p.precio_venta or 1000),
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=p.id,
            cantidad=1,
            precio_unitario=int(p.precio_venta or 1000),
            subtotal=int(p.precio_venta or 1000),
        )
    )
    db.session.commit()
    res = ecom.anular_pedido_web(v.id, motivo='Test QA', operador='QA')
    assert res.get('ok') is True
    db.session.refresh(v)
    assert v.estado == 'Anulada'


@pytest.mark.smoke
def test_api_ecommerce_pedidos(app_client, app_ctx, productos_con_stock, caja_abierta):
    from app import Venta, db

    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=ASISTENTE_USUARIO_WEB,
        monto_total=1000,
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    v.bodega_preparacion_estado = 'PENDIENTE'
    db.session.commit()

    r = app_client.get('/api/ecommerce/pedidos')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'contadores' in data
    assert 'metricas' in data


@pytest.mark.smoke
def test_timeline_pedido(app_ctx, productos_con_stock, caja_abierta):
    from app import Venta, db

    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=ASISTENTE_USUARIO_WEB,
        monto_total=1000,
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    v.bodega_preparacion_estado = 'LISTO_RETIRO'
    db.session.commit()
    tl = ecom.timeline_pedido(v)
    assert any('Pedido creado en vitrina' in (e.get('titulo') or '') for e in tl)


@pytest.mark.smoke
def test_actualizar_estado_preparacion(app_ctx, productos_con_stock, caja_abierta):
    from app import DetalleVenta, Venta, db

    p = productos_con_stock[2]
    v = Venta(
        estado='Pendiente',
        metodo_pago=None,
        usuario=f'{ASISTENTE_USUARIO_WEB} (Nombre: Prep QA; Tel: 900000001)',
        monto_total=float(p.precio_venta or 1000),
        caja_id=caja_abierta.id,
    )
    db.session.add(v)
    db.session.flush()
    db.session.add(
        DetalleVenta(
            id_venta=v.id,
            id_producto=p.id,
            cantidad=1,
            precio_unitario=int(p.precio_venta or 1000),
            subtotal=int(p.precio_venta or 1000),
        )
    )
    v.bodega_preparacion_estado = 'PENDIENTE'
    db.session.commit()

    res = ecom.actualizar_estado_preparacion(v.id, 'preparar', operador='QA')
    assert res.get('ok') is True
    db.session.refresh(v)
    assert (v.bodega_preparacion_estado or '').upper() == 'EN_PREPARACION'

    res2 = ecom.actualizar_estado_preparacion(v.id, 'listo_retiro', operador='QA')
    assert res2.get('ok') is True
    db.session.refresh(v)
    assert (v.bodega_preparacion_estado or '').upper() == 'LISTO_RETIRO'
