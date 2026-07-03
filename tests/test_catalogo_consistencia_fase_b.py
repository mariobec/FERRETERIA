"""Smoke — coherencia catálogo/stock Fase B (POS, enrolador, vitrina, dashboard)."""
from __future__ import annotations

import pytest

import app as m
from services.catalogo_resolucion_codigo_service import buscar_producto_por_codigo_escaneado
from services.producto_codigo_escaneo_service import asegurar_tabla_producto_codigo_escaneo
from services.stock_consulta_service import contadores_stock_tienda_activos, stock_tienda_por_ids
from tests.conftest import db


@pytest.fixture
def _tabla_alias(app_ctx):
    asegurar_tabla_producto_codigo_escaneo(m.app, db)
    yield


@pytest.mark.smoke
def test_enrol_y_pos_misma_resolucion_codigo(productos_con_stock, _tabla_alias):
    """Enrolador delega en la misma cadena que POS (alias escaneo)."""
    from services.producto_codigo_escaneo_service import vincular_codigo_a_producto

    p = productos_con_stock[0]
    scan = f'ENROLCOH{(int(p.id) % 100000):06d}'
    vincular_codigo_a_producto(
        scan,
        p.id,
        Producto=m.Producto,
        ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
        db=db,
        app=m.app,
        origen='test',
    )
    db.session.commit()
    pos = m._pos_buscar_producto_por_codigo(scan)
    enrol = m._enrol_buscar_producto_por_codigo(scan)
    assert pos is not None and enrol is not None
    assert int(pos.id) == int(enrol.id) == int(p.id)


@pytest.mark.smoke
def test_api_buscar_producto_usa_resolucion_pos(app_client, productos_con_stock, _tabla_alias):
    p = productos_con_stock[1]
    scan = f'MOBQA{(int(p.id) % 1000000):07d}'
    from services.producto_codigo_escaneo_service import vincular_codigo_a_producto

    vincular_codigo_a_producto(
        scan,
        p.id,
        Producto=m.Producto,
        ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
        db=db,
        app=m.app,
    )
    db.session.commit()
    r = app_client.get(f'/api/buscar_producto/{scan}')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('status') == 'success'
    assert int(data['id']) == int(p.id)
    assert 'stock_tienda' in data
    assert data['stock'] == data['stock_tienda']


@pytest.mark.smoke
def test_enrol_buscar_maestro_solo_activos(app_client, productos_con_stock):
    p = productos_con_stock[0]
    was_active = bool(p.activo)
    try:
        p.activo = False
        db.session.commit()
        token = (p.nombre or '')[:6]
        r = app_client.get(
            f'/api/enrolamiento/buscar_maestro?q={token}&origen=enrolamiento&filtro_pos=catalogo'
        )
        assert r.status_code == 200
        items = r.get_json().get('items') or []
        ids = {int(it['id']) for it in items}
        assert int(p.id) not in ids
    finally:
        p.activo = was_active
        db.session.commit()


@pytest.mark.smoke
def test_enrol_buscar_maestro_incluye_stock_tienda(app_client, productos_con_stock):
    p = productos_con_stock[0]
    token = (p.nombre or '')[:6]
    r = app_client.get(
        f'/api/enrolamiento/buscar_maestro?q={token}&origen=enrolamiento&filtro_pos=catalogo'
    )
    assert r.status_code == 200
    items = r.get_json().get('items') or []
    hit = next((it for it in items if int(it['id']) == int(p.id)), None)
    assert hit is not None
    assert 'stock_tienda' in hit


@pytest.mark.smoke
def test_stock_consulta_tienda_coincide_pos(productos_con_stock):
    p = productos_con_stock[0]
    st_map = stock_tienda_por_ids([p.id])
    st_pos = int(m.stock_disponible_venta_tienda(p) or 0)
    assert int(st_map.get(p.id, -1)) == st_pos


@pytest.mark.smoke
def test_contadores_stock_tienda_activos():
    cont = contadores_stock_tienda_activos(umbral_critico=5)
    assert cont['total_activos'] >= cont['con_stock'] + cont['sin_stock'] - 0  # partition
    assert cont['total_activos'] == cont['con_stock'] + cont['sin_stock']


@pytest.mark.smoke
def test_enrol_vincular_usa_alias_no_sobrescribe_maestro(app_client, productos_con_stock, _tabla_alias):
    """Vincular en enrolador debe crear alias (como POS), no pisar codigo_barra maestro."""
    from services.producto_codigo_escaneo_service import vincular_codigo_a_producto

    p = productos_con_stock[3]
    maestro_antes = (p.codigo_barra or '').strip()
    scan = f'ENROL-VIN-{(int(p.id) % 100000):05d}'
    ses = m.EnrolamientoTomaSesion(usuario='qa', id_almacen=m.id_almacen_tienda())
    db.session.add(ses)
    db.session.commit()

    r = app_client.post(
        '/api/enrolamiento/vincular',
        json={
            'sesion_id': ses.id,
            'producto_id': p.id,
            'codigo_barras': scan,
            'cantidad_inicial': 0,
        },
    )
    assert r.status_code == 200
    db.session.refresh(p)
    assert (p.codigo_barra or '').strip() == maestro_antes
    assert m._enrol_buscar_producto_por_codigo(scan) is not None
    assert int(m._enrol_buscar_producto_por_codigo(scan).id) == int(p.id)


@pytest.mark.smoke
def test_enrol_alta_manual_sin_codigo_barra(app_client, productos_con_stock):
    """Alta manual sin barra: código interno automático y vendible tras stock."""
    ses = m.EnrolamientoTomaSesion(usuario='qa', id_almacen=m.id_almacen_tienda())
    db.session.add(ses)
    db.session.commit()
    nombre = f'QA Sin Barra {ses.id}'
    r = app_client.post(
        '/api/enrolamiento/alta_manual',
        json={
            'sesion_id': ses.id,
            'nombre': nombre,
            'codigo_barras': '',
            'precio_venta': 3990,
            'precio_compra': 2100,
            'cantidad_inicial': 3,
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    prod = body.get('producto') or {}
    assert prod.get('codigo_barra') in (None, '',)
    assert (prod.get('codigo_interno') or '').strip()
    p = m.Producto.query.filter_by(nombre=nombre).first()
    assert p is not None
    assert not (p.codigo_barra or '').strip()
    assert (p.codigo_interno or '').strip()
    assert int(m.stock_tienda_por_producto_ids([p.id]).get(p.id, 0) or 0) == 3


@pytest.mark.smoke
def test_enrol_alta_manual_asigna_precio_venta_sd(app_client, productos_con_stock):
    """Alta manual debe dejar producto vendible en POS (precio_venta_sd)."""
    ses = m.EnrolamientoTomaSesion(usuario='qa', id_almacen=m.id_almacen_tienda())
    db.session.add(ses)
    db.session.commit()
    codigo = f'ENROL-ALTA-{ses.id}'
    r = app_client.post(
        '/api/enrolamiento/alta_manual',
        json={
            'sesion_id': ses.id,
            'nombre': 'QA Enrol Alta Manual',
            'codigo_barras': codigo,
            'precio_venta': 5990,
            'precio_compra': 3000,
            'cantidad_inicial': 0,
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    prod = body.get('producto') or {}
    assert float(prod.get('precio_venta_sd') or 0) == 5990.0
    assert float(prod.get('precio_efectivo_pos') or 0) == 5990.0
    assert prod.get('vendible_pos') is False  # sin stock tienda aún
    p = m.Producto.query.filter_by(codigo_barra=codigo).first()
    assert p is not None
    assert float(m.precio_efectivo_pos_producto(p) or 0) == 5990.0


@pytest.mark.smoke
def test_enrol_buscar_maestro_usa_motor_pos(app_client, productos_con_stock):
    """buscar_maestro delega en _buscar_productos_json (mismo motor que POS)."""
    p = productos_con_stock[0]
    token = (p.nombre or '')[:6]
    r_enrol = app_client.get(
        f'/api/enrolamiento/buscar_maestro?q={token}&origen=enrolamiento&filtro_pos=catalogo'
    )
    assert r_enrol.status_code == 200
    body = r_enrol.get_json()
    assert body.get('ok') is True
    assert body.get('meta', {}).get('filtro_pos') == 'catalogo'
    ids_enrol = {int(it['id']) for it in (body.get('items') or [])}
    assert int(p.id) in ids_enrol

    data_pos = m._buscar_productos_json(token, filtro_pos='catalogo', enriquecido=True, out_lim=40)
    ids_pos = {int(r.get('producto_id') or 0) for r in (data_pos.get('results') or [])}
    assert int(p.id) in ids_pos
    hit = next(it for it in body['items'] if int(it['id']) == int(p.id))
    assert 'semaforo' in hit
    assert 'stock_tienda' in hit


@pytest.mark.smoke
def test_servicio_resolucion_codigo_equivalente_pos(productos_con_stock):
    p = productos_con_stock[2]
    codigo = (p.codigo_barra or '').strip()
    if not codigo:
        pytest.skip('sin codigo_barra')
    via_svc = buscar_producto_por_codigo_escaneado(
        codigo,
        Producto=m.Producto,
        ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
        db=db,
        app=m.app,
        buscar_chilemat_fn=m._producto_por_codigo_chilemat_escaneo,
    )
    via_pos = m._pos_buscar_producto_por_codigo(codigo)
    assert via_svc is not None and via_pos is not None
    assert int(via_svc.id) == int(via_pos.id)
