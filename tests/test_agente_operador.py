"""Tests LhexIA Operador v0.1 y tabla agente_ejecuciones."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import app as m
from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    crear_registro,
    existe_dedupe_abierta,
    transicion_alerta,
)
from services.agente_operador_service import escanear_y_registrar_alertas

db = m.db


@pytest.fixture
def tabla_agente(app_ctx):
    assert m._asegurar_tabla_agente_ejecuciones()
    yield
    m.AgenteEjecucion.query.delete()
    db.session.commit()


def test_crear_alerta_y_dedupe(tabla_agente):
    rid = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Test alerta',
        codigo='test',
        dedupe_key='operador:test:1',
    )
    assert rid is not None
    assert existe_dedupe_abierta('operador:test:1')
    rid2 = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Dup',
        dedupe_key='operador:test:1',
    )
    assert rid2 is None


def test_transicion_reconocer(tabla_agente):
    rid = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Ack test',
        dedupe_key='operador:ack:1',
    )
    assert transicion_alerta(rid, 'reconocida', 'QA Test')
    row = m.AgenteEjecucion.query.get(rid)
    assert row.estado == 'reconocida'
    assert row.reconocido_por


def test_escanear_vale_pendiente_antiguo(
    tabla_agente, productos_con_stock, caja_abierta, cliente_final,
):
    from tests.conftest import crear_venta_pendiente

    venta, _dets = crear_venta_pendiente(
        [(productos_con_stock[0], 1)],
        caja_abierta,
        cliente_final,
    )
    venta.fecha = datetime.now() - timedelta(hours=5)
    db.session.commit()
    db.session.refresh(venta)

    chain_v = MagicMock()
    chain_v.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        venta,
    ]
    chain_c = MagicMock()
    chain_c.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    with patch.object(m.Venta, 'query', chain_v), patch.object(m.Caja, 'query', chain_c):
        res = escanear_y_registrar_alertas()

    assert res.get('ok') is True, res
    assert res.get('creadas') == 1, res

    alerta = m.AgenteEjecucion.query.filter_by(
        dedupe_key=f'operador:vale_pendiente:{venta.id}',
    ).first()
    assert alerta is not None
    assert alerta.codigo == 'vale_pendiente_horas'


@pytest.mark.smoke
def test_control_center_con_tabla(app_client, tabla_agente):
    r = app_client.get('/admin/control-center')
    assert r.status_code == 200
    assert b'LhexIA Operador' in r.data
    assert b'Escanear ahora' in r.data


@pytest.mark.smoke
def test_escanear_post(app_client, tabla_agente):
    r = app_client.post('/admin/agente-operador/escanear', follow_redirects=True)
    assert r.status_code == 200
