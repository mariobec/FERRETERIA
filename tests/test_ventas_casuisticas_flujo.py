"""
Casuísticas integrales: venta (POS POST) → cobro caja → entrega tienda/bodega/mixto.

Requiere catálogo SD-PRUEBA (fixture catalogo_casuisticas_qa o
`python scripts/seed_ventas_casuisticas_qa.py`).

Matriz de IDs: tests/qa_catalogo_casuisticas.py → ESCENARIOS_VENTA
Documentación: docs/CASUISTICAS_VENTAS_QA.md
"""
from __future__ import annotations

import pytest

import app as m
from tests.conftest import (
    asegurar_stock_bodega,
    crear_venta_pendiente,
    pos_emitir_vale_http,
    pos_escanear_agregar,
    procesar_cobro_http,
    ultima_venta_pendiente,
)
from tests.test_routes_criticas import _ensure_caja_abierta

pytestmark = [pytest.mark.casuisticas]


def _prod(cat, key):
    p = cat.get(key)
    assert p, f'Falta producto {key} en catálogo CAS'
    return p


@pytest.mark.smoke
class TestCasVentaTienda:
    """CAS-V01 — efectivo, retiro tienda."""

    def test_cas_v01_cobrar_tienda_cliente_obra(self, app_client, catalogo_casuisticas_qa, caja_abierta):
        cat = catalogo_casuisticas_qa
        cli = cat['cliente_obra']
        oferta = _prod(cat, 'oferta_clavo')
        venta, _ = crear_venta_pendiente([(oferta, 2)], caja_abierta, cli, 'Tienda')
        assert venta.punto_retiro == 'Tienda'
        rc = procesar_cobro_http(app_client, venta)
        assert rc.status_code == 200
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado' and vr.metodo_pago == 'Efectivo'
        assert oferta.pos_descuento_preautorizado is True

    def test_cas_v01b_pos_http_emitir_vale(self, app_client, catalogo_casuisticas_qa, caja_abierta):
        """Flujo POST real POS: escanear + finalizar_venta."""
        _ensure_caja_abierta()
        cat = catalogo_casuisticas_qa
        oferta = _prod(cat, 'oferta_clavo')
        r = pos_emitir_vale_http(
            app_client,
            [{'codigo': oferta.codigo_barra, 'qty': 1}],
            cliente_final=True,
            punto_retiro='Tienda',
        )
        if r.status_code == 409:
            pytest.skip('Producto en vale pendiente previo')
        assert r.status_code in (200, 302)
        venta = ultima_venta_pendiente(caja_abierta.id)
        if not venta:
            pytest.skip('finalizar_venta no dejó vale Pendiente (revisar stock tienda / vale abierto previo)')
        assert venta.estado == 'Pendiente'


@pytest.mark.smoke
class TestCasVentaBodega:
    """CAS-V02 — cobro + preparación bodega."""

    def test_cas_v02_bodega_cobro_y_preparacion(self, app_client, catalogo_casuisticas_qa, caja_abierta):
        _ensure_caja_abierta()
        cat = catalogo_casuisticas_qa
        p = _prod(cat, 'pvc')
        asegurar_stock_bodega(p, 40)
        venta, _ = crear_venta_pendiente(
            [(p, 2)], caja_abierta, cat['cliente_saldo_favor'], 'Bodega')
        procesar_cobro_http(app_client, venta)
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'
        assert (vr.bodega_preparacion_estado or '').upper() in ('PENDIENTE', 'EN_PREPARACION', '')

        rp = app_client.post(f'/bodega/vale/{venta.id}/preparacion', data={'estado': 'EN_PREPARACION'},
                             follow_redirects=True)
        assert rp.status_code in (200, 302)


@pytest.mark.smoke
class TestCasVentaMixto:
    """CAS-V03 — líneas con retiro distinto."""

    def test_cas_v03_venta_mixta_retiro_linea(self, catalogo_casuisticas_qa, caja_abierta, cliente_final):
        cat = catalogo_casuisticas_qa
        tienda_p = _prod(cat, 'oferta_clavo')
        bodega_p = _prod(cat, 'pvc')
        asegurar_stock_bodega(bodega_p, 30)
        venta, dets = crear_venta_pendiente(
            [
                (tienda_p, 1, 'Tienda'),
                (bodega_p, 2, 'Bodega'),
            ],
            caja_abierta,
            cliente_final,
            punto_retiro='Tienda',
        )
        assert venta.punto_retiro == 'Mixto'
        retiros = {(d.punto_retiro_linea or '').strip() for d in dets}
        assert retiros >= {'Tienda', 'Bodega'}


@pytest.mark.smoke
class TestCasCreditoYSaldoFavor:
    """CAS-V04 / CAS-V05."""

    def test_cas_v04_cobro_credito_incrementa_deuda(self, app_client, catalogo_casuisticas_qa, caja_abierta):
        cat = catalogo_casuisticas_qa
        cli = cat['cliente_credito_cas']
        deuda_antes = float(cli.saldo_deudor or 0)
        p = _prod(cat, 'cemento')
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cli, 'Tienda')
        total = float(venta.monto_total or 0)
        procesar_cobro_http(app_client, venta, metodo_pago='Credito', monto_recibido=0)
        m.db.session.refresh(cli)
        assert float(cli.saldo_deudor or 0) >= deuda_antes + total - 1

    def test_cas_v05_cobro_con_saldo_favor(self, app_client, catalogo_casuisticas_qa, caja_abierta):
        cat = catalogo_casuisticas_qa
        cli = cat['cliente_saldo_favor']
        saldo_ini = float(m._saldo_favor_actual(cli.id) or 0)
        assert saldo_ini > 0
        p = _prod(cat, 'arena')
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cli, 'Tienda')
        usar = min(5000, saldo_ini, float(venta.monto_total or 0))
        procesar_cobro_http(app_client, venta, usar_saldo_favor=int(usar))
        vr = m.db.session.get(m.Venta, venta.id)
        assert vr.estado == 'Pagado'
        assert float(vr.saldo_favor_usado or 0) == pytest.approx(usar, rel=0.01)
        saldo_fin = float(m._saldo_favor_actual(cli.id) or 0)
        assert saldo_fin == pytest.approx(saldo_ini - usar, rel=0.01)


@pytest.mark.smoke
class TestCasCrossSellYObra:
    """CAS-V06 / CAS-V07 / CAS-V08."""

    def test_cas_v06_producto_oferta_preautorizado_en_catalogo(self, catalogo_casuisticas_qa):
        oferta = _prod(catalogo_casuisticas_qa, 'oferta_clavo')
        assert oferta.pos_descuento_preautorizado is True
        assert float(oferta.pos_descuento_preautorizado_pct or 0) >= 10

    def test_cas_v07_cross_sell_cemento_sugiere_complementos(self, catalogo_casuisticas_qa):
        cemento = _prod(catalogo_casuisticas_qa, 'cemento')
        sugerencia = m._pos_cross_sell_match_rules([cemento.id], [])
        assert sugerencia is not None
        titulo = (sugerencia.get('titulo') or '').lower()
        assert 'arena' in titulo or 'obra' in titulo or 'completar' in titulo

    def test_cas_v08_cliente_obra_etapa_y_producto_fase(self, catalogo_casuisticas_qa):
        cli = catalogo_casuisticas_qa['cliente_obra']
        cem = _prod(catalogo_casuisticas_qa, 'cemento')
        assert (cli.c360_etapa_actual or '').upper() == 'OBRA_GRUESA'
        assert (cem.fase_obra or '').upper() == 'OBRA_GRUESA'


@pytest.mark.smoke
class TestCasCompras:
    """CAS-C01 — OC + línea con producto CAS."""

    def test_cas_c01_crear_oc_borrador(self, app_client, catalogo_casuisticas_qa, proveedor_test):
        from datetime import datetime

        p = _prod(catalogo_casuisticas_qa, 'cemento')
        r = app_client.post('/compras/ordenes/nueva', data={
            'proveedor_id': str(proveedor_test.id),
            'numero': f'CAS-OC-{datetime.now():%H%M%S%f}',
            'estado': 'Borrador',
            'producto_id[]': str(p.id),
            'cantidad[]': '20',
            'precio_unitario[]': str(p.precio_compra),
        }, follow_redirects=True)
        assert r.status_code in (200, 302)
        oc = m.OrdenCompra.query.filter(m.OrdenCompra.numero.like('CAS-OC-%')).order_by(m.OrdenCompra.id.desc()).first()
        assert oc and oc.estado == 'Borrador'


@pytest.mark.smoke
class TestCasAnuladaNoCierre:
    """Ventas anuladas no deben sumar en cuadratura (regresión cierre)."""

    def test_cas_anulada_excluida_de_cuadre(self, catalogo_casuisticas_qa, caja_abierta, cliente_final):
        from tests.conftest import anular_venta_con_audit

        p = _prod(catalogo_casuisticas_qa, 'cemento')
        venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final, 'Tienda')
        anular_venta_con_audit(venta)
        assert m._venta_cuenta_en_cuadre_caja(m.db.session.get(m.Venta, venta.id)) is False
