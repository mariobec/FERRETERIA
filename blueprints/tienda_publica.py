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
    dig = ''.join(c for c in (os.getenv('WHATSAPP_VENTAS', '') or '') if c.isdigit())
    return {
        'carrito_config': {
            'storage_key': vt.CARRITO_STORAGE_KEY,
            'max_qty': vt.CARRITO_MAX_CANTIDAD,
            'whatsapp': dig,
            'nombre_tienda': nombre_tienda,
            'whatsapp_api_url': url_for('tienda_api_carrito_whatsapp', slug=slug),
        },
    }


def _assistant_template_ctx(slug: str, *, producto_id: int | None = None):
    """Contexto compartido del widget Liz en vitrina."""
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
        items, total = vt._buscar_items_asistente(q_text)
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
    out = vt.respuesta_asistente(slug=slug, mensaje=mensaje, producto_id=pid)
    out['ia_local_disponible'] = vt.ollama_vitrina_disponible()
    return jsonify({'ok': True, **out})


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
