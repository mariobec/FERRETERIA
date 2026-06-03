"""Módulo cliente Fábrica de Color — fuera del catálogo vitrina pública."""
from __future__ import annotations

import os

from flask import abort, jsonify, render_template, request, url_for
from flask_login import current_user

from services import fabrica_color_service as fc
from services import modulo_pinturas_session_service as ms
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
    from blueprints.tienda_publica import _carrito_template_ctx as _ctx

    return _ctx(slug, nombre_tienda)


def _fabrica_assistant_ctx(slug: str):
    from blueprints.tienda_publica import _assistant_template_ctx

    ctx = _assistant_template_ctx(slug)
    ctx['assistant_chips'] = [
        '¿Qué brillo para dormitorio?',
        '¿Cuánto rinde un galón?',
        'Complementos para pintar',
        '¿Pintura exterior para fachada?',
    ]
    return ctx


def _canonical(path: str) -> str:
    from blueprints._app_ref import app_module

    m = app_module()
    try:
        return m._absolute_public_url(path)
    except Exception:
        return path


def _render_wizard(token: str, sesion: dict):
    if not vt.tienda_habilitada():
        abort(404)
    slug = vt.TIENDA_SLUG_SD
    cfg, nombre_tienda = _empresa_ctx()
    base_path = f'/modulos/pinturas/{token}'
    tv_mode = (request.args.get('tv') or '').strip().lower() in ('1', 'true', 'si', 'yes')
    if sesion.get('modo') == 'caja':
        tv_mode = True
    initial = fc.payload_inicial()
    scene_urls = {
        key: url_for('static', filename=path)
        for key, path in initial.get('scene_assets', {}).items()
    }
    for amb in initial.get('ambientes') or []:
        photo = amb.get('photo')
        if photo:
            amb['photo_url'] = url_for('static', filename=photo) + '?v=mask-v12-20260530'
        mask = amb.get('mask')
        if mask:
            amb['mask_url'] = url_for('static', filename=mask) + '?v=mask-v12-20260530'
    return render_template(
        'modulos/fabrica_color.html',
        slug=slug,
        nombre_tienda=nombre_tienda,
        empresa_cfg=cfg,
        wa_base=_wa_base(),
        sesion_modulo=sesion,
        es_preview_lab=sesion.get('modo') == 'lab',
        tv_mode=tv_mode,
        fabrica_config={
            'initial': initial,
            'cotizar_url': url_for('modulo_pinturas_api_cotizar', token=token),
            'liz_tip_url': url_for('modulo_pinturas_api_liz_tip', token=token),
            'modulo_home_url': url_for('modulo_pinturas_lab') if sesion.get('modo') == 'lab' else None,
            'modo_caja': sesion.get('modo') == 'caja',
            'habilitado_por': (sesion.get('nombre') or '').strip(),
            'tv_mode': tv_mode,
            'scene_urls': scene_urls,
        },
        **_fabrica_assistant_ctx(slug),
        page_canonical=_canonical(base_path),
        page_meta_description=(
            f'Colores en tienda {nombre_tienda}: ambiente, producto con stock, cantidad y cotización.'
        ),
    )


def modulo_pinturas_lab():
    if not ms.preview_habilitado():
        abort(404)
    cfg, nombre_tienda = _empresa_ctx()
    return render_template(
        'modulos/pinturas_lab.html',
        nombre_tienda=nombre_tienda,
        empresa_cfg=cfg,
        wizard_url=url_for('modulo_pinturas_lab_iniciar'),
        vitrina_url=url_for('tienda_vitrina', slug=vt.TIENDA_SLUG_SD),
    )


def modulo_pinturas_lab_iniciar():
    if not ms.preview_habilitado():
        abort(404)
    sesion = ms.validar_acceso(ms.LAB_TOKEN)
    if not sesion:
        abort(404)
    return _render_wizard(ms.LAB_TOKEN, sesion)


def modulo_pinturas_wizard(token: str):
    if token == ms.LAB_TOKEN:
        abort(404)
    sesion = ms.validar_acceso(token)
    if not sesion:
        abort(404)
    return _render_wizard(token, sesion)


def modulo_pinturas_api_cotizar(token: str):
    if not ms.validar_acceso(token):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    try:
        m2 = float(data.get('m2') or 0)
    except (TypeError, ValueError):
        m2 = 0
    producto_id = data.get('producto_id')
    try:
        pid = int(producto_id) if producto_id is not None else None
    except (TypeError, ValueError):
        pid = None
    try:
        out = fc.cotizar_proyecto(
            ambiente_id=(data.get('ambiente_id') or '').strip(),
            color_id=(data.get('color_id') or '').strip(),
            brillo_id=(data.get('brillo_id') or '').strip(),
            m2=m2,
            calidad_id=(data.get('calidad_id') or 'standard').strip(),
            producto_id=pid,
        )
        return jsonify(out)
    except Exception as ex:
        import logging

        logging.getLogger(__name__).exception('modulo_pinturas_api_cotizar: %s', ex)
        return jsonify({'ok': False, 'error': 'cotizar_error', 'mensaje': str(ex)[:200]}), 500


def modulo_pinturas_api_liz_tip(token: str):
    if not ms.validar_acceso(token):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    try:
        step = int(data.get('step') or 1)
    except (TypeError, ValueError):
        step = 1
    try:
        m2 = float(data.get('m2') or 0)
    except (TypeError, ValueError):
        m2 = 12.0
    try:
        out = fc.liz_tip_wizard(
            step=step,
            ambiente_id=(data.get('ambiente_id') or '').strip(),
            color_id=(data.get('color_id') or '').strip(),
            brillo_id=(data.get('brillo_id') or '').strip(),
            m2=m2,
        )
        return jsonify(out)
    except Exception as ex:
        import logging

        logging.getLogger(__name__).exception('modulo_pinturas_api_liz_tip: %s', ex)
        return jsonify({'ok': True, 'tip': '', 'fuente': 'reglas'})


def api_caja_habilitar_modulo_pinturas():
    from blueprints._app_ref import app_module

    m = app_module()
    if not current_user.is_authenticated:
        return jsonify({'ok': False, 'error': 'auth_required'}), 401
    if not (
        m.usuario_tiene_permiso('caja_cobrar_vale')
        or m.usuario_tiene_permiso('pos_emitir_vale')
        or m.usuario_tiene_permiso('gestionar_usuarios')
    ):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    try:
        out = ms.crear_sesion_modulo_pinturas(
            usuario_id=int(current_user.id),
            usuario_nombre=(getattr(current_user, 'nombre', None) or getattr(current_user, 'username', '') or 'Mostrador'),
        )
        try:
            out['url_absoluta'] = m._absolute_public_url(out['path'])
        except Exception:
            out['url_absoluta'] = out['path']
        return jsonify(out)
    except Exception as ex:
        import logging

        logging.getLogger(__name__).exception('api_caja_habilitar_modulo_pinturas: %s', ex)
        return jsonify({'ok': False, 'error': 'session_error', 'mensaje': str(ex)[:200]}), 500


def register_modulo_pinturas_routes(app) -> None:
    app.add_url_rule(
        '/modulos/pinturas/lab',
        view_func=modulo_pinturas_lab,
        methods=['GET'],
        endpoint='modulo_pinturas_lab',
    )
    app.add_url_rule(
        '/modulos/pinturas/lab/iniciar',
        view_func=modulo_pinturas_lab_iniciar,
        methods=['GET'],
        endpoint='modulo_pinturas_lab_iniciar',
    )
    app.add_url_rule(
        '/modulos/pinturas/<token>',
        view_func=modulo_pinturas_wizard,
        methods=['GET'],
        endpoint='modulo_pinturas_wizard',
    )
    app.add_url_rule(
        '/api/modulos/pinturas/<token>/cotizar',
        view_func=modulo_pinturas_api_cotizar,
        methods=['POST'],
        endpoint='modulo_pinturas_api_cotizar',
    )
    app.add_url_rule(
        '/api/modulos/pinturas/<token>/liz-tip',
        view_func=modulo_pinturas_api_liz_tip,
        methods=['POST'],
        endpoint='modulo_pinturas_api_liz_tip',
    )
    app.add_url_rule(
        '/api/caja/modulo-pinturas/habilitar',
        view_func=api_caja_habilitar_modulo_pinturas,
        methods=['POST'],
        endpoint='api_caja_modulo_pinturas_habilitar',
    )

    # Rutas legacy vitrina → 404 (módulo ya no vive en catálogo)
    def _legacy_fabrica_404(*_a, **_k):
        abort(404)

    app.add_url_rule(
        '/tienda/<slug>/fabrica-de-color',
        view_func=_legacy_fabrica_404,
        methods=['GET'],
        endpoint='tienda_fabrica_color_legacy',
    )
    app.add_url_rule(
        '/api/tienda/<slug>/fabrica-color/cotizar',
        view_func=_legacy_fabrica_404,
        methods=['POST'],
        endpoint='tienda_api_fabrica_cotizar_legacy',
    )
