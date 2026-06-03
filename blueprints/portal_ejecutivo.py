"""Portal ejecutivo SD Constructor — gerencia y dueños (fuera del flujo POS)."""
from __future__ import annotations

from flask import jsonify, render_template, request

from blueprints._app_ref import app_module
from services import portal_ejecutivo_service as portal_svc

_PERMISOS_PORTAL = (
    'panel_gerencia',
    'ver_gerencia',
    'gestionar_usuarios',
)


def register_portal_ejecutivo_routes(app):
    m = app_module()

    @app.route('/portal-ejecutivo')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def portal_ejecutivo_index():
        cfg = portal_svc.portal_config()
        periodo = (request.args.get('periodo') or 'mes').strip().lower()
        return render_template(
            'portal_ejecutivo.html',
            portal_marca=cfg['marca'],
            periodo_inicial=periodo if periodo in ('mes', 'trim', 'anio') else 'mes',
        )

    @app.route('/api/portal/resumen')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def api_portal_resumen():
        periodo = request.args.get('periodo', 'mes')
        return jsonify(portal_svc.construir_resumen(periodo))

    @app.route('/api/portal/activos')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def api_portal_activos():
        periodo = request.args.get('periodo', 'mes')
        return jsonify(portal_svc.construir_activos(periodo))

    @app.route('/api/portal/margenes')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def api_portal_margenes_stub():
        return jsonify(ok=False, fase='P2', mensaje='Márgenes — disponible en fase P2.'), 501

    @app.route('/api/portal/flujo')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def api_portal_flujo_stub():
        return jsonify(ok=False, fase='P2', mensaje='Flujo de caja — disponible en fase P2.'), 501

    @app.route('/api/portal/proyeccion')
    @m.permisos_required(*_PERMISOS_PORTAL)
    def api_portal_proyeccion_stub():
        return jsonify(ok=False, fase='P3', mensaje='Proyección — disponible en fase P3.'), 501
