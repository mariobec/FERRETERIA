"""Rutas dominio caja: cobranza, cambios, saldos a favor, historial de cierres."""
from flask_login import login_required

from blueprints._app_ref import app_module


def _wrap_ticket_lectura(fn):
    """Ver/imprimir tickets cobro y retiro: sin exigir caja abierta; incluye operadores ecom/bodega."""
    m = app_module()
    return login_required(
        m.permisos_required(
            'caja_cobrar_vale',
            'ecommerce_pedidos',
            'bodega_operador',
            'gestionar_usuarios',
            'caja_cerrar',
        )(fn)
    )


def _wrap_caja_vale(fn):
    m = app_module()
    return login_required(m.caja_requerida(m.permisos_required('caja_cobrar_vale')(fn)))


def _wrap_caja_prototipo(fn):
    """Prototipo caja: permiso cobrar, pero permite ver pantalla sin caja abierta (formulario inline)."""
    m = app_module()
    return login_required(m.permisos_required('caja_cobrar_vale')(fn))


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
    app.add_url_rule('/caja/prototipo', 'caja_prototipo', _wrap_caja_prototipo(m.caja_prototipo), methods=['GET'])
    app.add_url_rule(
        '/caja/transferencias',
        'caja_transferencias',
        _wrap_caja_vale(m.caja_transferencias),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/<int:vid>/confirmar',
        'api_caja_transferencia_confirmar',
        _wrap_caja_vale(m.api_caja_transferencia_confirmar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/<int:vid>/rechazar',
        'api_caja_transferencia_rechazar',
        _wrap_caja_vale(m.api_caja_transferencia_rechazar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/sincronizar-correo',
        'api_caja_transferencia_sincronizar_correo',
        _wrap_caja_vale(m.api_caja_transferencia_sincronizar_correo),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/correo/<int:cid>/confirmar',
        'api_caja_transferencia_confirmar_correo',
        _wrap_caja_vale(m.api_caja_transferencia_confirmar_correo),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/correo/<int:cid>/descartar',
        'api_caja_transferencia_descartar_correo',
        _wrap_caja_vale(m.api_caja_transferencia_descartar_correo),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/alerta',
        'api_caja_transferencias_alerta',
        _wrap_caja_vale(m.api_caja_transferencias_alerta),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/correo/<int:cid>',
        'api_caja_transferencia_correo_detalle',
        _wrap_caja_vale(m.api_caja_transferencia_correo_detalle),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/historial',
        'api_caja_transferencias_historial',
        _wrap_saldos_favor(m.api_caja_transferencias_historial),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/caja/transferencias/reactivar-descartados',
        'api_caja_transferencias_reactivar_descartados',
        _wrap_saldos_favor(m.api_caja_transferencias_reactivar_descartados),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/caja/vale-por-folio',
        'api_caja_vale_por_folio',
        _wrap_caja_vale(m.api_caja_vale_por_folio),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/caja/vales-pendientes/sla',
        'api_caja_vales_pendientes_sla',
        _wrap_caja_vale(m.api_caja_vales_pendientes_sla),
        methods=['GET'],
    )
    app.add_url_rule('/caja/cambios', 'caja_cambios', _wrap_caja_vale(m.caja_cambios), methods=['GET', 'POST'])
    # Postventa 2.0 (wizard). getattr evita tumbar el ERP si el reload ocurre a medias.
    _postventa = getattr(m, 'postventa_asistente', None)
    if callable(_postventa):
        app.add_url_rule(
            '/ventas/postventa',
            'postventa_asistente',
            _wrap_caja_vale(_postventa),
            methods=['GET'],
        )
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
        '/caja/vales/anular_lote',
        'anular_vales_caja_lote',
        _wrap_anular_vale(m.anular_vales_caja_lote),
        methods=['POST'],
    )
    app.add_url_rule(
        '/caja/limpiar_cola_cierre',
        'limpiar_cola_cierre_caja',
        login_required(m.permisos_required('gestionar_usuarios', 'anular_vale_caja')(m.limpiar_cola_cierre_caja)),
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
        _wrap_ticket_lectura(m.ver_ticket_cobro),
        methods=['GET'],
    )
    app.add_url_rule(
        '/caja/ticket_retiro/<int:id>',
        'ver_ticket_retiro',
        _wrap_ticket_lectura(m.ver_ticket_retiro),
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
