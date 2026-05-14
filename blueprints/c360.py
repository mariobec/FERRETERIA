"""Customer 360 — rutas registradas sobre la app principal (modelos y lógica siguen en app)."""

from blueprints._app_ref import app_module


def register_c360_routes(app):
    """Debe llamarse al final de la carga de `app` (después de definir las vistas en app.py)."""
    m = app_module()
    pr = m.permisos_required

    app.add_url_rule(
        '/gerencia/c360-ia-dashboard',
        'gerencia_c360_ia_dashboard',
        pr('panel_gerencia', 'gestionar_usuarios')(m.gerencia_c360_ia_dashboard),
    )
    app.add_url_rule(
        '/gerencia/c360-ejecutar-motor',
        'gerencia_c360_ejecutar_motor',
        pr('panel_gerencia', 'gestionar_usuarios')(m.gerencia_c360_ejecutar_motor),
        methods=['POST'],
    )
    app.add_url_rule(
        '/admin/clientes/<int:cliente_id>/c360',
        'admin_cliente_c360',
        pr('gestionar_usuarios')(m.admin_cliente_c360),
        methods=['GET', 'POST'],
    )
    app.add_url_rule(
        '/api/c360/ocr-mock',
        'api_c360_ocr_mock',
        pr('gestionar_usuarios')(m.api_c360_ocr_mock),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/c360/clientes/<int:cliente_id>/resumen',
        'api_c360_cliente_resumen',
        pr('gestionar_usuarios')(m.api_c360_cliente_resumen),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/c360/worker-noche',
        'api_c360_worker_noche',
        m.api_c360_worker_noche,
        methods=['POST'],
    )
    app.add_url_rule(
        '/admin/c360/llamadas-hoy',
        'admin_c360_llamadas_hoy',
        pr('gestionar_usuarios')(m.admin_c360_llamadas_hoy),
    )
    app.add_url_rule(
        '/admin/c360/enviar-oferta-ia',
        'admin_c360_enviar_oferta_ia',
        pr('gestionar_usuarios')(m.admin_c360_enviar_oferta_ia),
        methods=['POST'],
    )
    app.add_url_rule(
        '/p/c360-oferta/<token>',
        'c360_oferta_publica_landing',
        m.c360_oferta_publica_landing,
    )
    app.add_url_rule(
        '/p/c360-oferta/<token>/pdf',
        'c360_oferta_publica_pdf',
        m.c360_oferta_publica_pdf,
    )
