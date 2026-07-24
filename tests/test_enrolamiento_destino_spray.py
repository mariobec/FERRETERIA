"""Enrolamiento: destino elegido gana (sin forzar bodega por SPRAY/AEROSOL)."""
from types import SimpleNamespace

import pytest


@pytest.mark.smoke
def test_enrol_destino_respeta_tienda_aunque_nombre_sea_spray(app_ctx, monkeypatch):
    from app import Almacen, _enrol_destino_almacen

    tienda = Almacen.query.filter(Almacen.codigo.ilike('TIENDA')).filter_by(activo=True).first()
    bodega = Almacen.query.filter(Almacen.codigo.ilike('BODEGA')).filter_by(activo=True).first()
    if not tienda or not bodega:
        pytest.skip('Faltan almacenes TIENDA/BODEGA en QA')

    spray = SimpleNamespace(nombre='SILICONA SPRAY SIEGER')
    sesion = SimpleNamespace(id_almacen=tienda.id)

    # Antes la regla spray forzaba bodega; ahora gana el destino explícito
    aid = _enrol_destino_almacen(sesion, tienda.id, producto=spray, ruta_bodega=False)
    assert aid == tienda.id

    # Sin destino explícito: sesión tienda (aunque nombre sea spray)
    aid2 = _enrol_destino_almacen(sesion, None, producto=spray, ruta_bodega=False)
    assert aid2 == tienda.id

    # Flag manual ruta_bodega sigue pudiendo forzar bodega
    aid3 = _enrol_destino_almacen(sesion, None, producto=spray, ruta_bodega=True)
    assert aid3 == bodega.id


@pytest.mark.smoke
def test_enrol_producto_ruta_bodega_desactivada(app_ctx):
    from app import _enrol_producto_ruta_bodega

    assert _enrol_producto_ruta_bodega(nombre='SILICONA SPRAY SIEGER') is False
    assert _enrol_producto_ruta_bodega(nombre='PINTURA AEROSOL') is False
