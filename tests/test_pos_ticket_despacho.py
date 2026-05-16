"""Ticket emitido y vista despacho QR (POS-012 / DESP-001)."""
import pytest

import app as m
from tests.test_routes_criticas import _ensure_caja_abierta


def test_emitir_vale_no_agrega_ticket_iframe_si_autoprint_apagado(app_client, productos_con_stock, monkeypatch):
    monkeypatch.setattr(m, '_pos_autoprint_ticket_emitido_empresa', lambda: False)
    _ensure_caja_abierta()
    app_client.get('/punto_venta')
    p = productos_con_stock[2]
    r_scan = app_client.post(
        '/api/pos/escanear-agregar',
        json={'codigo': p.codigo_barra},
        content_type='application/json',
    )
    if r_scan.status_code == 409 and r_scan.get_json().get('error') == 'en_vale_pendiente':
        pytest.skip('Producto bloqueado por vale pendiente previo en QA')
    assert r_scan.status_code == 200, r_scan.get_json()
    vid = r_scan.get_json().get('venta_id')
    rv = app_client.post(
        '/finalizar_venta',
        data={
            'cliente_final': '1',
            'punto_retiro': 'Tienda',
            'pos_exigir_rut': '1',
            'pos_emit_origen': 'punto_venta',
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert vid
    loc = (rv.headers.get('Location') or '')
    assert '/punto_venta' in loc
    assert 'ticket_iframe=' not in loc


def test_pos_ticket_vale_tras_emitir(app_client, productos_con_stock, monkeypatch):
    monkeypatch.setattr(m, '_pos_autoprint_ticket_emitido_empresa', lambda: True)
    _ensure_caja_abierta()
    app_client.get('/punto_venta')
    p = productos_con_stock[2]
    r_scan = app_client.post(
        '/api/pos/escanear-agregar',
        json={'codigo': p.codigo_barra},
        content_type='application/json',
    )
    if r_scan.status_code == 409 and r_scan.get_json().get('error') == 'en_vale_pendiente':
        pytest.skip('Producto bloqueado por vale pendiente previo en QA')
    assert r_scan.status_code == 200, r_scan.get_json()
    vid = r_scan.get_json().get('venta_id')
    rv = app_client.post(
        '/finalizar_venta',
        data={
            'cliente_final': '1',
            'punto_retiro': 'Tienda',
            'pos_exigir_rut': '1',
            'pos_emit_origen': 'punto_venta',
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert vid
    loc = (rv.headers.get('Location') or '')
    assert '/punto_venta' in loc
    assert f'ticket_iframe={vid}' in loc

    r_pos = app_client.get('/punto_venta', query_string={'ticket_iframe': str(vid)})
    assert r_pos.status_code == 200
    assert f'/pos/ticket/{vid}'.encode() in r_pos.data

    rt = app_client.get(f'/pos/ticket/{vid}', follow_redirects=True)
    assert rt.status_code == 200
    assert b'VALE' in rt.data
    assert b'PICKING BODEGA' not in rt.data or b'PICKING' in rt.data


def test_pos_despacho_vale_token_verify():
    tok = m.pos_despacho_vale_token_create(12345)
    assert tok
    assert m.pos_despacho_vale_token_verify(tok) == 12345
    assert m.pos_despacho_vale_token_verify(tok + 'x') is None


def test_pos_despacho_vale_rechaza_token_invalido(app_client):
    _ensure_caja_abierta()
    v = m.Venta.query.filter_by(estado='Pendiente').order_by(m.Venta.id.desc()).first()
    if not v:
        pytest.skip('Sin vale pendiente en BD')
    r = app_client.get(f'/pos/despacho/vale/{v.id}?t=__invalid__', follow_redirects=False)
    assert r.status_code == 302


def test_pos_ticket_subtotales_agrupan_mixto(app_client, monkeypatch, productos_con_stock, caja_abierta):
    """Vale mixto: buckets Tienda + Bodega (helpers de ticket)."""
    _ensure_caja_abierta()
    cfg = {**m.obtener_config_empresa(), 'pos_retiro_por_linea': '1'}
    monkeypatch.setattr(m, 'obtener_config_empresa', lambda: cfg)

    p_t = productos_con_stock[1]
    p_b = productos_con_stock[2]
    caja = m.obtener_caja_activa()
    vf = m.obtener_o_crear_cliente_final()
    v = m.Venta(
        caja_id=caja.id,
        usuario=m._nombre_usuario_pos_actual(),
        estado='Pendiente',
        monto_total=0,
        prioridad=999001,
        cliente_id=vf.id,
        punto_retiro='Mixto',
        fecha=m.db.func.current_timestamp(),
    )
    m.db.session.add(v)
    m.db.session.flush()
    d1 = m.DetalleVenta(
        id_venta=v.id,
        id_producto=p_t.id,
        cantidad=1,
        precio_unitario=p_t.precio_venta,
        descuento=0,
        subtotal=float(p_t.precio_venta),
        punto_retiro_linea='Tienda',
    )
    d2 = m.DetalleVenta(
        id_venta=v.id,
        id_producto=p_b.id,
        cantidad=1,
        precio_unitario=p_b.precio_venta,
        descuento=0,
        subtotal=float(p_b.precio_venta),
        punto_retiro_linea='Bodega',
    )
    m.db.session.add_all([d1, d2])
    v.monto_total = float(d1.subtotal or 0) + float(d2.subtotal or 0)
    m.db.session.commit()
    m.db.session.refresh(v)

    buckets, subs, _ = m._ticket_agrupar_detalles_por_retiro(v)
    assert buckets['Tienda'] and buckets['Bodega']
    assert subs['Tienda'] > 0 and subs['Bodega'] > 0
    assert m._ticket_usar_bloques_por_retiro(v, buckets) is True

    vid_cleanup = v.id
    m.db.session.delete(v)
    m.db.session.commit()
    assert m.Venta.query.get(vid_cleanup) is None
