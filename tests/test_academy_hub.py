"""Tests LX-ACAD-1 / LX-ACAD-2 — hub /academy y progreso."""
import pytest
from flask_login import login_user

import app as m
from services.academy_service import (
    construir_caminos_academy_hub,
    obtener_dedupes_completados_usuario,
    obtener_progreso_academy_usuario,
    registrar_lectura_academy,
)


def _admin_login_ctx():
    from app import Rol

    admin = (
        m.Usuario.query.join(Rol)
        .filter(Rol.nombre.in_(['Admin', 'admin', 'Administrador', 'administrador', 'SuperAdmin']))
        .first()
    )
    if admin is None:
        admin = m.Usuario.query.first()
    assert admin is not None
    login_user(admin)
    return admin


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


class TestAcademyHub:
    def test_get_academy_muestra_caminos(self, app_client, tabla_academy_hub):
        r = app_client.get('/academy')
        assert r.status_code == 200
        assert b'academy-pos' in r.data
        assert b'academy-caja' in r.data
        assert b'academy-bodega' in r.data
        assert b'Ruta del Vendedor' in r.data
        assert b'Ruta del Cajero' in r.data
        assert b'Practicar ahora' in r.data

    def test_obtener_progreso_tras_telemetria(self, app_client, tabla_academy_hub):
        with app_client.application.test_request_context():
            admin = _admin_login_ctx()
            uid = int(admin.id)
            dk = 'academy:manual_v2:seccion_d_apertura_caja'
            registrar_lectura_academy(
                usuario_id=uid,
                usuario_nombre=admin.nombre,
                dedupe_key=dk,
                accion='expandir',
                url='/academy',
            )
            dedupes = obtener_dedupes_completados_usuario(uid)
            assert dk in dedupes
            prog = obtener_progreso_academy_usuario(uid)
            assert prog.get('caja', {}).get('total', 0) >= 2

    def test_construir_caminos_incluye_practicar_href(self, app_client, tabla_academy_hub):
        with app_client.application.test_request_context():
            admin = _admin_login_ctx()
            caminos = construir_caminos_academy_hub(int(admin.id))
            assert len(caminos) >= 3
            caja = next(c for c in caminos if c['category'] == 'caja')
            art = next(
                (a for a in caja['articulos'] if a['dedupe_key'] == 'academy:manual_v2:seccion_b_arqueo_ciego_plat11'),
                None,
            )
            assert art is not None
            assert art.get('practicar_href') == '/cerrar_caja'

    def test_api_pildora_practicar_href_abrir_caja(self, app_client, tabla_academy_hub):
        r = app_client.get('/api/mentor/context?url=/abrir_caja')
        assert r.status_code == 200
        pill = (r.get_json() or {}).get('pildora_prioritaria') or {}
        assert pill.get('practicar_href') == '/abrir_caja'
