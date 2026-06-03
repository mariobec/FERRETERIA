"""POS: vincular código escaneado a producto existente (alias mostrador)."""
from __future__ import annotations

import pytest

import app as m
from services.producto_codigo_escaneo_service import (
    asegurar_tabla_producto_codigo_escaneo,
    vincular_codigo_a_producto,
)
from tests.conftest import db


@pytest.fixture
def _tabla_alias(app_ctx):
    asegurar_tabla_producto_codigo_escaneo(m.app, db)
    yield


@pytest.mark.smoke
def test_vincular_y_escanear_resuelve_mismo_producto(
    app_client, productos_con_stock, caja_abierta, _tabla_alias
):
    p = productos_con_stock[1]
    scan = f'VINCQA{(int(p.id) % 1000000):07d}'
    assert m._pos_buscar_producto_por_codigo(scan) is None
    r1 = app_client.post(
        '/api/pos/vincular-codigo',
        json={'codigo_escaneado': scan, 'producto_id': p.id, 'agregar_vale': False},
        content_type='application/json',
    )
    data1 = r1.get_json()
    assert r1.status_code == 200, data1
    assert data1.get('ok') is True
    found = m._pos_buscar_producto_por_codigo(scan)
    assert found is not None
    assert int(found.id) == int(p.id)
    r2 = app_client.post(
        '/api/pos/escanear-agregar',
        json={'codigo': scan},
        content_type='application/json',
    )
    data2 = r2.get_json()
    assert r2.status_code == 200, data2
    assert data2.get('ok') is True


@pytest.mark.smoke
def test_vincular_codigo_duplicado_otro_producto(
    app_client, productos_con_stock, _tabla_alias
):
    p1 = productos_con_stock[0]
    p2 = productos_con_stock[2]
    scan = (p2.codigo_barra or '').strip()
    if not scan:
        pytest.skip('producto sin codigo_barra')
    r = app_client.post(
        '/api/pos/vincular-codigo',
        json={'codigo_escaneado': scan, 'producto_id': p1.id, 'agregar_vale': False},
        content_type='application/json',
    )
    assert r.status_code == 409
    assert r.get_json().get('error') == 'barras_duplicado'


@pytest.mark.smoke
def test_vincular_aplica_precio_sd_y_agrega(
    app_client, productos_con_stock, caja_abierta, _tabla_alias
):
    p = productos_con_stock[4]
    old_sd = float(getattr(p, 'precio_venta_sd', None) or 0)
    p.precio_venta_sd = 0
    p.precio_venta = 0
    db.session.commit()
    scan = f'VINCPR{(int(p.id) % 100000):06d}'
    r = app_client.post(
        '/api/pos/vincular-codigo',
        json={
            'codigo_escaneado': scan,
            'producto_id': p.id,
            'precio_venta_sd': 4321,
            'agregar_vale': True,
        },
        content_type='application/json',
    )
    data = r.get_json()
    assert r.status_code == 200, data
    assert data.get('ok') is True
    assert data.get('agregado_vale') is True
    assert data.get('precio_sd_aplicado') == 4321
    db.session.refresh(p)
    assert float(p.precio_venta_sd or 0) == 4321
    p.precio_venta_sd = old_sd if old_sd > 0 else None
    db.session.commit()


def test_vincular_servicio_sin_duplicar_stock(app_ctx, productos_con_stock, _tabla_alias):
    p = productos_con_stock[3]
    old_stock = int(p.stock or 0)
    scan = f'SRVVINC{(int(p.id) % 100000):06d}'
    res = vincular_codigo_a_producto(
        scan,
        p.id,
        Producto=m.Producto,
        ProductoCodigoEscaneo=m.ProductoCodigoEscaneo,
        db=db,
        app=m.app,
        usuario='QA',
    )
    db.session.commit()
    assert res.get('ok') is True
    db.session.refresh(p)
    assert int(p.stock or 0) == old_stock
