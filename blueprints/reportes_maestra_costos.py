"""Reportes Gerencia — Maestra compras 2024-2026."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import login_required

from blueprints._app_ref import app_module
from services import maestra_reportes_costos_service as rep


def _wrap(fn):
    m = app_module()
    return login_required(
        m.permisos_required(
            'ver_gerencia', 'panel_gerencia', 'revision_precios', 'gestionar_usuarios'
        )(fn)
    )


def reporte_fuga_costos():
    m = app_module()
    umbral = request.args.get('umbral', type=float) or 5.0
    force = request.args.get('refresh') == '1'
    try:
        data = rep.get_reports_cached(m.app, umbral_pct=umbral, force=force)
    except FileNotFoundError as ex:
        return render_template(
            'reportes/maestra_error.html',
            titulo='Reporte no disponible',
            mensaje=str(ex),
        ), 404
    return render_template(
        'reportes/maestra_fuga_costos.html',
        data=data,
        umbral=umbral,
    )


def reporte_inflacion_compras():
    m = app_module()
    umbral = request.args.get('umbral', type=float) or 5.0
    force = request.args.get('refresh') == '1'
    try:
        data = rep.get_reports_cached(m.app, umbral_pct=umbral, force=force)
    except FileNotFoundError as ex:
        return render_template(
            'reportes/maestra_error.html',
            titulo='Reporte no disponible',
            mensaje=str(ex),
        ), 404
    return render_template(
        'reportes/maestra_inflacion_compras.html',
        data=data,
        umbral=umbral,
    )


def _csv_response(nombre: str, filas: list[dict], columnas: list[str]) -> Response:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columnas, extrasaction='ignore')
    w.writeheader()
    for row in filas:
        w.writerow(row)
    out = buf.getvalue().encode('utf-8-sig')
    stamp = datetime.now().strftime('%Y%m%d')
    return Response(
        out,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={nombre}_{stamp}.csv'},
    )


def reporte_fuga_csv():
    m = app_module()
    data = rep.get_reports_cached(m.app)
    cols = [
        'producto_id', 'codigo_factura', 'proveedor', 'descripcion', 'grupo5',
        'costo_erp', 'ultimo_costo_maestra', 'delta_pct', 'fuga_recompra_clp',
        'neto_comprado_historico', 'precio_venta', 'margen_erp_pct', 'margen_real_pct',
    ]
    return _csv_response('fuga_costos_maestra', rep.fuga_to_csv_rows(data), cols)


def reporte_inflacion_csv():
    m = app_module()
    data = rep.get_reports_cached(m.app)
    cols = [
        'proveedor', 'neto_2024', 'neto_2025', 'neto_2026', 'neto_total',
        'variacion_24_26_pct', 'variacion_25_26_pct',
    ]
    return _csv_response('inflacion_proveedores_maestra', rep.inflacion_proveedores_csv(data), cols)


def reporte_fuga_detalle():
    m = app_module()
    codigo = (request.args.get('codigo') or '').strip()
    proveedor = (request.args.get('proveedor') or '').strip()
    producto_id = request.args.get('producto_id', type=int)
    umbral = request.args.get('umbral', type=float) or 5.0
    if not codigo or not proveedor:
        return redirect(url_for('reporte_fuga_costos', umbral=umbral))
    try:
        det = rep.historial_compras_detalle(
            m.app,
            codigo_factura=codigo,
            proveedor=proveedor,
            producto_id=producto_id,
        )
    except FileNotFoundError as ex:
        return render_template(
            'reportes/maestra_error.html',
            titulo='Detalle no disponible',
            mensaje=str(ex),
        ), 404
    if not det.get('ok'):
        flash('No hay líneas en la maestra para ese código y proveedor.', 'warning')
        return redirect(url_for('reporte_fuga_costos', umbral=umbral))
    return render_template(
        'reportes/maestra_fuga_detalle.html',
        det=det,
        umbral=umbral,
    )


def reportes_maestra_hub():
    m = app_module()
    try:
        data = rep.get_reports_cached(m.app)
    except FileNotFoundError as ex:
        return render_template(
            'reportes/maestra_error.html',
            titulo='Reportes no disponibles',
            mensaje=str(ex),
        ), 404
    inf = data.get('inflacion', {}).get('kpis', {})
    fug = data.get('fuga', {}).get('kpis', {})
    return render_template(
        'reportes/maestra_hub.html',
        generado_ts=data.get('generado_ts', ''),
        fuga_total=fug.get('fuga_total_fmt', '$0'),
        skus=fug.get('skus_desactualizados', 0),
        neto_total=rep._fmt_clp(
            (inf.get('neto_2024') or 0)
            + (inf.get('neto_2025') or 0)
            + (inf.get('neto_2026') or 0)
        ),
        top3=inf.get('concentracion_top3_pct', 0),
        proveedores=inf.get('proveedores_activos', 0),
    )


def register_reportes_maestra_routes(app):
    app.add_url_rule(
        '/gerencia/reportes/costos',
        'reportes_maestra_hub',
        _wrap(reportes_maestra_hub),
        methods=['GET'],
    )
    app.add_url_rule(
        '/gerencia/reportes/fuga-costos',
        'reporte_fuga_costos',
        _wrap(reporte_fuga_costos),
        methods=['GET'],
    )
    app.add_url_rule(
        '/gerencia/reportes/fuga-costos/detalle',
        'reporte_fuga_detalle',
        _wrap(reporte_fuga_detalle),
        methods=['GET'],
    )
    app.add_url_rule(
        '/gerencia/reportes/inflacion-compras',
        'reporte_inflacion_compras',
        _wrap(reporte_inflacion_compras),
        methods=['GET'],
    )
    app.add_url_rule(
        '/gerencia/reportes/fuga-costos.csv',
        'reporte_fuga_costos_csv',
        _wrap(reporte_fuga_csv),
        methods=['GET'],
    )
    app.add_url_rule(
        '/gerencia/reportes/inflacion-compras.csv',
        'reporte_inflacion_compras_csv',
        _wrap(reporte_inflacion_csv),
        methods=['GET'],
    )
