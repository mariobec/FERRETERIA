"""Explorador visual catálogo Chilemat (VTEX) + vinculación ERP."""
from __future__ import annotations

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from blueprints._app_ref import app_module
from services import chilemat_cargas_service as chm_cargas
from services import chilemat_catalogo_ui_service as chm_ui
from services import chilemat_ficha_service as chm_ficha
from services import chilemat_vinculacion_service as chm_vinc


def _wrap(fn):
    m = app_module()
    return login_required(
        m.permisos_required(
            'revision_precios',
            'radar_precios',
            'gestionar_usuarios',
            'ver_gerencia',
            'admin_inventario',
        )(fn)
    )


def _usuario_puede_cargas_destructivas() -> bool:
    if not getattr(current_user, 'is_authenticated', False) or not current_user.is_authenticated:
        return False
    rol = getattr(current_user, 'rol', None)
    if rol:
        rol_nombre = (rol.nombre or '').strip().lower()
        if rol_nombre in ('admin', 'administrador', 'superadmin', 'super admin'):
            return True
        permisos_rol = [rp.permiso.nombre for rp in rol.rol_permisos if rp.permiso]
        if 'gestionar_usuarios' in permisos_rol or 'admin_inventario' in permisos_rol:
            return True
    return False


def _accion_es_destructiva(accion: str, *, masivo: bool) -> bool:
    accion = (accion or '').strip()
    if accion in ('reset_total', 'reset_taxonomia'):
        return True
    return accion == 'borrar_productos' and masivo


def chilemat_catalogo_explorer():
    stats = chm_ui.estadisticas_explorador()
    filtros = chm_ui.opciones_filtros()
    return render_template(
        'chilemat_catalogo_explorer.html',
        stats=stats,
        filtros=filtros,
    )


def api_chilemat_catalogo_productos():
    rubro = request.args.get('rubro_vtex_id') or request.args.get('rubro')
    sub = request.args.get('sub_vtex_id') or request.args.get('sub')
    try:
        rubro_id = int(rubro) if rubro not in (None, '', '0') else None
    except (TypeError, ValueError):
        rubro_id = None
    try:
        sub_id = int(sub) if sub not in (None, '', '0') else None
    except (TypeError, ValueError):
        sub_id = None

    data = chm_ui.listar_productos(
        q=(request.args.get('q') or '').strip(),
        rubro_vtex_id=rubro_id,
        sub_vtex_id=sub_id,
        solo_vinculados=request.args.get('solo_vinculados') in ('1', 'true', 'on'),
        solo_sin_vincular=request.args.get('solo_sin_vincular') in ('1', 'true', 'on'),
        page=int(request.args.get('page') or 1),
        per_page=int(request.args.get('per_page') or 50),
    )
    return jsonify({'ok': True, **data})


def api_chilemat_catalogo_stats():
    return jsonify({'ok': True, 'stats': chm_ui.estadisticas_explorador()})


def chilemat_vinculacion_index():
    stats = chm_ui.estadisticas_explorador()
    filtros = chm_ui.opciones_filtros()
    return render_template(
        'chilemat_vinculacion.html',
        stats=stats,
        filtros=filtros,
    )


def api_chilemat_vincular_lista():
    rubro = request.args.get('rubro_vtex_id')
    sub = request.args.get('sub_vtex_id')
    try:
        rubro_id = int(rubro) if rubro not in (None, '', '0') else None
    except (TypeError, ValueError):
        rubro_id = None
    try:
        sub_id = int(sub) if sub not in (None, '', '0') else None
    except (TypeError, ValueError):
        sub_id = None
    data = chm_vinc.listar_pendientes_vinculacion(
        q=(request.args.get('q') or '').strip(),
        rubro_vtex_id=rubro_id,
        sub_vtex_id=sub_id,
        page=int(request.args.get('page') or 1),
        per_page=int(request.args.get('per_page') or 25),
        con_sugerencias=True,
    )
    return jsonify({'ok': True, **data})


def api_chilemat_vincular_buscar_erp():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'ok': True, 'items': []})
    items = chm_vinc.buscar_productos_erp(q, limit=int(request.args.get('limit') or 20))
    return jsonify({'ok': True, 'items': items})


def api_chilemat_ficha_vtex(vtex_product_id: str):
    refrescar = request.args.get('refresh') in ('1', 'true', 'on')
    ficha = chm_ficha.ficha_por_vtex_id(vtex_product_id, refrescar_api=refrescar)
    if not ficha.get('ok'):
        return jsonify(ficha), 404
    return jsonify(ficha)


def api_chilemat_ficha_producto(producto_id: int):
    refrescar = request.args.get('refresh') in ('1', 'true', 'on')
    ficha = chm_ficha.ficha_por_producto_erp(producto_id, refrescar_api=refrescar)
    if not ficha.get('ok'):
        return jsonify(ficha), 404
    return jsonify(ficha)


def api_chilemat_vincular_guardar():
    data = request.get_json(silent=True) or {}
    vtex_id = (data.get('vtex_product_id') or '').strip()
    producto_id = data.get('producto_id')
    usuario = getattr(current_user, 'nombre', None) or 'usuario'
    res = chm_vinc.vincular_producto(
        vtex_product_id=vtex_id,
        producto_id=producto_id,
        usuario=usuario,
        actualizar_codigo_chilemat=data.get('actualizar_codigo_chilemat', True) is not False,
        registrar_codigo_factura=data.get('registrar_codigo_factura', True) is not False,
        copiar_imagen=data.get('copiar_imagen', True) is not False,
    )
    if not res.get('ok'):
        return jsonify(res), 400
    return jsonify(res)


def api_chilemat_vincular_quitar():
    data = request.get_json(silent=True) or {}
    vtex_id = (data.get('vtex_product_id') or '').strip()
    res = chm_vinc.desvincular_producto(vtex_product_id=vtex_id)
    if not res.get('ok'):
        return jsonify(res), 400
    return jsonify(res)


def api_chilemat_vincular_auto():
    data = request.get_json(silent=True) or {}
    usuario = getattr(current_user, 'nombre', None) or 'usuario'
    res = chm_vinc.auto_vincular_sugerencias(
        max_items=int(data.get('max_items') or 25),
        confianza_min=float(data.get('confianza_min') or 0.7),
        usuario=usuario,
    )
    return jsonify(res)


def chilemat_cargas_index():
    stats = chm_cargas.resumen_bd()
    filtros = chm_ui.opciones_filtros()
    return render_template(
        'chilemat_cargas.html',
        stats=stats,
        filtros=filtros,
        acciones=chm_cargas.ACCIONES,
        puede_destructivo=_usuario_puede_cargas_destructivas(),
    )


def _parse_cargas_body() -> dict:
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()
    rubro_vtex_id = data.get('rubro_vtex_id')
    try:
        rubro_vtex_id = int(rubro_vtex_id) if rubro_vtex_id not in (None, '', '0') else None
    except (TypeError, ValueError):
        rubro_vtex_id = None
    limit = data.get('limit')
    try:
        limit = int(limit) if limit not in (None, '', '0') else None
    except (TypeError, ValueError):
        limit = None
    return {
        'accion': (data.get('accion') or '').strip(),
        'sin_sync': data.get('sin_sync') in (True, 'true', '1', 'on', 1),
        'solo_faltantes_sync': data.get('solo_faltantes_sync') in (True, 'true', '1', 'on', 1),
        'rubro': (data.get('rubro') or '').strip(),
        'rubro_vtex_id': rubro_vtex_id,
        'q': (data.get('q') or '').strip(),
        'limit': limit,
        'masivo': data.get('masivo') in (True, 'true', '1', 'on', 1),
        'forzar': data.get('forzar') in (True, 'true', '1', 'on', 1),
        'preview': data.get('preview') in (True, 'true', '1', 'on', 1),
        'confirmacion': (data.get('confirmacion') or '').strip(),
    }


def api_chilemat_cargas_ejecutar():
    p = _parse_cargas_body()
    if _accion_es_destructiva(p['accion'], masivo=p['masivo']) and not _usuario_puede_cargas_destructivas():
        return jsonify(
            ok=False,
            error='sin_permiso',
            mensaje='Esta acción requiere permiso de administrador o inventario.',
        ), 403

    out = chm_cargas.ejecutar(**p)
    status = 200 if out.get('ok') else 400
    return jsonify(out), status


def register_chilemat_catalogo_routes(app) -> None:
    app.add_url_rule(
        '/compras/chilemat/explorador',
        'chilemat_catalogo_explorer',
        _wrap(chilemat_catalogo_explorer),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/catalogo',
        'api_chilemat_catalogo_productos',
        _wrap(api_chilemat_catalogo_productos),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/catalogo/stats',
        'api_chilemat_catalogo_stats',
        _wrap(api_chilemat_catalogo_stats),
        methods=['GET'],
    )
    app.add_url_rule(
        '/compras/chilemat/vincular',
        'chilemat_vinculacion',
        _wrap(chilemat_vinculacion_index),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/vincular/lista',
        'api_chilemat_vincular_lista',
        _wrap(api_chilemat_vincular_lista),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/vincular/buscar-erp',
        'api_chilemat_vincular_buscar_erp',
        _wrap(api_chilemat_vincular_buscar_erp),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/vincular',
        'api_chilemat_vincular_guardar',
        _wrap(api_chilemat_vincular_guardar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/vincular/quitar',
        'api_chilemat_vincular_quitar',
        _wrap(api_chilemat_vincular_quitar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/vincular/auto',
        'api_chilemat_vincular_auto',
        _wrap(api_chilemat_vincular_auto),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/ficha/<vtex_product_id>',
        'api_chilemat_ficha_vtex',
        _wrap(api_chilemat_ficha_vtex),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/ficha/producto/<int:producto_id>',
        'api_chilemat_ficha_producto',
        _wrap(api_chilemat_ficha_producto),
        methods=['GET'],
    )
    app.add_url_rule(
        '/compras/chilemat/cargas',
        'chilemat_cargas',
        _wrap(chilemat_cargas_index),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/compras/chilemat/cargas/ejecutar',
        'api_chilemat_cargas_ejecutar',
        _wrap(api_chilemat_cargas_ejecutar),
        methods=['POST'],
    )
