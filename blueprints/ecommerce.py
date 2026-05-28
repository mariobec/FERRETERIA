"""E-commerce ERP — bandeja pedidos web (PED-WEB)."""
from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints._app_ref import app_module
from services import ecommerce_pedidos_service as ecom


def _wrap_ecom(fn):
    m = app_module()
    return login_required(
        m.permisos_required(
            'ecommerce_pedidos',
            'gestionar_usuarios',
            'bodega_operador',
            'caja_cobrar_vale',
        )(fn)
    )


def ecommerce_bandeja():
    filtro = (request.args.get('estado') or 'ACTIVOS').strip().upper()
    pedidos_raw = ecom.listar_pedidos_web(estado=filtro)
    pedidos = [ecom.enriquecer_pedido_fila(v) for v in pedidos_raw]
    contadores = ecom.contadores_bandeja()
    return render_template(
        'ecommerce/bandeja_pedidos.html',
        pedidos=pedidos,
        filtro_estado=filtro,
        contadores=contadores,
    )


def ecommerce_pedido_detalle(vid: int):
    venta = ecom.obtener_pedido_web(int(vid))
    if not venta:
        flash('Pedido web no encontrado.', 'warning')
        return redirect(url_for('ecommerce_bandeja'))
    fila = ecom.enriquecer_pedido_fila(venta)
    return render_template('ecommerce/pedido_detalle.html', fila=fila, venta=venta)


def ecommerce_pedido_estado(vid: int):
    accion = (request.form.get('accion') or '').strip()
    operador = (getattr(current_user, 'nombre', None) or 'operador')[:80]
    res = ecom.actualizar_estado_preparacion(int(vid), accion, operador=operador)
    if res.get('ok'):
        flash(f"Pedido {res.get('ped_web_codigo')} → {res.get('estado')}", 'success')
    else:
        flash('No se pudo actualizar el pedido.', 'warning')
    next_url = request.form.get('next') or url_for('ecommerce_bandeja')
    return redirect(next_url)


def register_ecommerce_routes(app):
    app.add_url_rule(
        '/ecommerce/pedidos',
        view_func=_wrap_ecom(ecommerce_bandeja),
        methods=['GET'],
        endpoint='ecommerce_bandeja',
    )
    app.add_url_rule(
        '/ecommerce/pedidos/<int:vid>',
        view_func=_wrap_ecom(ecommerce_pedido_detalle),
        methods=['GET'],
        endpoint='ecommerce_pedido_detalle',
    )
    app.add_url_rule(
        '/ecommerce/pedidos/<int:vid>/estado',
        view_func=_wrap_ecom(ecommerce_pedido_estado),
        methods=['POST'],
        endpoint='ecommerce_pedido_estado',
    )
