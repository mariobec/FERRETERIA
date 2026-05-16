"""Fase 2 POS: modal compromiso de entrega y tabla ventas_a_pedido."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

import app as m
from services.pos_compromiso_entrega_service import (
    fecha_entrega_estimada,
    formatear_fecha_entrega_cl,
    persistir_ventas_a_pedido,
    sumar_dias_habiles,
)
from tests.conftest import QA_USER, db
from tests.test_routes_criticas import _ensure_caja_abierta


def test_sumar_dias_habiles_salta_fin_de_semana():
    # Viernes 2026-05-15 + 1 hábil = lunes 2026-05-18
    base = date(2026, 5, 15)
    assert base.weekday() == 4
    assert sumar_dias_habiles(base, 1) == date(2026, 5, 18)


def test_formatear_fecha_entrega_cl():
    f = date(2026, 5, 20)
    txt = formatear_fecha_entrega_cl(f)
    assert 'mayo' in txt.lower()
    assert '20' in txt


@pytest.mark.happy_path
def test_persistir_ventas_a_pedido_crea_filas(app_ctx, productos_con_stock, caja_abierta, cliente_final):
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
        cantidad=2,
        precio_unitario=p.precio_venta,
        subtotal=2 * float(p.precio_venta or 0),
        a_pedido=True,
    )
    db.session.add(det)
    db.session.commit()

    fecha_iso = (date.today() + timedelta(days=7)).isoformat()
    form = {
        'fecha_entrega_prometida': fecha_iso,
        'compromiso_retiro_tienda': '1',
        'compromiso_despacho': '0',
        'notificar_whatsapp': '1',
        'telefono_notificacion': '+56912345678',
    }
    creados = persistir_ventas_a_pedido(venta, form, QA_USER)
    db.session.commit()
    assert len(creados) == 1
    rec = m.VentaAPedido.query.filter_by(detalle_venta_id=det.id).first()
    assert rec is not None
    assert rec.estado_entrega == 'por_pedir'
    assert rec.cantidad == 2
    assert rec.notificar_whatsapp is True
    assert rec.telefono_notificacion == '+56912345678'
    assert rec.fecha_promesa == date.fromisoformat(fecha_iso)


@pytest.mark.happy_path
def test_finalizar_venta_a_pedido_persiste_compromiso(app_client, productos_con_stock):
    m._asegurar_tabla_ventas_a_pedido()
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
    vid = r_add.get_json().get('venta_id')
    fecha_prom = fecha_entrega_estimada().isoformat()

    rv = app_client.post(
        '/finalizar_venta',
        data={
            'cliente_final': '1',
            'punto_retiro': 'Tienda',
            'compromiso_confirmado': '1',
            'fecha_entrega_prometida': fecha_prom,
            'compromiso_retiro_tienda': '1',
            'compromiso_despacho': '0',
            'notificar_whatsapp': '0',
        },
        follow_redirects=False,
    )
    assert rv.status_code in (200, 302), (rv.status_code, rv.get_data(as_text=True)[:500])
    venta = m.Venta.query.get(vid)
    assert venta is not None
    assert venta.estado == 'Pendiente'
    recs = m.VentaAPedido.query.filter_by(venta_id=vid).all()
    assert len(recs) >= 1
    assert all(r.estado_entrega == 'por_pedir' for r in recs)


@pytest.mark.happy_path
def test_finalizar_venta_a_pedido_sin_compromiso_rechaza(app_client, productos_con_stock):
    m._asegurar_tabla_ventas_a_pedido()
    _ensure_caja_abierta()
    p = productos_con_stock[3]
    aid_t = m.id_almacen_tienda()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 0)
    db.session.commit()

    app_client.get('/punto_venta')
    r_add = app_client.post(
        '/api/pos/escanear-agregar',
        json={'producto_id': p.id, 'a_pedido': True},
        content_type='application/json',
    )
    if r_add.status_code == 409:
        pytest.skip('Producto bloqueado por vale pendiente previo en QA')
    assert r_add.status_code == 200
    vid = r_add.get_json().get('venta_id')

    rv = app_client.post(
        '/finalizar_venta',
        data={'cliente_final': '1', 'punto_retiro': 'Tienda'},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    venta = m.Venta.query.get(vid)
    assert venta.estado == 'Abierta'
    assert m.VentaAPedido.query.filter_by(venta_id=vid).count() == 0
