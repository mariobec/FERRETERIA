"""Smoke — carga manual precios piloto SD (precio_venta_sd)."""
import pytest

import app as m
from app import db
from services.precios_piloto_service import (
    aplicar_precio_venta_sd,
    guardar_precio_piloto,
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


@pytest.mark.smoke
def test_api_precios_piloto_buscar(app_client, productos_con_stock):
    p = productos_con_stock[0]
    codigo = p.codigo_barra
    r = app_client.get(f'/api/precios/piloto/buscar?q={codigo}&origen=pos')
    assert r.status_code == 200
    data = r.get_json()
    assert 'results' in data
    assert len(data['results']) >= 1
    ids = [x.get('producto_id') for x in data['results']]
    assert p.id in ids


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
