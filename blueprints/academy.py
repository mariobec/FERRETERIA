"""LhexIA Academy — API Mentor (/api/mentor/*)."""
from flask_login import login_required

from blueprints._app_ref import app_module


def _wrap_mentor_api(fn):
    m = app_module()
    return login_required(
        m.permisos_required('pos_emitir_vale', 'caja_cobrar_vale', 'gestionar_usuarios')(fn)
    )


def register_academy_routes(app):
    m = app_module()
    app.add_url_rule(
        '/api/mentor/context',
        'api_mentor_context',
        _wrap_mentor_api(m.api_mentor_context),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/mentor/log_read',
        'api_mentor_log_read',
        _wrap_mentor_api(m.api_mentor_log_read),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/mentor/save_step',
        'api_mentor_save_step',
        _wrap_mentor_api(m.api_mentor_save_step),
        methods=['POST'],
    )
