"""Tests Mentor Coach — /api/mentor/pregunta."""
import pytest

import app as m


@pytest.fixture
def tabla_academy_hub(app_client):
    assert m._asegurar_tabla_academy_articles()
    assert m._asegurar_tabla_agente_ejecuciones()
    assert m._asegurar_tabla_user_academy_progress()
    yield
    try:
        m.UserAcademyProgress.query.delete(synchronize_session=False)
        m.AgenteEjecucion.query.filter(m.AgenteEjecucion.agente_nombre == 'mentor').delete(
            synchronize_session=False
        )
        m.db.session.commit()
    except Exception:
        m.db.session.rollback()


@pytest.mark.smoke
def test_api_mentor_pregunta_emitir_vale(app_client, tabla_academy_hub):
    r = app_client.post(
        '/api/mentor/pregunta',
        json={'pregunta': '¿Cómo emitir un vale en POS?', 'usar_ia': False},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get('ok') is True
    art = body.get('articulo') or {}
    assert 'vale' in (art.get('title') or '').lower() or 'pos' in (art.get('title') or '').lower()
    assert art.get('launch_interactivo_href', '').find('mentor_open=1') >= 0


@pytest.mark.smoke
def test_api_mentor_pregunta_corta(app_client, tabla_academy_hub):
    r = app_client.post('/api/mentor/pregunta', json={'pregunta': 'ok'})
    assert r.status_code == 400
    assert r.get_json().get('error') == 'pregunta_corta'
