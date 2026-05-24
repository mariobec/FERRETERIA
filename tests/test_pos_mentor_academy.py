"""Tests LhexIA Academy / Mentor en POS y caja."""
import json

import pytest

import app as m
from services.agente_ejecuciones_service import EST_LOG_EJECUTADO, TIPO_LOG, asegurar_tabla
from services.vertex_mentor_service import (
    PILDORA_NOTA_CREDITO,
    construir_contexto_mentor,
    detectar_contexto_pantalla,
    registrar_consulta_academy,
)


@pytest.fixture
def tabla_agente_mentor(app_client):
    assert m._asegurar_tabla_agente_ejecuciones()
    yield
    try:
        m.AgenteEjecucion.query.filter(m.AgenteEjecucion.agente_nombre == 'mentor').delete(
            synchronize_session=False
        )
        m.db.session.commit()
    except Exception:
        m.db.session.rollback()


class TestMentorService:
    def test_detectar_contexto_cambios(self):
        assert detectar_contexto_pantalla('/caja/cambios') == 'cambios_devoluciones'

    def test_detectar_contexto_pos(self):
        assert detectar_contexto_pantalla('/punto_venta') == 'pos'

    def test_detectar_contexto_abrir_caja(self):
        assert detectar_contexto_pantalla('/abrir_caja') == 'abrir_caja'

    def test_detectar_contexto_movimiento_caja(self):
        assert detectar_contexto_pantalla('/movimiento_caja') == 'movimiento_caja'

    def test_contexto_cambios_prioriza_nota_credito(self):
        payload = construir_contexto_mentor(url='/caja/cambios')
        assert payload['ok'] is True
        assert payload['contexto'] == 'cambios_devoluciones'
        pill = payload.get('pildora_prioritaria') or {}
        assert pill.get('codigo') == 'mentor_guia_nota_credito'
        assert pill.get('agente_producto') == 'vertex_mentor'

    def test_registrar_consulta_academy_inserta_ejecutado(self, app_client, tabla_agente_mentor):
        assert asegurar_tabla()
        out = registrar_consulta_academy(
            usuario_id=1,
            usuario_nombre='Cajera Test',
            dedupe_key='academy:caja:cobrar_vale',
            accion='expandir',
            url='/caja/vales_pendientes',
        )
        assert out.get('ok') is True
        assert out.get('registro_id')
        row = m.AgenteEjecucion.query.get(out['registro_id'])
        assert row is not None
        assert row.agente_nombre == 'mentor'
        assert row.tipo == TIPO_LOG
        assert row.estado == EST_LOG_EJECUTADO


@pytest.mark.smoke
class TestMentorApi:
    def test_api_contexto_pos(self, app_client):
        r = app_client.get('/api/pos/mentor/contexto?url=/punto_venta')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'biblioteca' in data
        assert isinstance(data.get('biblioteca'), list)

    def test_api_contexto_cambios_pildora(self, app_client):
        r = app_client.get('/api/pos/mentor/contexto?url=/caja/cambios')
        assert r.status_code == 200
        data = r.get_json()
        pill = data.get('pildora_prioritaria') or {}
        assert pill.get('codigo') == 'mentor_guia_nota_credito'
        snap = pill.get('kpi_snapshot') or {}
        assert snap.get('pildora_dedupe_key') == PILDORA_NOTA_CREDITO

    def test_api_telemetria_expandir(self, app_client, tabla_agente_mentor):
        r = app_client.post(
            '/api/pos/mentor/telemetria',
            data=json.dumps({
                'dedupe_key': 'academy:pos:emitir_vale',
                'accion': 'expandir',
                'url': '/punto_venta',
            }),
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('estado') == EST_LOG_EJECUTADO

    def test_punto_venta_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/punto_venta')
        assert r.status_code in (200, 302)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data
            assert b'initLhexiaMentorAcademy' in r.data or b'pos.js' in r.data

    def test_caja_pendientes_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/caja/vales_pendientes')
        assert r.status_code in (200, 302)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data

    def test_caja_cambios_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/caja/cambios')
        assert r.status_code in (200, 302)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data
            assert b'initLhexiaMentorAcademy' in r.data or b'lhexia-mentor-config' in r.data

    def test_cerrar_caja_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/cerrar_caja')
        assert r.status_code in (200, 302, 403)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data

    def test_abrir_caja_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/abrir_caja')
        assert r.status_code in (200, 302)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data
            assert b'lhexia-mentor-config' in r.data

    def test_movimiento_caja_incluye_mentor_sidebar(self, app_client):
        r = app_client.get('/movimiento_caja')
        assert r.status_code in (200, 302, 403)
        if r.status_code == 200:
            assert b'lhexia-mentor-sidebar' in r.data
            assert b'initLhexiaMentorAcademy' in r.data or b'lhexia-mentor-config' in r.data

    def test_api_contexto_abrir_caja_pildora(self, app_client):
        r = app_client.get('/api/mentor/context?url=/abrir_caja')
        assert r.status_code == 200
        pill = (r.get_json() or {}).get('pildora_prioritaria') or {}
        assert pill.get('codigo') == 'mentor_apertura_caja'

    def test_api_contexto_practicar_href_caja(self, app_client):
        r = app_client.get('/api/mentor/context?url=/caja/vales_pendientes')
        assert r.status_code == 200
        data = r.get_json()
        guia = next(
            (g for g in (data.get('biblioteca') or []) if g.get('dedupe_key') == 'academy:caja:cobrar_vale'),
            None,
        )
        assert guia is not None
        assert guia.get('practicar_href') == '/caja/vales_pendientes'
