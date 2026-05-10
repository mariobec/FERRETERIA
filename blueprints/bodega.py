"""Rutas dominio bodega — registradas sobre la app principal (evita duplicar modelos)."""
from flask_login import login_required

from blueprints._app_ref import app_module


def register_bodega_routes(app):
    """Debe llamarse al final de la carga de `app` (después de definir vistas y decoradores)."""
    m = app_module()
    permisos_required = m.permisos_required
    view_despachos = login_required(permisos_required('bodega_operador')(m.bodega_despachos))
    app.add_url_rule('/bodega/despachos', 'bodega_despachos', view_despachos, methods=['GET'])

    view_voice = login_required(m.api_bodega_voice_command)
    app.add_url_rule('/api/bodega/voice-command', 'api_bodega_voice_command', view_voice, methods=['POST'])
