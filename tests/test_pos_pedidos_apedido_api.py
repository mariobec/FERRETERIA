"""API bandeja pedidos a pedido (ventas_a_pedido) en POS."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

import app as m
from services.pos_compromiso_entrega_service import persistir_ventas_a_pedido
from services.pos_pedidos_a_pedido_service import actualizar_estado_pedido
from tests.conftest import QA_USER, db


@pytest.mark.happy_path
def test_api_pedidos_apedido_lista_y_estado(app_client, productos_con_stock, caja_abierta, cliente_final):
    m._asegurar_tabla_ventas_a_pedido()
    p = productos_con_stock[0]
    venta = m.Venta(
        fecha=date.today(),
        monto_total=float(p.precio_venta or 0),
        usuario=QA_USER,
        estado='Pendiente',
        caja_id=caja_abierta.id,
        cliente_id=cliente_final.id,
    )
    db.session.add(venta)
    db.session.flush()
    det = m.DetalleVenta(
        id_venta=venta.id,
        id_producto=p.id,
        cantidad=1,
        precio_unitario=p.precio_venta,
        subtotal=float(p.precio_venta or 0),
        a_pedido=True,
    )
    db.session.add(det)
    db.session.commit()

    fecha_iso = (date.today() + timedelta(days=5)).isoformat()
    persistir_ventas_a_pedido(
        venta,
        {
            'fecha_entrega_prometida': fecha_iso,
            'compromiso_retiro_tienda': '1',
            'notificar_whatsapp': '1',
            'telefono_notificacion': '+56987654321',
        },
        QA_USER,
    )
    db.session.commit()
    rec = m.VentaAPedido.query.filter_by(detalle_venta_id=det.id).first()
    assert rec is not None

    r = app_client.get('/api/pos/pedidos-apedido')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['resumen']['total'] >= 1
    ids = [it['id'] for it in data['items']]
    assert rec.id in ids

    r2 = app_client.post(
        f'/api/pos/pedidos-apedido/{rec.id}/estado',
        json={'estado': 'listo'},
    )
    assert r2.status_code == 200
    db.session.expire_all()
    rec2 = m.VentaAPedido.query.get(rec.id)
    assert rec2.estado_entrega == 'listo'


def test_actualizar_estado_pedido_rechaza_invalido(app_ctx, productos_con_stock, caja_abierta, cliente_final):
    m._asegurar_tabla_ventas_a_pedido()
    p = productos_con_stock[0]
    venta = m.Venta(
        fecha=date.today(),
        monto_total=1000.0,
        usuario=QA_USER,
        estado='Pendiente',
        caja_id=caja_abierta.id,
        cliente_id=cliente_final.id,
    )
    db.session.add(venta)
    db.session.flush()
    det = m.DetalleVenta(
        id_venta=venta.id,
        id_producto=p.id,
        cantidad=1,
        precio_unitario=1000,
        subtotal=1000,
        a_pedido=True,
    )
    db.session.add(det)
    db.session.commit()
    persistir_ventas_a_pedido(venta, {'fecha_entrega_prometida': date.today().isoformat()}, QA_USER)
    db.session.commit()
    rec = m.VentaAPedido.query.filter_by(detalle_venta_id=det.id).first()
    ok, msg = actualizar_estado_pedido(rec.id, 'entregado', QA_USER)
    assert ok is True
    ok2, _ = actualizar_estado_pedido(rec.id, 'listo', QA_USER)
    assert ok2 is False
