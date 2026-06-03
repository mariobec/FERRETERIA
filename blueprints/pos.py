"""Punto de venta y APIs /api/pos/* (Fase 3)."""
from functools import wraps

from flask import request
from flask_login import login_required

from blueprints._app_ref import app_module


def _wrap_pos_acceso_directo(fn):
    m = app_module()
    return login_required(m.permisos_required('pos_emitir_vale')(fn))


def _wrap_pos_emitir_caja(fn):
    m = app_module()
    return login_required(m.caja_requerida(m.permisos_required('pos_emitir_vale')(fn)))


def _wrap_guardar_venta(fn):
    m = app_module()
    return login_required(
        m.caja_requerida(m.permisos_required('pos_emitir_vale', 'caja_cobrar_vale', 'gestionar_usuarios')(fn))
    )


def _wrap_pos_caja_sin_permiso(fn):
    m = app_module()
    return login_required(m.caja_requerida(fn))


def _wrap_pos_api_emitir(fn):
    m = app_module()
    return login_required(m.permisos_required('pos_emitir_vale')(fn))


def _wrap_pos_despacho_vale(fn):
    """Con token QR válido no exige sesión (lector en mesón bodega/tienda)."""
    m = app_module()
    guarded = m.permisos_required(
        'pos_emitir_vale', 'bodega_operador', 'caja_cobrar_vale', 'gestionar_usuarios'
    )(fn)

    @wraps(fn)
    def decorated(*args, **kwargs):
        tok = (request.args.get('t') or '').strip()
        vid = kwargs.get('vid')
        if tok and vid is not None:
            try:
                vv = m.pos_despacho_vale_token_verify(tok)
                if vv is not None and int(vv) == int(vid):
                    return fn(*args, **kwargs)
            except (TypeError, ValueError):
                pass
        return guarded(*args, **kwargs)

    return decorated


def _wrap_pos_ticket_vale(fn):
    m = app_module()
    return login_required(
        m.caja_requerida(
            m.permisos_required('pos_emitir_vale', 'caja_cobrar_vale', 'gestionar_usuarios')(fn)
        )
    )


def _wrap_pos_mentor_api(fn):
    m = app_module()
    return login_required(
        m.permisos_required('pos_emitir_vale', 'caja_cobrar_vale', 'gestionar_usuarios')(fn)
    )


def register_pos_routes(app):
    m = app_module()
    app.add_url_rule('/punto_venta', 'punto_venta', _wrap_pos_emitir_caja(m.punto_venta), methods=['GET'])
    app.add_url_rule('/pos', 'pos_acceso_directo', _wrap_pos_acceso_directo(m.pos_acceso_directo), methods=['GET'])
    app.add_url_rule(
        '/pos/vendedor',
        'pos_acceso_vendedor',
        _wrap_pos_acceso_directo(m.pos_acceso_directo),
        methods=['GET'],
    )
    app.add_url_rule(
        '/pos/command-deck',
        'pos_command_deck',
        _wrap_pos_emitir_caja(m.pos_command_deck),
        methods=['GET'],
    )
    app.add_url_rule('/guardar_venta', 'guardar_venta', _wrap_guardar_venta(m.guardar_venta), methods=['POST'])
    app.add_url_rule(
        '/agregar_producto_venta',
        'agregar_producto_venta',
        _wrap_pos_emitir_caja(m.agregar_producto_venta),
        methods=['GET', 'POST'],
    )
    app.add_url_rule(
        '/eliminar_detalle/<int:id>',
        'eliminar_detalle',
        _wrap_pos_emitir_caja(m.eliminar_detalle),
        methods=['POST'],
    )
    app.add_url_rule('/finalizar_venta', 'finalizar_venta', _wrap_pos_emitir_caja(m.finalizar_venta), methods=['POST'])
    app.add_url_rule(
        '/pos/ticket/<int:venta_id>',
        'pos_ticket_vale',
        _wrap_pos_ticket_vale(m.pos_ticket_vale),
        methods=['GET'],
    )
    app.add_url_rule(
        '/pos/despacho/vale/<int:vid>',
        'pos_despacho_vale',
        _wrap_pos_despacho_vale(m.pos_despacho_vale),
        methods=['GET'],
    )
    app.add_url_rule(
        '/r/despacho/<int:vid>/<token_qr>',
        'pos_despacho_vale_qr',
        m.pos_despacho_vale_qr_short,
        methods=['GET'],
    )
    app.add_url_rule(
        '/r/despacho/folio/<int:folio>',
        'pos_despacho_vale_folio',
        m.pos_despacho_vale_folio_qr,
        methods=['GET'],
    )
    app.add_url_rule(
        '/r/scan',
        'qr_scan_despacho',
        m.qr_scan_despacho_redirect,
        methods=['GET', 'POST'],
    )
    app.add_url_rule(
        '/api/pos/despacho/vale/<int:vid>/registrar-entrega',
        'api_registrar_entrega_ticket',
        m.api_registrar_entrega_ticket,
        methods=['POST'],
    )
    app.add_url_rule('/actualizar_item', 'actualizar_item', _wrap_pos_emitir_caja(m.actualizar_item), methods=['POST'])
    app.add_url_rule(
        '/pos/usuarios_autorizar_descuento',
        'pos_usuarios_autorizar_descuento',
        _wrap_pos_caja_sin_permiso(m.pos_usuarios_autorizar_descuento),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/producto-ficha/<int:producto_id>',
        'api_pos_producto_ficha',
        _wrap_pos_api_emitir(m.api_pos_producto_ficha),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/cross-sell-sugerencias',
        'api_pos_cross_sell_sugerencias',
        _wrap_pos_api_emitir(m.api_pos_cross_sell_sugerencias),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/cross-sell-toggle',
        'api_pos_cross_sell_toggle',
        _wrap_pos_api_emitir(m.api_pos_cross_sell_toggle),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/rut-obligatorio-toggle',
        'api_pos_rut_obligatorio_toggle',
        _wrap_pos_api_emitir(m.api_pos_rut_obligatorio_toggle),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/cross-sell-reject',
        'api_pos_cross_sell_reject',
        _wrap_pos_api_emitir(m.api_pos_cross_sell_reject),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/identificar-producto-foto',
        'api_pos_identificar_producto_foto',
        _wrap_pos_api_emitir(m.api_pos_identificar_producto_foto),
        methods=['POST'],
    )
    app.add_url_rule(
        '/pos/live-wall/staff',
        'pos_live_wall_staff',
        _wrap_pos_emitir_caja(m.pos_live_wall_staff),
        methods=['GET'],
    )
    app.add_url_rule(
        '/pos/live-wall/cliente',
        'pos_live_wall_cliente',
        m.pos_live_wall_cliente,
        methods=['GET'],
    )
    app.add_url_rule(
        '/pos/experience-wall',
        'pos_experience_wall',
        m.pos_experience_wall,
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/live-wall/snapshot',
        'api_pos_live_wall_snapshot',
        m.api_pos_live_wall_snapshot,
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/vincular-cliente',
        'api_pos_vincular_cliente',
        _wrap_pos_api_emitir(m.api_pos_vincular_cliente),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/vales-hoy',
        'api_pos_vales_hoy',
        _wrap_pos_api_emitir(m.api_pos_vales_hoy),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/pedidos-apedido',
        'api_pos_pedidos_apedido',
        _wrap_pos_api_emitir(m.api_pos_pedidos_apedido),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/pedidos-apedido/<int:pedido_id>/estado',
        'api_pos_pedidos_apedido_estado',
        _wrap_pos_api_emitir(m.api_pos_pedidos_apedido_estado),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/carrito-html',
        'api_pos_carrito_html',
        _wrap_pos_api_emitir(m.api_pos_carrito_html),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/nueva-venta',
        'api_pos_nueva_venta',
        _wrap_pos_api_emitir(m.api_pos_nueva_venta),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/retiro-linea',
        'api_pos_retiro_linea',
        _wrap_pos_api_emitir(m.api_pos_retiro_linea),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/escanear-agregar',
        'api_pos_escanear_agregar',
        _wrap_pos_api_emitir(m.api_pos_escanear_agregar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/producto-alta-rapida',
        'api_pos_producto_alta_rapida',
        _wrap_pos_api_emitir(m.api_pos_producto_alta_rapida),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/vincular-codigo',
        'api_pos_vincular_codigo',
        _wrap_pos_api_emitir(m.api_pos_vincular_codigo),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/imprimir-ticket/<int:venta_id>',
        'api_pos_imprimir_ticket_termica',
        login_required(
            m.permisos_required('pos_emitir_vale', 'caja_cobrar_vale', 'gestionar_usuarios')(
                m.api_pos_imprimir_ticket_termica
            )
        ),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/pos/impresora/diagnostico',
        'api_pos_impresora_diagnostico',
        login_required(m.permisos_required('gestionar_usuarios', 'pos_emitir_vale')(m.api_pos_impresora_diagnostico)),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/mentor/contexto',
        'api_pos_mentor_contexto',
        _wrap_pos_mentor_api(m.api_pos_mentor_contexto),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/mentor/telemetria',
        'api_pos_mentor_telemetria',
        _wrap_pos_mentor_api(m.api_pos_mentor_telemetria),
        methods=['POST'],
    )
