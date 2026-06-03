"""E-commerce ERP — bandeja pedidos web (PED-WEB)."""
from __future__ import annotations

from flask import Response, flash, jsonify, redirect, render_template, request, url_for
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
    from services import vitrina_tienda_service as vt

    m = app_module()
    m._asegurar_columnas_entrega_ticket()
    vista = (request.args.get('vista') or 'activos').strip().lower()
    filtro = (request.args.get('estado') or 'ACTIVOS').strip().upper()
    filtro_extra = (request.args.get('extra') or '').strip().lower() or None

    if vista == 'historial':
        pedidos_raw = ecom.listar_pedidos_historial(dias=int(request.args.get('dias') or 7))
        pedidos = [ecom.enriquecer_pedido_fila(v) for v in pedidos_raw]
    else:
        pedidos_raw = ecom.listar_pedidos_web(estado=filtro, filtro_extra=filtro_extra)
        pedidos = [ecom.enriquecer_pedido_fila(v) for v in pedidos_raw]

    contadores = ecom.contadores_bandeja()
    metricas = ecom.metricas_ecommerce(dias=7)
    caja = None
    try:
        caja = m.obtener_caja_activa()
    except Exception:
        caja = None
    return render_template(
        'ecommerce/bandeja_pedidos.html',
        pedidos=pedidos,
        filtro_estado=filtro,
        filtro_extra=filtro_extra,
        vista=vista,
        contadores=contadores,
        metricas=metricas,
        pedido_web_habilitado=vt.pedido_web_habilitado(),
        vitrina_url=vt.url_tienda(vt.TIENDA_SLUG_SD),
        sin_caja_abierta=(caja is None),
        requiere_caja=ecom.requiere_caja_abierta_pedido_web(),
    )


def ecommerce_pedido_detalle(vid: int):
    venta = ecom.obtener_pedido_web(int(vid))
    if not venta:
        flash('Pedido web no encontrado.', 'warning')
        return redirect(url_for('ecommerce_bandeja'))
    det = ecom.enriquecer_pedido_detalle(venta)
    return render_template(
        'ecommerce/pedido_detalle.html',
        fila=det,
        venta=venta,
        timeline=det.get('timeline') or [],
        lineas=det.get('lineas') or [],
    )


def ecommerce_pedido_estado(vid: int):
    accion = (request.form.get('accion') or '').strip()
    operador = (getattr(current_user, 'nombre', None) or 'operador')[:80]
    notificar = request.form.get('notificar_whatsapp') == '1'
    res = ecom.actualizar_estado_preparacion(
        int(vid),
        accion,
        operador=operador,
        notificar_whatsapp=notificar or accion in ('listo', 'listo_retiro', 'listo_meson'),
    )
    if res.get('ok'):
        flash(f"Pedido {res.get('ped_web_codigo')} → {res.get('estado')}", 'success')
        if res.get('whatsapp_url'):
            flash('Puede avisar al cliente por WhatsApp desde el detalle del pedido.', 'info')
    else:
        flash('No se pudo actualizar el pedido.', 'warning')
    next_url = request.form.get('next') or url_for('ecommerce_bandeja')
    return redirect(next_url)


def ecommerce_pedido_anular(vid: int):
    motivo = (request.form.get('motivo') or '').strip()
    operador = (getattr(current_user, 'nombre', None) or 'operador')[:80]
    res = ecom.anular_pedido_web(int(vid), motivo=motivo, operador=operador)
    if res.get('ok'):
        flash(res.get('mensaje') or 'Pedido anulado.', 'success')
    else:
        flash(res.get('mensaje') or 'No se pudo anular.', 'warning')
    return redirect(request.form.get('next') or url_for('ecommerce_bandeja'))


def api_ecommerce_pedidos():
    vista = (request.args.get('vista') or 'activos').strip().lower()
    filtro = (request.args.get('estado') or 'ACTIVOS').strip().upper()
    filtro_extra = (request.args.get('extra') or '').strip().lower() or None
    if vista == 'historial':
        rows = ecom.listar_pedidos_historial(dias=int(request.args.get('dias') or 7))
    else:
        rows = ecom.listar_pedidos_web(estado=filtro, filtro_extra=filtro_extra)
    data = [ecom.serializar_pedido_api(ecom.enriquecer_pedido_fila(v)) for v in rows]
    return jsonify(
        ok=True,
        vista=vista,
        contadores=ecom.contadores_bandeja(),
        metricas=ecom.metricas_ecommerce(),
        pedidos=data,
    )


def ecommerce_export_csv():
    vista = (request.args.get('vista') or 'activos').strip().lower()
    filtro = (request.args.get('estado') or 'ACTIVOS').strip().upper()
    if vista == 'historial':
        rows = ecom.listar_pedidos_historial(dias=int(request.args.get('dias') or 7))
    else:
        rows = ecom.listar_pedidos_web(estado=filtro)
    csv_text = ecom.exportar_pedidos_csv(rows, historial=(vista == 'historial'))
    fname = f'pedidos_web_{vista}_{filtro.lower()}.csv'
    return Response(
        csv_text,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}'},
    )


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
    app.add_url_rule(
        '/ecommerce/pedidos/<int:vid>/anular',
        view_func=_wrap_ecom(ecommerce_pedido_anular),
        methods=['POST'],
        endpoint='ecommerce_pedido_anular',
    )
    app.add_url_rule(
        '/api/ecommerce/pedidos',
        view_func=_wrap_ecom(api_ecommerce_pedidos),
        methods=['GET'],
        endpoint='api_ecommerce_pedidos',
    )
    app.add_url_rule(
        '/ecommerce/pedidos/export.csv',
        view_func=_wrap_ecom(ecommerce_export_csv),
        methods=['GET'],
        endpoint='ecommerce_export_csv',
    )
