"""API JSON PWA dueño (Fase 1–2 — semáforo caja / inventario + assets PWA)."""
import os
from datetime import datetime

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
            'name': 'Lhexia Guardián',
            'short_name': 'Guardián',
            'description': 'Agente móvil de control — caja e inventario en vivo',
            'start_url': f'{base}/owner-mobile',
            'scope': f'{base}/',
            'display': 'standalone',
            'display_override': ['standalone', 'fullscreen'],
            'orientation': 'portrait',
            'background_color': '#020617',
            'theme_color': '#020617',
            'lang': 'es-CL',
            'categories': ['business', 'finance'],
            'icons': [
                {
                    'src': f'{base}/static/img/lhexia-icon-transparent.png',
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
        resp = send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
        resp.headers['Cache-Control'] = 'no-store, max-age=0'
        resp.headers['Service-Worker-Allowed'] = '/'
        return resp

    @app.route('/api/v1/owner/dashboard', methods=['GET'])
    @m.permisos_required('panel_gerencia', 'ver_gerencia', 'gestionar_usuarios')
    def api_owner_dashboard_v1():
        """Lhexia Guardián v3 — JSON multiperfil, KPIs, acciones y feed Operador."""
        from services.owner_dashboard_service import construir_owner_dashboard
        from services.vertex_control_center_service import (
            SCOPE_GLOBAL_MAESTRO,
            construir_dashboard_global_maestro,
            usuario_es_vertex_maestro,
        )

        usuario = current_user if current_user.is_authenticated else None
        dev_mock = os.getenv('OWNER_GUARDIAN_DEV_MOCK', '').strip() == '1'
        scope = (request.args.get('scope') or '').strip().lower()

        if not session.get('_user_id') or not usuario:
            if dev_mock:
                usuario = None
            else:
                return jsonify(status='error', error='login_required'), 401

        if scope == SCOPE_GLOBAL_MAESTRO:
            if not usuario_es_vertex_maestro(usuario):
                return jsonify(
                    status='error',
                    error='vertex_maestro_required',
                    hint='Requiere permiso plataforma (gestionar_usuarios) o LHEXIA_VERTEX_MAESTRO_USERS',
                ), 403
            try:
                data = construir_dashboard_global_maestro(
                    calcular_ctx_caja=m._calcular_contexto_turno_caja,
                    usuario=usuario,
                )
            except Exception as ex:
                m.app.logger.exception('api_owner_dashboard_global_maestro: %s', ex)
                return jsonify(status='error', error='dashboard_error'), 500
        else:
            try:
                data = construir_owner_dashboard(
                    calcular_ctx_caja=m._calcular_contexto_turno_caja,
                    usuario=usuario,
                )
            except Exception as ex:
                m.app.logger.exception('api_owner_dashboard_v1: %s', ex)
                return jsonify(status='error', error='dashboard_error'), 500

        resp = jsonify(status='success', data=data)
        resp.headers['Cache-Control'] = 'no-store'
        resp.headers['X-Lhexia-Ecosystem'] = 'VERTEX'
        if scope == SCOPE_GLOBAL_MAESTRO:
            resp.headers['X-Lhexia-Scope'] = SCOPE_GLOBAL_MAESTRO
        return resp

    @app.route('/owner/vertex-control')
    @m.permisos_required('gestionar_usuarios')
    def owner_vertex_control():
        """Centro de Mandos Global Multi-Cliente (cascarón V3 — solo plataforma LhexIA)."""
        from services.vertex_control_center_service import usuario_es_vertex_maestro

        if not usuario_es_vertex_maestro(current_user):
            return (
                'Acceso restringido al Centro de Mandos VERTEX.',
                403,
            )
        return m.render_template(
            'owner_vertex_control.html',
            fecha_hoy_str=datetime.now().strftime('%Y-%m-%d'),
            api_maestro_url=m.url_for(
                'api_owner_dashboard_v1',
                scope='global_maestro',
            ),
        )
