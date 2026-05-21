"""Tests LhexIA Operador v0.2 — Ollama client y enriquecimiento (mock)."""
from unittest.mock import MagicMock, patch

import pytest

from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    crear_registro,
    listar_alertas_sin_enriquecer,
    parse_payload_json,
)
from services.agente_operador_service import enriquecer_alerta_operativa, ejecutar_lote_enriquecimiento
from services.ollama_client import generar_chat

import app as m

db = m.db


@pytest.fixture
def tabla_agente(app_ctx):
    assert m._asegurar_tabla_agente_ejecuciones()
    yield
    m.AgenteEjecucion.query.delete()
    db.session.commit()


def test_ollama_disabled_sin_llamada(monkeypatch):
    monkeypatch.delenv('AGENTE_OLLAMA_ENABLED', raising=False)
    res = generar_chat(system='s', user='u')
    assert res['ok'] is False
    assert res['error'] == 'ollama_disabled'


def test_enriquecer_fallback_ollama_off(tabla_agente, monkeypatch):
    monkeypatch.setenv('AGENTE_OLLAMA_ENABLED', '0')
    rid = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Test enrich off',
        cuerpo='Cuerpo base v01.',
        dedupe_key='operador:enrich:off:1',
        payload={'enriquecido_semantico': False, 'cuerpo_base_v01': 'Cuerpo base v01.'},
    )
    res = enriquecer_alerta_operativa(rid)
    assert res.get('ok') is False
    assert res.get('fallback') is True
    row = m.AgenteEjecucion.query.get(rid)
    assert 'Cuerpo base' in (row.cuerpo or '')
    assert not parse_payload_json(row.payload_json).get('enriquecido_semantico')


def test_enriquecer_ok_mock_ollama(tabla_agente, monkeypatch):
    monkeypatch.setenv('AGENTE_OLLAMA_ENABLED', '1')
    rid = crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Test enrich on',
        cuerpo='Base matematica.',
        codigo='vale_pendiente_horas',
        dedupe_key='operador:enrich:on:1',
        payload={'enriquecido_semantico': False, 'venta_id': 1, 'cuerpo_base_v01': 'Base matematica.'},
    )
    with patch('services.agente_operador_service.ollama_disponible', return_value=True):
        with patch('services.agente_operador_service.generar_chat') as mock_chat:
            with patch('services.agente_contexto_service.empaquetar_contexto_alerta') as mock_ctx:
                mock_ctx.return_value = {'codigo': 'vale_pendiente_horas', 'historial': {}}
                mock_chat.return_value = {
                    'ok': True,
                    'texto': 'Analisis IA: revisar cajero y cobrar vale.',
                    'tokens_total': 42,
                    'modelo': 'qwen2.5:7b',
                }
                res = enriquecer_alerta_operativa(rid)
    assert res.get('ok') is True
    row = m.AgenteEjecucion.query.get(rid)
    assert 'Analisis IA' in (row.cuerpo or '')
    assert row.tokens_total == 42
    assert parse_payload_json(row.payload_json).get('enriquecido_semantico') is True


def test_listar_sin_enriquecer(tabla_agente):
    crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Pendiente IA',
        dedupe_key='operador:pend:1',
        payload={'enriquecido_semantico': False},
    )
    crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Ya IA',
        dedupe_key='operador:pend:2',
        payload={'enriquecido_semantico': True},
    )
    pend = listar_alertas_sin_enriquecer(limite=10)
    assert len(pend) == 1
    assert pend[0].titulo == 'Pendiente IA'


def test_lote_enriquecimiento_mock(tabla_agente, monkeypatch):
    monkeypatch.setenv('AGENTE_OLLAMA_ENABLED', '1')
    crear_registro(
        agente_nombre='operador',
        tipo=TIPO_ALERTA,
        estado=EST_ALERTA_ABIERTA,
        titulo='Lote 1',
        cuerpo='b',
        dedupe_key='operador:lote:1',
        payload={'enriquecido_semantico': False},
    )
    with patch('services.agente_operador_service.ollama_disponible', return_value=True):
        with patch('services.agente_operador_service.enriquecer_alerta_operativa') as mock_e:
            mock_e.return_value = {'ok': True, 'id': 1}
            res = ejecutar_lote_enriquecimiento(limite=5)
    assert res.get('enriquecidas') == 1
