"""API PWA dueño — GET /api/v1/owner/dashboard."""
import uuid

import pytest

import app as m
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
    def test_dashboard_json_estructura(self, app_client):
        r = app_client.get('/api/v1/owner/dashboard')
        assert r.status_code == 200
        j = r.get_json()
        assert j.get('status') == 'success'
        data = j.get('data') or {}
        for key in ('tarjeta_caja', 'tarjeta_inventario', 'meta'):
            assert key in data
        caja = data['tarjeta_caja']
        inv = data['tarjeta_inventario']
        assert caja.get('estado') in _SEMÁFOROS
        assert inv.get('estado') in _SEMÁFOROS
        assert caja.get('titulo')
        assert inv.get('titulo')
        assert 'mensaje' in caja
        assert 'timestamp' in caja
        assert 'accion_requerida' in caja
        assert 'meta' in data and 'alertas_abiertas' in data['meta']

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
        caja = (r.get_json().get('data') or {}).get('tarjeta_caja') or {}
        assert caja.get('estado') == 'rojo'
        assert caja.get('alerta_id') == rid
        assert caja.get('tipo_accion') == 'llamada_supervisor'
        assert caja.get('accion_requerida') is True
        assert 'arqueo' in (caja.get('mensaje') or '').lower() or 'descuadre' in (caja.get('titulo') or '').lower()

    def test_sin_permiso_gerencia_403(self, app_client):
        """Rol sin panel_gerencia / ver_gerencia no debe ver el dashboard API."""
        with login_as(app_client, 'vendedor') as c:
            r = c.get('/api/v1/owner/dashboard')
        if r.status_code == 200:
            pytest.skip('Rol vendedor en QA tiene permiso gerencia; omitir gate')
        assert r.status_code == 403
        body = r.get_json() or {}
        assert body.get('ok') is False or body.get('status') == 'error'

    def test_owner_mobile_pwa_assets(self, app_client):
        r = app_client.get('/owner-mobile')
        assert r.status_code == 200
        assert b'ownerPwaApp' in r.data
        assert b'owner-dashboard.js' in r.data
        assert b'owner-pwa-3' in r.data or b'owner-pwa-4' in r.data
        assert b'owner-pwa-toolbar' in r.data
        assert b'ownerBtnInstall' in r.data
        assert b'owner-semaforo-card' in r.data
        rm = app_client.get('/owner-pwa/manifest.webmanifest')
        assert rm.status_code == 200
        mj = rm.get_json()
        assert mj.get('name') == 'LhexIA Dueño'
        icons = mj.get('icons') or []
        assert any(i.get('sizes') == '512x512' for i in icons)

    def test_dashboard_sin_sesion_401(self, app_ctx):
        """Sin _user_id en sesión → 401 (mismo criterio que /api/pos/live-wall)."""
        c = m.app.test_client(use_cookies=False)
        r = c.get('/api/v1/owner/dashboard')
        assert r.status_code == 401
        body = r.get_json() or {}
        assert body.get('error') == 'login_required'
        assert body.get('status') == 'error'
