"""Smoke — conciliación transferencias caja (cobro → confirmar abono → entrega)."""
import pytest

import app as m
from tests.conftest import crear_venta_pendiente
from services.transferencia_caja_service import (
    es_transferencia_pendiente_confirmacion,
    transferencia_autoriza_entrega,
)


@pytest.mark.smoke
class TestTransferenciaCaja:

    def test_cobro_transferencia_bloquea_entrega_hasta_confirmar(
        self, app_client, productos_con_stock, caja_abierta, cliente_final
    ):
        p = productos_con_stock[0]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        total = float(venta.monto_total or 0)

        r = app_client.post(
            f'/procesar_cobro_caja/{venta.id}',
            data={
                'metodo_pago': 'Transferencia',
                'tipo_documento': 'Boleta',
                'monto_recibido': str(int(total)),
                'transferencia_referencia': 'TRF-QA-001',
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303)
        assert '/caja/transferencias' in (r.location or '')

        m.db.session.expire_all()
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'
        assert vr.metodo_pago == 'Transferencia'
        assert vr.transferencia_referencia == 'TRF-QA-001'
        assert vr.transferencia_confirmada_at is None
        assert es_transferencia_pendiente_confirmacion(vr)
        assert not transferencia_autoriza_entrega(vr)

        r_ent = app_client.post(
            f'/api/pos/despacho/vale/{venta.id}/registrar-entrega',
            json={'accion': 'entregar_todo'},
            content_type='application/json',
        )
        assert r_ent.status_code == 403
        body = r_ent.get_json() or {}
        assert body.get('codigo') == 'transferencia_pendiente'

        r_band = app_client.get('/caja/transferencias')
        assert r_band.status_code == 200
        assert b'TRF-QA-001' in r_band.data

        r_conf = app_client.post(
            f'/api/caja/transferencias/{venta.id}/confirmar',
            follow_redirects=True,
        )
        assert r_conf.status_code == 200

        m.db.session.expire_all()
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.transferencia_confirmada_at is not None
        assert transferencia_autoriza_entrega(vr)

        r_ent2 = app_client.post(
            f'/api/pos/despacho/vale/{venta.id}/registrar-entrega',
            json={'accion': 'entregar_todo'},
            content_type='application/json',
        )
        assert r_ent2.status_code == 200
        assert (r_ent2.get_json() or {}).get('ok') is True

    def test_revertir_transferencia_vuelve_a_pendiente(
        self, app_client, productos_con_stock, caja_abierta, cliente_final
    ):
        p = productos_con_stock[2]
        stock_pre = m.stock_disponible_venta_tienda(p)
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)

        r = app_client.post(
            f'/procesar_cobro_caja/{venta.id}',
            data={
                'metodo_pago': 'Transferencia',
                'tipo_documento': 'Boleta',
                'monto_recibido': str(float(venta.monto_total or 0) + 50),
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303)

        m.db.session.expire_all()
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado', 'cobro transferencia debe quedar Pagado'

        r_rev = app_client.post(
            f'/api/caja/transferencias/{venta.id}/rechazar',
            json={'motivo': 'QA no llegó abono'},
            content_type='application/json',
        )
        assert r_rev.status_code == 200
        assert (r_rev.get_json() or {}).get('ok') is True

        m.db.session.expire_all()
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pendiente'
        assert vr.metodo_pago is None
        assert vr.transferencia_referencia is None
        assert m.stock_disponible_venta_tienda(p) >= stock_pre

    def test_api_transferencias_alerta(self, app_client, caja_abierta):
        r = app_client.get('/api/caja/transferencias/alerta')
        assert r.status_code == 200
        body = r.get_json() or {}
        assert body.get('ok') is True
        assert 'n_vales' in body
        assert 'n_correos' in body
        assert 'total' in body
        assert 'items' in body
        assert isinstance(body.get('items'), list)
        for it in body.get('items') or []:
            if it.get('tipo') == 'vale':
                assert 'url_confirmar' in it
            if it.get('tipo') == 'correo' and it.get('venta_id_sugerida'):
                assert 'url_confirmar' in it
