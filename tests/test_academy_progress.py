"""Tests LX-ACAD-3 — progreso checklist Academy."""
import json

import pytest

import app as m
from services.academy_service import guardar_paso_academy, obtener_mapa_progreso_usuario


@pytest.fixture
def tabla_academy_progress(app_client):
    assert m._asegurar_tabla_academy_articles()
    assert m._asegurar_tabla_user_academy_progress()
    yield
    try:
        m.UserAcademyProgress.query.delete(synchronize_session=False)
        m.db.session.commit()
    except Exception:
        m.db.session.rollback()


GUIDE_KEY = 'academy:pos:emitir_vale'


def _admin_qa():
    from app import Rol

    return (
        m.Usuario.query.join(Rol)
        .filter(Rol.nombre.in_(['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin']))
        .first()
    )


class TestAcademyProgressService:
    def test_guardar_paso_persiste_y_completa(self, app_client, tabla_academy_progress):
        with app_client.application.app_context():
            admin = _admin_qa()
            assert admin is not None
            uid = int(admin.id)

            out1 = guardar_paso_academy(
                user_id=uid,
                dedupe_key=GUIDE_KEY,
                step_id='step-0',
                checked=True,
            )
            assert out1.get('ok') is True
            assert 'step-0' in out1.get('completed_steps', [])

            for i in range(1, 4):
                guardar_paso_academy(
                    user_id=uid,
                    dedupe_key=GUIDE_KEY,
                    step_id=f'step-{i}',
                    checked=True,
                )
            prog = obtener_mapa_progreso_usuario(uid)
            assert prog[GUIDE_KEY]['all_complete'] is True

    def test_usuarios_aislados(self, app_client, tabla_academy_progress):
        with app_client.application.app_context():
            u1 = _admin_qa()
            assert u1 is not None
            guardar_paso_academy(
                user_id=int(u1.id),
                dedupe_key=GUIDE_KEY,
                step_id='step-0',
                checked=True,
            )
            otros = (
                m.Usuario.query.filter(m.Usuario.id != u1.id).order_by(m.Usuario.id.asc()).first()
            )
            if otros:
                mapa = obtener_mapa_progreso_usuario(int(otros.id))
                assert GUIDE_KEY not in mapa or 'step-0' not in (mapa.get(GUIDE_KEY) or {}).get(
                    'completed_steps', []
                )


@pytest.mark.smoke
class TestAcademyProgressApi:
    def test_api_save_step(self, app_client, tabla_academy_progress):
        r = app_client.post(
            '/api/mentor/save_step',
            data=json.dumps({
                'dedupe_key': GUIDE_KEY,
                'step_id': 'step-0',
                'checked': True,
            }),
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('step_id') == 'step-0'

    def test_context_incluye_pasos_detalle(self, app_client, tabla_academy_progress):
        app_client.post(
            '/api/mentor/save_step',
            data=json.dumps({
                'dedupe_key': GUIDE_KEY,
                'step_id': 'step-0',
                'checked': True,
            }),
            content_type='application/json',
        )
        r = app_client.get('/api/mentor/context?url=/punto_venta')
        assert r.status_code == 200
        data = r.get_json()
        biblioteca = data.get('biblioteca') or []
        guia = next((g for g in biblioteca if g.get('dedupe_key') == GUIDE_KEY), None)
        assert guia is not None
        detalle = guia.get('pasos_detalle') or []
        assert len(detalle) >= 4
        assert detalle[0].get('completed') is True

    def test_save_step_rechaza_step_invalido(self, app_client, tabla_academy_progress):
        r = app_client.post(
            '/api/mentor/save_step',
            data=json.dumps({
                'dedupe_key': GUIDE_KEY,
                'step_id': 'step-99',
                'checked': True,
            }),
            content_type='application/json',
        )
        assert r.status_code == 400
        assert r.get_json().get('ok') is False
