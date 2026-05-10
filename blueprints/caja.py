"""Rutas dominio caja: cobranza, cambios, saldos a favor, historial de cierres."""
from flask_login import login_required

from blueprints._app_ref import app_module


def _wrap_caja_vale(fn):
    m = app_module()
    return login_required(m.caja_requerida(m.permisos_required('caja_cobrar_vale')(fn)))


def _wrap_saldos_favor(fn):
    m = app_module()
    return login_required(m.permisos_required('caja_cobrar_vale', 'gestionar_usuarios')(fn))


def _wrap_gest_usuarios(fn):
    m = app_module()
    return login_required(m.permisos_required('gestionar_usuarios')(fn))


def _wrap_ticket_cierre(fn):
    m = app_module()
    return login_required(m.permisos_required('gestionar_usuarios', 'caja_cerrar')(fn))


def _wrap_anular_vale(fn):
    m = app_module()
    return login_required(m.caja_requerida(m.permisos_required('anular_vale_caja')(fn)))


def register_caja_routes(app):
    m = app_module()
    app.add_url_rule('/caja/vales_pendientes', 'caja_pendientes', _wrap_caja_vale(m.caja_pendientes), methods=['GET'])
    app.add_url_rule('/caja/cambios', 'caja_cambios', _wrap_caja_vale(m.caja_cambios), methods=['GET', 'POST'])
    app.add_url_rule(
        '/api/cambios/producto/<codigo>',
        'api_cambios_producto',
        _wrap_caja_vale(m.api_cambios_producto),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/cambios/buscar_venta',
        'api_cambios_buscar_venta',
        _wrap_caja_vale(m.api_cambios_buscar_venta),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/cambios/venta/<int:id>',
        'api_cambios_venta_detalle',
        _wrap_caja_vale(m.api_cambios_venta_detalle),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/cambios/<int:id>/ticket',
        'ticket_cambio',
        _wrap_caja_vale(m.ticket_cambio),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/cambios/historial',
        'caja_cambios_historial',
        _wrap_caja_vale(m.caja_cambios_historial),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/saldos-favor',
        'caja_saldos_favor',
        _wrap_saldos_favor(m.caja_saldos_favor),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/vales/<int:id>/anular',
        'anular_vale_caja',
        _wrap_anular_vale(m.anular_vale_caja),
        methods=['POST'],
    )
    app.add_url_rule(
        '/procesar_cobro_caja/<int:id>',
        'procesar_cobro_caja',
        _wrap_caja_vale(m.procesar_cobro_caja),
        methods=['POST'],
    )
    app.add_url_rule(
        '/caja/vale_retiro/<int:id>',
        'ver_ticket_cobro',
        _wrap_caja_vale(m.ver_ticket_cobro),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/historial_cierres',
        'caja_historial_cierres',
        _wrap_gest_usuarios(m.caja_historial_cierres),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/historial_cierres/<int:id>/ticket',
        'ticket_cierre_historico',
        _wrap_ticket_cierre(m.ticket_cierre_historico),
        methods=['GET'],
    )
