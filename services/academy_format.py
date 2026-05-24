"""Formateo HUD LhexIA Academy — badges, callouts y normalización de atajos."""
from __future__ import annotations

import html
import re

from markupsafe import Markup

INVARIANTE_FINANCIERA = (
    'Invariante Financiera: El POS jamás recauda dinero real; el flujo operativo se cierra '
    'única y exclusivamente en la estación de Caja.'
)

_ESC_REGLA = 'Esc → Cerrar modal o cancelar línea actual'

_ATAJOS_REEMPLAZOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r'(`?F8`?\s*(?:→|->|:)?\s*(?:Foco\s+b[uú]squeda|buscar|enfocar|foco)[^.\n|]*)',
            re.I,
        ),
        'F2 → Foco búsqueda de producto / Invocación de Escáner universal',
    ),
    (
        re.compile(
            r'(`?F9`?\s*(?:→|->|:)?\s*(?:Emitir\s+vale|emitir)[^.\n|]*)',
            re.I,
        ),
        'F8 → Emitir vale de venta pendiente (Bloqueo de caja diferido)',
    ),
    (
        re.compile(r'(`?F2`?\s*(?:→|->|:)?\s*(?:Foco|buscar|b[uú]squeda)[^.\n|]*)', re.I),
        'F2 → Foco búsqueda de producto / Invocación de Escáner universal',
    ),
    (
        re.compile(r'(`?Esc`?\s*(?:→|->|:)?\s*[^.\n|]*)', re.I),
        _ESC_REGLA,
    ),
)

_BADGE_VERDE = (
    '<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">'
    '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Entrega Inmediata</span>'
)
_BADGE_AMARILLO = (
    '<span class="badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1">'
    '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Reserva Parcial</span>'
)
_BADGE_NARANJA = (
    '<span class="badge text-orange border px-2 py-1" '
    'style="color:#ff5500;border-color:#ff5500;background:rgba(255,85,0,0.12);font-weight:600;">'
    '<i class="fas fa-bolt me-1"></i> Venta en Verde</span>'
)


def normalizar_atajos_texto(texto: str | None) -> str:
    if not texto:
        return ''
    out = str(texto)
    for pat, repl in _ATAJOS_REEMPLAZOS:
        out = pat.sub(repl, out)
    return out


def _aplicar_badges_linea(linea_esc: str) -> str:
    linea = linea_esc
    patrones = (
        (r'\*\*Verde:\*\*|\*\*Verde\*\*|🟢\s*Verde', _BADGE_VERDE),
        (r'\*\*Amarillo:\*\*|\*\*Amarillo\*\*|🟡\s*Amarillo', _BADGE_AMARILLO),
        (
            r'\*\*Rojo:\*\*|\*\*Rojo\*\*|\*\*Naranja:\*\*|\*\*Naranja\*\*|🍊\s*Naranja|🔴\s*Rojo',
            _BADGE_NARANJA,
        ),
    )
    for pat, badge in patrones:
        linea = re.sub(pat, badge, linea, flags=re.I)
    return linea


def formatear_contenido_academy_html(texto: str | None) -> Markup:
    """Convierte markdown operativo en bloques HUD (badges + glass callouts)."""
    if not texto:
        return Markup('')

    texto = normalizar_atajos_texto(texto)
    bloques: list[str] = []
    lista_items: list[str] = []
    lista_tipo = 'ul'

    def flush_lista() -> None:
        nonlocal lista_items, lista_tipo
        if not lista_items:
            return
        tag = lista_tipo
        items = ''.join(f'<li>{item}</li>' for item in lista_items)
        bloques.append(f'<{tag} class="lhexia-academy-list">{items}</{tag}>')
        lista_items = []

    for raw in texto.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_lista()
            continue

        if stripped.startswith('|') and stripped.count('|') >= 2:
            flush_lista()
            celdas = [c.strip() for c in stripped.strip('|').split('|')]
            if len(celdas) >= 2 and celdas[0].lower() not in ('tecla', '---', '-------'):
                tecla = html.escape(normalizar_atajos_texto(celdas[0]))
                accion = html.escape(normalizar_atajos_texto(celdas[1]))
                bloques.append(
                    f'<div class="lhexia-academy-kbd-row">'
                    f'<kbd>{tecla}</kbd><span>{accion}</span></div>'
                )
            continue

        if re.match(r'^[-|:\s]+$', stripped):
            continue

        if stripped.startswith('> '):
            flush_lista()
            cuerpo = html.escape(stripped[2:].strip())
            bloques.append(f'<div class="lhexia-academy-callout">{cuerpo}</div>')
            continue

        if re.match(r'^Importante\s*:', stripped, re.I):
            flush_lista()
            cuerpo = html.escape(re.sub(r'^Importante\s*:\s*', '', stripped, flags=re.I))
            bloques.append(f'<div class="lhexia-academy-callout">{cuerpo}</div>')
            continue

        m_head = re.match(r'^(#{1,3})\s+(.+)$', stripped)
        if m_head:
            flush_lista()
            titulo = html.escape(m_head.group(2).strip())
            bloques.append(f'<div class="lhexia-academy-subtitle">{titulo}</div>')
            continue

        if re.match(r'^📌\s*PROTOCOLO', stripped, re.I) or re.match(r'^Sección\s+\d', stripped, re.I):
            flush_lista()
            titulo = html.escape(stripped)
            bloques.append(f'<div class="lhexia-academy-subtitle">{titulo}</div>')
            continue

        m_num = re.match(r'^\d+[\.\)]\s*(.+)$', stripped)
        if m_num:
            if lista_tipo != 'ol':
                flush_lista()
                lista_tipo = 'ol'
            item = _aplicar_badges_linea(html.escape(normalizar_atajos_texto(m_num.group(1))))
            lista_items.append(item)
            continue

        m_bul = re.match(r'^[-*]\s+(.+)$', stripped)
        if m_bul:
            if lista_tipo != 'ul':
                flush_lista()
                lista_tipo = 'ul'
            item = _aplicar_badges_linea(html.escape(normalizar_atajos_texto(m_bul.group(1))))
            lista_items.append(item)
            continue

        flush_lista()
        linea = _aplicar_badges_linea(html.escape(normalizar_atajos_texto(stripped)))
        bloques.append(f'<p class="lhexia-academy-p">{linea}</p>')

    flush_lista()
    return Markup('\n'.join(bloques))


def formatear_texto_plano(texto: str | None) -> str:
    return normalizar_atajos_texto(texto or '')
