"""Base de conocimiento Mentor — manual operación Q&A para Ollama y Coach."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_KB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'mentor' / 'manual_operacion_ollama.json'

_STOP = frozenset(
    'de la el en y a o u con por para que es un una del los las al como sin sobre'.split()
)


@lru_cache(maxsize=1)
def cargar_kb_operacion() -> dict[str, Any]:
    if not _KB_PATH.is_file():
        return {'faq': [], 'modulos': [], 'invariantes': [], 'rutas': {}}
    with open(_KB_PATH, encoding='utf-8') as f:
        return json.load(f)


def recargar_kb_operacion() -> dict[str, Any]:
    """Invalida caché tras editar manual_operacion_ollama.json (tests / hot reload)."""
    cargar_kb_operacion.cache_clear()
    return cargar_kb_operacion()


def kb_version() -> str:
    return str(cargar_kb_operacion().get('version') or '')


def kb_invariantes_texto() -> list[str]:
    out: list[str] = []
    for inv in cargar_kb_operacion().get('invariantes') or []:
        t = (inv.get('texto') or '').strip()
        if t:
            out.append(t)
    return out


def _tokens(texto: str) -> set[str]:
    raw = re.findall(r'[a-záéíóúñ0-9]{3,}', (texto or '').lower())
    return {t for t in raw if t not in _STOP}


_SOPORTE_SEÑALES = (
    'sin precio', 'no deja vender', 'no me deja', 'no puedo vender',
    'no vendible', 'no aparece', 'error', 'falla', 'problema con',
    'bloqueado', 'no funciona', 'no deja', 'dice sin',
)
_APRENDER_SEÑALES = (
    'enseñame', 'enséñame', 'enseñar', 'aprender', 'aprende',
    'como vendo', 'cómo vendo', 'como vender', 'cómo vender',
    'como uso', 'cómo uso', 'primeros pasos', 'desde cero',
    'nuevo en', 'soy nuevo', 'guía para', 'tutorial', 'paso a paso',
    'flujo de', 'primera venta', 'primera toma',
)
_ONBOARDING_SEÑALES = (
    'convierto', 'convertirme', 'capacitarme', 'capacito', 'capacitación',
    'capacitacion', 'ser cajero', 'ser vendedor', 'ser bodeguero',
    'empiezo como', 'nuevo cajero', 'nuevo vendedor', 'nuevo bodeguero',
    'donde aprendo a ser', 'como empiezo', 'cómo empiezo', 'ruta cajero',
    'ruta vendedor', 'ruta bodega',
)


def _clasificar_intencion_pregunta(pregunta: str) -> str:
    pl = (pregunta or '').lower().strip()
    if any(s in pl for s in _SOPORTE_SEÑALES):
        return 'soporte'
    if any(s in pl for s in _ONBOARDING_SEÑALES):
        return 'onboarding'
    if any(s in pl for s in _APRENDER_SEÑALES):
        return 'aprender'
    if pl.startswith(('como ', 'cómo ', 'que es ', 'qué es ')):
        return 'aprender'
    return 'general'


def _score_faq(pregunta: str, faq: dict[str, Any]) -> float:
    qtok = _tokens(pregunta)
    if not qtok:
        return 0.0
    pl = (pregunta or '').lower()
    intent = _clasificar_intencion_pregunta(pregunta)
    faq_intent = str(faq.get('intencion') or 'general').lower()
    blob_parts = [
        faq.get('pregunta') or '',
        faq.get('respuesta') or '',
        faq.get('modulo') or '',
        ' '.join(faq.get('variantes') or []),
        ' '.join(faq.get('pasos') or []),
    ]
    blob = ' '.join(str(p) for p in blob_parts).lower()
    hit = sum(1 for t in qtok if t in blob)
    bonus = 0.0
    pregunta_kb = (faq.get('pregunta') or '').lower()
    for t in qtok:
        if t in pregunta_kb:
            bonus += 2.5
    for var in faq.get('variantes') or []:
        v = str(var).lower().strip()
        if v and v in pl:
            bonus += 8.0 if intent == 'aprender' and faq_intent == 'aprender' else 4.0
    if intent == 'aprender':
        if faq_intent == 'aprender':
            bonus += 10.0
        elif faq_intent == 'soporte':
            bonus -= 14.0
        if any(s in pregunta_kb for s in ('no deja', 'sin precio', 'error', 'problema')):
            bonus -= 8.0
    elif intent == 'soporte':
        if faq_intent == 'soporte':
            bonus += 10.0
        elif faq_intent == 'aprender':
            bonus -= 5.0
    elif intent == 'onboarding':
        if faq_intent == 'onboarding':
            bonus += 16.0
        elif faq_intent == 'aprender':
            bonus -= 8.0
        elif faq_intent == 'soporte':
            bonus -= 12.0
    return hit + bonus


def buscar_faq_kb(pregunta: str, *, top_n: int = 3) -> list[dict[str, Any]]:
    faqs = list(cargar_kb_operacion().get('faq') or [])
    scored = [( _score_faq(pregunta, f), f) for f in faqs]
    scored = [(s, f) for s, f in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for score, faq in scored[: max(1, int(top_n))]:
        item = dict(faq)
        item['_score'] = score
        out.append(item)
    return out


def buscar_procedimiento_kb(modulo_id: str, proc_id: str | None = None) -> dict[str, Any] | None:
    for mod in cargar_kb_operacion().get('modulos') or []:
        if (mod.get('id') or '') != modulo_id:
            continue
        procs = mod.get('procedimientos') or []
        if not proc_id:
            return mod
        for p in procs:
            if (p.get('id') or '') == proc_id:
                return {'modulo': mod, 'procedimiento': p}
    return None


def formatear_faq_respuesta(faq: dict[str, Any]) -> str:
    lines = [f"**{(faq.get('pregunta') or 'Consulta').strip()}**"]
    resp = (faq.get('respuesta') or '').strip()
    if resp:
        lines.append(resp)
    pasos = [str(p).strip() for p in (faq.get('pasos') or []) if str(p).strip()]
    if pasos:
        lines.append('')
        lines.append('**Pasos:**')
        for i, p in enumerate(pasos, 1):
            lines.append(f'{i}. {p}')
    ruta = (faq.get('ruta') or '').strip()
    if ruta:
        lines.append('')
        lines.append(f'**Pantalla:** `{ruta}`')
    return '\n'.join(lines)


def construir_contexto_ollama_manual(
    pregunta: str,
    *,
    faq_hits: list[dict[str, Any]] | None = None,
    articulo_md: str | None = None,
    max_chars: int = 9000,
) -> str:
    """Texto consolidado para system/user prompt de Ollama."""
    kb = cargar_kb_operacion()
    chunks: list[str] = [
        f"Producto: {kb.get('producto', 'LhexIA ERP')}",
        f"Versión manual KB: {kb.get('version', '')}",
    ]
    invs = kb_invariantes_texto()
    if invs:
        chunks.append('INVARIANTES (obligatorias):')
        for inv in invs:
            chunks.append(f'- {inv}')

    hits = faq_hits if faq_hits is not None else buscar_faq_kb(pregunta, top_n=5)
    if hits:
        chunks.append('')
        chunks.append('FAQ OFICIAL (prioridad — no contradecir):')
        for faq in hits:
            chunks.append(f"P: {faq.get('pregunta')}")
            chunks.append(f"R: {faq.get('respuesta')}")
            pasos = faq.get('pasos') or []
            if pasos:
                chunks.append('Pasos: ' + ' → '.join(str(p) for p in pasos[:6]))
            if faq.get('ruta'):
                chunks.append(f"Ruta ERP: {faq['ruta']}")

    if articulo_md:
        chunks.append('')
        chunks.append('GUÍA ACADEMY (complementaria):')
        chunks.append(articulo_md[:4000])

    rutas = kb.get('rutas') or {}
    if rutas:
        chunks.append('')
        chunks.append('RUTAS ERP (referencia):')
        for k, v in list(rutas.items())[:15]:
            chunks.append(f'- {k}: {v}')

    text = '\n'.join(chunks)
    return text[:max_chars]


def system_prompt_mentor_ollama() -> str:
    return (
        'Sos **Maylén**, **profesora IA** de **LhexIA Academy** en Ferretería Santo Domingo (Chile). '
        'Llevás el rol de profesora del ERP (icono de lentes en la interfaz; no describas tu apariencia). '
        'En la tienda web sos asesora de obra; acá enseñás el ERP interno. '
        'Respondés SOLO con información del manual operativo provisto. '
        'Si no está en el contexto, decí "No tengo esa respuesta en el manual — consultá a supervisión o /academy". '
        'Reglas: español claro, máximo 150 palabras, numerá pasos si aplica, '
        'mencioná la ruta de menú exacta (ej. /punto_venta), '
        'nunca inventes permisos ni pantallas. '
        'Recordá: POS no cobra; caja sí. Stock POS = almacén Tienda.'
    )


def listar_preguntas_rapidas_desde_kb(limit: int = 8) -> list[dict[str, str]]:
    """Chips sugeridos para UI Academy Coach."""
    faqs = cargar_kb_operacion().get('faq') or []
    preferidos = (
        'faq_026', 'faq_029', 'faq_030', 'faq_027', 'faq_031', 'faq_033',
        'faq_007', 'faq_011', 'faq_034', 'faq_017',
    )
    by_id = {f.get('id'): f for f in faqs}
    out: list[dict[str, str]] = []
    for fid in preferidos:
        f = by_id.get(fid)
        if not f:
            continue
        q = (f.get('pregunta') or '').strip()
        if not q:
            continue
        out.append({'id': fid, 'label': q if len(q) <= 42 else q[:39] + '…', 'q': q})
        if len(out) >= limit:
            break
    return out
