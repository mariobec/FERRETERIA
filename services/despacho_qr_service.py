"""URLs y normalización QR despacho (lectores tipo teclado / térmica)."""
from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import quote, unquote


def public_site_base() -> str:
    return (
        os.getenv('PUBLIC_SITE_URL')
        or os.getenv('PUBLIC_BASE_URL')
        or 'http://127.0.0.1:5000'
    ).rstrip('/')


def token_para_qr_path(token: str) -> str:
    """Evita ? y . en el path del QR (puntos del token → _)."""
    return quote((token or '').replace('.', '_'), safe='_')


def token_desde_qr_path(segment: str) -> str:
    raw = unquote((segment or '').strip())
    return raw.replace('_', '.')


def url_despacho_qr_corta(venta_id: int, token: str, *, base: str | None = None) -> str:
    """
    URL para imprimir en QR: sin ? ni : en query.
    Ej: http://host/r/despacho/3136/eyJ2IjozMTM2fQ_ah4hfA_...
    """
    base = (base or public_site_base()).rstrip('/')
    seg = token_para_qr_path(token)
    return f'{base}/r/despacho/{int(venta_id)}/{seg}'


def _limpiar_prefijos_lector(raw: str) -> str:
    s = (raw or '').strip()
    if not s:
        return ''
    for pref in ('qr1', 'QR1', 'qr:', 'QR:'):
        if s.lower().startswith(pref.lower()):
            s = s[len(pref) :]
            break
    return s.strip()


def _corregir_teclado_es_wedge(s: str) -> str:
    """Correcciones típicas lector HID en layout ES (Ñ→:, ¿→?)."""
    return (
        s.replace('Ñ', ':')
        .replace('ñ', ':')
        .replace('¿', '?')
        .replace('¡', '!')
    )


def resolver_url_despacho_desde_escaneo(raw: str) -> Optional[str]:
    """
    Convierte texto leído (a veces corrupto) a path interno /r/despacho/... o /pos/despacho/vale/...
    """
    s = _corregir_teclado_es_wedge(_limpiar_prefijos_lector(raw))
    if not s:
        return None

    # Ya es ruta corta válida
    m_short = re.search(r'/r/despacho/(\d+)/([A-Za-z0-9_%.-]+)\s*$', s)
    if m_short:
        return f'/r/despacho/{m_short.group(1)}/{m_short.group(2)}'

    # Formato corrupto lector ES: ...pos-despacho-vale-3136_t¿TOKEN
    m_bad = re.search(
        r'pos[-_/]*despacho[-_/]*vale[-_/]*(\d+)[-_/]*t[¿?=]?([A-Za-z0-9_.-]+)',
        s,
        re.I,
    )
    if m_bad:
        vid = int(m_bad.group(1))
        tok = m_bad.group(2).replace('_', '.')
        seg = token_para_qr_path(tok)
        return f'/r/despacho/{vid}/{seg}'

    # URL con slashes correctos
    m_url = re.search(
        r'/pos/despacho/vale/(\d+)(?:\?t=|&t=|/t/)([A-Za-z0-9_.-]+)',
        s,
    )
    if m_url:
        vid = int(m_url.group(1))
        tok = m_url.group(2).replace('_', '.')
        return f'/r/despacho/{vid}/{token_para_qr_path(tok)}'

    # Solo folio VL######
    from services.entrega_ticket_service import parse_folio_vale

    folio = parse_folio_vale(s)
    if folio:
        return f'/r/despacho/folio/{folio}'

    return None
