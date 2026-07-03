"""Tests KB manual operación Ollama."""
import pytest

import app as m
from services.academy_mentor_kb_service import (
    buscar_faq_kb,
    cargar_kb_operacion,
    formatear_faq_respuesta,
    kb_version,
    recargar_kb_operacion,
)


@pytest.fixture(autouse=True)
def _kb_fresco():
    recargar_kb_operacion()
    yield


@pytest.fixture
def tabla_academy_hub(app_client):
    assert m._asegurar_tabla_academy_articles()
    assert m._asegurar_tabla_agente_ejecuciones()
    assert m._asegurar_tabla_user_academy_progress()
    yield


def test_kb_carga():
    kb = cargar_kb_operacion()
    assert kb.get('faq')
    assert len(kb['faq']) >= 20
    assert kb_version()


def test_buscar_faq_emitir_vale():
    hits = buscar_faq_kb('¿Cómo emitir un vale en POS?')
    assert hits
    assert 'vale' in hits[0].get('pregunta', '').lower() or hits[0].get('id') == 'faq_001'


def test_buscar_faq_tablet():
    hits = buscar_faq_kb('tablet pistola bodega BCST')
    assert hits
    assert any('tablet' in (h.get('pregunta') or '').lower() for h in hits)


def test_buscar_faq_enseñame_vender_pos_no_es_soporte():
    hits = buscar_faq_kb('Hola maylén enseñame a vender en el pos')
    assert hits
    assert hits[0].get('id') == 'faq_026'
    assert hits[0].get('id') != 'faq_005'


def test_buscar_faq_sin_precio_sigue_siendo_soporte():
    hits = buscar_faq_kb('El POS dice sin precio y no deja vender')
    assert hits
    assert hits[0].get('id') == 'faq_005'


def test_buscar_faq_aprender_caja():
    hits = buscar_faq_kb('enseñame a usar la caja paso a paso')
    assert hits
    assert hits[0].get('id') == 'faq_027'


def test_buscar_faq_enseñame_semáforos():
    hits = buscar_faq_kb('enseñame los semáforos del pos')
    assert hits
    assert hits[0].get('id') == 'faq_030'


def test_buscar_faq_enseñame_cobrar_vale():
    hits = buscar_faq_kb('enseñame a cobrar un vale')
    assert hits
    assert hits[0].get('id') == 'faq_029'


def test_buscar_faq_anular_vale_soporte():
    hits = buscar_faq_kb('necesito anular un vale pendiente')
    assert hits
    assert hits[0].get('id') == 'faq_042'


def test_buscar_faq_traslado_bodega():
    hits = buscar_faq_kb('enseñame traslado bodega a tienda')
    assert hits
    assert hits[0].get('id') == 'faq_035'


def test_buscar_faq_convierto_cajero_onboarding():
    hits = buscar_faq_kb('como me convierto en cajero')
    assert hits
    assert hits[0].get('id') == 'faq_044'
    txt = formatear_faq_respuesta(hits[0])
    assert 'arqueo' not in txt.lower()


def test_faq_027_trabajar_caja_sin_arqueo():
    hits = buscar_faq_kb('flujo del cajero paso a paso')
    faq = next(h for h in hits if h.get('id') == 'faq_027')
    txt = formatear_faq_respuesta(faq)
    assert 'arqueo' not in txt.lower()


def test_formatear_faq_tiene_pasos():
    hits = buscar_faq_kb('abrir caja')
    assert hits
    txt = formatear_faq_respuesta(hits[0])
    assert 'Pasos' in txt or 'pasos' in txt.lower()
    assert '/abrir_caja' in txt or 'caja' in txt.lower()


@pytest.mark.smoke
def test_coach_usa_kb(app_client, tabla_academy_hub):
    r = app_client.post(
        '/api/mentor/pregunta',
        json={'pregunta': '¿Puedo cobrar en el punto de venta?', 'usar_ia': False},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get('ok') is True
    assert 'caja' in (body.get('respuesta') or '').lower()
    assert body.get('fuente') in ('kb', 'ollama', 'reglas', 'academy')
