"""Resolución de códigos escaneados en POS (EAN-13/14, ceros, prefijos)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app import Producto


def _solo_digitos(codigo: str) -> str:
    return re.sub(r'\D', '', codigo or '')


# Separadores que pistolas Code 128 suelen confundir con guion medio (-) en códigos FERRE-*.
_PISTOL_SEP_ALTERNATIVOS = ("~", "'", "'", "`", "´", "–", "—")


def _normalizar_guion_medio(codigo: str) -> str:
    out = codigo or ""
    for alt in _PISTOL_SEP_ALTERNATIVOS:
        out = out.replace(alt, "-")
    return out


def _variantes_separador_pistola(codigo: str) -> list[str]:
    """
    Pistolas Code 128 a veces leen guion medio (-) como apóstrofo ('), virgulilla (~), etc.
    Genera forma canónica con guion y variantes inversas en códigos alfanuméricos.
    """
    raw = (codigo or '').strip()
    if not raw or _solo_digitos(raw) == raw:
        return []
    out: list[str] = []
    canon = _normalizar_guion_medio(raw)
    if canon != raw:
        out.append(canon)
    base = canon if '-' in canon else raw
    if '-' in base:
        for alt in ("'", "~", "'"):
            out.append(base.replace('-', alt))
    return out


def variantes_codigo_barras_escaneo(codigo: str) -> list[str]:
    """
    Variantes habituales pistola vs maestro (EAN-13 + dígito empaque, ceros, mayúsculas).
    Orden: más específico primero.
    """
    raw = (codigo or '').strip()
    if not raw:
        return []

    out: list[str] = []
    seen: set[str] = set()

    def add(val: str | None) -> None:
        v = (val or '').strip()
        if not v or v in seen:
            return
        seen.add(v)
        out.append(v)

    add(raw)
    add(raw.upper())
    for alt in _variantes_separador_pistola(raw):
        add(alt)
        add(alt.upper())
    digits = _solo_digitos(raw)
    if digits:
        add(digits)
        if len(digits) == 13:
            add(digits + '0')
        if len(digits) == 14 and digits.endswith('0'):
            add(digits[:-1])
        if len(digits) == 12:
            add('0' + digits)
        stripped = digits.lstrip('0')
        if stripped and stripped != digits:
            add(stripped)
            if len(stripped) == 13:
                add(stripped + '0')
    return out


def buscar_producto_por_variantes_codigo(
    codigo: str,
    *,
    buscar_fn,
    buscar_chilemat_fn=None,
) -> tuple[Any | None, str | None]:
    """
    buscar_fn(cnorm) -> Producto | None por codigo_barra / interno.
    buscar_chilemat_fn(cnorm) -> Producto | None (opcional).
    Retorna (producto, variante_que_matcheo).
    """
    for variant in variantes_codigo_barras_escaneo(codigo):
        cnorm = variant.strip().upper()
        producto = buscar_fn(cnorm)
        if producto:
            return producto, variant
        if buscar_chilemat_fn:
            producto = buscar_chilemat_fn(cnorm)
            if producto:
                return producto, variant
    return None, None


def sugerencias_productos_por_codigo_escaneo(
    codigo: str,
    *,
    query_productos,
    stock_tienda_fn,
    precio_pos_fn,
    limit: int = 5,
) -> list[dict]:
    """
    Candidatos cuando no hubo match exacto: código numérico contenido en barras/interno.
    query_productos(like_pattern) -> iterable Producto activos.
    """
    digits = _solo_digitos(codigo)
    if len(digits) < 8:
        return []
    like = f'%{digits}%'
    rows = list(query_productos(like, limit=limit * 3))
    out: list[dict] = []
    seen_ids: set[int] = set()
    for p in rows:
        pid = int(getattr(p, 'id', 0) or 0)
        if not pid or pid in seen_ids:
            continue
        bar_digits = _solo_digitos(getattr(p, 'codigo_barra', None) or '')
        int_digits = _solo_digitos(getattr(p, 'codigo_interno', None) or '')
        if digits not in bar_digits and digits not in int_digits:
            if not (bar_digits and (bar_digits.startswith(digits) or digits.startswith(bar_digits))):
                continue
        seen_ids.add(pid)
        out.append({
            'id': pid,
            'nombre': (getattr(p, 'nombre', None) or '').strip(),
            'codigo_barra': (getattr(p, 'codigo_barra', None) or '').strip(),
            'stock_tienda': int(stock_tienda_fn(p) or 0),
            'precio': float(precio_pos_fn(p) or 0),
            'coincidencia': 'codigo_similar',
        })
        if len(out) >= limit:
            break
    return out
