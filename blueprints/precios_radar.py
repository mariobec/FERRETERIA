"""LhexIA Radar Precios — formulario SSE + dashboard premium."""
from __future__ import annotations

import json

from flask import Response, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from blueprints._app_ref import app_module
from services import radar_precios_service as radar
from services import radar_maestro_csv as radar_csv
from services.radar_precios_fetch import playwright_chromium_listo, playwright_disponible


def _wrap_radar(fn):
    m = app_module()
    return login_required(
        m.permisos_required(
            'radar_precios', 'revision_precios', 'gestionar_usuarios', 'ver_gerencia'
        )(fn)
    )


def precios_radar_index():
    m = app_module()
    maestro = radar_csv.estadisticas_maestro_csv(m.app.root_path)
    proveedor_preseleccionado = None
    pid = request.args.get('proveedor_id', type=int)
    if pid:
        p = m.Proveedor.query.get(pid)
        if p:
            nombre = (p.nombre or '').strip()
            meta = []
            if (p.rut or '').strip():
                meta.append(f'RUT {p.rut.strip()}')
            text = nombre if not meta else f'{nombre} · {" · ".join(meta)}'
            proveedor_preseleccionado = {
                'id': p.id,
                'text': text,
                'nombre': nombre,
                'rut': (p.rut or '').strip(),
            }
    return render_template(
        'precios_radar.html',
        ollama=radar.ollama_status(),
        maestro_csv=maestro,
        proveedor_preseleccionado=proveedor_preseleccionado,
        playwright_ok=playwright_chromium_listo(),
        playwright_pkg=playwright_disponible(),
    )


def api_radar_buscar_proveedores():
    """Select2 AJAX — nombre, RUT, contacto, email, teléfono."""
    m = app_module()
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'results': []})
    like = f'%{q}%'
    filas = (
        m.Proveedor.query.filter(
            or_(
                m.Proveedor.nombre.ilike(like),
                m.Proveedor.rut.ilike(like),
                m.Proveedor.contacto.ilike(like),
                m.Proveedor.email.ilike(like),
                m.Proveedor.telefono.ilike(like),
            )
        )
        .order_by(m.Proveedor.nombre.asc())
        .limit(30)
        .all()
    )
    results = []
    for p in filas:
        nombre = (p.nombre or '').strip()
        meta = []
        if (p.rut or '').strip():
            meta.append(f'RUT {p.rut.strip()}')
        if (p.contacto or '').strip():
            meta.append(p.contacto.strip())
        elif (p.email or '').strip():
            meta.append(p.email.strip())
        text = nombre if not meta else f'{nombre} · {" · ".join(meta)}'
        results.append({
            'id': p.id,
            'text': text,
            'nombre': nombre,
            'rut': (p.rut or '').strip(),
        })
    return jsonify({'results': results})


def api_radar_crear_proveedor():
    """Alta rápida desde Radar (nombre obligatorio). Si ya existe, devuelve el existente."""
    m = app_module()
    data = request.get_json(silent=True) or {}
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'nombre_requerido'}), 400
    if len(nombre) > 100:
        return jsonify({'ok': False, 'error': 'nombre_demasiado_largo'}), 400

    exist = m.Proveedor.query.filter(m.Proveedor.nombre.ilike(nombre)).first()
    if exist:
        nombre_ex = (exist.nombre or '').strip()
        meta = []
        if (exist.rut or '').strip():
            meta.append(f'RUT {exist.rut.strip()}')
        text = nombre_ex if not meta else f'{nombre_ex} · {" · ".join(meta)}'
        return jsonify({
            'ok': True,
            'id': exist.id,
            'text': text,
            'nombre': nombre_ex,
            'rut': (exist.rut or '').strip(),
            'ya_existia': True,
        })

    rut = (data.get('rut') or '').strip() or None
    contacto = (data.get('contacto') or '').strip() or None
    telefono = (data.get('telefono') or '').strip() or None
    email = (data.get('email') or '').strip() or None
    prov = m.Proveedor(
        nombre=nombre,
        rut=rut,
        contacto=contacto,
        telefono=telefono,
        email=email,
    )
    m.db.session.add(prov)
    m.db.session.commit()
    try:
        m.guardar_canal_compra_proveedor(prov.id, 'manual')
    except Exception:
        pass

    meta = []
    if rut:
        meta.append(f'RUT {rut}')
    text = nombre if not meta else f'{nombre} · {" · ".join(meta)}'
    return jsonify({
        'ok': True,
        'id': prov.id,
        'text': text,
        'nombre': nombre,
        'rut': rut or '',
        'ya_existia': False,
    })


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
    guardar_resultados = data.get('guardar_resultados')
    if guardar_resultados is None:
        guardar_resultados = request.form.get('guardar_resultados') in ('1', 'true', 'on', 'yes')
    else:
        guardar_resultados = bool(guardar_resultados)
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
            guardar_resultados=guardar_resultados,
        )
        proveedor_nombre = ''
        if proveedor_id:
            pr = m.Proveedor.query.get(proveedor_id)
            if pr:
                proveedor_nombre = (pr.nombre or '').strip()
        return jsonify({
            'ok': True,
            'job_id': job_id,
            'proveedor_id': proveedor_id,
            'proveedor_nombre': proveedor_nombre,
            'guardar_resultados': guardar_resultados,
        })
    except ValueError as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 400
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500


def api_radar_ejecutar():
    """SSE unificado: crea job y transmite progreso (GET ?url=)."""
    m = app_module()
    url = (request.args.get('url') or '').strip()
    proveedor_id = request.args.get('proveedor_id')
    guardar_resultados = request.args.get('guardar') in ('1', 'true', 'yes', 'on')
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
                guardar_resultados=guardar_resultados,
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
        'proveedor_id': job.get('proveedor_id'),
        'proveedor_nombre': job.get('proveedor_nombre') or '',
        'maestro_csv_total': job.get('maestro_csv_total'),
        'maestro_csv_path': job.get('maestro_csv_path'),
        'guardar_resultados': bool(job.get('guardar_resultados')),
        'persistido': bool(job.get('persistido')),
    })


def api_radar_guardar_escaneo():
    m = app_module()
    data = request.get_json(silent=True) or {}
    job_id = (data.get('job_id') or '').strip()
    if not job_id:
        return jsonify({'ok': False, 'error': 'job_id_requerido'}), 400
    res = radar.persistir_escaneo_en_maestro(
        m,
        job_id,
        usuario=getattr(current_user, 'nombre', None) or 'usuario',
    )
    if not res.get('ok'):
        return jsonify(res), 400
    return jsonify(res)


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
        '/api/precios/radar/proveedores/buscar',
        'api_radar_buscar_proveedores',
        _wrap_radar(api_radar_buscar_proveedores),
        methods=['GET'],
    )
    app.add_url_rule(
        '/api/precios/radar/proveedores/crear',
        'api_radar_crear_proveedor',
        _wrap_radar(api_radar_crear_proveedor),
        methods=['POST'],
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
        '/api/precios/radar/guardar',
        'api_radar_guardar_escaneo',
        _wrap_radar(api_radar_guardar_escaneo),
        methods=['POST'],
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
