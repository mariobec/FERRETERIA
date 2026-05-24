"""Tests cron LhexIA Operador dispatch-scan y cuerpo UI."""
import pytest

import app as m
from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    crear_registro,
    cuerpo_alerta_para_ui,
)


@pytest.fixture
def tabla_agente(app_ctx):
    assert m._asegurar_tabla_agente_ejecuciones()
    yield
    m.AgenteEjecucion.query.delete()
    m.db.session.commit()


def test_cuerpo_alerta_para_ui_sin_base_operativa():
    cuerpo = "Hipótesis: vale olvidado en caja.\n\n---\n[Base operativa] Vale pendiente 4h"
    payload = {'enriquecido_semantico': True}
    assert cuerpo_alerta_para_ui(cuerpo, payload) == 'Hipótesis: vale olvidado en caja.'


def test_dispatch_scan_sin_secreto_503(app_client, monkeypatch):
    monkeypatch.delenv('AGENTE_OPERADOR_CRON_SECRET', raising=False)
    monkeypatch.delenv('COBRANZA_DISPATCH_CRON_SECRET', raising=False)
    r = app_client.post('/api/agente/operador/dispatch-scan', json={})
    assert r.status_code == 503


def test_dispatch_scan_unauthorized(app_client, monkeypatch):
    monkeypatch.setenv('AGENTE_OPERADOR_CRON_SECRET', 'qa-operador-secret')
    r = app_client.post(
        '/api/agente/operador/dispatch-scan',
        json={},
        headers={'Authorization': 'Bearer wrong'},
    )
    assert r.status_code == 401


def test_dispatch_scan_ok(app_client, monkeypatch, tabla_agente):
    secret = 'qa-operador-secret-dispatch'
    monkeypatch.setenv('AGENTE_OPERADOR_CRON_SECRET', secret)
    r = app_client.post(
        '/api/agente/operador/dispatch-scan',
        json={},
        headers={'Authorization': f'Bearer {secret}'},
    )
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('ok') is True
    assert j.get('scan', {}).get('ok') is True


@pytest.mark.smoke
def test_feed_preview_incluye_mensaje_enriquecido(app_client, tabla_agente, caja_abierta):
    uid = __import__('uuid').uuid4().hex[:8]
    rid = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Vale #99 pendiente',
        cuerpo='Análisis Ollama: cobrar antes del cierre.\n\n---\n[Base operativa] Vale 5h',
        severidad='warning',
        codigo='vale_pendiente_horas',
        dedupe_key=f'operador:vale:qa:{uid}',
        payload={'enriquecido_semantico': True},
    )
    assert rid
    r = app_client.get('/api/v1/owner/dashboard?v=3')
    assert r.status_code == 200
    feed = (r.get_json().get('data') or {}).get('feed_preview') or []
    match = [f for f in feed if f.get('id') == rid]
    assert match
    assert 'Ollama' in (match[0].get('mensaje') or '')
    assert match[0].get('enriquecido') is True
    msg_ia = (r.get_json().get('data') or {}).get('mensaje_ia') or ''
    assert 'Ollama' in msg_ia or 'cobrar' in msg_ia.lower()
