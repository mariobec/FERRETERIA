# -*- coding: utf-8 -*-
"""Etiquetas góndola · ZPL para impresoras Zebra (GX420d y compatibles)."""
from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

_SERVICES_DIR = Path(__file__).resolve().parent


def _erp_runtime_root() -> Path:
    """Raíz de datos en DEV o carpeta del .exe (PyInstaller onedir)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return _SERVICES_DIR.parent


def _config_path() -> Path:
    return _erp_runtime_root() / 'data' / 'zebra_etiqueta_config.json'

_PERFIL_GX420D: dict[str, Any] = {
    'perfil': 'gx420d',
    'layout': 'simple',
    'ancho_mm': 50,
    'alto_mm': 30,
    'ancho_papel_mm': 50,
    'columna_ancho_mm': 40,
    'columna_gap_mm': 4,
    'dpi': 203,
    'margen_x_mm': 2,
    'margen_y_mm': 2,
    'nombre_font': 22,
    'nombre_max_lineas': 2,
    'codigo_font': 18,
    'precio_font': 28,
    'precio_sec_font': 16,
    'barcode_modulo': 2,
    'barcode_ratio': 2,
    'barcode_altura_mm': 10,
    'espacio_nombre_barcode_mm': 1,
    'espacio_barcode_codigo_mm': 1,
    'espacio_codigo_precio_mm': 1,
    'mostrar_codigo_texto': True,
    'mostrar_precio_lista': True,
    'mostrar_precio_mayoreo': True,
    'impresora_nombre': '',
}

_PERFIL_DOBLE_85x30: dict[str, Any] = {
    'perfil': 'gx420d_doble',
    'layout': 'doble_columna',
    'ancho_mm': 85,
    'alto_mm': 30,
    'ancho_papel_mm': 85,
    'columna_ancho_mm': 40,
    'columna_gap_mm': 4,
    'dpi': 203,
    'margen_x_mm': 2,
    'margen_y_mm': 2,
    'nombre_font': 20,
    'nombre_max_lineas': 2,
    'codigo_font': 16,
    'precio_font': 24,
    'precio_sec_font': 14,
    'barcode_modulo': 1,
    'barcode_ratio': 2,
    'barcode_altura_mm': 8,
    'espacio_nombre_barcode_mm': 1,
    'espacio_barcode_codigo_mm': 1,
    'espacio_codigo_precio_mm': 1,
    'mostrar_codigo_texto': True,
    'mostrar_precio_lista': True,
    'mostrar_precio_mayoreo': True,
    'impresora_nombre': '',
}

PERFILES_ZEBRA: dict[str, dict[str, Any]] = {
    'gx420d': _PERFIL_GX420D,
    'gx420d_doble': _PERFIL_DOBLE_85x30,
}

_CONFIG_KEYS: set[str] = set(_PERFIL_GX420D.keys()) | set(_PERFIL_DOBLE_85x30.keys())
_MIGRANDO_CONFIG = False


def _persistir_config_etiqueta_zebra(actual: dict[str, Any]) -> dict[str, Any]:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding='utf-8')
    return actual


def _merge_config_desde_raw(raw: dict[str, Any]) -> dict[str, Any]:
    base = _defaults_por_perfil(raw.get('perfil'))
    base.update(raw)
    base['dpi'] = int(base.get('dpi') or 203)
    base['ancho_mm'] = float(base.get('ancho_mm') or 50)
    base['alto_mm'] = float(base.get('alto_mm') or 30)
    base['ancho_papel_mm'] = float(base.get('ancho_papel_mm') or base['ancho_mm'])
    base['columna_ancho_mm'] = float(base.get('columna_ancho_mm') or 40)
    base['columna_gap_mm'] = float(base.get('columna_gap_mm') or 4)
    base['layout'] = (base.get('layout') or 'simple').strip()
    return base


def mm_a_dots(mm: float, dpi: int = 203) -> int:
    return max(1, int(round(float(mm) / 25.4 * int(dpi))))


def zpl_escape(texto: str) -> str:
    s = (texto or '').replace('\\', '\\\\').replace('^', '\\^').replace('~', '\\~')
    return s.replace('\r', ' ').replace('\n', ' ').strip()


def formatear_precio_clp(valor: float | int | None) -> str:
    n = int(round(float(valor or 0)))
    if n <= 0:
        return ''
    return f'${n:,}'.replace(',', '.')


def _defaults_por_perfil(perfil: str | None) -> dict[str, Any]:
    key = (perfil or 'gx420d').strip().lower()
    if key in PERFILES_ZEBRA:
        return deepcopy(PERFILES_ZEBRA[key])
    return deepcopy(_PERFIL_GX420D)


def cargar_config_etiqueta_zebra() -> dict[str, Any]:
    global _MIGRANDO_CONFIG
    raw: dict[str, Any] = {}
    path = _config_path()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                raw = loaded
        except (json.JSONDecodeError, OSError):
            pass
    base = _merge_config_desde_raw(raw)

    from services.ticket_impresion_escpos import (
        _es_cola_zebra,
        _impresora_abrible,
        elegir_cola_zebra_preferida,
        listar_impresoras_zebra,
    )

    imp_raw = (raw.get('impresora_nombre') or '').strip()
    imp = (base.get('impresora_nombre') or '').strip()
    migrar = bool(imp_raw and not _es_cola_zebra(imp_raw))
    if imp and not _es_cola_zebra(imp):
        base['impresora_nombre'] = ''
        imp = ''
    if not imp:
        env_z = (os.getenv('ZEBRA_IMPRESORA_NOMBRE') or os.getenv('ETIQUETAS_ZEBRA_IMPRESORA') or '').strip()
        if env_z and _es_cola_zebra(env_z):
            base['impresora_nombre'] = env_z
            imp = env_z
        else:
            zebra_cols = listar_impresoras_zebra()
            if zebra_cols:
                base['impresora_nombre'] = zebra_cols[0]
                imp = zebra_cols[0]
    if imp and _es_cola_zebra(imp):
        mejor = elegir_cola_zebra_preferida(imp)
        if mejor and mejor != imp:
            base['impresora_nombre'] = mejor
            migrar = True
    if not _MIGRANDO_CONFIG and (migrar or (imp_raw and imp_raw != (base.get('impresora_nombre') or ''))):
        _MIGRANDO_CONFIG = True
        try:
            _persistir_config_etiqueta_zebra(base)
        finally:
            _MIGRANDO_CONFIG = False
    return base


def _aplicar_config_parcial(cfg: dict[str, Any], parcial: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(cfg or cargar_config_etiqueta_zebra())
    if parcial and parcial.get('perfil') and parcial.get('perfil') != out.get('perfil'):
        out = _defaults_por_perfil(parcial.get('perfil'))
        out.update(cfg or {})
    for k, v in (parcial or {}).items():
        if k in _CONFIG_KEYS:
            out[k] = v
    if (parcial or {}).get('perfil'):
        defaults = _defaults_por_perfil(parcial.get('perfil'))
        if defaults.get('layout'):
            out['layout'] = defaults['layout']
    return out


def guardar_config_etiqueta_zebra(cfg: dict[str, Any]) -> dict[str, Any]:
    if cfg and cfg.get('perfil'):
        actual = _defaults_por_perfil(cfg.get('perfil'))
        actual.update(cargar_config_etiqueta_zebra())
    else:
        actual = cargar_config_etiqueta_zebra()
    for k, v in (cfg or {}).items():
        if k not in _CONFIG_KEYS:
            continue
        if k == 'perfil':
            actual[k] = str(v or 'gx420d')
        elif k == 'layout':
            actual[k] = str(v or 'simple')
        elif k == 'impresora_nombre':
            nom = str(v or '').strip()[:120]
            if nom:
                from services.ticket_impresion_escpos import _es_cola_zebra

                if not _es_cola_zebra(nom):
                    nom = ''
            actual[k] = nom
        elif isinstance(_PERFIL_GX420D.get(k), bool) or k.startswith('mostrar_'):
            actual[k] = bool(v)
        elif k == 'dpi':
            actual[k] = max(150, min(int(v or 203), 600))
        elif k.endswith('_mm') or k in ('ancho_mm', 'alto_mm', 'ancho_papel_mm', 'columna_ancho_mm', 'columna_gap_mm'):
            actual[k] = max(1.0, min(float(v), 120.0))
        elif isinstance(v, (int, float)) and k not in ('perfil', 'layout'):
            actual[k] = int(v)
        else:
            actual[k] = v
    _persistir_config_etiqueta_zebra(actual)
    return actual


def _partir_nombre(nombre: str, max_lineas: int = 2, max_chars: int = 28) -> list[str]:
    txt = re.sub(r'\s+', ' ', (nombre or 'Sin nombre').strip())
    if len(txt) <= max_chars:
        return [txt][:max_lineas]
    palabras = txt.split(' ')
    lineas: list[str] = []
    actual = ''
    for pal in palabras:
        cand = f'{actual} {pal}'.strip()
        if len(cand) <= max_chars:
            actual = cand
        else:
            if actual:
                lineas.append(actual)
            actual = pal[:max_chars]
        if len(lineas) >= max_lineas:
            break
    if actual and len(lineas) < max_lineas:
        lineas.append(actual)
    if not lineas:
        lineas = [txt[:max_chars]]
    return lineas[:max_lineas]


def _lineas_precio(fila: dict[str, Any], cfg: dict[str, Any], variante: str) -> list[str]:
    out: list[str] = []
    if variante == 'enrolamiento':
        pos = float(fila.get('precio_pos') or 0)
        lista = float(fila.get('precio_lista') or 0)
        may = float(fila.get('precio_mayoreo') or 0)
        if pos > 0:
            out.append(f'POS {formatear_precio_clp(pos)}')
        elif lista > 0:
            out.append(formatear_precio_clp(lista))
        else:
            p = formatear_precio_clp(fila.get('precio_clp'))
            if p:
                out.append(p)
        if cfg.get('mostrar_precio_lista') and lista > 0 and (pos <= 0 or lista != pos):
            out.append(f'Lista {formatear_precio_clp(lista)}')
        if cfg.get('mostrar_precio_mayoreo') and may > 0:
            out.append(f'May {formatear_precio_clp(may)}')
    else:
        p = formatear_precio_clp(fila.get('precio_clp'))
        if p:
            out.append(p)
    return [x for x in out if x]


def _max_chars_por_ancho_mm(ancho_mm: float) -> int:
    return max(12, min(32, int(round(ancho_mm / 1.85))))


def _es_codigo_ean13(codigo: str) -> bool:
    digits = re.sub(r'\D', '', codigo or '')
    return len(digits) == 13 and digits.isdigit()


def _ancho_barcode_estimado_dots(codigo: str, modulo: int) -> int:
    """Ancho aproximado del símbolo en dots (Code128 o EAN-13)."""
    c = str(codigo or '').strip()
    w = max(1, int(modulo or 1))
    if _es_codigo_ean13(c):
        return 95 * w
    n = max(len(c), 1)
    return (11 * n + 35) * w


def _elegir_modulo_barcode(codigo: str, ancho_col_mm: float, dpi: int, modulo_pref: int) -> int:
    """Elige módulo ^BY que quepa en la columna (evita solapamiento en doble)."""
    ancho_dots = max(40, mm_a_dots(float(ancho_col_mm), dpi) - mm_a_dots(3, dpi))
    pref = max(1, min(int(modulo_pref or 2), 3))
    for w in (pref, 2, 1):
        if _ancho_barcode_estimado_dots(codigo, w) <= ancho_dots:
            return w
    return 1


def _x_barcode_en_columna(x0: int, codigo: str, modulo: int, ancho_col_mm: float, dpi: int) -> int:
    col_dots = mm_a_dots(float(ancho_col_mm), dpi)
    bc_w = _ancho_barcode_estimado_dots(codigo, modulo)
    return x0 + max(0, (col_dots - bc_w) // 2)


def _agregar_campos_etiqueta(
    partes: list[str],
    fila: dict[str, Any],
    x0: int,
    y: int,
    cfg: dict[str, Any],
    *,
    variante: str,
    max_chars: int,
    ancho_col_mm: float | None = None,
) -> int:
    """Añade campos ZPL de una etiqueta en (x0, y). Devuelve y final."""
    dpi = int(cfg.get('dpi') or 203)
    nombre_font = int(cfg.get('nombre_font') or 22)
    codigo_font = int(cfg.get('codigo_font') or 18)
    precio_font = int(cfg.get('precio_font') or 28)
    precio_sec = int(cfg.get('precio_sec_font') or 16)
    max_lineas = int(cfg.get('nombre_max_lineas') or 2)

    codigo = zpl_escape(str(fila.get('codigo') or '').strip() or 'SIN-CODIGO')
    lineas_nombre = _partir_nombre(str(fila.get('nombre') or ''), max_lineas=max_lineas, max_chars=max_chars)

    for ln in lineas_nombre:
        partes.append(f'^FO{x0},{y}^A0N,{nombre_font},{nombre_font}^FD{zpl_escape(ln)}^FS')
        y += nombre_font + 3

    y += mm_a_dots(float(cfg.get('espacio_nombre_barcode_mm') or 1), dpi)
    bc_h = mm_a_dots(float(cfg.get('barcode_altura_mm') or 10), dpi)
    bc_r = int(cfg.get('barcode_ratio') or 2)
    pref_w = int(cfg.get('barcode_modulo') or 2)
    if ancho_col_mm:
        bc_w = _elegir_modulo_barcode(codigo, ancho_col_mm, dpi, pref_w)
        x_bc = _x_barcode_en_columna(x0, codigo, bc_w, ancho_col_mm, dpi)
    else:
        bc_w = pref_w
        x_bc = x0
    if _es_codigo_ean13(codigo):
        ean = re.sub(r'\D', '', codigo)
        partes.append(f'^FO{x_bc},{y}^BY{bc_w},{bc_r},{bc_h}^BEN,{bc_h},Y,N^FD{ean}^FS')
    else:
        partes.append(f'^FO{x_bc},{y}^BY{bc_w},{bc_r},{bc_h}^BCN,{bc_h},N,N,N^FD{codigo}^FS')
    y += bc_h + mm_a_dots(float(cfg.get('espacio_barcode_codigo_mm') or 1), dpi)

    if cfg.get('mostrar_codigo_texto', True):
        partes.append(f'^FO{x0},{y}^A0N,{codigo_font},{codigo_font}^FD{codigo}^FS')
        y += codigo_font + mm_a_dots(float(cfg.get('espacio_codigo_precio_mm') or 1), dpi)

    precios = _lineas_precio(fila, cfg, variante)
    for i, pr in enumerate(precios[:2]):
        fz = precio_font if i == 0 else precio_sec
        partes.append(f'^FO{x0},{y}^A0N,{fz},{fz}^FD{zpl_escape(pr)}^FS')
        y += fz + 2
    return y


def _es_layout_doble(cfg: dict[str, Any]) -> bool:
    return (cfg.get('layout') or '').strip().lower() == 'doble_columna'


def _offset_columna2_mm(cfg: dict[str, Any]) -> float:
    return float(cfg.get('columna_ancho_mm') or 40) + float(cfg.get('columna_gap_mm') or 4)


def generar_zpl_strip_doble(
    fila1: dict[str, Any] | None,
    fila2: dict[str, Any] | None,
    cfg: dict[str, Any] | None = None,
    *,
    variante: str = 'catalogo',
) -> str:
    """Una franja 85×30 mm con hasta 2 etiquetas (40 mm + gap 4 mm + 40 mm)."""
    c = cfg or cargar_config_etiqueta_zebra()
    dpi = int(c.get('dpi') or 203)
    pw = mm_a_dots(float(c.get('ancho_papel_mm') or c.get('ancho_mm') or 85), dpi)
    ll = mm_a_dots(float(c.get('alto_mm') or 30), dpi)
    margen_x = mm_a_dots(float(c.get('margen_x_mm') or 2), dpi)
    y0 = mm_a_dots(float(c.get('margen_y_mm') or 2), dpi)
    col_w_mm = float(c.get('columna_ancho_mm') or 40)
    x_col1 = margen_x
    x_col2 = mm_a_dots(_offset_columna2_mm(c), dpi) + margen_x
    max_chars = _max_chars_por_ancho_mm(col_w_mm)

    partes = ['^XA', '^CI28', f'^PW{pw}', f'^LL{ll}', '^LH0,0']
    if fila1:
        _agregar_campos_etiqueta(
            partes, fila1, x_col1, y0, c, variante=variante, max_chars=max_chars, ancho_col_mm=col_w_mm
        )
    if fila2:
        _agregar_campos_etiqueta(
            partes, fila2, x_col2, y0, c, variante=variante, max_chars=max_chars, ancho_col_mm=col_w_mm
        )
    partes.append('^XZ')
    return '\n'.join(partes)


def generar_zpl_calibracion_doble(cfg: dict[str, Any] | None = None) -> str:
    """ZPL de prueba: texto en columna 1 y columna 2."""
    c = cfg or cargar_config_etiqueta_zebra()
    f1 = {
        'nombre': 'PRUEBA COL 1',
        'codigo': '1111111111111',
        'precio_clp': 1990,
        'precio_pos': 1990,
        'cantidad': 1,
    }
    f2 = {
        'nombre': 'PRUEBA COL 2',
        'codigo': '2222222222222',
        'precio_clp': 2990,
        'precio_pos': 2990,
        'cantidad': 1,
    }
    return generar_zpl_strip_doble(f1, f2, c, variante='catalogo')


def generar_zpl_etiqueta(
    fila: dict[str, Any],
    cfg: dict[str, Any] | None = None,
    *,
    variante: str = 'catalogo',
) -> str:
    """Genera bloque ZPL (^XA … ^XZ) para una etiqueta simple."""
    c = cfg or cargar_config_etiqueta_zebra()
    if _es_layout_doble(c):
        return generar_zpl_strip_doble(fila, None, c, variante=variante)

    dpi = int(c.get('dpi') or 203)
    pw = mm_a_dots(float(c.get('ancho_mm') or 50), dpi)
    ll = mm_a_dots(float(c.get('alto_mm') or 30), dpi)
    x0 = mm_a_dots(float(c.get('margen_x_mm') or 2), dpi)
    y0 = mm_a_dots(float(c.get('margen_y_mm') or 2), dpi)
    max_chars = _max_chars_por_ancho_mm(float(c.get('ancho_mm') or 50))

    partes = ['^XA', '^CI28', f'^PW{pw}', f'^LL{ll}', '^LH0,0']
    _agregar_campos_etiqueta(partes, fila, x0, y0, c, variante=variante, max_chars=max_chars)
    partes.append('^XZ')
    return '\n'.join(partes)


def _expandir_filas_copias(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fila in filas or []:
        copias = max(1, min(int(fila.get('cantidad') or 1), 50))
        out.extend([fila] * copias)
    return out


def generar_zpl_lote(
    filas: list[dict[str, Any]],
    cfg: dict[str, Any] | None = None,
    *,
    variante: str = 'catalogo',
) -> str:
    c = cfg or cargar_config_etiqueta_zebra()
    if _es_layout_doble(c):
        expandidas = _expandir_filas_copias(filas)
        bloques: list[str] = []
        for i in range(0, len(expandidas), 2):
            f1 = expandidas[i]
            f2 = expandidas[i + 1] if i + 1 < len(expandidas) else None
            bloques.append(generar_zpl_strip_doble(f1, f2, c, variante=variante))
        return '\n'.join(bloques)

    bloques = []
    for fila in filas or []:
        copias = max(1, min(int(fila.get('cantidad') or 1), 50))
        zpl_one = generar_zpl_etiqueta(fila, c, variante=variante)
        bloques.extend([zpl_one] * copias)
    return '\n'.join(bloques)


def nombre_impresora_zebra(cfg: dict[str, Any] | None = None) -> str:
    if cfg and (cfg.get('impresora_nombre') or '').strip():
        return str(cfg['impresora_nombre']).strip()
    return (os.getenv('ZEBRA_IMPRESORA_NOMBRE') or os.getenv('ETIQUETAS_ZEBRA_IMPRESORA') or '').strip()


def _coincidir_cola_zebra(pref: str, candidatos: list[str]) -> str | None:
    """Nombre exacto o parcial contra colas Windows (case-insensitive)."""
    pref = (pref or '').strip()
    if not pref or not candidatos:
        return None
    if pref in candidatos:
        return pref
    pl = pref.lower()
    for c in candidatos:
        if c.lower() == pl:
            return c
    for c in candidatos:
        cl = c.lower()
        if pl in cl or cl in pl:
            return c
    return None


def impresora_para_panel(
    cfg: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """(cola activa, opciones datalist, detalle colas Windows)."""
    from services.ticket_impresion_escpos import _es_cola_zebra, elegir_cola_zebra_preferida, listar_colas_zebra_detalle

    c = cfg or cargar_config_etiqueta_zebra()
    colas = listar_colas_zebra_detalle()
    detectadas = [d.get('nombre') or '' for d in colas if d.get('nombre')]
    preferida = (c.get('impresora_nombre') or '').strip() or nombre_impresora_zebra(c)
    seleccionada = elegir_cola_zebra_preferida(preferida)

    opciones: list[str] = []
    for p in [seleccionada] + detectadas + [
        'ZDesigner GX420d',
        'Zebra GX420d - ZPL',
    ]:
        p = (p or '').strip()
        if p and p not in opciones and _es_cola_zebra(p):
            opciones.append(p)
    return seleccionada, opciones, colas


def resolver_impresora_zebra(cfg: dict[str, Any] | None = None) -> str | None:
    from services.ticket_impresion_escpos import resolver_nombre_impresora_zebra

    return resolver_nombre_impresora_zebra(nombre_impresora_zebra(cfg) or None)


def zebra_habilitada() -> bool:
    v = (os.getenv('ZEBRA_ETIQUETAS_HABILITADA') or '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')


def imprimir_zpl_en_zebra(zpl: str, *, impresora: str | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    if not zpl.strip():
        return {'ok': False, 'error': 'vacio', 'mensaje': 'Sin ZPL para imprimir.'}
    from services.ticket_impresion_escpos import enviar_raw_zpl

    c = cfg or cargar_config_etiqueta_zebra()
    nombre = (impresora or nombre_impresora_zebra(c) or '').strip()
    if not nombre:
        sel, _, _ = impresora_para_panel(c)
        nombre = sel
    nombre = nombre or None
    res = enviar_raw_zpl(zpl.encode('utf-8', errors='replace'), nombre)
    if res.get('ok'):
        res['tipo'] = 'zebra_zpl'
    return res


def fila_ejemplo_calibracion() -> dict[str, Any]:
    return {
        'id': 0,
        'nombre': 'Tornillo zincado 1 pulgada cabeza Phillips',
        'codigo': '7805201592032',
        'precio_clp': 1990,
        'precio_pos': 1990,
        'precio_lista': 2490,
        'precio_mayoreo': 1650,
        'cantidad': 1,
    }


def filas_ejemplo_calibracion_doble() -> list[dict[str, Any]]:
    return [
        {
            'id': 0,
            'nombre': 'PRUEBA COL 1 tornillo',
            'codigo': '1111111111111',
            'precio_clp': 1990,
            'precio_pos': 1990,
            'cantidad': 1,
        },
        {
            'id': 0,
            'nombre': 'PRUEBA COL 2 clavo',
            'codigo': '2222222222222',
            'precio_clp': 2990,
            'precio_pos': 2990,
            'cantidad': 1,
        },
    ]
