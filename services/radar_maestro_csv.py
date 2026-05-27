"""Radar Precios — acumula escaneos en CSV maestro (formato /cargar_productos)."""
from __future__ import annotations

import csv
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from homologar_productos_excel import (
    TARGET_COLUMNS,
    _codigo_barra_pendiente,
    _codigo_interno_sugerido,
)

_log = logging.getLogger(__name__)
_lock = threading.Lock()

DEFAULT_REL_PATH = Path('CARGA DE DATOS') / 'radar_maestro_acumulado.csv'


def ruta_maestro_csv(erp_root: str | None = None) -> Path:
    custom = (os.getenv('RADAR_MAESTRO_CSV_PATH') or '').strip()
    if custom:
        p = Path(custom)
        if not p.is_absolute() and erp_root:
            p = Path(erp_root) / p
        return p
    root = Path(erp_root) if erp_root else Path.cwd()
    return root / DEFAULT_REL_PATH


def _inferir_origen_web(url: str) -> tuple[str, str]:
    """Retorna (slug_proveedor, categoria_sugerida)."""
    host = (urlparse(url or '').hostname or '').lower()
    if 'chilemat' in host:
        return 'chilemat', 'Ferreteria'
    if 'sodimac' in host:
        return 'sodimac', 'Ferreteria'
    if 'easy' in host:
        return 'easy', 'Ferreteria'
    if 'construmart' in host:
        return 'construmart', 'Ferreteria'
    return 'web', 'Importacion Radar'


def _clip_txt(val: Any, max_len: int) -> str:
    return str(val or '').strip()[:max_len]


def _precio_csv(val: Any) -> str:
    try:
        n = int(float(str(val or '0').replace('.', '').replace(',', '.')))
    except (TypeError, ValueError):
        n = 0
    return str(max(0, n))


def linea_radar_a_fila_maestro(
    *,
    sku_proveedor: str,
    descripcion: str,
    precio_lista_clp: int,
    url: str = '',
    proveedor_nombre: str = '',
) -> dict[str, str]:
    """
    Convierte línea Radar al formato maestro (homologar_productos_excel.TARGET_COLUMNS).
    Reglas Chilemat/maestro: stock=0, PEND-* / CHM-* si faltan códigos ERP.
    """
    slug, cat_default = _inferir_origen_web(url)
    nombre = _clip_txt(descripcion, 100) or _clip_txt(sku_proveedor, 100)
    sku = _clip_txt(sku_proveedor, 80)
    chm = sku
    if slug == 'sodimac' and chm and not chm.upper().startswith('SOD-'):
        chm = f'SOD-{chm}'[:80]
    elif slug == 'easy' and chm and not chm.upper().startswith('EASY-'):
        chm = f'EASY-{chm}'[:80]

    interno = _codigo_interno_sugerido(chm) if chm else ''
    barra = _codigo_barra_pendiente(chm) if chm else ''

    subcat = _clip_txt(proveedor_nombre, 50) or slug.replace('_', ' ').title()

    return {
        'nombre': nombre,
        'codigo_chilemat': chm,
        'codigo_interno': interno,
        'codigo_barra': barra,
        'precio_compra': _precio_csv(precio_lista_clp),
        'precio_venta': '',
        'precio_mayoreo': '',
        'unidad_compra': 'unidad',
        'unidad_venta': 'unidad',
        'factor_conversion': '1.0',
        'stock': '0',
        'categoria': cat_default,
        'subcategoria': subcat,
        'ubicacion_pasillo': '',
        'ubicacion_estante': '',
        'ubicacion_nivel': '',
    }


def _clave_dedupe(row: dict[str, str]) -> str:
    for k in ('codigo_chilemat', 'codigo_barra', 'codigo_interno'):
        v = (row.get(k) or '').strip().upper()
        if v:
            return f'{k}:{v}'
    nom = re.sub(r'\s+', ' ', (row.get('nombre') or '').strip().upper())
    return f'nombre:{nom[:80]}'


def _leer_filas_existentes(path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not path.is_file():
        return [], {}
    filas: list[dict[str, str]] = []
    idx_map: dict[str, int] = {}
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc, newline='') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    norm = {c: str(row.get(c) or '').strip() for c in TARGET_COLUMNS}
                    if not norm.get('nombre'):
                        continue
                    filas.append(norm)
                    idx_map[_clave_dedupe(norm)] = len(filas) - 1
            return filas, idx_map
        except Exception as ex:
            _log.debug('leer maestro csv %s (%s): %s', path, enc, ex)
    return [], {}


def _escribir_csv(path: Path, filas: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.csv.tmp')
    with open(tmp, 'w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=TARGET_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        for row in filas:
            writer.writerow({c: row.get(c, '') for c in TARGET_COLUMNS})
    tmp.replace(path)


def append_linea_maestro_csv(
    *,
    sku_proveedor: str,
    descripcion: str,
    precio_lista_clp: int,
    url: str = '',
    proveedor_nombre: str = '',
    erp_root: str | None = None,
) -> dict[str, Any]:
    """Agrega o actualiza una fila en el CSV maestro acumulado."""
    path = ruta_maestro_csv(erp_root)
    fila = linea_radar_a_fila_maestro(
        sku_proveedor=sku_proveedor,
        descripcion=descripcion,
        precio_lista_clp=precio_lista_clp,
        url=url,
        proveedor_nombre=proveedor_nombre,
    )
    if not fila.get('nombre'):
        return {'ok': False, 'error': 'sin_nombre', 'path': str(path)}

    with _lock:
        filas, idx_map = _leer_filas_existentes(path)
        clave = _clave_dedupe(fila)
        accion = 'nuevo'
        if clave in idx_map:
            prev = filas[idx_map[clave]]
            # Conservar códigos ya asignados si existían
            for k in ('codigo_barra', 'codigo_interno', 'codigo_chilemat'):
                if prev.get(k) and not str(prev.get(k)).startswith('PEND-'):
                    fila[k] = prev[k]
                elif prev.get(k):
                    fila[k] = prev[k]
            for k in ('categoria', 'subcategoria', 'ubicacion_pasillo', 'ubicacion_estante', 'ubicacion_nivel'):
                if prev.get(k) and not fila.get(k):
                    fila[k] = prev[k]
            filas[idx_map[clave]] = fila
            accion = 'actualizado'
        else:
            filas.append(fila)
        try:
            _escribir_csv(path, filas)
        except Exception as ex:
            _log.exception('No se pudo escribir maestro CSV: %s', ex)
            return {'ok': False, 'error': str(ex), 'path': str(path)}
        return {
            'ok': True,
            'accion': accion,
            'path': str(path),
            'total_filas': len(filas),
            'fila': fila,
        }


def estadisticas_maestro_csv(erp_root: str | None = None) -> dict[str, Any]:
    path = ruta_maestro_csv(erp_root)
    filas, _ = _leer_filas_existentes(path)
    return {
        'path': str(path),
        'existe': path.is_file(),
        'total_filas': len(filas),
        'columnas': list(TARGET_COLUMNS),
    }


def preview_maestro_csv(
    erp_root: str | None = None,
    *,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    """Retorna una página del CSV maestro para vista en UI."""
    page = max(1, int(page or 1))
    per_page = max(10, min(int(per_page or 50), 200))
    path = ruta_maestro_csv(erp_root)
    filas, _ = _leer_filas_existentes(path)
    total = len(filas)
    if total == 0:
        return {
            'path': str(path),
            'total_filas': 0,
            'page': 1,
            'per_page': per_page,
            'total_pages': 1,
            'rows': [],
            'columns': list(TARGET_COLUMNS),
        }
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    ini = (page - 1) * per_page
    fin = ini + per_page
    rows = filas[ini:fin]
    return {
        'path': str(path),
        'total_filas': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'rows': rows,
        'columns': list(TARGET_COLUMNS),
    }
