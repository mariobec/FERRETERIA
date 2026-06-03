"""Portal ejecutivo SD Constructor — smoke API y página."""
import pytest

from services import portal_ejecutivo_service as portal_svc


@pytest.mark.smoke
class TestPortalEjecutivo:

    def test_portal_pagina_ok(self, app_client):
        r = app_client.get('/portal-ejecutivo')
        assert r.status_code == 200
        assert b'SD Constructor' in r.data or b'portalSdRoot' in r.data

    def test_api_resumen_ok(self, app_client):
        r = app_client.get('/api/portal/resumen?periodo=mes')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'ventas_clp' in data
        assert 'utilidad_operativa_est_clp' in data
        assert data.get('marca')

    def test_api_activos_ok(self, app_client):
        r = app_client.get('/api/portal/activos?periodo=mes')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'inventario_clp' in data
        assert 'notas' in data

    def test_api_margenes_stub_501(self, app_client):
        r = app_client.get('/api/portal/margenes')
        assert r.status_code == 501

    def test_construir_resumen_servicio(self, app_ctx):
        with app_ctx.app_context():
            out = portal_svc.construir_resumen('mes')
            assert out['ok'] is True
            assert out['gastos_op_clp'] >= 0

    def test_admin_empresa_form_portal(self, app_client):
        r = app_client.get('/admin/empresa')
        assert r.status_code == 200
        assert b'portal_gastos_op_mensual_clp' in r.data

    def test_admin_empresa_guarda_portal(self, app_client, app_ctx):
        import app as m
        keys = (
            'nombre_comercial',
            'portal_marca',
            'portal_gastos_op_mensual_clp',
            'portal_activos_fijos_clp',
            'portal_meta_ventas_anual_clp',
        )
        with app_ctx.app_context():
            snap = {k: m.obtener_config_empresa().get(k) for k in keys}
        try:
            r = app_client.post(
                '/admin/empresa',
                data={
                    'nombre_comercial': snap['nombre_comercial'] or 'QA Portal Empresa',
                    'razon_social': 'QA',
                    'portal_marca': 'SD Constructor QA',
                    'portal_gastos_op_mensual_clp': '7.500.000',
                    'portal_activos_fijos_clp': '1000000',
                    'portal_meta_ventas_anual_clp': '120000000',
                },
                follow_redirects=True,
            )
            assert r.status_code == 200
            with app_ctx.app_context():
                cfg = m.obtener_config_empresa()
                assert cfg.get('portal_marca') == 'SD Constructor QA'
                assert cfg.get('portal_gastos_op_mensual_clp') == '7500000'
                assert cfg.get('portal_activos_fijos_clp') == '1000000'
                assert cfg.get('portal_meta_ventas_anual_clp') == '120000000'
        finally:
            with app_ctx.app_context():
                m.guardar_config_empresa({k: snap[k] for k in keys if snap.get(k) is not None})
