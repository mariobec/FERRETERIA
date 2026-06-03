"""Vitrina pública piloto — extensión lhexia.cl/tienda/ferreteria-santo-domingo."""
from __future__ import annotations

import os

from flask import abort, jsonify, redirect, render_template, request, url_for

from services import vitrina_tienda_service as vt


def _empresa_ctx():
    from blueprints._app_ref import app_module

    m = app_module()
    cfg = m.obtener_config_empresa()
    nombre = (cfg.get('nombre_comercial') or cfg.get('razon_social') or vt.TIENDA_TITULO_DEFAULT).strip()
    return cfg, nombre


def _wa_base():
    dig = ''.join(c for c in (os.getenv('WHATSAPP_VENTAS', '') or '') if c.isdigit())
    return f'https://wa.me/{dig}' if dig else None


def _carrito_template_ctx(slug: str, nombre_tienda: str):
    from services import webpay_service as wp

    dig = ''.join(c for c in (os.getenv('WHATSAPP_VENTAS', '') or '') if c.isdigit())
    pedido_web = vt.pedido_web_habilitado()
    return {
        'carrito_config': {
            'storage_key': vt.CARRITO_STORAGE_KEY,
            'max_qty': vt.CARRITO_MAX_CANTIDAD,
            'whatsapp': dig,
            'nombre_tienda': nombre_tienda,
            'whatsapp_api_url': url_for('tienda_api_carrito_whatsapp', slug=slug),
            'vale_api_url': url_for('tienda_api_carrito_vale', slug=slug),
            'checkout_api_url': url_for('tienda_api_carrito_checkout', slug=slug),
            'pedido_web_habilitado': pedido_web,
            'webpay_habilitado': wp.webpay_habilitado() and pedido_web,
        },
    }


def _assistant_template_ctx(slug: str, *, producto_id: int | None = None):
    """Contexto compartido del widget Maylén en vitrina."""
    _cfg, nombre = _empresa_ctx()
    return {
        'assistant_producto_id': producto_id,
        'assistant_chips': vt.chips_asistente(producto_id=producto_id),
        'assistant_config': {
            'api_url': url_for('tienda_asistente', slug=slug),
            'catalogo_api_url': url_for('tienda_api_catalogo', slug=slug),
            'slug': slug,
            'producto_id': producto_id,
            'nombre_tienda': nombre,
            'asistente_nombre': vt.ASISTENTE_NOMBRE,
            'asistente_subtitulo': vt.ASISTENTE_SUBTITULO,
        },
        **_carrito_template_ctx(slug, nombre),
    }


def _canonical(path: str) -> str:
    from blueprints._app_ref import app_module

    m = app_module()
    try:
        return m._absolute_public_url(path)
    except Exception:
        return path


def tienda_index():
    if not vt.tienda_habilitada():
        abort(404)
    return redirect(url_for('tienda_vitrina', slug=vt.TIENDA_SLUG_SD))


def tienda_vitrina(slug: str):
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        abort(404)

    cfg, nombre_tienda = _empresa_ctx()
    page = request.args.get('page', 1, type=int)
    q_text = (request.args.get('q') or '').strip()
    marca = (request.args.get('marca') or '').strip()
    categoria = (request.args.get('categoria') or '').strip()
    cat_vtex = request.args.get('cat', type=int)
    orden = (request.args.get('orden') or 'recomendados').strip()
    solo_disp = request.args.get('solo_disponibles', '') in ('1', 'true', 'si', 'on')
    precio_min = request.args.get('precio_min', type=int)
    precio_max = request.args.get('precio_max', type=int)
    menu_param = request.args.get('menu')
    if menu_param is None:
        # Si ya viene una categoría seleccionada, cerrar menú por defecto
        # para no empujar el grid de productos hacia abajo.
        menu_abierto = (not q_text) and (cat_vtex is None)
    else:
        menu_abierto = (menu_param != '0') and (not q_text)

    if q_text:
        productos, total = vt.buscar_catalogo_vitrina(q_text, limite=48)
        listado = {
            'productos': productos,
            'total': total,
            'page': 1,
            'pages': 1,
            'per_page': max(len(productos), 1),
            'has_prev': False,
            'has_next': False,
        }
    else:
        listado = vt.listar_productos(
            page=page,
            q_text=q_text,
            marca=marca,
            categoria=categoria,
            cat_vtex_id=cat_vtex,
            precio_min=precio_min,
            precio_max=precio_max,
            orden=orden,
            solo_disponibles=solo_disp,
        )
    facetas = vt.facetas_filtro()
    menu_nav = vt.construir_menu_mega(slug=slug, cat_activa=cat_vtex)
    panel_activo = next((p for p in (menu_nav.get('paneles') or []) if p.get('visible')), None)
    base_path = f'/tienda/{slug}'
    return render_template(
        'tienda/ferreteria_santo_domingo.html',
        slug=slug,
        nombre_tienda=nombre_tienda,
        empresa_cfg=cfg,
        listado=listado,
        facetas=facetas,
        menu_nav=menu_nav,
        panel_activo=panel_activo,
        menu_abierto=menu_abierto,
        cat_vtex=cat_vtex,
        q=q_text,
        marca=marca,
        categoria=categoria,
        orden=orden,
        solo_disponibles=solo_disp,
        precio_min=precio_min,
        precio_max=precio_max,
        wa_base=_wa_base(),
        **_assistant_template_ctx(slug),
        page_canonical=_canonical(base_path),
        page_meta_description=(
            f'Catálogo en línea de {nombre_tienda}: productos con referencia Chilemat '
            'y disponibilidad en tienda. Precio referencial web.'
        ),
    )


def tienda_producto(slug: str, producto_id: int):
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        abort(404)

    det = vt.detalle_producto(producto_id)
    if not det:
        abort(404)

    cfg, nombre_tienda = _empresa_ctx()
    wa = _wa_base()
    msg = (
        f'Hola, consulto por: {det["nombre"]} '
        f'(ref {det.get("referencia") or det["producto_id"]}) — vitrina {nombre_tienda}'
    )
    wa_item = vt.whatsapp_pedido_url(telefono=os.getenv('WHATSAPP_VENTAS', ''), mensaje=msg) or wa

    return render_template(
        'tienda/producto.html',
        slug=slug,
        nombre_tienda=nombre_tienda,
        empresa_cfg=cfg,
        item=det,
        wa_item=wa_item,
        wa_base=wa,
        **_assistant_template_ctx(slug, producto_id=producto_id),
        vitrina_url=url_for('tienda_vitrina', slug=slug),
        page_canonical=_canonical(f'/tienda/{slug}/producto/{producto_id}'),
        page_meta_description=(det['nombre'][:160] + ' — ' + nombre_tienda)[:300],
    )


def tienda_api_catalogo(slug: str):
    """JSON catálogo para filtrar grilla sin recargar (Liz vitrina)."""
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    q_text = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    orden = (request.args.get('orden') or 'recomendados').strip()
    solo_disp = request.args.get('solo_disponibles', '') in ('1', 'true', 'si', 'on')
    if q_text:
        items, total = vt.buscar_catalogo_vitrina(q_text, limite=48)
        return jsonify(
            {
                'ok': True,
                'q': q_text,
                'productos': items,
                'total': total,
                'page': 1,
                'pages': 1,
                'per_page': len(items),
                'has_prev': False,
                'has_next': False,
            }
        )
    listado = vt.listar_productos(
        page=page,
        per_page=24,
        q_text=q_text,
        cat_vtex_id=None,
        orden=orden,
        solo_disponibles=solo_disp,
    )
    return jsonify({'ok': True, 'q': q_text, **listado})


def _sanitizar_lineas_carrito(lineas) -> list[dict]:
    clean: list[dict] = []
    if not isinstance(lineas, list):
        return clean
    for ln in lineas[:30]:
        if not isinstance(ln, dict):
            continue
        try:
            pid = int(ln.get('producto_id') or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        try:
            qty = int(ln.get('cantidad') or 1)
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, min(qty, vt.CARRITO_MAX_CANTIDAD))
        try:
            precio = int(ln.get('precio') or 0)
        except (TypeError, ValueError):
            precio = 0
        clean.append(
            {
                'producto_id': pid,
                'nombre': str(ln.get('nombre') or 'Producto').strip()[:120],
                'referencia': str(ln.get('referencia') or '').strip()[:80],
                'precio': max(0, precio),
                'precio_fmt': str(ln.get('precio_fmt') or '').strip()[:40],
                'cantidad': qty,
                'disponible': bool(ln.get('disponible')),
            }
        )
    return clean


def tienda_api_carrito_whatsapp(slug: str):
    """Arma mensaje y URL wa.me para el carrito vitrina."""
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    lineas = _sanitizar_lineas_carrito(data.get('lineas'))
    if not lineas:
        return jsonify({'ok': False, 'error': 'carrito_vacio'}), 400
    _cfg, nombre = _empresa_ctx()
    msg = vt.mensaje_whatsapp_carrito(
        nombre,
        lineas,
        cliente_nombre=(data.get('cliente_nombre') or '').strip(),
        cliente_telefono=(data.get('cliente_telefono') or '').strip(),
    )
    url = vt.whatsapp_pedido_url(
        telefono=os.getenv('WHATSAPP_VENTAS', ''),
        mensaje=msg,
        max_len=2000,
    )
    if not url:
        return jsonify({'ok': False, 'error': 'whatsapp_no_configurado'}), 503
    tot = vt.calcular_totales_carrito(lineas)
    return jsonify({'ok': True, 'url': url, 'mensaje': msg, 'totales': tot})


def tienda_asistente(slug: str):
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    mensaje = (data.get('mensaje') or '').strip()
    producto_id = data.get('producto_id')
    try:
        pid = int(producto_id) if producto_id is not None else None
    except (TypeError, ValueError):
        pid = None
    carrito = data.get('carrito') or data.get('carrito_lineas')
    if not isinstance(carrito, list):
        carrito = None
    try:
        out = vt.respuesta_asistente(
            slug=slug,
            mensaje=mensaje,
            producto_id=pid,
            carrito_lineas=carrito,
            cliente_nombre=(data.get('cliente_nombre') or '').strip(),
            cliente_telefono=(data.get('cliente_telefono') or '').strip(),
        )
        out['ia_local_disponible'] = vt.ollama_vitrina_disponible()
        return jsonify({'ok': True, **out})
    except Exception as ex:
        import logging

        logging.getLogger(__name__).exception('tienda_asistente: %s', ex)
        return jsonify({'ok': False, 'error': 'asistente_error', 'mensaje': str(ex)[:200]}), 500


def tienda_api_carrito_vale(slug: str):
    """Genera vale ERP Pendiente PED-WEB-###### desde carrito vitrina."""
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    if not vt.pedido_web_habilitado():
        return jsonify({'ok': False, 'error': 'pedido_web_disabled'}), 503
    data = request.get_json(silent=True) or {}
    lineas = _sanitizar_lineas_carrito(data.get('lineas') or data.get('carrito'))
    if not lineas:
        return jsonify({'ok': False, 'error': 'carrito_vacio'}), 400
    _cfg, nombre = _empresa_ctx()
    res = vt.crear_vale_pedido_web(
        lineas,
        cliente_nombre=(data.get('cliente_nombre') or '').strip(),
        cliente_telefono=(data.get('cliente_telefono') or '').strip(),
        nombre_tienda=nombre,
        punto_retiro=(data.get('punto_retiro') or 'Tienda').strip(),
    )
    if not res.get('ok'):
        err = res.get('error') or ''
        code = 503
        if err in ('carrito_vacio', 'sin_productos_validos', 'sin_stock'):
            code = 400
        elif err == 'sin_caja':
            code = 503
        return jsonify(res), code
    ui = vt._construir_ui_respuesta(
        reply=res.get('mensaje') or 'Vale generado.',
        cards=[],
        cierre_carrito=True,
        vale_pedido=res,
    )
    return jsonify({'ok': True, **res, 'ui': ui})


def _url_publica(endpoint: str, **kwargs) -> str:
    base = (os.getenv('PUBLIC_SITE_URL') or os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')
    if base:
        return base + url_for(endpoint, _external=False, **kwargs)
    return url_for(endpoint, _external=True, **kwargs)


def tienda_api_carrito_checkout(slug: str):
    """Checkout vitrina: reservar pedido (caja) o iniciar Webpay."""
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    if not vt.pedido_web_habilitado():
        return jsonify({'ok': False, 'error': 'pedido_web_disabled'}), 503

    from services import ecommerce_pedidos_service as ecom
    from services import webpay_service as wp

    data = request.get_json(silent=True) or {}
    lineas = _sanitizar_lineas_carrito(data.get('lineas') or data.get('carrito'))
    if not lineas:
        return jsonify({'ok': False, 'error': 'carrito_vacio'}), 400

    metodo = (data.get('metodo') or data.get('metodo_pago') or 'tienda').strip().lower()
    _cfg, nombre = _empresa_ctx()
    res = vt.crear_vale_pedido_web(
        lineas,
        cliente_nombre=(data.get('cliente_nombre') or '').strip(),
        cliente_telefono=(data.get('cliente_telefono') or '').strip(),
        nombre_tienda=nombre,
        punto_retiro=(data.get('punto_retiro') or 'Tienda').strip(),
    )
    if not res.get('ok'):
        err = res.get('error') or ''
        code = 503
        if err in ('carrito_vacio', 'sin_productos_validos', 'sin_stock'):
            code = 400
        return jsonify(res), code

    if metodo in ('tienda', 'caja', 'retiro', 'store'):
        ui = vt._construir_ui_respuesta(
            reply=res.get('mensaje') or 'Pedido registrado.',
            cierre_carrito=True,
            vale_pedido=res,
        )
        return jsonify({'ok': True, 'modo': 'tienda', **res, 'ui': ui})

    if metodo in ('webpay', 'tarjeta', 'card'):
        if not wp.webpay_habilitado():
            return jsonify({'ok': False, 'error': 'webpay_disabled', 'mensaje': 'Pago con tarjeta no disponible.'}), 503
        vid = int(res.get('venta_id') or 0)
        monto = int(res.get('monto_total') or 0)
        if vid <= 0 or monto <= 0:
            return jsonify({'ok': False, 'error': 'monto_invalido'}), 400
        retorno = _url_publica('tienda_webpay_retorno', slug=slug)
        tx = wp.crear_transaccion(
            buy_order=f'WEB{vid:08d}',
            session_id=f'PED{vid:08d}',
            amount=monto,
            return_url=retorno,
        )
        if not tx.get('ok'):
            return jsonify(tx), 502
        return jsonify(
            {
                'ok': True,
                'modo': 'webpay',
                'venta_id': vid,
                'ped_web_codigo': res.get('ped_web_codigo'),
                'monto_total': monto,
                'monto_total_fmt': res.get('monto_total_fmt'),
                'webpay_url': tx.get('url'),
                'webpay_token': tx.get('token'),
            }
        )

    return jsonify({'ok': False, 'error': 'metodo_invalido'}), 400


def tienda_webpay_retorno(slug: str):
    """Retorno Transbank → confirma pago y redirige a pantalla resultado."""
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        abort(404)

    from services import ecommerce_pedidos_service as ecom
    from services import webpay_service as wp

    token = (request.args.get('token_ws') or request.form.get('token_ws') or '').strip()
    _cfg, nombre = _empresa_ctx()
    ctx = {
        'slug': slug,
        'nombre_tienda': nombre,
        'vitrina_url': url_for('tienda_vitrina', slug=slug),
    }
    if not token:
        return render_template('tienda/pago_resultado.html', ok=False, mensaje='Token de pago no recibido.', **ctx)

    commit = wp.confirmar_transaccion(token)
    if not commit.get('ok'):
        return render_template(
            'tienda/pago_resultado.html',
            ok=False,
            mensaje=commit.get('mensaje') or 'No se pudo confirmar el pago.',
            **ctx,
        )
    if not commit.get('approved'):
        return render_template(
            'tienda/pago_resultado.html',
            ok=False,
            mensaje='El pago fue rechazado o cancelado. Puedes intentar de nuevo desde el carrito.',
            **ctx,
        )

    buy_order = (commit.get('buy_order') or '').strip()
    venta_id = 0
    if buy_order.upper().startswith('WEB') and buy_order[3:].isdigit():
        venta_id = int(buy_order[3:])
    if venta_id <= 0:
        return render_template(
            'tienda/pago_resultado.html',
            ok=False,
            mensaje='Pago aprobado pero no se pudo vincular al pedido. Contacte a la tienda.',
            **ctx,
        )

    cobro = ecom.cobrar_pedido_web_tarjeta(venta_id, metodo_pago='Webpay')
    ped_codigo = vt.codigo_pedido_web(venta_id)
    if not cobro.get('ok') and not cobro.get('ya_cobrado'):
        return render_template(
            'tienda/pago_resultado.html',
            ok=False,
            mensaje=cobro.get('mensaje') or 'Pago aprobado; confirme en caja con su código.',
            ped_web_codigo=ped_codigo,
            **ctx,
        )

    return render_template(
        'tienda/pago_resultado.html',
        ok=True,
        mensaje='¡Pago recibido! Estamos preparando tu pedido.',
        ped_web_codigo=ped_codigo,
        monto_total_fmt=vt._fmt_clp(commit.get('amount')),
        **ctx,
    )


def register_tienda_publica_routes(app) -> None:
    app.add_url_rule('/tienda', view_func=tienda_index, methods=['GET'])
    app.add_url_rule(
        '/tienda/<slug>',
        view_func=tienda_vitrina,
        methods=['GET'],
        endpoint='tienda_vitrina',
    )
    app.add_url_rule(
        '/tienda/<slug>/producto/<int:producto_id>',
        view_func=tienda_producto,
        methods=['GET'],
        endpoint='tienda_producto',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/catalogo',
        view_func=tienda_api_catalogo,
        methods=['GET'],
        endpoint='tienda_api_catalogo',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/asistente',
        view_func=tienda_asistente,
        methods=['POST'],
        endpoint='tienda_asistente',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/carrito/whatsapp',
        view_func=tienda_api_carrito_whatsapp,
        methods=['POST'],
        endpoint='tienda_api_carrito_whatsapp',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/carrito/vale',
        view_func=tienda_api_carrito_vale,
        methods=['POST'],
        endpoint='tienda_api_carrito_vale',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/carrito/checkout',
        view_func=tienda_api_carrito_checkout,
        methods=['POST'],
        endpoint='tienda_api_carrito_checkout',
    )
    app.add_url_rule(
        '/tienda/<slug>/pago/webpay/retorno',
        view_func=tienda_webpay_retorno,
        methods=['GET', 'POST'],
        endpoint='tienda_webpay_retorno',
    )
