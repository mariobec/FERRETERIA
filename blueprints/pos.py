"""Punto de venta y APIs /api/pos/* (Fase 3)."""
from flask_login import login_required

from blueprints._app_ref import app_module


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


def register_pos_routes(app):
    m = app_module()
    app.add_url_rule('/punto_venta', 'punto_venta', _wrap_pos_emitir_caja(m.punto_venta), methods=['GET'])
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
    app.add_url_rule('/actualizar_item', 'actualizar_item', _wrap_pos_emitir_caja(m.actualizar_item), methods=['POST'])
    app.add_url_rule(
        '/pos/usuarios_autorizar_descuento',
        'pos_usuarios_autorizar_descuento',
        _wrap_pos_caja_sin_permiso(m.pos_usuarios_autorizar_descuento),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/pos/cross-sell-sugerencias',
        'api_pos_cross_sell_sugerencias',
        _wrap_pos_api_emitir(m.api_pos_cross_sell_sugerencias),
        methods=['GET'],
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
