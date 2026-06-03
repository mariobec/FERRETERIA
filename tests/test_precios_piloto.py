"""Smoke — carga manual precios piloto SD (precio_venta_sd)."""
import pytest

import app as m
from app import db
from services.precios_piloto_service import (
    aplicar_precio_venta_sd,
    detalle_informe_factura_piloto,
    guardar_carga_piloto_mostrador,
    guardar_precio_piloto,
    resumen_facturas_piloto,
    serializar_producto_precios_piloto,
    stats_precios_piloto,
)


@pytest.mark.smoke
def test_precios_piloto_pantalla_ok(app_client):
    r = app_client.get('/precios/piloto')
    assert r.status_code == 200
    assert b'Carga mostrador piloto SD' in r.data
    assert b'Precio venta SD' in r.data
    assert b'posBuscarManual' in r.data
    assert b'Operativo' in r.data
    assert b'precios-piloto-busqueda.js' in r.data
    assert b'precios-piloto-panel.js' in r.data
    import re
    assert re.search(
        rb'precios-piloto-panel\.js\?v=[^"]+"></script>',
        r.data,
    ), 'Etiqueta script panel mal cerrada (rompe init del buscador)'
    assert b'inpNumeroFacturaPiloto' in r.data
    assert b'inpNumeroGuiaPiloto' in r.data
    assert b'20260602-buscar-codigo' in r.data
    assert b'asegurarBusquedaPiloto' in r.data


def test_api_precios_piloto_buscar_codigo_barras_exacto(app_client, productos_con_stock):
    p = productos_con_stock[0]
    codigo = (p.codigo_barra or '').strip()
    assert len(codigo) >= 2
    r = app_client.get(
        f'/api/precios/piloto/buscar?q={codigo}&origen=precios_piloto&filtro_pos=catalogo'
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('meta', {}).get('match') == 'codigo_exacto' or p.id in [
        x.get('producto_id') for x in (data.get('results') or [])
    ]


@pytest.mark.smoke
def test_api_precios_piloto_buscar(app_client, productos_con_stock):
    p = productos_con_stock[0]
    codigo = p.codigo_barra
    r = app_client.get(f'/api/precios/piloto/buscar?q={codigo}&origen=precios_piloto&filtro_pos=catalogo')
    assert r.status_code == 200
    data = r.get_json()
    assert 'results' in data
    assert len(data['results']) >= 1
    assert data.get('meta', {}).get('match') == 'codigo_exacto'


@pytest.mark.smoke
def test_api_precios_piloto_buscar_codigo_inexistente(app_client):
    r = app_client.get(
        '/api/precios/piloto/buscar?q=9999999999999&origen=precios_piloto&filtro_pos=catalogo'
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('results') == []
    assert data.get('meta', {}).get('codigo_no_encontrado') is True


@pytest.mark.smoke
def test_api_precios_piloto_producto(app_client, productos_con_stock):
    p = productos_con_stock[0]
    r = app_client.get(f'/api/precios/piloto/producto/{p.id}')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['producto']['id'] == p.id
    assert data['producto']['precio_lista'] == pytest.approx(float(p.precio_venta or 0), abs=1)


@pytest.mark.smoke
def test_api_precios_piloto_guardar_bitacora(app_client, productos_con_stock, app_ctx):
    p = productos_con_stock[1]
    lista_antes = float(p.precio_venta or 0)
    p.precio_venta_sd = 1111
    db.session.commit()
    db.session.expire_all()
    antes = float(m.precio_efectivo_pos_producto(p) or 0)
    nuevo = 22222.0

    r = app_client.post(
        '/api/precios/piloto/guardar',
        json={
            'producto_id': p.id,
            'precio_venta': str(int(nuevo)),
            'motivo': 'QA piloto precios',
            'modo_stock': 'solo_precio',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data.get('sin_cambio') is not True
    assert float(data['precio_nuevo']) == pytest.approx(nuevo, abs=1)

    db.session.expire_all()
    p2 = m.Producto.query.get(p.id)
    assert float(m.precio_efectivo_pos_producto(p2)) == pytest.approx(nuevo, abs=1)
    assert float(p2.precio_venta or 0) == pytest.approx(lista_antes, abs=1)
    assert float(p2.precio_venta_sd or 0) == pytest.approx(nuevo, abs=1)

    db.session.rollback()
    ult_piloto = (
        m.BitacoraPilotoMostrador.query.filter_by(producto_id=p.id)
        .order_by(m.BitacoraPilotoMostrador.id.desc())
        .first()
    )
    assert ult_piloto is not None
    assert 'Piloto SD' in (ult_piloto.motivo or '')
    assert float(ult_piloto.precio_nuevo or 0) == pytest.approx(nuevo, abs=1)


@pytest.mark.smoke
def test_api_precios_piloto_guardar_factura_guia(app_client, productos_con_stock, app_ctx):
    p = productos_con_stock[3]
    nuevo = 18750.0
    r = app_client.post(
        '/api/precios/piloto/guardar',
        json={
            'producto_id': p.id,
            'precio_venta': str(int(nuevo)),
            'motivo': 'QA piloto factura guia',
            'modo_stock': 'solo_precio',
            'numero_factura': 'FAC-QA-998877',
            'numero_guia': 'GD-QA-112233',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data.get('numero_factura') == 'FAC-QA-998877'
    assert data.get('numero_guia') == 'GD-QA-112233'
    br = data.get('bitacora_row') or {}
    assert 'F FAC-QA-998877' in (br.get('stock') or '')

    ult = (
        m.BitacoraPilotoMostrador.query.filter_by(producto_id=p.id)
        .order_by(m.BitacoraPilotoMostrador.id.desc())
        .first()
    )
    assert ult is not None
    assert (ult.numero_factura or '').strip() == 'FAC-QA-998877'
    assert (ult.numero_guia or '').strip() == 'GD-QA-112233'


@pytest.mark.smoke
def test_precios_piloto_informe_facturas_pantalla(app_client, productos_con_stock, app_ctx):
    p = productos_con_stock[2]
    app_client.post(
        '/api/precios/piloto/guardar',
        json={
            'producto_id': p.id,
            'precio_venta': '15990',
            'motivo': 'QA informe factura',
            'modo_stock': 'solo_precio',
            'numero_factura': 'INF-QA-2026-001',
            'numero_guia': 'GD-INF-001',
        },
    )
    r = app_client.get('/precios/piloto/informe-facturas')
    assert r.status_code == 200
    assert b'Informe cargas piloto por factura' in r.data
    assert b'INF-QA-2026-001' in r.data

    rd = app_client.get('/precios/piloto/informe-facturas?factura=INF-QA-2026-001')
    assert rd.status_code == 200
    assert p.nombre.encode('utf-8') in rd.data or b'Detalle factura' in rd.data

    rc = app_client.get('/precios/piloto/informe-facturas.csv?factura=INF-QA-2026-001')
    assert rc.status_code == 200
    assert b'numero_factura' in rc.data
    assert b'INF-QA-2026-001' in rc.data


def test_resumen_y_detalle_informe_factura_servicio(app_ctx, productos_con_stock):
    p = productos_con_stock[4]
    guardar_carga_piloto_mostrador(
        producto_id=p.id,
        precio_nuevo=4200.0,
        motivo='QA servicio informe',
        usuario='QA',
        modo_stock='solo_precio',
        numero_factura='SRV-FAC-77',
        numero_guia='SRV-G-7',
    )
    db.session.commit()
    res = resumen_facturas_piloto(q='SRV-FAC')
    nums = [x['numero_factura'] for x in res['facturas']]
    assert 'SRV-FAC-77' in nums
    det = detalle_informe_factura_piloto('SRV-FAC-77')
    assert det is not None
    assert det['resumen']['lineas'] >= 1
    assert any(ln['producto_id'] == p.id for ln in det['lineas'])


def test_aplicar_precio_venta_sd_no_toca_lista(app_ctx, productos_con_stock):
    p = productos_con_stock[2]
    p.precio_venta = 10000
    p.precio_mayoreo = 5000
    p.precio_venta_sd = None
    db.session.flush()
    ef = aplicar_precio_venta_sd(p, 3500)
    assert ef == 3500
    assert float(p.precio_venta) == 10000
    assert float(p.precio_mayoreo) == 5000
    assert float(p.precio_venta_sd) == 3500


def test_precio_efectivo_pos_solo_sd(app_ctx, productos_con_stock):
    p = productos_con_stock[0]
    p.precio_venta = 99999
    p.precio_mayoreo = 88888
    p.precio_venta_sd = 1234
    db.session.flush()
    assert m.precio_efectivo_pos_producto(p) == 1234


def test_precio_efectivo_pos_sin_sd_es_cero(app_ctx, productos_con_stock):
    p = productos_con_stock[0]
    p.precio_venta = 99999
    p.precio_venta_sd = 0
    db.session.flush()
    assert m.precio_efectivo_pos_producto(p) == 0


def test_serializar_producto_precios_piloto(app_ctx, productos_con_stock):
    p = productos_con_stock[0]
    row = serializar_producto_precios_piloto(p)
    assert row['id'] == p.id
    assert 'precio_lista' in row
    assert 'precio_venta_sd' in row


def test_serializar_costo_incoherente(app_ctx, productos_con_stock):
    p = productos_con_stock[1]
    p.precio_compra = 50000
    p.precio_venta = 1490
    p.precio_mayoreo = 1490
    db.session.flush()
    row = serializar_producto_precios_piloto(p)
    assert row['costo_incoherente'] is True
    assert row['costo_alerta']
    assert row['precio_sd_sugerido'] == 1490


def test_stats_precios_piloto(app_ctx):
    s = stats_precios_piloto()
    assert s['total_activos'] >= 1
    assert s['sin_precio'] + s['con_precio'] >= 0


@pytest.mark.smoke
def test_guardar_piloto_stock_inicial(app_client, productos_con_stock, app_ctx):
    from services.precios_piloto_service import guardar_carga_piloto_mostrador

    p = productos_con_stock[3]
    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 2)
    if aid_b:
        m.fijar_stock_almacen(p.id, aid_b, 1)
    db.session.commit()

    res = guardar_carga_piloto_mostrador(
        producto_id=p.id,
        precio_nuevo=8888.0,
        motivo='QA stock piloto',
        usuario='QA',
        modo_stock='reemplazar',
        stock_tienda=11,
        stock_bodega=4,
        sector_ubicacion='Pasillo QA',
    )
    assert res.get('ok') is True
    assert res.get('stock', {}).get('tienda') == 11
    assert res.get('stock', {}).get('bodega') == 4

    res2 = guardar_carga_piloto_mostrador(
        producto_id=p.id,
        precio_nuevo=None,
        motivo='QA sumar sector',
        usuario='QA',
        modo_stock='sumar',
        stock_tienda=3,
        stock_bodega=0,
        sector_ubicacion='Estante B',
    )
    assert res2.get('ok') is True
    assert res2.get('stock', {}).get('tienda') == 14
    assert res2.get('stock', {}).get('bodega') == 4


@pytest.mark.smoke
def test_api_precios_piloto_guardar_stock_inicial_http(app_client, productos_con_stock, app_ctx):
    p = productos_con_stock[2]
    aid_t = m.id_almacen_tienda()
    if aid_t:
        m.fijar_stock_almacen(p.id, aid_t, 0)
    db.session.commit()
    r = app_client.post(
        '/api/precios/piloto/guardar',
        json={
            'producto_id': p.id,
            'precio_venta': '5590',
            'motivo': 'QA piloto stock http',
            'modo_stock': 'inicial',
            'stock_tienda': 17,
            'stock_bodega': 2,
        },
        content_type='application/json',
    )
    data = r.get_json()
    assert r.status_code == 200, data
    assert data.get('ok') is True
    assert data.get('stock', {}).get('tienda') == 17
    assert data.get('stock', {}).get('bodega') == 2
