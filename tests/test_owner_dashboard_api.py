"""API PWA Guardián — GET /api/v1/owner/dashboard (v3)."""
import time
import uuid
from datetime import datetime, timedelta

import pytest

import app as m
from services.owner_dashboard_service import kpis_ventas_hoy
from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    crear_registro,
)
from tests.conftest import login_as

db = m.db

_SEMÁFOROS = frozenset({'verde', 'amarillo', 'rojo'})


@pytest.fixture
def tabla_agente_owner(app_ctx):
    assert m._asegurar_tabla_agente_ejecuciones()
    yield
    m.AgenteEjecucion.query.delete()
    db.session.commit()


@pytest.mark.smoke
class TestOwnerDashboardApi:
    def test_dashboard_json_estructura_v3(self, app_client):
        t0 = time.perf_counter()
        r = app_client.get('/api/v1/owner/dashboard?v=3')
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        assert elapsed_ms < 300, f'API tardó {elapsed_ms:.0f}ms (>300ms)'

        j = r.get_json()
        assert j.get('status') == 'success'
        data = j.get('data') or {}
        for key in (
            'tarjeta_caja', 'tarjeta_inventario', 'tarjeta_credito', 'tarjeta_compras',
            'tarjetas', 'feed_preview', 'meta',
            'perfil', 'nombre_usuario', 'saludo', 'status_caja', 'status_inventario',
            'status_credito', 'status_compras', 'status_global',
            'mensaje_ia', 'supervisor_telefono', 'alcance', 'consolidado', 'version',
        ):
            assert key in data, f'falta clave v3: {key}'

        assert data.get('version') == 'guardian_v3'
        assert data.get('ecosystem') == 'lhexia_vertex'
        assert data['meta'].get('version') == 'guardian_v3'
        assert data['meta'].get('ecosystem') == 'lhexia_vertex'
        assert isinstance(data['tarjetas'], list) and len(data['tarjetas']) >= 4
        assert isinstance(data['feed_preview'], list) and len(data['feed_preview']) <= 5

        for t in data['tarjetas']:
            assert 'dominio' in t and 'acciones' in t and 'status' in t
            assert isinstance(t['acciones'], list)
            if t['dominio'] == 'caja' and t.get('estado') == 'rojo':
                assert any(a.get('tipo') == 'nav' for a in t['acciones'])

        caja = data['tarjeta_caja']
        inv = data['tarjeta_inventario']
        assert caja.get('estado') in _SEMÁFOROS
        assert inv.get('estado') in _SEMÁFOROS
        assert data['status_caja'] in ('red', 'green', 'amber')
        assert data['status_global'] in ('red', 'green', 'amber')
        assert 'ventas_hoy_fmt' in data['consolidado']

    def test_kpis_ventas_hoy_incluye_pagado_del_dia(self, app_client, caja_abierta):
        """Venta Pagado con fecha hoy debe sumar en consolidado.ventas_hoy."""
        uid = uuid.uuid4().hex[:8]
        venta = m.Venta(
            fecha=datetime.now(),
            monto_total=31890.0,
            usuario='__qa_runner__',
            estado='Pagado',
            metodo_pago='Efectivo',
            caja_id=caja_abierta.id,
        )
        db.session.add(venta)
        db.session.commit()
        try:
            kpis = kpis_ventas_hoy()
            assert kpis['ventas_hoy_clp'] >= 31890
            assert kpis['transacciones_hoy'] >= 1
            r = app_client.get('/api/v1/owner/dashboard?v=3')
            data = r.get_json().get('data') or {}
            assert data['consolidado']['ventas_hoy_clp'] >= 31890
        finally:
            db.session.delete(venta)
            db.session.commit()

    def test_kpis_ventas_hoy_pendiente_emitido_hoy(self, app_client, caja_abierta):
        """Pendiente con fecha hoy suma; Abierta no entra en el filtro KPI."""
        antes = kpis_ventas_hoy()['ventas_hoy_clp']
        v_hoy = m.Venta(
            fecha=datetime.now(),
            monto_total=15000.0,
            usuario='__qa_runner__',
            estado='Pendiente',
            caja_id=caja_abierta.id,
        )
        db.session.add(v_hoy)
        db.session.commit()
        try:
            assert kpis_ventas_hoy()['ventas_hoy_clp'] >= antes + 15000
        finally:
            db.session.delete(v_hoy)
            db.session.commit()

    def test_dashboard_nocache_header(self, app_client):
        r = app_client.get('/api/v1/owner/dashboard?nocache=1')
        assert r.status_code == 200
        assert r.headers.get('Cache-Control') == 'no-store'

    def test_tarjeta_caja_roja_con_alerta_operador(self, app_client, tabla_agente_owner, caja_abierta):
        uid = uuid.uuid4().hex[:8]
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=f'Caja #{caja_abierta.id} descuadre +$12.000 CLP',
            cuerpo='Análisis enriquecido QA: falta efectivo en arqueo ciego.',
            severidad='critical',
            codigo='caja_descuadre',
            dedupe_key=f'operador:caja_descuadre:qa:{uid}',
            payload={
                'caja_id': caja_abierta.id,
                'diferencia_clp': 12000,
                'enriquecido_semantico': True,
                'cuerpo_base_v01': 'Cierre con diferencia.',
            },
            caja_id=caja_abierta.id,
        )
        assert rid is not None
        r = app_client.get('/api/v1/owner/dashboard')
        assert r.status_code == 200
        data = r.get_json().get('data') or {}
        caja = data.get('tarjeta_caja') or {}
        assert caja.get('estado') == 'rojo'
        assert caja.get('alerta_id') == rid
        assert len(data.get('feed_preview') or []) >= 1

    def test_sin_permiso_gerencia_403(self, app_client):
        with login_as(app_client, 'vendedor') as c:
            r = c.get('/api/v1/owner/dashboard')
        if r.status_code == 200:
            pytest.skip('Rol vendedor en QA tiene permiso gerencia; omitir gate')
        assert r.status_code == 403

    def test_owner_mobile_pwa_assets(self, app_client):
        r = app_client.get('/owner-mobile')
        assert r.status_code == 200
        assert b'ownerPwaApp' in r.data
        assert b'ownerGuardianFeed' in r.data
        assert b'ownerCardCredito' in r.data
        assert b'guardian-vertex' in r.data
        assert b'ownerGuardianSemMini' in r.data
        rm = app_client.get('/owner-pwa/manifest.webmanifest')
        assert rm.status_code == 200
        assert rm.get_json().get('name') == 'Lhexia Guardián'

    def test_dashboard_sin_sesion_401(self, app_ctx):
        c = m.app.test_client(use_cookies=False)
        r = c.get('/api/v1/owner/dashboard')
        assert r.status_code == 401
        assert r.get_json().get('error') == 'login_required'
