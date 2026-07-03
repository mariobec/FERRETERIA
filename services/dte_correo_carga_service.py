# -*- coding: utf-8 -*-
"""Carga DTE desde Gmail por periodo (mes/año) — invoca lector IMAP."""
from __future__ import annotations

import importlib.util
import os
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_env_local() -> None:
    p = ROOT / '.env.local'
    if not p.is_file():
        return
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def rango_mes(anio: int, mes: int) -> tuple[date, date]:
    """[desde, hasta) — hasta = primer día mes siguiente (IMAP BEFORE)."""
    anio, mes = int(anio), int(mes)
    if mes < 1 or mes > 12:
        raise ValueError('Mes inválido')
    d1 = date(anio, mes, 1)
    if mes == 12:
        d2 = date(anio + 1, 1, 1)
    else:
        d2 = date(anio, mes + 1, 1)
    return d1, d2


def rango_anio(anio: int) -> tuple[date, date]:
    anio = int(anio)
    return date(anio, 1, 1), date(anio + 1, 1, 1)


def _importar_lector():
    path = ROOT / 'scripts' / 'lector_correo_dte.py'
    spec = importlib.util.spec_from_file_location('lector_correo_dte', path)
    if not spec or not spec.loader:
        raise RuntimeError('No se pudo cargar lector_correo_dte.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ejecutar_carga_correo(
    *,
    desde: date,
    hasta: date | None = None,
    limite: int = 500,
    offset: int = 0,
    solo_etiquetar: bool = False,
    carpeta_imap: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Escanea Gmail en el rango [desde, hasta) y etiqueta / importa DTE SD.
    Requiere .env.local con IMAP_* configurado.
    """
    _load_env_local()
    if not (os.getenv('IMAP_USER') and os.getenv('IMAP_PASSWORD')):
        return {'ok': False, 'error': 'Configure IMAP en .env.local'}

    if carpeta_imap:
        os.environ['IMAP_FOLDER'] = carpeta_imap.strip()

    lector = _importar_lector()
    carpeta_dest = ROOT / (os.getenv('DTE_CORREO_CARPETA') or 'datos_rcv')

    try:
        stats = lector.procesar_buzon(
            carpeta_destino=carpeta_dest,
            dry_run=dry_run,
            marcar_leidos=False,
            limite=limite if limite > 0 else None,
            offset=max(0, int(offset or 0)),
            recientes=False,
            solo_etiquetar=solo_etiquetar,
            etiquetar=True,
            criterio=None,
            desde=desde,
            hasta=hasta,
            todos=True,
            omitir_sii=True,
        )
    except Exception as ex:
        return {'ok': False, 'error': str(ex), 'stats': {}}

    return {
        'ok': True,
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat() if hasta else None,
        'stats': stats,
    }


def ejecutar_carga_mes(anio: int, mes: int, **kwargs) -> dict[str, Any]:
    d1, d2 = rango_mes(anio, mes)
    return ejecutar_carga_correo(desde=d1, hasta=d2, **kwargs)


def ejecutar_carga_anio(anio: int, **kwargs) -> dict[str, Any]:
    d1, d2 = rango_anio(anio)
    return ejecutar_carga_correo(desde=d1, hasta=d2, **kwargs)


def payload_visor_recepcion(rec) -> dict[str, Any]:
    """Detalle JSON para panel visor facturas."""
    lineas_erp = []
    for d in rec.detalles or []:
        p = d.producto
        lineas_erp.append({
            'producto_id': d.producto_id,
            'codigo': (p.codigo_barra or p.codigo_interno or '') if p else '',
            'nombre': p.nombre if p else '(sin producto)',
            'cantidad_documento': int(d.cantidad_documento or 0),
            'cantidad_recibida': int(d.cantidad_recibida or 0),
            'costo_unitario': float(d.costo_unitario or 0),
            'total_linea': round(float(d.costo_unitario or 0) * int(d.cantidad_documento or d.cantidad_recibida or 0)),
            'tiene_sku': True,
        })

    lineas_doc = []
    for ld in getattr(rec, 'lineas_documento', None) or []:
        p = ld.producto
        qty = float(ld.cantidad or 0)
        prc = float(ld.precio_unitario or 0)
        monto = float(ld.monto_linea or 0) if ld.monto_linea else round(prc * qty)
        lineas_doc.append({
            'nro_linea': int(ld.nro_linea or 0),
            'producto_id': ld.producto_id,
            'codigo': (ld.codigo_factura or '') or ((p.codigo_barra or p.codigo_interno or '') if p else ''),
            'nombre': ld.nombre or (p.nombre if p else '(sin descripción)'),
            'cantidad_documento': qty,
            'cantidad_recibida': 0,
            'costo_unitario': prc,
            'total_linea': monto,
            'tiene_sku': bool(ld.producto_id),
        })

    if lineas_doc:
        lineas = lineas_doc
        fuente_lineas = 'xml'
    elif lineas_erp:
        lineas = lineas_erp
        fuente_lineas = 'erp'
    else:
        lineas = []
        fuente_lineas = None

    hint = None
    origen = rec.origen_importacion or 'manual'
    if not lineas and origen == 'rcv_sii':
        hint = (
            'Importado solo desde RCV SII (cabecera). '
            'Use Cargador DTE correo para traer ítems y precios del XML.'
        )
    elif not lineas:
        hint = 'Sin ítems en el ERP. Cargue el XML desde Correo DTE o ingrese manualmente en Recepción.'

    fd = rec.fecha_documento or (rec.fecha_recepcion.date() if rec.fecha_recepcion else None)
    return {
        'id': rec.id,
        'documento_tipo': rec.documento_tipo,
        'documento_numero': rec.documento_numero,
        'proveedor': rec.proveedor.nombre if rec.proveedor else (rec.razon_social_doc or ''),
        'rut_proveedor': rec.rut_proveedor_doc or (rec.proveedor.rut if rec.proveedor else ''),
        'estado': rec.estado,
        'origen': origen,
        'fecha_documento': fd.isoformat() if fd else None,
        'monto_neto': float(rec.monto_neto or 0),
        'monto_total': float(rec.monto_total or 0),
        'oc_numero': rec.orden_compra.numero if rec.orden_compra else None,
        'oc_id': rec.orden_compra_id,
        'guia': rec.guia_despacho_numero,
        'n_lineas': len(lineas),
        'lineas': lineas,
        'fuente_lineas': fuente_lineas,
        'hint_lineas': hint,
        'tiene_documento_adjunto': bool(getattr(rec, '_tiene_doc', False)),
    }
