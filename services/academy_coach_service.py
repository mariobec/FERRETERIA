"""Mentor Coach — búsqueda conversacional sobre Manual Academy + KB Ollama."""
from __future__ import annotations

import re
from typing import Any

from services.academy_mentor_kb_service import (
    buscar_faq_kb,
    construir_contexto_ollama_manual,
    formatear_faq_respuesta,
    listar_preguntas_rapidas_desde_kb,
    system_prompt_mentor_ollama,
)

_PREGUNTAS_RAPIDAS_FALLBACK: list[dict[str, str]] = [
    {'id': 'vale', 'label': '¿Cómo emitir un vale?', 'q': '¿Cómo emitir un vale en el POS?'},
    {'id': 'caja', 'label': '¿Cómo abrir caja?', 'q': '¿Cómo abro la caja al iniciar el turno?'},
]

_STOP = frozenset(
    'de la el en y a o u con por para que es un una del los las al como sin sobre'.split()
)


def listar_preguntas_rapidas_academy() -> list[dict[str, str]]:
    kb_chips = listar_preguntas_rapidas_desde_kb()
    return kb_chips if kb_chips else list(_PREGUNTAS_RAPIDAS_FALLBACK)


def _tokens(texto: str) -> set[str]:
    raw = re.findall(r'[a-záéíóúñ0-9]{3,}', (texto or '').lower())
    return {t for t in raw if t not in _STOP}


def _score_articulo(pregunta: str, art: dict[str, Any]) -> float:
    qtok = _tokens(pregunta)
    if not qtok:
        return 0.0
    blob = ' '.join(
        [
            str(art.get('title') or ''),
            str(art.get('summary') or ''),
            str(art.get('content_markdown') or ''),
            str(art.get('category') or ''),
        ]
    ).lower()
    hit = sum(1 for t in qtok if t in blob)
    bonus = 0.0
    title = (art.get('title') or '').lower()
    for t in qtok:
        if t in title:
            bonus += 2.0
    return hit + bonus


def _pasos_resumen(art: dict[str, Any], max_pasos: int = 4) -> list[str]:
    pasos = [str(p).strip() for p in (art.get('pasos') or []) if str(p).strip()]
    if pasos:
        return pasos[:max_pasos]
    md = art.get('content_markdown') or ''
    out: list[str] = []
    for line in md.splitlines():
        m = re.match(r'^\d+[\.\)]\s*(.+)$', line.strip())
        if m:
            out.append(m.group(1).strip())
        if len(out) >= max_pasos:
            break
    return out


def _articulo_desde_faq(faq: dict[str, Any]) -> dict[str, Any]:
    ruta = (faq.get('ruta') or '/academy').strip()
    launch = (faq.get('mentor_launch') or f'{ruta}?mentor_open=1').strip()
    return {
        'title': faq.get('pregunta') or 'Guía Mentor',
        'dedupe_key': faq.get('id') or '',
        'category': faq.get('modulo') or 'general',
        'practicar_href': ruta,
        'launch_interactivo_href': launch,
        'ancla': '/academy',
    }


def _enriquecer_ollama(
    pregunta: str,
    *,
    faq_hits: list[dict[str, Any]],
    articulo: dict[str, Any] | None,
    base: str,
) -> tuple[str, str]:
    try:
        from services.ollama_client import generar_chat, ollama_disponible

        if not ollama_disponible(scope='vitrina', requiere_modelo=False):
            return base, 'reglas'
    except Exception:
        return base, 'reglas'

    art_md = (articulo.get('content_markdown') or '') if articulo else ''
    ctx = construir_contexto_ollama_manual(pregunta, faq_hits=faq_hits, articulo_md=art_md)
    system = system_prompt_mentor_ollama()
    user = (
        f'Pregunta del operador:\n{pregunta}\n\n'
        f'MANUAL OPERATIVO OFICIAL:\n{ctx}\n\n'
        f'Borrador inicial:\n{base}\n\n'
        'Respondé al operador en segunda persona, directo y accionable. '
        'Incluí la ruta de pantalla si aplica.'
    )
    try:
        chat = generar_chat(scope='vitrina', system=system, user=user)
        if chat.get('ok') and (chat.get('texto') or '').strip():
            return str(chat['texto']).strip(), 'ollama'
    except Exception:
        pass
    return base, 'reglas'


def responder_pregunta_academy(pregunta: str, *, usar_ia: bool = True) -> dict[str, Any]:
    """Resuelve pregunta contra KB FAQ + artículos Academy Manual V2."""
    from services.academy_service import listar_manual_v2_para_ayuda

    pregunta = (pregunta or '').strip()
    if len(pregunta) < 3:
        return {
            'ok': False,
            'error': 'pregunta_corta',
            'mensaje': 'Escribí al menos 3 caracteres. Ej: «¿Cómo emitir un vale?»',
            'sugerencias': listar_preguntas_rapidas_academy(),
        }

    faq_hits = buscar_faq_kb(pregunta, top_n=3)
    best_faq = faq_hits[0] if faq_hits else None
    faq_score = float(best_faq.get('_score') or 0) if best_faq else 0.0

    articulos = listar_manual_v2_para_ayuda()
    best_art = None
    art_score = 0.0
    if articulos:
        scored = [(_score_articulo(pregunta, a), a) for a in articulos]
        scored.sort(key=lambda x: x[0], reverse=True)
        art_score, best_art = scored[0]

    usar_faq = best_faq is not None and faq_score >= max(art_score, 2.0)

    if not usar_faq and art_score < 1 and not faq_hits:
        alts_art = articulos[:3] if articulos else []
        return {
            'ok': True,
            'confianza': 'baja',
            'respuesta': (
                'No encontré una guía exacta en el manual. Probá reformular o usá las '
                'tarjetas rápidas.'
            ),
            'articulo': None,
            'alternativas': [
                {'title': a.get('title'), 'dedupe_key': a.get('dedupe_key'), 'practicar_href': a.get('practicar_href')}
                for a in alts_art
            ],
            'sugerencias': listar_preguntas_rapidas_academy(),
            'fuente': 'reglas',
        }

    if usar_faq and best_faq:
        texto = formatear_faq_respuesta(best_faq)
        art_payload = _articulo_desde_faq(best_faq)
        pasos = [str(p) for p in (best_faq.get('pasos') or [])]
        conf = 'alta' if faq_score >= 5 else 'media'
        fuente = 'kb'
    else:
        assert best_art is not None
        pasos = _pasos_resumen(best_art, 5)
        titulo = best_art.get('title') or 'Guía Academy'
        summary = (best_art.get('summary') or '').strip()
        lines = [f'**{titulo}**']
        if summary:
            lines.append(summary)
        if pasos:
            lines.append('')
            lines.append('**Pasos recomendados:**')
            for i, p in enumerate(pasos, 1):
                lines.append(f'{i}. {p}')
        lines.append('')
        lines.append('Usá **Guía interactiva** para abrir la pantalla con el Mentor violeta.')
        texto = '\n'.join(lines)
        href = best_art.get('practicar_href') or '/academy'
        dk = best_art.get('dedupe_key') or ''
        art_payload = {
            'title': titulo,
            'dedupe_key': dk,
            'category': best_art.get('category'),
            'practicar_href': href,
            'launch_interactivo_href': f'{href}?mentor_open=1&academy_guide={dk}' if dk else href,
            'ancla': best_art.get('ancla'),
        }
        conf = 'alta' if art_score >= 4 else 'media'
        fuente = 'academy'

    if usar_ia:
        texto, fuente_ia = _enriquecer_ollama(
            pregunta,
            faq_hits=faq_hits,
            articulo=best_art if not usar_faq else None,
            base=texto,
        )
        if fuente_ia == 'ollama':
            fuente = 'ollama'

    return {
        'ok': True,
        'confianza': conf,
        'respuesta': texto,
        'articulo': art_payload,
        'pasos': pasos,
        'faq_id': best_faq.get('id') if best_faq else None,
        'sugerencias': listar_preguntas_rapidas_academy(),
        'fuente': fuente,
    }
