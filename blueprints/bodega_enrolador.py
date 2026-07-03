"""PWA Enrolador Bodega — manifest, service worker y registro de rutas."""
import os

from flask import jsonify, request, send_from_directory
from flask_login import login_required

from blueprints._app_ref import app_module

_BODEGA_ENROLADOR_STATIC = 'bodega-enrolador'


def register_bodega_enrolador_routes(app):
    m = app_module()
    permisos_required = m.permisos_required
    static_dir = os.path.join(m.app.root_path, 'static', _BODEGA_ENROLADOR_STATIC)

    @app.route('/bodega-enrolador/manifest.webmanifest')
    def bodega_enrolador_manifest():
        base = request.url_root.rstrip('/')
        payload = {
            'id': f'{base}/inventario/enrolamiento/tablet',
            'name': 'Enrolador Bodega LhexIA',
            'short_name': 'Enrolador',
            'description': 'Enrolamiento inventario con pistola — bodega Santo Domingo',
            'start_url': f'{base}/inventario/enrolamiento/tablet',
            'scope': f'{base}/',
            'display': 'standalone',
            'display_override': ['standalone', 'fullscreen'],
            'orientation': 'portrait',
            'background_color': '#0f172a',
            'theme_color': '#0f172a',
            'lang': 'es-CL',
            'categories': ['business', 'productivity'],
            'icons': [
                {
                    'src': f'{base}/static/owner-pwa/icon-192.png',
                    'sizes': '192x192',
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
                    'src': f'{base}/static/owner-pwa/icon-512-maskable.png',
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'maskable',
                },
            ],
        }
        return jsonify(payload), 200, {'Content-Type': 'application/manifest+json'}

    @app.route('/bodega-enrolador/sw.js')
    def bodega_enrolador_service_worker():
        resp = send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
        resp.headers['Cache-Control'] = 'no-store, max-age=0'
        resp.headers['Service-Worker-Allowed'] = '/'
        return resp

    view_setup = login_required(
        permisos_required('enrolamiento_inventario', 'admin_inventario')(m.bodega_enrolador_setup)
    )
    app.add_url_rule('/bodega/enrolador', 'bodega_enrolador_setup', view_setup, methods=['GET'])

    view_tablet = login_required(
        permisos_required('enrolamiento_inventario', 'admin_inventario')(m.inventario_enrolamiento_tablet)
    )
    app.add_url_rule(
        '/inventario/enrolamiento/tablet',
        'inventario_enrolamiento_tablet',
        view_tablet,
        methods=['GET'],
    )
