"""Listado / filtros / archivado recepciones (SD-1 D2)."""
from __future__ import annotations

from datetime import date

import pytest

import app as m
from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS
from services.recepciones_lista_service import (
    ESTADO_ARCHIVADO_RCV,
    archivar_recepciones_lote,
    query_lista_recepciones,
)


@pytest.fixture
def proveedor_rcv(app_ctx, limpieza_qa, proveedor_test):
    yield proveedor_test


def _crear_rcv(proveedor, folio: str, anio: int, monto: float):
    rec = m.RecepcionCompra(
        proveedor_id=proveedor.id,
        documento_tipo='Factura',
        documento_numero=folio,
        estado=ESTADO_PENDIENTE_ITEMS,
        fecha_documento=date(anio, 6, 15),
        monto_total=monto,
        origen_importacion='rcv_sii',
        usuario_bodega='RCV-SII',
    )
    m.db.session.add(rec)
    m.db.session.commit()
    return rec


@pytest.mark.smoke
def test_query_filtro_anio_y_orden_monto(app_ctx, proveedor_rcv):
    _crear_rcv(proveedor_rcv, 'F-2025-1', 2025, 1000.0)
    r26 = _crear_rcv(proveedor_rcv, 'F-2026-1', 2026, 500000.0)
    _crear_rcv(proveedor_rcv, 'F-2026-2', 2026, 10000.0)

    q = query_lista_recepciones(anio=2026, estado=ESTADO_PENDIENTE_ITEMS, orden='monto')
    filas = q.filter(m.RecepcionCompra.proveedor_id == proveedor_rcv.id).all()
    assert filas[0].id == r26.id


@pytest.mark.smoke
def test_archivar_anio_2025(app_ctx, proveedor_rcv):
    m._asegurar_columnas_recepcion_rcv()
    r25 = _crear_rcv(proveedor_rcv, 'ARCH-25', 2025, 2000.0)
    r26 = _crear_rcv(proveedor_rcv, 'ARCH-26', 2026, 3000.0)

    res = archivar_recepciones_lote(anio=2025)
    assert res['ok'] is True
    assert res['actualizadas'] >= 1

    m.db.session.refresh(r25)
    m.db.session.refresh(r26)
    assert r25.estado == ESTADO_ARCHIVADO_RCV
    assert r26.estado == ESTADO_PENDIENTE_ITEMS


@pytest.mark.smoke
def test_lista_recepciones_http_filtros(app_client, proveedor_rcv):
    _crear_rcv(proveedor_rcv, 'HTTP-26', 2026, 99999.0)
    r = app_client.get(
        '/recepciones',
        query_string={
            'estado': ESTADO_PENDIENTE_ITEMS,
            'anio': 2026,
            'orden': 'monto',
        },
    )
    assert r.status_code == 200
    assert b'Pareto' in r.data or b'Monto total' in r.data or b'monto_total' in r.data.lower()


@pytest.mark.smoke
def test_archivar_post_seleccion(app_client, app_ctx, proveedor_rcv):
    m._asegurar_columnas_recepcion_rcv()
    rec = _crear_rcv(proveedor_rcv, 'SEL-ARCH', 2026, 100.0)
    r = app_client.post(
        '/recepciones/archivar-rcv',
        data={'accion': 'seleccion', 'recepcion_ids': [str(rec.id)]},
        follow_redirects=True,
    )
    assert r.status_code == 200
    m.db.session.refresh(rec)
    assert rec.estado == ESTADO_ARCHIVADO_RCV
