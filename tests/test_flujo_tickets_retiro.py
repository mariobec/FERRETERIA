"""Smoke — flujo tickets: vale interno POS → cobro → vale interno caja → ticket retiro QR."""
import pytest

import app as m
from tests.conftest import crear_venta_pendiente, procesar_cobro_http


@pytest.mark.smoke
class TestFlujoTicketsRetiro:

    def test_vale_pos_sin_qr_con_leyenda_interno(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r = app_client.get(f'/pos/ticket/{venta.id}')
        assert r.status_code == 200
        html = r.data.decode('utf-8', errors='replace')
        assert 'VALE INTERNO' in html
        assert 'NO ES BOLETA' in html
        assert 'PENDIENTE DE COBRO EN CAJA' in html
        assert 'ticket de retiro' in html.lower()
        assert 'qr_ticket_src' not in html
        assert 'ESCANEO BODEGA' not in html

    def test_cobro_redirige_vale_interno_y_ticket_retiro(
        self, app_client, productos_con_stock, caja_abierta, cliente_final
    ):
        p = productos_con_stock[1]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)

        r_cobro = procesar_cobro_http(app_client, venta)
        assert r_cobro.status_code == 200

        r_ctrl = app_client.get(
            f'/caja/vale_retiro/{venta.id}?auto_print=1&chain_retiro=1'
        )
        assert r_ctrl.status_code == 200
        ctrl = r_ctrl.data.decode('utf-8', errors='replace')
        assert 'VALE INTERNO' in ctrl
        assert 'NO ES BOLETA' in ctrl
        assert '/caja/ticket_retiro/' in ctrl
        assert 'chainRetiro' in ctrl

        r_ret = app_client.get(f'/caja/ticket_retiro/{venta.id}')
        assert r_ret.status_code == 200
        ret = r_ret.data.decode('utf-8', errors='replace')
        assert 'TICKET DE RETIRO' in ret or 'Ticket de retiro' in ret
        assert 'NO ES BOLETA' in ret
        assert 'qr-wrap' in ret or 'codes__qr' in ret or 'Retiro' in ret

    def test_venta_mixta_dos_tickets_qr(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        from tests.conftest import asegurar_stock_bodega

        p_tienda, p_bodega = productos_con_stock[0], productos_con_stock[2]
        asegurar_stock_bodega(p_bodega, 5)
        venta, _ = crear_venta_pendiente(
            [(p_tienda, 1, 'Tienda'), (p_bodega, 1, 'Bodega')],
            caja_abierta,
            cliente_final,
            punto_retiro='Mixto',
        )
        r_cobro = procesar_cobro_http(app_client, venta)
        assert r_cobro.status_code == 200, (r_cobro.data.decode()[:500] if r_cobro.data else r_cobro.status_code)
        r = app_client.get(f'/caja/ticket_retiro/{venta.id}')
        assert r.status_code == 200
        html = r.data.decode('utf-8', errors='replace')
        assert html.count('Ticket de retiro') >= 2 or html.count('TICKET DE RETIRO') >= 2
        assert 'Retiro · Tienda' in html or 'TIENDA' in html.upper()
        assert 'Retiro · Bodega' in html or 'BODEGA' in html.upper()
        assert 'Precicado' in html or 'Corte aquí' in html
        assert 'page-break-after: always' not in html
        assert 'VL' in html
        assert 'code128' in html.lower() or '<svg' in html

    def test_cobro_dispara_retiro_termica_si_escpos(
        self, app_client, productos_con_stock, caja_abierta, cliente_final, monkeypatch
    ):
        """Con POS_IMPRESION_MODO térmica, el cobro intenta ESC/POS del ticket de retiro."""
        called = {'n': 0}

        def _fake_print(venta, *, printer_name=None):
            called['n'] += 1
            called['vid'] = getattr(venta, 'id', None)
            return {'ok': True, 'impresora': 'XP-80-TEST'}

        monkeypatch.setenv('POS_IMPRESION_MODO', 'escpos')
        monkeypatch.setattr(
            'services.ticket_impresion_service.imprimir_retiro_termica',
            _fake_print,
        )

        p = productos_con_stock[0]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        r_cobro = procesar_cobro_http(app_client, venta)
        assert r_cobro.status_code == 200
        assert called['n'] >= 1
        assert called.get('vid') == venta.id

    def test_pos_retiros_cola_y_busqueda(self, app_client, productos_con_stock, caja_abierta, cliente_final):
        p = productos_con_stock[3]
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
        procesar_cobro_http(app_client, venta)

        r_pant = app_client.get('/pos/retiros')
        assert r_pant.status_code == 200
        assert b'Retiros pendientes' in r_pant.data
        assert str(venta.id).encode() in r_pant.data

        folio = f'VL{venta.id:06d}'
        r_bus = app_client.get(f'/api/pos/retiros/buscar?q={folio}')
        assert r_bus.status_code == 200
        body = r_bus.get_json() or {}
        assert body.get('ok') is True
        assert body.get('venta_id') == venta.id
        assert body.get('pagado') is True
        assert body.get('puede_entregar') is True

        r_sug = app_client.get(f'/api/pos/retiros/sugerencias?q={venta.id}')
        assert r_sug.status_code == 200
        sug = r_sug.get_json() or {}
        assert sug.get('ok') is True
        assert any(s.get('venta_id') == venta.id for s in (sug.get('sugerencias') or []))

    def test_pos_retiros_entrega_parcial_por_linea(
        self, app_client, productos_con_stock, caja_abierta, cliente_final
    ):
        p = productos_con_stock[4]
        venta, _ = crear_venta_pendiente([(p, 3)], caja_abierta, cliente_final)
        procesar_cobro_http(app_client, venta)

        folio = f'VL{venta.id:06d}'
        body = (app_client.get(f'/api/pos/retiros/buscar?q={folio}').get_json() or {})
        assert body.get('ok') is True
        lineas = body.get('lineas') or []
        assert lineas, 'buscar debe devolver las líneas para el modal'
        det = lineas[0]
        assert det.get('pendiente') == 3
        detalle_id = det.get('detalle_id')

        # Retiro parcial: 2 de 3 → PARCIAL, sigue pendiente 1
        r1 = app_client.post(
            f'/api/pos/despacho/vale/{venta.id}/registrar-entrega',
            json={'accion': 'entregar_linea', 'detalle_id': detalle_id, 'cantidad': 2},
        )
        assert r1.status_code == 200
        d1 = r1.get_json() or {}
        assert d1.get('ok') is True
        assert d1.get('completa') is False
        assert d1.get('estado') == 'PARCIAL'
        ln1 = (d1.get('lineas') or [])[0]
        assert ln1.get('entregada') == 2
        assert ln1.get('pendiente') == 1

        # Retiro del resto: 1 → CERRADO / completa
        r2 = app_client.post(
            f'/api/pos/despacho/vale/{venta.id}/registrar-entrega',
            json={'accion': 'entregar_linea', 'detalle_id': detalle_id, 'cantidad': 1},
        )
        assert r2.status_code == 200
        d2 = r2.get_json() or {}
        assert d2.get('ok') is True
        assert d2.get('completa') is True
