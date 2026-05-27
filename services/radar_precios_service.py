"""LhexIA Radar Precios — jobs async, SSE, mapeo ERP y aplicación de costos."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from services.radar_precios_fetch import (
    extraer_candidatos_texto_crudo,
    extraer_productos_de_html,
    fetch_public_html,
    mensaje_error_radar,
    recortar_html_para_ollama,
    validar_url_publica,
)
from services import radar_precios_db as radar_db
from services import radar_maestro_csv as radar_csv

_log = logging.getLogger(__name__)

_PROMPT_ITEM = (
    'Extrae SKU/código del proveedor, nombre limpio del producto y precio en pesos chilenos (entero). '
    'Responde ÚNICAMENTE JSON: {"sku":"", "nombre":"", "precio":0}. Sin markdown.'
)


def _ollama_por_item_habilitado() -> bool:
    v = (os.getenv('RADAR_PRECIOS_OLLAMA_POR_ITEM') or '1').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return False
    from services.ollama_client import ollama_disponible, ollama_habilitado

    return ollama_habilitado() and ollama_disponible()


def ollama_normalizar_item(texto_crudo: str) -> dict[str, Any]:
    """Normaliza un fragmento ruidoso de catálogo (1 producto) vía Ollama local."""
    from services.ollama_client import generar_chat, ollama_disponible

    texto = (texto_crudo or '').strip()
    if not texto or not ollama_disponible():
        return {'ok': False, 'producto': None, 'error': 'ollama_no_disponible'}
    user = f'Texto del proveedor:\n{texto[:2500]}'
    chat = generar_chat(system=_PROMPT_ITEM, user=user)
    if not chat.get('ok'):
        return {'ok': False, 'producto': None, 'error': chat.get('error') or 'ollama_error'}
    parsed = _extraer_json_ollama(chat.get('texto') or '')
    if not parsed:
        try:
            data = json.loads((chat.get('texto') or '').strip())
            if isinstance(data, dict):
                parsed = _normalizar_items([data])
        except json.JSONDecodeError:
            parsed = []
    if not parsed:
        return {'ok': False, 'producto': None, 'error': 'json_invalido'}
    return {'ok': True, 'producto': parsed[0], 'modelo': chat.get('modelo'), 'error': None}


def _refinar_producto_con_ollama(prod: dict[str, Any]) -> dict[str, Any]:
    """Opcional: pasa un ítem ya parseado por Ollama para limpiar SKU/nombre."""
    raw = (
        f"SKU {prod.get('codigo_interno', '')} "
        f"{prod.get('descripcion_producto', '')} ${prod.get('precio', 0)}"
    )
    res = ollama_normalizar_item(raw)
    if res.get('ok') and res.get('producto'):
        return res['producto']
    return prod


_PROMPT_SISTEMA = (
    'Eres un extractor de catálogo para un ERP de ferretería en Chile. '
    'Recibes HTML de una página web pública con productos. '
    'Devuelve ÚNICAMENTE un JSON válido: un array de objetos. '
    'Cada objeto: "codigo_interno" (string), "descripcion_producto" (string), '
    '"precio" (entero CLP sin puntos). Si no hay productos, []. No inventes datos.'
)

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_historial: deque = deque(maxlen=30)


def _build_page_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url.strip()
    parsed = urlparse(base_url.strip())
    q = parse_qs(parsed.query, keep_blank_values=True)
    q.pop('offset', None)
    q['page'] = [str(page)]
    new_query = urlencode({k: v[0] for k, v in q.items()})
    return urlunparse(parsed._replace(query=new_query))


def _detectar_total_paginas_sodimac(html: str) -> int | None:
    try:
        from scripts._sodimac_listado_rapido import pagination_from_next_data

        pag = pagination_from_next_data(html)
        if isinstance(pag, dict):
            total = int(pag.get('count') or pag.get('totalResults') or 0)
            per = int(pag.get('perPage') or pag.get('totalPerPage') or 48) or 48
            if total > 0:
                return max(1, (total + per - 1) // per)
    except Exception:
        pass
    for pat in (
        r'"totalPages"\s*:\s*(\d+)',
        r'"numberOfPages"\s*:\s*(\d+)',
        r'"pageCount"\s*:\s*(\d+)',
    ):
        m = re.search(pat, html)
        if m:
            return max(1, int(m.group(1)))
    m = re.search(r'"totalResults"\s*:\s*(\d+)', html)
    if m:
        total = int(m.group(1))
        per = 48
        return max(1, (total + per - 1) // per)
    return None


def _expandir_paginas_url(url: str, html_primera_pagina: str) -> list[str]:
    host = (urlparse(url).hostname or '').lower()
    if 'sodimac' not in host:
        return [url]
    max_pag = int((os.getenv('RADAR_PRECIOS_MAX_PAGINAS_SODIMAC') or '25').strip() or '25')
    max_pag = max(1, min(max_pag, 60))
    total_paginas = _detectar_total_paginas_sodimac(html_primera_pagina) or 1
    total_paginas = min(total_paginas, max_pag)
    return [_build_page_url(url, p) for p in range(1, total_paginas + 1)]


def _erp_app_context(erp_mod):
    """
    Contexto Flask del ERP. erp_mod es el módulo app (o __main__ con python app.py).
    No usar erp_mod.app_context() — eso falla cuando el proceso carga __main__.
    """
    flask_app = getattr(erp_mod, 'app', None)
    if flask_app is None or not hasattr(flask_app, 'app_context'):
        raise RuntimeError('Módulo ERP sin instancia Flask (app)')
    return flask_app.app_context()


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extraer_json_ollama(texto: str) -> list[dict[str, Any]]:
    texto = (texto or '').strip()
    if not texto:
        return []
    bloques = re.findall(r'```(?:json)?\s*([\s\S]*?)```', texto, flags=re.I)
    candidatos = bloques + [texto]
    for raw in candidatos:
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'(\[[\s\S]*\])', raw)
            if not m:
                continue
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
        if isinstance(data, list):
            return _normalizar_items(data)
        if isinstance(data, dict) and isinstance(data.get('productos'), list):
            return _normalizar_items(data['productos'])
    return []


def _normalizar_items(items: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        codigo = str(
            it.get('codigo_interno') or it.get('sku') or it.get('codigo') or it.get('id') or ''
        ).strip()
        desc = str(
            it.get('descripcion_producto') or it.get('descripcion') or it.get('nombre') or ''
        ).strip()
        precio_raw = it.get('precio') or it.get('price') or it.get('precio_clp')
        try:
            if isinstance(precio_raw, str):
                precio_raw = re.sub(r'[^\d]', '', precio_raw)
            precio = int(precio_raw) if precio_raw not in (None, '') else 0
        except (TypeError, ValueError):
            precio = 0
        if not codigo and not desc:
            continue
        if not codigo:
            codigo = re.sub(r'[^a-zA-Z0-9_-]', '-', desc[:28])[:28] or 'WEB'
        out.append({
            'codigo_interno': codigo[:64],
            'descripcion_producto': desc[:500],
            'precio': max(0, precio),
        })
    return out


def ollama_estructurar_html(html: str) -> dict[str, Any]:
    from services.ollama_client import generar_chat, ollama_disponible

    if not ollama_disponible():
        return {'ok': False, 'productos': [], 'error': 'ollama_no_disponible'}
    html_rec = recortar_html_para_ollama(html)
    user = (
        'Extrae todos los productos visibles del HTML (nombre, código/SKU si existe, precio CLP). '
        'Responde solo con el array JSON.\n\nHTML:\n' + html_rec
    )
    chat = generar_chat(system=_PROMPT_SISTEMA, user=user)
    if not chat.get('ok'):
        return {'ok': False, 'productos': [], 'error': chat.get('error') or 'ollama_error'}
    productos = _extraer_json_ollama(chat.get('texto') or '')
    return {
        'ok': True,
        'productos': productos,
        'modelo': chat.get('modelo'),
        'tokens': int(chat.get('tokens_total') or 0),
    }


def ollama_status() -> dict[str, Any]:
    from services.ollama_client import ollama_disponible, ollama_habilitado, ollama_model

    hab = ollama_habilitado()
    disp = ollama_disponible() if hab else False
    return {
        'habilitado': hab,
        'disponible': disp,
        'modelo': ollama_model() if hab else '',
    }


def _emit(job: dict[str, Any], payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload['ts'] = _ahora_iso()
    job['events'].append(payload)
    for cb in list(job.get('listeners') or []):
        try:
            cb(payload)
        except Exception:
            pass


def _match_producto(
    app,
    *,
    sku_proveedor: str,
    descripcion: str,
    proveedor_id: int | None,
) -> dict[str, Any]:
    Producto = app.Producto
    ProductoCodigoProveedor = app.ProductoCodigoProveedor
    db = app.db
    from sqlalchemy import or_

    sku = (sku_proveedor or '').strip()
    desc = (descripcion or '').strip()
    producto = None
    confianza = 0.0
    metodo = 'sin_match'

    if proveedor_id and sku:
        link = (
            ProductoCodigoProveedor.query.filter_by(
                proveedor_id=proveedor_id,
                codigo_factura_proveedor=sku,
            )
            .first()
        )
        if link:
            producto = Producto.query.get(link.producto_id)
            if producto:
                confianza = 0.98
                metodo = 'codigo_proveedor'

    if not producto and sku:
        producto = Producto.query.filter(
            or_(
                Producto.codigo_barra == sku,
                Producto.codigo_interno == sku,
            ),
            Producto.activo == True,
        ).first()
        if producto:
            confianza = 0.92
            metodo = 'codigo_exacto'

    if not producto and desc:
        like = f'%{desc[:60]}%'
        candidatos = (
            Producto.query.filter(Producto.activo == True, Producto.nombre.ilike(like))
            .limit(5)
            .all()
        )
        if len(candidatos) == 1:
            producto = candidatos[0]
            confianza = 0.75
            metodo = 'nombre_unico'
        elif len(candidatos) > 1:
            producto = candidatos[0]
            confianza = 0.45
            metodo = 'nombre_ambiguo'

    if not producto:
        return {
            'producto_id': None,
            'codigo_erp': '',
            'costo_actual': None,
            'venta_actual': None,
            'confianza': 0.0,
            'estado': 'sin_match',
            'metodo': metodo,
        }

    costo = float(producto.precio_compra or 0)
    venta = float(app.precio_efectivo_pos_producto(producto) or 0)
    codigo_erp = (producto.codigo_barra or producto.codigo_interno or '').strip()
    estado = 'mapeado_auto' if confianza >= 0.7 else 'revisar'

    return {
        'producto_id': producto.id,
        'codigo_erp': codigo_erp,
        'costo_actual': costo,
        'venta_actual': venta,
        'confianza': confianza,
        'estado': estado,
        'metodo': metodo,
    }


def _job_guarda_resultados(job: dict[str, Any]) -> bool:
    return bool(job.get('guardar_resultados'))


def _persistir_linea_radar(
    app,
    job: dict[str, Any],
    job_id: str,
    *,
    indice: int,
    linea: dict[str, Any],
    proveedor_id: int | None,
    proveedor_nombre: str,
    url_origen: str,
) -> dict[str, Any]:
    """Escribe una línea en BD radar + CSV maestro acumulado."""
    maestro_info: dict[str, Any] = {}
    try:
        radar_db.insertar_linea_db(app, job_id, indice, linea)
    except Exception as ex:
        _log.warning('Radar: no se pudo persistir linea %s: %s', linea.get('id'), ex)
    try:
        erp_root = getattr(getattr(app, 'app', None), 'root_path', None) or getattr(app, 'root_path', None)
        maestro_info = radar_csv.append_linea_maestro_csv(
            sku_proveedor=linea.get('sku_proveedor') or '',
            descripcion=linea.get('descripcion') or '',
            precio_lista_clp=int(linea.get('precio_lista_clp') or 0),
            url=url_origen or job.get('url_final') or job.get('url') or '',
            proveedor_nombre=proveedor_nombre,
            proveedor_id=proveedor_id,
            erp_root=erp_root,
        )
        if maestro_info.get('ok'):
            job['maestro_csv_total'] = maestro_info.get('total_filas')
            job['maestro_csv_path'] = maestro_info.get('path')
    except Exception as ex:
        _log.warning('Radar maestro CSV: %s', ex)
    return maestro_info


def _emit_linea_job(
    app,
    job: dict[str, Any],
    job_id: str,
    *,
    indice: int,
    total: int,
    prod: dict[str, Any],
    proveedor_id: int | None,
    parser: str,
    url_origen: str = '',
    proveedor_nombre: str = '',
) -> None:
    sku = prod['codigo_interno']
    desc = prod['descripcion_producto']
    precio = int(prod.get('precio') or 0)

    match = _match_producto(
        app,
        sku_proveedor=sku,
        descripcion=desc,
        proveedor_id=proveedor_id,
    )
    costo_act = match.get('costo_actual')
    delta_pct = None
    if costo_act and costo_act > 0 and precio > 0:
        delta_pct = round(((precio - costo_act) / costo_act) * 100, 1)

    linea_id = str(uuid.uuid4())[:12]
    linea = {
        'id': linea_id,
        'sku_proveedor': sku,
        'descripcion': desc,
        'precio_lista_clp': precio,
        'producto_id': match.get('producto_id'),
        'codigo_erp': match.get('codigo_erp') or '',
        'costo_actual': costo_act,
        'venta_actual': match.get('venta_actual'),
        'delta_pct': delta_pct,
        'estado': match.get('estado', 'sin_match'),
        'confianza': match.get('confianza', 0),
        'metodo': match.get('metodo', ''),
        'aplicado': False,
        'parser': parser,
    }

    maestro_info: dict[str, Any] = {}
    if _job_guarda_resultados(job):
        maestro_info = _persistir_linea_radar(
            app,
            job,
            job_id,
            indice=indice,
            linea=linea,
            proveedor_id=proveedor_id,
            proveedor_nombre=proveedor_nombre,
            url_origen=url_origen,
        )

    job['lineas'].append(linea)
    pct = int((indice / total) * 100) if total else 100
    job['progreso'] = pct
    _emit(
        job,
        {
            'fase': 'linea',
            'progreso': pct,
            'total': total,
            'indice': indice,
            'linea': linea,
            'sku_proveedor': sku,
            'producto': desc,
            'precio': precio,
            'estado_db': 'Guardado en maestro' if maestro_info.get('ok') else (
                'Solo lectura' if not _job_guarda_resultados(job) else 'Sin guardar en maestro'
            ),
            'maestro_csv': maestro_info if maestro_info.get('ok') else None,
            'proveedor_id': proveedor_id,
            'proveedor_nombre': proveedor_nombre,
            'guardar_resultados': _job_guarda_resultados(job),
        },
    )


def _min_productos_nativo_ok() -> int:
    try:
        return max(1, int((os.getenv('RADAR_PRECIOS_MIN_NATIVO') or '5').strip() or '5'))
    except ValueError:
        return 5


def _fusionar_productos(
    *listas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Une listas de ítems Radar deduplicando por SKU o nombre."""
    out: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for lista in listas:
        for p in lista or []:
            sku = (p.get('codigo_interno') or '').strip().upper()
            nom = re.sub(r'\s+', ' ', (p.get('descripcion_producto') or '').strip().upper())[:80]
            clave = f'sku:{sku}' if sku else f'nombre:{nom}'
            if not sku and not nom:
                continue
            if clave in vistos:
                continue
            vistos.add(clave)
            out.append(p)
    return out


def _resolver_productos_desde_html(
    job: dict[str, Any],
    html: str,
    url: str,
) -> tuple[list[dict[str, Any]], str]:
    productos, parser = extraer_productos_de_html(html, url)
    ollama_item = _ollama_por_item_habilitado()
    min_ok = _min_productos_nativo_ok()

    # Pocos resultados nativos en página de listado → no cortar; ampliar con Ollama.
    if productos and len(productos) >= min_ok:
        if ollama_item:
            job['parser'] = f'{parser}+ollama_item'
        return productos, parser or 'nativo'

    productos_ollama: list[dict[str, Any]] = []

    if ollama_item:
        _emit(job, {'fase': 'ia', 'progreso': 20, 'mensaje': 'Ollama item a item…'})
        candidatos = extraer_candidatos_texto_crudo(html)
        total_c = max(len(candidatos), 1)
        for idx, crudo in enumerate(candidatos):
            _emit(
                job,
                {
                    'fase': 'ia_item',
                    'progreso': 15 + int(((idx + 1) / total_c) * 10),
                    'mensaje': f'Ollama normalizando {idx + 1}/{len(candidatos)}…',
                },
            )
            res = ollama_normalizar_item(crudo)
            if res.get('ok') and res.get('producto'):
                productos_ollama.append(res['producto'])
            time.sleep(0.15)
        if productos_ollama:
            fusion = _fusionar_productos(productos, productos_ollama)
            etiqueta = 'nativo+ollama_item' if productos else 'ollama_item'
            if productos and len(productos) < min_ok:
                job['aviso_parser'] = (
                    f'Solo {len(productos)} producto(s) con parser HTML; '
                    f'Ollama amplió a {len(fusion)}.'
                )
            return fusion, etiqueta

    if productos:
        return productos, parser or 'nativo'

    _emit(job, {'fase': 'ia', 'progreso': 25, 'mensaje': 'Ollama estructurando catálogo…'})
    ia = ollama_estructurar_html(html)
    productos = ia.get('productos') or []
    job['ollama_modelo'] = ia.get('modelo')
    job['ollama_tokens'] = ia.get('tokens')
    if productos:
        return productos, 'ollama_bulk'
    if not ia.get('ok'):
        job['ollama_error'] = ia.get('error')
    return [], parser or 'ninguno'


def _run_job(app, job_id: str) -> None:
    with _erp_app_context(app):
        job = get_job(job_id)
        if not job:
            return
        urls = job.get('urls') or [job['url']]
        proveedor_id = job.get('proveedor_id')
        usuario = job.get('usuario') or 'usuario'
        proveedor_nombre = ''
        if proveedor_id:
            try:
                pr = app.Proveedor.query.get(int(proveedor_id))
                if pr:
                    proveedor_nombre = (pr.nombre or '').strip()
            except Exception:
                pass
        job['proveedor_id'] = proveedor_id
        job['proveedor_nombre'] = proveedor_nombre

        guardar = _job_guarda_resultados(job)
        if guardar:
            try:
                radar_db.crear_escaneo_db(
                    app,
                    job_id=job_id,
                    url=urls[0],
                    proveedor_id=proveedor_id,
                    usuario=usuario,
                )
            except Exception as ex:
                _log.warning('Radar escaneo DB: %s', ex)

        todas_lineas: list[dict[str, Any]] = []
        vistos_por_sku: set[str] = set()
        ollama_item = _ollama_por_item_habilitado()
        max_lineas = int((os.getenv('RADAR_PRECIOS_MAX_LINEAS') or '1200').strip() or '1200')

        try:
            cola_urls = list(urls)
            url_idx = -1
            while cola_urls:
                url_idx += 1
                url = cola_urls.pop(0)
                if job.get('cancelled'):
                    job['status'] = 'cancelado'
                    _emit(job, {'fase': 'cancelado', 'progreso': job.get('progreso', 0)})
                    return

                pref = f'Link {url_idx + 1}: '
                _emit(job, {'fase': 'descargando', 'progreso': 2, 'mensaje': pref + 'Descargando…'})
                paso = fetch_public_html(url)
                if paso.get('fuente'):
                    job['fetch_fuente'] = paso.get('fuente')
                if paso.get('aviso'):
                    _emit(job, {'fase': 'aviso', 'mensaje': paso.get('aviso')})
                if not paso.get('ok'):
                    if len(urls) == 1:
                        job['status'] = 'error'
                        job['error'] = paso.get('error') or 'error_descarga'
                        if guardar:
                            radar_db.actualizar_escaneo_db(
                                app, job_id, status='error', error=job['error'], finished_at=_ahora_iso()
                            )
                        hint = paso.get('hint') or ''
                        msg = mensaje_error_radar(job['error'], url)
                        if hint and hint not in msg:
                            msg = msg + ' ' + hint
                        _emit(job, {'fase': 'error', 'error': msg, 'progreso': 0})
                        return
                    _emit(job, {'fase': 'aviso', 'mensaje': f'No se pudo descargar {url}'})
                    continue

                html = paso.get('html') or ''
                job['url_final'] = paso.get('url_final')
                job['titulo'] = paso.get('titulo')

                if url_idx == 0:
                    urls_extra = _expandir_paginas_url(url, html)
                    if len(urls_extra) > 1:
                        _emit(
                            job,
                            {
                                'fase': 'descubierto_paginas',
                                'mensaje': f'Sodimac: {len(urls_extra)} páginas detectadas.',
                            },
                        )
                        for u in urls_extra[1:]:
                            if u not in cola_urls:
                                cola_urls.append(u)

                _emit(job, {'fase': 'extrayendo', 'progreso': 12, 'mensaje': pref + 'Analizando HTML…'})
                productos, parser = _resolver_productos_desde_html(job, html, url)
                job['parser'] = parser

                if not productos:
                    if len(urls) == 1:
                        job['status'] = 'error'
                        job['error'] = job.get('ollama_error') or 'sin_productos_en_pagina'
                        if guardar:
                            radar_db.actualizar_escaneo_db(
                                app,
                                job_id,
                                status='error',
                                error=job['error'],
                                parser=parser,
                                finished_at=_ahora_iso(),
                            )
                        _emit(
                            job,
                            {
                                'fase': 'error',
                                'error': mensaje_error_radar(job['error'], url),
                                'progreso': 0,
                            },
                        )
                        return
                    continue

                restante = max_lineas - len(todas_lineas)
                productos = productos[:restante]
                total_url = len(productos)

                for i, prod in enumerate(productos):
                    if job.get('cancelled'):
                        job['status'] = 'cancelado'
                        _emit(job, {'fase': 'cancelado', 'progreso': job.get('progreso', 0)})
                        return

                    if ollama_item and 'ollama_item' not in parser:
                        _emit(
                            job,
                            {'fase': 'ia_item', 'mensaje': f'Ollama refinando {i + 1}/{total_url}…'},
                        )
                        prod = _refinar_producto_con_ollama(prod)

                    sku_key = (prod.get('codigo_interno') or '').strip().upper()
                    if sku_key and sku_key in vistos_por_sku:
                        continue
                    if sku_key:
                        vistos_por_sku.add(sku_key)

                    indice_global = len(todas_lineas) + 1
                    _emit_linea_job(
                        app,
                        job,
                        job_id,
                        indice=indice_global,
                        total=max_lineas,
                        prod=prod,
                        proveedor_id=proveedor_id,
                        parser=parser,
                        url_origen=url,
                        proveedor_nombre=proveedor_nombre,
                    )
                    todas_lineas.append(job['lineas'][-1])
                    time.sleep(0.08)

                if len(todas_lineas) >= max_lineas:
                    break

            total = len(todas_lineas)
            if total == 0:
                job['status'] = 'error'
                job['error'] = 'sin_productos_en_pagina'
                if guardar:
                    radar_db.actualizar_escaneo_db(
                        app, job_id, status='error', error=job['error'], finished_at=_ahora_iso()
                    )
                _emit(
                    job,
                    {
                        'fase': 'error',
                        'error': mensaje_error_radar(job['error'], urls[0] if urls else ''),
                        'progreso': 0,
                    },
                )
                return

            job['total'] = total
            if len(todas_lineas) >= max_lineas:
                _emit(
                    job,
                    {
                        'fase': 'aviso',
                        'mensaje': f'Se alcanzó RADAR_PRECIOS_MAX_LINEAS={max_lineas}.',
                    },
                )
            job['status'] = 'completado'
            job['finished_at'] = _ahora_iso()
            if guardar:
                job['persistido'] = True
                radar_db.actualizar_escaneo_db(
                    app,
                    job_id,
                    status='completado',
                    url_final=job.get('url_final'),
                    titulo=job.get('titulo'),
                    parser=job.get('parser'),
                    total=total,
                    finished_at=job['finished_at'],
                )
            msg_fin = (
                'Escaneo finalizado y guardado en maestro.'
                if guardar
                else 'Escaneo en solo lectura (no se guardó en maestro). Use «Guardar escaneo» si desea conservarlo.'
            )
            _emit(
                job,
                {
                    'fase': 'listo',
                    'progreso': 100,
                    'total': total,
                    'mensaje': msg_fin,
                    'maestro_csv_path': job.get('maestro_csv_path'),
                    'maestro_csv_total': job.get('maestro_csv_total'),
                    'proveedor_id': proveedor_id,
                    'proveedor_nombre': proveedor_nombre,
                    'lineas_guardadas': len(job.get('lineas') or []) if guardar else 0,
                    'guardar_resultados': guardar,
                    'persistido': bool(job.get('persistido')),
                    'parser': job.get('parser'),
                    'aviso_parser': job.get('aviso_parser'),
                    'productos_este_escaneo': total,
                },
            )

            if guardar:
                with _lock:
                    _historial.appendleft({
                        'job_id': job_id,
                        'url': urls[0],
                        'titulo': job.get('titulo'),
                        'total': total,
                        'parser': job.get('parser'),
                        'finished_at': job['finished_at'],
                        'mapeados': sum(1 for ln in job['lineas'] if ln.get('producto_id')),
                        'proveedor_id': proveedor_id,
                        'proveedor_nombre': proveedor_nombre,
                    })

        except Exception as ex:
            _log.exception('Radar job %s: %s', job_id, ex)
            job['status'] = 'error'
            job['error'] = str(ex)
            if _job_guarda_resultados(job):
                try:
                    radar_db.actualizar_escaneo_db(
                        app, job_id, status='error', error=str(ex)[:500], finished_at=_ahora_iso()
                    )
                except Exception:
                    pass
            _emit(job, {'fase': 'error', 'error': str(ex), 'progreso': 0})


def _parse_urls_input(url: str, urls_extra: list | None = None) -> list[str]:
    out: list[str] = []
    for u in urls_extra or []:
        u = (u or '').strip()
        if u:
            out.append(validar_url_publica(u))
    raw = (url or '').strip()
    if raw:
        partes = [p.strip() for p in re.split(r'[\r\n]+', raw) if p.strip()]
        if len(partes) > 1:
            for p in partes:
                out.append(validar_url_publica(p))
        elif not out:
            out.append(validar_url_publica(raw))
        elif raw not in out:
            out.insert(0, validar_url_publica(raw))
    if not out:
        raise ValueError('url_requerida')
    seen: set[str] = set()
    deduped: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped[:10]


def crear_job(
    *,
    url: str,
    proveedor_id: int | None,
    usuario: str,
    app,
    urls: list[str] | None = None,
    guardar_resultados: bool = False,
) -> str:
    urls_ok = _parse_urls_input(url, urls)
    job_id = str(uuid.uuid4())
    job = {
        'id': job_id,
        'url': urls_ok[0],
        'urls': urls_ok,
        'proveedor_id': proveedor_id,
        'usuario': usuario,
        'status': 'en_proceso',
        'created_at': _ahora_iso(),
        'finished_at': None,
        'progreso': 0,
        'total': 0,
        'lineas': [],
        'events': [],
        'listeners': [],
        'parser': '',
        'error': None,
        'cancelled': False,
        'url_final': '',
        'titulo': '',
        'guardar_resultados': bool(guardar_resultados),
        'persistido': False,
    }
    with _lock:
        _jobs[job_id] = job

    t = threading.Thread(target=_run_job, args=(app, job_id), daemon=True)
    t.start()
    return job_id


def persistir_escaneo_en_maestro(app, job_id: str, *, usuario: str) -> dict[str, Any]:
    """Guarda en BD + CSV maestro un escaneo que se hizo en solo lectura."""
    with _erp_app_context(app):
        job = get_job(job_id)
        if not job:
            return {'ok': False, 'error': 'job_no_encontrado'}
        if job.get('status') not in ('completado',):
            return {'ok': False, 'error': 'escaneo_no_finalizado'}
        lineas = job.get('lineas') or []
        if not lineas:
            return {'ok': False, 'error': 'sin_lineas'}
        if job.get('persistido'):
            return {
                'ok': True,
                'ya_guardado': True,
                'lineas': len(lineas),
                'maestro_csv_total': job.get('maestro_csv_total'),
            }

        urls = job.get('urls') or [job.get('url') or '']
        proveedor_id = job.get('proveedor_id')
        proveedor_nombre = job.get('proveedor_nombre') or ''
        if proveedor_id and not proveedor_nombre:
            try:
                pr = app.Proveedor.query.get(int(proveedor_id))
                if pr:
                    proveedor_nombre = (pr.nombre or '').strip()
                    job['proveedor_nombre'] = proveedor_nombre
            except Exception:
                pass

        try:
            radar_db.crear_escaneo_db(
                app,
                job_id=job_id,
                url=urls[0],
                proveedor_id=proveedor_id,
                usuario=usuario,
            )
            radar_db.actualizar_escaneo_db(
                app,
                job_id,
                status='completado',
                url_final=job.get('url_final'),
                titulo=job.get('titulo'),
                parser=job.get('parser'),
                total=len(lineas),
                finished_at=job.get('finished_at') or _ahora_iso(),
            )
        except Exception as ex:
            _log.warning('Radar persistir escaneo DB: %s', ex)

        guardadas = 0
        url_base = job.get('url_final') or job.get('url') or ''
        for i, ln in enumerate(lineas, start=1):
            info = _persistir_linea_radar(
                app,
                job,
                job_id,
                indice=i,
                linea=ln,
                proveedor_id=proveedor_id,
                proveedor_nombre=proveedor_nombre,
                url_origen=url_base,
            )
            if info.get('ok'):
                guardadas += 1

        job['guardar_resultados'] = True
        job['persistido'] = True

        with _lock:
            _historial.appendleft({
                'job_id': job_id,
                'url': urls[0],
                'titulo': job.get('titulo'),
                'total': len(lineas),
                'parser': job.get('parser'),
                'finished_at': job.get('finished_at'),
                'mapeados': sum(1 for ln in lineas if ln.get('producto_id')),
                'proveedor_id': proveedor_id,
                'proveedor_nombre': proveedor_nombre,
            })

        return {
            'ok': True,
            'lineas': len(lineas),
            'lineas_en_maestro': guardadas,
            'maestro_csv_total': job.get('maestro_csv_total'),
            'maestro_csv_path': job.get('maestro_csv_path'),
        }


def crear_job_y_stream(
    *,
    url: str,
    proveedor_id: int | None,
    usuario: str,
    app,
    urls: list[str] | None = None,
    guardar_resultados: bool = False,
):
    job_id = crear_job(
        url=url,
        proveedor_id=proveedor_id,
        usuario=usuario,
        app=app,
        urls=urls,
        guardar_resultados=guardar_resultados,
    )
    yield from iter_sse(job_id)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        return _jobs.get(job_id)


def cancelar_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job or job.get('status') != 'en_proceso':
        return False
    job['cancelled'] = True
    return True


def iter_sse(job_id: str, *, timeout_sec: int | None = None):
    """Generador SSE: reenvía eventos y termina al completar/error."""
    if timeout_sec is None:
        try:
            timeout_sec = int((os.getenv('RADAR_SSE_TIMEOUT_SEC') or '3600').strip() or '3600')
        except ValueError:
            timeout_sec = 3600
    job = get_job(job_id)
    if not job:
        yield f"data: {json.dumps({'fase': 'error', 'error': 'job_no_encontrado'}, ensure_ascii=False)}\n\n"
        return

    enviados = 0
    inicio = time.time()
    while time.time() - inicio < timeout_sec:
        events = job.get('events') or []
        while enviados < len(events):
            payload = events[enviados]
            enviados += 1
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if payload.get('fase') in ('listo', 'error', 'cancelado'):
                return
        if job.get('status') in ('completado', 'error', 'cancelado'):
            if enviados >= len(events):
                return
        time.sleep(0.25)

    yield f"data: {json.dumps({'fase': 'error', 'error': 'timeout_sse'}, ensure_ascii=False)}\n\n"


def aplicar_costos(
    app,
    *,
    job_id: str,
    linea_ids: list[str],
    usuario: str,
    motivo: str,
) -> dict[str, Any]:
    with _erp_app_context(app):
        job = get_job(job_id)
        if not job:
            return {'ok': False, 'error': 'job_no_encontrado', 'aplicados': 0}
        ids_set = set(linea_ids or [])
        aplicados = 0
        errores: list[str] = []

        for ln in job.get('lineas') or []:
            if ids_set and ln['id'] not in ids_set:
                continue
            if ln.get('aplicado'):
                continue
            pid = ln.get('producto_id')
            precio = int(ln.get('precio_lista_clp') or 0)
            if not pid or precio <= 0:
                errores.append(f"{ln.get('sku_proveedor')}: sin producto o precio")
                continue
            producto = app.Producto.query.get(pid)
            if not producto:
                errores.append(f"{ln.get('sku_proveedor')}: producto no existe")
                continue
            anterior = float(producto.precio_compra or 0)
            producto.precio_compra = float(precio)
            ln['aplicado'] = True
            ln['estado'] = 'aplicado'
            try:
                radar_db.marcar_linea_aplicada_db(app, ln['id'])
            except Exception:
                pass
            aplicados += 1
            if app._bitacora_precios_disponible():
                try:
                    app.db.session.add(
                        app.BitacoraPrecioVenta(
                            producto_id=producto.id,
                            precio_anterior=anterior,
                            precio_nuevo=anterior,
                            costo_referencia=precio,
                            margen_objetivo=None,
                            usuario=usuario,
                            motivo=motivo or 'radar_precios_costo',
                        )
                    )
                except Exception:
                    pass
        try:
            app.db.session.commit()
        except Exception as ex:
            app.db.session.rollback()
            return {'ok': False, 'error': str(ex), 'aplicados': 0}
        return {'ok': True, 'aplicados': aplicados, 'errores': errores}


def dashboard_metrics(app) -> dict[str, Any]:
    with _erp_app_context(app):
        Producto = app.Producto
        productos = Producto.query.filter(Producto.activo == True).limit(3000).all()
        alertas = 0
        sin_costo = 0
        filas_riesgo: list[dict[str, Any]] = []
        margen_obj = 0.30

        for p in productos:
            costo = float(p.precio_compra or 0)
            if costo <= 0:
                sin_costo += 1
                continue
            venta = float(app.precio_efectivo_pos_producto(p) or 0)
            if venta <= 0:
                continue
            margen = ((venta - costo) / venta) if venta > 0 else 0
            sugerido = app._precio_sugerido_redondeado(costo, margen_obj, 90)
            if sugerido > venta + 0.01 or margen < 0.05:
                alertas += 1
                perdida = max(0, (sugerido - venta) * 50)
                filas_riesgo.append({
                    'producto': p.nombre,
                    'codigo': (p.codigo_barra or p.codigo_interno or '—'),
                    'costo': costo,
                    'venta': venta,
                    'margen_pct': round(margen * 100, 1),
                    'sugerido': sugerido,
                    'perdida_estimada': perdida,
                    'estado': 'critico' if margen < 0 else ('alerta' if margen < 0.12 else 'ok'),
                })

        filas_riesgo.sort(key=lambda x: x['perdida_estimada'], reverse=True)
        filas_riesgo = filas_riesgo[:12]
        dinero_riesgo = sum(f['perdida_estimada'] for f in filas_riesgo)
        crit = sum(1 for f in filas_riesgo if f['estado'] == 'critico')

        with _lock:
            historial_mem = list(_historial)
        historial_db = radar_db.historial_escaneos_db(app, limit=15)
        historial = historial_db or historial_mem
        if historial_db and historial_mem:
            ids = {h.get('job_id') for h in historial_db}
            for h in historial_mem:
                if h.get('job_id') not in ids:
                    historial.append(h)
            historial = historial[:15]

        ultimo_job = get_job(historial[0]['job_id']) if historial else None

        return {
            'total_productos': len(productos),
            'alertas_margen': alertas,
            'sin_costo': sin_costo,
            'dinero_en_riesgo': dinero_riesgo,
            'productos_criticos': crit,
            'filas_riesgo': filas_riesgo,
            'historial': historial,
            'ultimo_job': ultimo_job,
            'ollama': ollama_status(),
        }
