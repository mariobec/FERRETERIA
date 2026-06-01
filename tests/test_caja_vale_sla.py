"""Tests SLA vales pendientes en caja."""
from datetime import datetime, timedelta

import pytest

from services.caja_vale_sla_service import (
    evaluar_sla_vale,
    obtener_config_sla_caja,
    serializar_vale_sla,
    venta_elegible_sla_caja,
)


class _ValeStub:
    def __init__(self, **kw):
        self.id = kw.get('id', 1)
        self.estado = kw.get('estado', 'Pendiente')
        self.metodo_pago = kw.get('metodo_pago', None)
        self.caja_id = kw.get('caja_id', 1)
        self.fecha = kw.get('fecha', datetime.now())
        self.monto_total = kw.get('monto_total', 1000)
        self.usuario = kw.get('usuario', 'QA')


@pytest.mark.smoke
def test_evaluar_sla_vale_tiers():
    cfg = {'alertas': [10, 15], 'anular_minutos': 20, 'motivo_auto': 'test'}
    assert evaluar_sla_vale(5, cfg)['tier'] == 0
    assert evaluar_sla_vale(10, cfg)['tier'] == 1
    assert evaluar_sla_vale(14, cfg)['accion'] == 'atencion'
    assert evaluar_sla_vale(15, cfg)['tier'] == 2
    assert evaluar_sla_vale(15, cfg)['accion'] == 'modal_cobrar_anular'
    assert evaluar_sla_vale(20, cfg)['tier'] == 3
    assert evaluar_sla_vale(20, cfg)['accion'] == 'auto_anular'


def test_venta_elegible_sla_excluye_bodega():
    v = _ValeStub()
    assert venta_elegible_sla_caja(v, 1, tiene_despacho_bodega=False) is True
    assert venta_elegible_sla_caja(v, 1, tiene_despacho_bodega=True) is False
    v.estado = 'Pagado'
    assert venta_elegible_sla_caja(v, 1) is False


def test_serializar_vale_sla_auto_flag():
    cfg = obtener_config_sla_caja()
    ahora = datetime.now()
    v = _ValeStub(fecha=ahora - timedelta(minutes=21))
    row = serializar_vale_sla(v, cfg, ahora, tiene_despacho_bodega=False)
    assert row['elegible_auto_anular'] is True
    row2 = serializar_vale_sla(v, cfg, ahora, tiene_despacho_bodega=True)
    assert row2['elegible_auto_anular'] is False
    assert row2['bloqueado_auto_anular'] is True


@pytest.mark.smoke
class TestCajaValeSlaApi:
    def test_api_sla_sin_auth(self, app_client):
        app_client.get('/logout', follow_redirects=True)
        r = app_client.get('/api/caja/vales-pendientes/sla')
        assert r.status_code in (302, 401, 403)

    def test_api_sla_ok(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        from tests.conftest import crear_venta_pendiente
        import app as m
        from tests.conftest import db

        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        venta.fecha = datetime.now() - timedelta(minutes=11)
        db.session.commit()

        r = app_client.get('/api/caja/vales-pendientes/sla')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        ids = [x['id'] for x in data.get('vales', [])]
        assert venta.id in ids
        row = next(x for x in data['vales'] if x['id'] == venta.id)
        assert row['tier'] >= 1
        assert row['minutos'] >= 10

    def test_api_sla_auto_anula_20_min(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        from tests.conftest import crear_venta_pendiente, db

        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        venta.fecha = datetime.now() - timedelta(minutes=21)
        db.session.commit()

        r = app_client.get('/api/caja/vales-pendientes/sla')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        auto = data.get('auto_anulados') or []
        assert any(x['id'] == venta.id for x in auto)

        db.session.expire_all()
        import app as m

        vr = db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Anulada'
