"""Rutas dominio bodega — registradas sobre la app principal (evita duplicar modelos)."""
from flask_login import login_required

from blueprints._app_ref import app_module


def register_bodega_routes(app):
    """Debe llamarse al final de la carga de `app` (después de definir vistas y decoradores)."""
    m = app_module()
    permisos_required = m.permisos_required
    view_qr_vals = login_required(permisos_required('bodega_operador')(m.bodega_despacho_qr_vales))
    app.add_url_rule(
        '/bodega/despacho-qr-vales',
        'bodega_despacho_qr_vales',
        view_qr_vals,
        methods=['GET'],
    )

    view_despachos = login_required(permisos_required('bodega_operador')(m.bodega_despachos))
    app.add_url_rule('/bodega/despachos', 'bodega_despachos', view_despachos, methods=['GET'])

    view_mando = login_required(permisos_required('bodega_operador')(m.bodega_cuadro_mando))
    app.add_url_rule('/bodega/cuadro-mando', 'bodega_cuadro_mando', view_mando, methods=['GET'])

    view_plat = login_required(permisos_required('bodega_operador')(m.bodega_plataforma))
    app.add_url_rule('/bodega/plataforma', 'bodega_plataforma', view_plat, methods=['GET'])
    view_vale = login_required(permisos_required('bodega_operador')(m.bodega_vale_retiro))
    app.add_url_rule('/bodega/vale/<int:vid>/retiro', 'bodega_vale_retiro', view_vale, methods=['GET'])
    view_prep = login_required(permisos_required('bodega_operador')(m.bodega_vale_preparacion_post))
    app.add_url_rule(
        '/bodega/vale/<int:vid>/preparacion',
        'bodega_vale_preparacion_post',
        view_prep,
        methods=['POST'],
    )
    view_rline = login_required(permisos_required('bodega_operador')(m.bodega_vale_retiro_linea_post))
    app.add_url_rule(
        '/bodega/vale/<int:vid>/retiro-linea',
        'bodega_vale_retiro_linea_post',
        view_rline,
        methods=['POST'],
    )

    view_sug = login_required(permisos_required('bodega_operador')(m.bodega_vale_sugerido_preparar_post))
    app.add_url_rule(
        '/bodega/vale/<int:vid>/sugerido-preparar',
        'bodega_vale_sugerido_preparar_post',
        view_sug,
        methods=['POST'],
    )

    view_snap = login_required(permisos_required('bodega_operador')(m.api_bodega_retiros_cola_snapshot))
    app.add_url_rule(
        '/api/bodega/retiros-cola-snapshot',
        'api_bodega_retiros_cola_snapshot',
        view_snap,
        methods=['GET'],
    )

    view_voice = login_required(m.api_bodega_voice_command)
    app.add_url_rule('/api/bodega/voice-command', 'api_bodega_voice_command', view_voice, methods=['POST'])

    view_export = login_required(permisos_required('bodega_operador')(m.bodega_export_dia))
    app.add_url_rule('/bodega/export-dia', 'bodega_export_dia', view_export, methods=['GET'])

    view_fs = login_required(permisos_required('bodega_operador')(m.bodega_cuadro_mando_fullscreen))
    app.add_url_rule('/bodega/cuadro-mando/tv', 'bodega_cuadro_mando_fullscreen', view_fs, methods=['GET'])
