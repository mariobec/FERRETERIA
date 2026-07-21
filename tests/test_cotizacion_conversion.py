"""Smoke tests — asistente cotización → venta POS."""
from datetime import date, datetime, timedelta

import pytest

import app as m


def _crear_cotizacion_qa(producto, cantidad=2, descuento_global=0):
    neto = m._precio_neto_cotizacion_desde_catalogo(
        float(producto.precio_venta_sd or producto.precio_venta or 0)
    )
    cot = m.Cotizacion(
        numero=m._siguiente_numero_cotizacion(),
        fecha=datetime.utcnow(),
        validez_dias=15,
        fecha_vencimiento=date.today() + timedelta(days=15),
        cliente_nombre='TEST Cot Cliente',
        cliente_rut='11.111.111-1',
        estado='Vigente',
        descuento_global=float(descuento_global),
        usuario_creador='__qa_runner__',
    )
    m.db.session.add(cot)
    m.db.session.flush()
    sub = m._subtotal_linea_cotizacion_clp(cantidad, neto, 0)
    det = m.CotizacionDetalle(
        cotizacion_id=cot.id,
        producto_id=producto.id,
        codigo=producto.codigo_barra,
        nombre=producto.nombre,
        cantidad=float(cantidad),
        precio_unitario=float(neto),
        descuento=0.0,
        subtotal=float(sub),
    )
    m.db.session.add(det)
    neto_t, iva_t, total_t = m._calcular_totales_cotizacion(cot.detalles, cot.descuento_global)
    cot.neto = neto_t
    cot.iva = iva_t
    cot.monto_total = total_t
    m.db.session.commit()
    return cot


def _payload_desde_cot(cot):
    lineas = []
    for d in cot.detalles:
        lineas.append({
            'detalle_id': d.id,
            'accion': 'incluir',
            'cantidad': float(d.cantidad or 1),
            'precio_unitario': float(d.precio_unitario or 0),
            'descuento': float(d.descuento or 0),
            'a_pedido': False,
        })
    return {
        'modo': 'pos',
        'modo_proyecto': False,
        'confirmacion_cliente': True,
        'lineas': lineas,
    }


@pytest.mark.smoke
class TestCotizacionConversion:
    def test_conversion_preview(self, app_client, productos_con_stock, caja_abierta):
        cot = _crear_cotizacion_qa(productos_con_stock[0])
        r = app_client.get(f'/api/cotizaciones/{cot.id}/conversion-preview')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert len(data.get('lineas') or []) == 1
        assert data['lineas'][0].get('stock_ok') is True

    def test_conversion_crea_venta_abierta_sin_marcar_convertida(
        self, app_client, productos_con_stock, caja_abierta
    ):
        cot = _crear_cotizacion_qa(productos_con_stock[1])
        payload = _payload_desde_cot(cot)
        r = app_client.post(
            f'/api/cotizaciones/{cot.id}/convertir',
            json=payload,
            headers={'Accept': 'application/json'},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        venta_id = data.get('venta_id')
        assert venta_id

        m.db.session.expire_all()
        cot_db = m.Cotizacion.query.get(cot.id)
        assert (cot_db.estado or '') != 'Convertida'
        assert cot_db.estado == 'Aceptada'
        assert cot_db.venta_id == venta_id

        venta = m.Venta.query.get(venta_id)
        assert (venta.estado or '') == 'Abierta'
        assert venta.cotizacion_origen_id == cot.id
        assert len(list(venta.detalles or [])) == 1

    def test_marcar_convertida_al_emitir_vale(self, app_client, productos_con_stock, caja_abierta):
        from services.cotizacion_venta_service import marcar_cotizacion_convertida_al_emitir_vale

        cot = _crear_cotizacion_qa(productos_con_stock[2])
        venta = m.Venta(
            usuario='__qa_runner__',
            estado='Pendiente',
            monto_total=1000,
            caja_id=caja_abierta.id,
            cotizacion_origen_id=cot.id,
        )
        m.db.session.add(venta)
        cot.venta_id = venta.id
        cot.estado = 'Aceptada'
        m.db.session.commit()

        marcar_cotizacion_convertida_al_emitir_vale(venta)
        m.db.session.commit()

        m.db.session.expire_all()
        cot_db = m.Cotizacion.query.get(cot.id)
        assert cot_db.estado == 'Convertida'

    def test_linea_sin_stock_requiere_a_pedido(
        self, app_client, productos_con_stock, caja_abierta
    ):
        cot = _crear_cotizacion_qa(productos_con_stock[0], cantidad=99999)
        payload = _payload_desde_cot(cot)
        r = app_client.post(f'/api/cotizaciones/{cot.id}/convertir', json=payload)
        assert r.status_code == 400
        data = r.get_json()
        assert data.get('ok') is False

        payload['lineas'][0]['a_pedido'] = True
        r2 = app_client.post(f'/api/cotizaciones/{cot.id}/convertir', json=payload)
        assert r2.status_code == 200
        assert r2.get_json().get('ok') is True


@pytest.mark.smoke
def test_gmail_compose_url_cotizacion(app_client, productos_con_stock):
    cot = _crear_cotizacion_qa(productos_con_stock[0])
    cot.cliente_correo = 'cliente.qa@example.com'
    m.db.session.commit()
    url = m._url_gmail_compose_cotizacion(cot)
    assert 'mail.google.com/mail/' in url
    assert 'view=cm' in url
    assert 'cliente.qa' in url
    r = app_client.get(f'/cotizaciones/{cot.id}/gmail', follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location') or ''
    assert 'mail.google.com' in loc
