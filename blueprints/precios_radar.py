"""LhexIA Radar Precios — formulario SSE + dashboard premium."""
from __future__ import annotations

import json

from flask import Response, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from blueprints._app_ref import app_module
from services import radar_precios_service as radar
from services import radar_maestro_csv as radar_csv


def _wrap_radar(fn):
    m = app_module()
    return login_required(
        m.permisos_required(
            'radar_precios', 'revision_precios', 'gestionar_usuarios', 'ver_gerencia'
        )(fn)
    )


def precios_radar_index():
    m = app_module()
    proveedores = m.Proveedor.query.order_by(m.Proveedor.nombre.asc()).limit(200).all()
    maestro = radar_csv.estadisticas_maestro_csv(m.app.root_path)
    return render_template(
        'precios_radar.html',
        proveedores=proveedores,
        ollama=radar.ollama_status(),
        maestro_csv=maestro,
    )


def precios_radar_dashboard():
    m = app_module()
    ctx = radar.dashboard_metrics(m)
    return render_template('precios_radar_dashboard.html', **ctx)


def api_radar_iniciar():
    m = app_module()
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or request.form.get('url') or '').strip()
    urls_extra = data.get('urls') or []
    proveedor_id = data.get('proveedor_id') or request.form.get('proveedor_id')
    try:
        proveedor_id = int(proveedor_id) if proveedor_id not in (None, '', '0') else None
    except (TypeError, ValueError):
        proveedor_id = None
    if not url and not urls_extra:
        return jsonify({'ok': False, 'error': 'url_requerida'}), 400
    try:
        job_id = radar.crear_job(
            url=url,
            urls=urls_extra if isinstance(urls_extra, list) else None,
            proveedor_id=proveedor_id,
            usuario=getattr(current_user, 'nombre', None) or 'usuario',
            app=m,
        )
        return jsonify({'ok': True, 'job_id': job_id})
    except ValueError as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 400
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500


def api_radar_ejecutar():
    """SSE unificado: crea job y transmite progreso (GET ?url=)."""
    m = app_module()
    url = (request.args.get('url') or '').strip()
    proveedor_id = request.args.get('proveedor_id')
    try:
        proveedor_id = int(proveedor_id) if proveedor_id not in (None, '', '0') else None
    except (TypeError, ValueError):
        proveedor_id = None
    if not url:
        def err_gen():
            yield 'data: {"fase":"error","error":"url_requerida"}\n\n'
        return Response(err_gen(), mimetype='text/event-stream')

    def generate():
        try:
            for chunk in radar.crear_job_y_stream(
                url=url,
                proveedor_id=proveedor_id,
                usuario=getattr(current_user, 'nombre', None) or 'usuario',
                app=m,
            ):
                yield chunk
        except ValueError as ex:
            yield f'data: {json.dumps({"fase": "error", "error": str(ex)}, ensure_ascii=False)}\n\n'

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
    return Response(generate(), mimetype='text/event-stream', headers=headers)


def api_radar_stream(job_id):
    def generate():
        for chunk in radar.iter_sse(job_id):
            yield chunk

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
    return Response(generate(), mimetype='text/event-stream', headers=headers)


def api_radar_estado(job_id):
    job = radar.get_job(job_id)
    if not job:
        return jsonify({'ok': False, 'error': 'job_no_encontrado'}), 404
    return jsonify({
        'ok': True,
        'job_id': job_id,
        'status': job.get('status'),
        'progreso': job.get('progreso'),
        'total': job.get('total'),
        'parser': job.get('parser'),
        'error': job.get('error'),
        'lineas': job.get('lineas') or [],
        'url_final': job.get('url_final'),
        'titulo': job.get('titulo'),
    })


def api_radar_ollama():
    return jsonify({'ok': True, **radar.ollama_status()})


def api_radar_maestro_estado():
    m = app_module()
    return jsonify({'ok': True, **radar_csv.estadisticas_maestro_csv(m.app.root_path)})


def api_radar_maestro_preview():
    m = app_module()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    data = radar_csv.preview_maestro_csv(m.app.root_path, page=page, per_page=per_page)
    return jsonify({'ok': True, **data})


def precios_radar_descargar_maestro():
    m = app_module()
    path = radar_csv.ruta_maestro_csv(m.app.root_path)
    if not path.is_file():
        flash('Aún no hay productos acumulados en el maestro Radar.', 'warning')
        return redirect(url_for('precios_radar'))
    return send_file(
        path,
        mimetype='text/csv',
        as_attachment=True,
        download_name='radar_maestro_acumulado.csv',
    )


def api_radar_aplicar():
    m = app_module()
    data = request.get_json(silent=True) or {}
    job_id = (data.get('job_id') or '').strip()
    linea_ids = data.get('linea_ids') or []
    motivo = (data.get('motivo') or 'Radar Precios — actualización costo desde web').strip()
    if not job_id:
        return jsonify({'ok': False, 'error': 'job_id_requerido'}), 400
    res = radar.aplicar_costos(
        m,
        job_id=job_id,
        linea_ids=linea_ids,
        usuario=getattr(current_user, 'nombre', None) or 'usuario',
        motivo=motivo,
    )
    if not res.get('ok'):
        return jsonify(res), 400
    return jsonify(res)


def precios_radar_aplicar_form():
    m = app_module()
    job_id = request.form.get('job_id', '').strip()
    ids_raw = request.form.get('linea_ids', '')
    linea_ids = [x.strip() for x in ids_raw.split(',') if x.strip()]
    motivo = request.form.get('motivo', 'Radar Precios')
    res = radar.aplicar_costos(
        m,
        job_id=job_id,
        linea_ids=linea_ids,
        usuario=getattr(current_user, 'nombre', None) or 'usuario',
        motivo=motivo,
    )
    if res.get('ok'):
        flash(f"Se actualizaron {res.get('aplicados', 0)} costos de compra.", 'success')
    else:
        flash(res.get('error') or 'No se pudo aplicar.', 'danger')
    return redirect(url_for('precios_radar'))


def register_precios_radar_routes(app):
    app.add_url_rule(
        '/precios/radar',
        'precios_radar',
        _wrap_radar(precios_radar_index),
        methods=['GET'],
    )
    app.add_url_rule(
        '/precios/radar/dashboard',
        'precios_radar_dashboard',
        _wrap_radar(precios_radar_dashboard),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/iniciar',
        'api_radar_iniciar',
        _wrap_radar(api_radar_iniciar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/api/precios/radar/ejecutar',
        'api_radar_ejecutar',
        _wrap_radar(api_radar_ejecutar),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/stream/<job_id>',
        'api_radar_stream',
        _wrap_radar(api_radar_stream),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/estado/<job_id>',
        'api_radar_estado',
        _wrap_radar(api_radar_estado),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/ollama',
        'api_radar_ollama',
        _wrap_radar(api_radar_ollama),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/maestro',
        'api_radar_maestro_estado',
        _wrap_radar(api_radar_maestro_estado),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/maestro/preview',
        'api_radar_maestro_preview',
        _wrap_radar(api_radar_maestro_preview),
        methods=['GET'],
    )
    app.add_url_rule(
        '/precios/radar/maestro.csv',
        'precios_radar_descargar_maestro',
        _wrap_radar(precios_radar_descargar_maestro),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/aplicar',
        'api_radar_aplicar',
        _wrap_radar(api_radar_aplicar),
        methods=['POST'],
    )
    app.add_url_rule(
        '/precios/radar/aplicar',
        'precios_radar_aplicar_form',
        _wrap_radar(precios_radar_aplicar_form),
        methods=['POST'],
    )
