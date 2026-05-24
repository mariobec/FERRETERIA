"""Tests LhexIA Academy — modelo DB y API /api/mentor/*."""
import json

import pytest

import app as m
from services.academy_bootstrap import MANUAL_V2_ARTICLES
from services.agente_ejecuciones_service import EST_LOG_EJECUTADO, TIPO_LOG, asegurar_tabla


@pytest.fixture
def tabla_academy(app_client):
    assert m._asegurar_tabla_academy_articles()
    yield
    try:
        keys = [a['dedupe_key'] for a in MANUAL_V2_ARTICLES]
        m.AcademyArticle.query.filter(m.AcademyArticle.dedupe_key.in_(keys)).delete(
            synchronize_session=False
        )
        m.db.session.commit()
    except Exception:
        m.db.session.rollback()


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


class TestAcademyModel:
    def test_seed_manual_v2_tres_articulos(self, app_client, tabla_academy):
        rows = m.AcademyArticle.query.order_by(m.AcademyArticle.id).all()
        assert len(rows) >= 5
        cats = {r.category for r in rows}
        assert 'pos' in cats
        assert 'caja' in cats
        assert 'bodega' in cats
        assert m.AcademyArticle.query.filter_by(
            dedupe_key='academy:manual_v2:seccion_d_apertura_caja'
        ).first() is not None

    def test_articulo_pos_tiene_markdown(self, app_client, tabla_academy):
        art = m.AcademyArticle.query.filter_by(
            dedupe_key='academy:manual_v2:seccion_a_pos_semaforos'
        ).first()
        assert art is not None
        assert 'Semáforos' in (art.content_markdown or '')


@pytest.mark.smoke
class TestMentorApiV2:
    def test_api_mentor_context_pos(self, app_client, tabla_academy):
        r = app_client.get('/api/mentor/context?url=/punto_venta')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('categoria_academy') == 'pos'
        assert data.get('articulo_principal')
        assert isinstance(data.get('atajos_teclado'), list)
        assert isinstance(data.get('biblioteca'), list)

    def test_api_mentor_log_read(self, app_client, tabla_academy, tabla_agente_mentor):
        assert asegurar_tabla()
        r = app_client.post(
            '/api/mentor/log_read',
            data=json.dumps({
                'dedupe_key': 'academy:manual_v2:seccion_a_pos_semaforos',
                'accion': 'cargar',
                'url': '/punto_venta',
            }),
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('estado') == EST_LOG_EJECUTADO
        assert data.get('tipo') == TIPO_LOG

    def test_legacy_pos_mentor_alias(self, app_client, tabla_academy):
        r = app_client.get('/api/pos/mentor/contexto?url=/punto_venta')
        assert r.status_code == 200
        assert r.get_json().get('ok') is True
