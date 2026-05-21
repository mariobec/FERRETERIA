"""API JSON PWA dueño (Fase 1–2 — semáforo caja / inventario + assets PWA)."""
import os

from flask import jsonify, request, send_from_directory, session
from flask_login import current_user

from blueprints._app_ref import app_module

_OWNER_PWA_STATIC = 'owner-pwa'


def register_owner_api_routes(app):
    m = app_module()
    static_dir = os.path.join(m.app.root_path, 'static', _OWNER_PWA_STATIC)

    @app.route('/owner-pwa/manifest.webmanifest')
    def owner_pwa_manifest():
        """Manifest con URLs absolutas (Chrome exige icono 512 real + start_url HTTPS)."""
        base = request.url_root.rstrip('/')
        payload = {
            'id': f'{base}/owner-mobile',
            'name': 'LhexIA Dueño',
            'short_name': 'Dueño',
            'description': 'Control en un vistazo — caja e inventario',
            'start_url': f'{base}/owner-mobile',
            'scope': f'{base}/',
            'display': 'standalone',
            'display_override': ['standalone', 'fullscreen'],
            'orientation': 'portrait',
            'background_color': '#0f172a',
            'theme_color': '#0f172a',
            'lang': 'es-CL',
            'categories': ['business', 'finance'],
            'icons': [
                {
                    'src': f'{base}/static/img/lhexia-icon-approved.png',
                    'sizes': '256x256',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': f'{base}/static/owner-pwa/icon-512.png',
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': f'{base}/static/owner-pwa/icon-512.png',
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'maskable',
                },
            ],
        }
        return jsonify(payload), 200, {'Content-Type': 'application/manifest+json'}

    @app.route('/owner-pwa/sw.js')
    def owner_pwa_service_worker():
        return send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')

    @app.route('/api/v1/owner/dashboard', methods=['GET'])
    @m.permisos_required('panel_gerencia', 'ver_gerencia', 'gestionar_usuarios')
    def api_owner_dashboard_v1():
        if not session.get('_user_id') or not current_user.is_authenticated:
            return jsonify(status='error', error='login_required'), 401

        from services.owner_dashboard_service import construir_owner_dashboard

        try:
            data = construir_owner_dashboard(calcular_ctx_caja=m._calcular_contexto_turno_caja)
        except Exception as ex:
            m.app.logger.exception('api_owner_dashboard_v1: %s', ex)
            return jsonify(status='error', error='dashboard_error'), 500

        resp = jsonify(status='success', data=data)
        if request.args.get('nocache') == '1':
            resp.headers['Cache-Control'] = 'no-store'
        return resp
