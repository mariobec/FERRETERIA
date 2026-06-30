"""Vitrina pública piloto: catálogo Chilemat + stock ERP (Ferretería Santo Domingo)."""
from __future__ import annotations

import html
import json
import os
import re
import unicodedata
from typing import Any

from sqlalchemy import and_, func, or_

TIENDA_SLUG_SD = 'ferreteria-santo-domingo'
TIENDA_TITULO_DEFAULT = 'Ferretería Santo Domingo'

# Vendedora vitrina / pedidos web (antes «Liz»)
ASISTENTE_NOMBRE = 'Maylén'
ASISTENTE_SUBTITULO = 'Agente constructor · ventas y asesoría técnica'
ASISTENTE_USUARIO_WEB = 'Maylen-Web'
ASISTENTE_USUARIO_WEB_LEGACY = ('Liz-Web',)


def prefijos_usuario_pedido_web() -> tuple[str, ...]:
    return (ASISTENTE_USUARIO_WEB,) + ASISTENTE_USUARIO_WEB_LEGACY


def es_usuario_pedido_web(usuario: str | None) -> bool:
    u = (usuario or '').strip()
    return any(u.startswith(p) for p in prefijos_usuario_pedido_web())


def filtro_sql_usuario_pedido_web():
    """OR ilike para ventas creadas desde vitrina (Maylén o legado Liz-Web)."""
    from app import Venta

    return or_(*[Venta.usuario.ilike(f'{p}%') for p in prefijos_usuario_pedido_web()])

_TOKENS_RUIDO_ASISTENTE = {
    'busco', 'buscar', 'quiero', 'necesito', 'dame', 'mostrar', 'muestrame', 'muestrame',
    'tienes', 'tenis', 'hay', 'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos',
    'unas', 'por', 'para', 'con', 'favor', 'porfa', 'me', 'cotiza', 'cotizar', 'precio',
    'stock', 'cuanto', 'cuánto',
    'hola', 'buenas', 'buen', 'dia', 'tardes', 'noches', 'ayuda', 'asesor', 'liz', 'tal',
    'que', 'cual', 'cuales', 'como', 'puedo', 'puede', 'usar', 'uso', 'sirve', 'sirven',
    'algo', 'algun', 'alguna', 'este', 'esta', 'estoy', 'tengo', 'hacer', 'hago',
}
_SALUDO_SOLO = {'hola', 'buenas', 'buen', 'dia', 'tardes', 'noches', 'ayuda', 'asesor', 'liz', 'maylen', 'tal', 'que'}
_INTENCION_RECOMENDAR = (
    'recomiend', 'recomendar', 'recomendacion', 'suger', 'sugerencia',
    'alternativa', 'alternativas', 'opcion', 'opciones', 'que me recomiendas',
)

# Maestro Constructor: el cliente describe un problema (gotera, humedad), no un SKU.
_MARCADORES_PROBLEMA = (
    'gotera', 'gotea', 'filtr', 'humed', 'moho', 'grieta', 'fisura', 'fuga', 'filtra',
    'impermeabil', 'techo', 'zinc', 'lluvia', 'llueve', 'oxida', 'herrumbre', 'corrosion',
    'cortocircuito', 'chispa', 'disyuntor', 'entra agua', 'sellar', 'empapa', 'filtracion',
    'se rompio', 'se quemo', 'no prende', 'no enciende', 'tapar agua', 'goteando',
    'picar tierra', 'cavar tierra', 'excavar', 'romper tierra', 'mover tierra',
)
_PREGUNTA_SOLUCION = (
    'que me sirve', 'que necesito', 'que compro', 'como arreglo', 'como reparo',
    'como solucion', 'que uso para', 'que llevo para', 'ayudame con',
    'con que puedo', 'con que se puede', 'que puedo usar', 'para picar', 'para cavar',
)
_INTENCION_CIERRE_CARRITO = (
    'listo', 'termin', 'finaliz', 'cerrar pedido', 'vale de retiro', 'vale retiro',
    'generar vale', 'pedir retiro', 'retiro en tienda', 'confirmar carrito',
    'ver mi carrito', 'mi carrito', 'pasar a retirar', 'cotizar pedido', 'hacer pedido',
)

CARRITO_MAX_CANTIDAD = 99
CARRITO_STORAGE_KEY = 'sd_vitrina_carrito_v1'

# Término de búsqueda → categoría Chilemat (raíz o nivel 1)
_INTENCION_CATEGORIA: dict[str, tuple[str, ...]] = {
    'pintura': ('pintura', 'pinturas'),
    'cemento': ('cemento', 'cementos', 'hormigon'),
    'broca': ('broca', 'brocas'),
    'cinta': ('cinta', 'cintas', 'masking'),
}

# Accesorios de pintura (no pintura en sí) — penalizar si buscan solo "pintura"
_ACCESORIO_PINTURA = (
    'bandeja', 'rodillo', 'brocha', 'espatula', 'pincel', 'mezclador', 'extension',
    'bandeja pintura', 'reja', 'lijador',
)


def url_tienda(slug: str, *, cat: int | None = None, q: str | None = None, menu: int | None = None) -> str:
    """Ruta pública vitrina (sin depender de url_for — usable en tests y servicios)."""
    from urllib.parse import urlencode

    base = f'/tienda/{slug}'
    params: dict[str, str] = {}
    if cat is not None:
        params['cat'] = str(int(cat))
    if q:
        params['q'] = q.strip()
    if menu is not None:
        params['menu'] = str(int(menu))
    return f'{base}?{urlencode(params)}' if params else base


def url_tienda_producto(slug: str, producto_id: int) -> str:
    return f'/tienda/{slug}/producto/{int(producto_id)}'


def tienda_habilitada() -> bool:
    return (os.getenv('VITRINA_TIENDA_HABILITADA', '1').strip().lower() in ('1', 'true', 'si', 'yes', 'on'))


def _fmt_clp(n: float | int | None) -> str:
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        v = 0
    return f'${"{:,}".format(v).replace(",", ".")}'


def _precio_mostrar(chm, prod) -> float:
    # Prioridad: Precio ajustado en enrolamiento (Piloto SD), luego lista Vtex, luego precio base ERP
    sd = float(getattr(prod, 'precio_venta_sd', None) or 0)
    if sd > 0:
        return sd
    pl = getattr(chm, 'precio_lista', None)
    if pl is not None and float(pl) > 0:
        return float(pl)
    return float(getattr(prod, 'precio_venta', None) or 0)


def _texto_descripcion_producto(desc: str | None) -> str:
    """Texto plano para ficha (sin HTML crudo ni entidades &oacute; visibles)."""
    if not desc:
        return ''
    t = html.unescape(str(desc))
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > 2000:
        t = t[:1999] + '…'
    return t


def _categoria_label(path: str | None) -> str:
    if not path:
        return ''
    parts = [p.strip() for p in str(path).split('/') if p.strip()]
    return parts[-1] if parts else ''


def _texto_simple(txt: str) -> str:
    base = unicodedata.normalize('NFKD', txt or '')
    base = ''.join(ch for ch in base if not unicodedata.combining(ch))
    base = re.sub(r'[^a-zA-Z0-9\s]+', ' ', base).lower()
    return re.sub(r'\s+', ' ', base).strip()


def _modo_combo_habilitado() -> bool:
    """Activa venta cruzada Liz + relaciones producto_relacion (Chilemat sync)."""
    v = (os.getenv('VITRINA_LIZ_MODO_COMBO') or '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')


def _maestro_constructor_habilitado() -> bool:
    """Asesoría técnica: problema del cliente → términos de catálogo reales."""
    v = (os.getenv('VITRINA_MAESTRO_CONSTRUCTOR') or '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')


def _es_consulta_por_problema(txt: str) -> bool:
    """True si el mensaje describe una situación/reparación, no solo un nombre de producto."""
    base = _texto_simple(txt)
    if not base:
        return False
    if any(m in base for m in _MARCADORES_PROBLEMA):
        return True
    if any(p in base for p in _PREGUNTA_SOLUCION) and len(base.split()) >= 4:
        return True
    if '?' in (txt or '') and len(base) >= 28 and any(m in base for m in _MARCADORES_PROBLEMA[:12]):
        return True
    return False


def _interpretar_problema_reglas(txt: str) -> dict[str, Any]:
    """Mapa heurístico problema → términos de búsqueda (sin Ollama)."""
    base = _texto_simple(txt)
    if not base:
        return {'ok': False}

    if any(x in base for x in ('gotera', 'gotea', 'filtr', 'goteando')) or (
        'agua' in base and any(x in base for x in ('techo', 'zinc', 'cubre', 'teja', 'cubierta'))
    ):
        diag = 'Filtración o gotera en cubierta o techo'
        if 'zinc' in base:
            diag = 'Gotera o filtración en techo de zinc (lluvia / cubierta metálica)'
        terminos = ['silicona', 'tapagotera', 'sellador', 'cinta']
        if 'zinc' in base or 'metal' in base:
            terminos = ['silicona neutra', 'tapagotera', 'cinta autoadhesiva', 'sellador']
        return {'ok': True, 'diagnostico': diag, 'terminos': terminos, 'fuente': 'reglas'}

    if any(x in base for x in ('humedad', 'moho', 'empapa')) and any(
        x in base for x in ('muro', 'pared', 'bano', 'cocina', 'sotano')
    ):
        return {
            'ok': True,
            'diagnostico': 'Humedad o moho en muro o ambiente húmedo',
            'terminos': ['impermeabilizante', 'sellador', 'antihumedad'],
            'fuente': 'reglas',
        }

    if any(x in base for x in ('cortocircuito', 'chispa', 'disyuntor', 'se va la luz')):
        return {
            'ok': True,
            'diagnostico': 'Protección o falla eléctrica en instalación',
            'terminos': ['disyuntor', 'cable', 'cinta aisladora'],
            'fuente': 'reglas',
        }

    if any(x in base for x in ('oxida', 'herrumbre', 'corrosion', 'oxido')):
        return {
            'ok': True,
            'diagnostico': 'Óxido o corrosión en metal',
            'terminos': ['anticorrosivo', 'convertidor', 'esmalte'],
            'fuente': 'reglas',
        }

    if 'grieta' in base or 'fisura' in base:
        return {
            'ok': True,
            'diagnostico': 'Grietas o fisuras en mampostería',
            'terminos': ['masilla', 'cemento', 'mortero', 'sellador'],
            'fuente': 'reglas',
        }

    if any(x in base for x in ('picar', 'cavar', 'excavar', 'romper', 'zapar')) and any(
        x in base for x in ('tierra', 'suelo', 'terreno', 'zanja', 'pozo', 'hoyo')
    ):
        return {
            'ok': True,
            'diagnostico': 'Excavación o picado de tierra / movimiento de suelo a mano',
            'terminos': ['pico', 'pala', 'zapapico', 'barreno', 'calderilla'],
            'fuente': 'reglas',
        }

    return {'ok': False}


def _prompt_maestro_constructor_interpretar() -> str:
    extra = (os.getenv('VITRINA_MAESTRO_PROMPT_EXTRA') or '').strip()
    base = (
        'Eres el Maestro Constructor (asesor técnico) de una ferretería en Chile. '
        'El cliente describe un PROBLEMA en su casa (gotera, humedad, grieta), no el nombre exacto del producto. '
        'Traduce el problema a entre 3 y 5 términos cortos para buscar en catálogo ferretero real '
        '(ej: silicona neutra, tapagotera, cinta autoadhesiva, impermeabilizante). '
        'NO inventes marcas. Responde SOLO JSON válido sin markdown ni texto extra: '
        '{"diagnostico":"una frase técnica breve","terminos_busqueda":["term1","term2","term3"]}'
    )
    return f'{base} {extra}'.strip()


def _parse_json_desde_ollama(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    texto = raw.strip()
    m = re.search(r'\{[\s\S]*\}', texto)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _interpretar_problema_ollama(txt: str) -> dict[str, Any]:
    """Ollama traduce problema → términos de catálogo (JSON)."""
    vacio: dict[str, Any] = {'ok': False}
    try:
        from services.ollama_client import generar_chat_vitrina, ollama_disponible_vitrina
    except Exception:
        return vacio
    if not ollama_disponible_vitrina():
        return vacio

    user = (
        f'Problema del cliente: {txt.strip()[:500]}\n'
        'Devuelve solo el JSON con diagnostico y terminos_busqueda.'
    )
    out = generar_chat_vitrina(system=_prompt_maestro_constructor_interpretar(), user=user)
    if not out.get('ok'):
        return vacio
    data = _parse_json_desde_ollama(out.get('texto') or '')
    if not data:
        return vacio
    terminos_raw = data.get('terminos_busqueda') or data.get('terminos') or []
    if isinstance(terminos_raw, str):
        terminos_raw = [terminos_raw]
    terminos: list[str] = []
    for t in terminos_raw:
        s = (str(t) if t is not None else '').strip()[:60]
        if s and s.lower() not in {x.lower() for x in terminos}:
            terminos.append(s)
    if not terminos:
        return vacio
    diag = (str(data.get('diagnostico') or data.get('resumen') or '')).strip()[:200]
    return {
        'ok': True,
        'diagnostico': diag or 'Consulta técnica del cliente',
        'terminos': terminos[:5],
        'fuente': 'ollama',
    }


def _interpretar_problema_cliente(txt: str) -> dict[str, Any]:
    """Reglas locales + Ollama (si está activo); prioriza términos útiles para el catálogo."""
    reglas = _interpretar_problema_reglas(txt)
    ollama = _interpretar_problema_ollama(txt) if ollama_vitrina_disponible() else {'ok': False}

    if ollama.get('ok') and reglas.get('ok'):
        terminos = list(ollama.get('terminos') or [])
        for t in reglas.get('terminos') or []:
            if t and t.lower() not in {x.lower() for x in terminos}:
                terminos.append(t)
        return {
            'ok': True,
            'diagnostico': (ollama.get('diagnostico') or reglas.get('diagnostico') or '').strip(),
            'terminos': terminos[:6],
            'fuente': 'ollama+reglas',
        }
    if ollama.get('ok'):
        return ollama
    if reglas.get('ok'):
        return reglas
    return {'ok': False}


def _buscar_items_maestro(terminos: list[str]) -> tuple[list[dict[str, Any]], int]:
    """Búsqueda multi-término tras interpretación técnica."""
    limpios = [(t or '').strip()[:60] for t in (terminos or []) if (t or '').strip()]
    if not limpios:
        return [], 0

    rank_tokens: list[str] = []
    for term in limpios:
        for tok in _texto_simple(term).split():
            if len(tok) >= 3 and tok not in rank_tokens:
                rank_tokens.append(tok)
    rank_tokens = rank_tokens[:10]

    lotes: list[list[dict[str, Any]]] = []
    for term in limpios[:4]:
        try:
            r = listar_productos(page=1, per_page=28, q_text=term, solo_disponibles=False)
            if r.get('productos'):
                lotes.append(r['productos'])
        except Exception:
            continue

    merged = _merge_items_por_producto(*lotes, limite=48)
    if not merged:
        return [], 0

    ranked = _rankear_y_filtrar_items(merged, rank_tokens, min_score=3, limite=24)
    if not ranked:
        ranked = merged[:24]

    def _sort_key(it: dict[str, Any]) -> tuple[int, int]:
        disp = 0 if it.get('disponible') else 1
        score = _score_item_busqueda(it, rank_tokens)
        return (disp, -score)

    ranked.sort(key=_sort_key)
    return ranked, len(ranked)


def _reply_maestro_constructor(
    items: list[dict[str, Any]],
    interpret: dict[str, Any],
    mensaje: str,
) -> str:
    """Respuesta asesoría técnica con producto estrella + precio/stock."""
    if not items:
        diag = (interpret.get('diagnostico') or 'tu situación').strip()
        return (
            f'Entiendo: {diag}. No encontré coincidencias claras en catálogo ahora; '
            'prueba en tienda o dime otra palabra (marca o medida).'
        )
    diag = (interpret.get('diagnostico') or 'tu situación').strip()
    top = items[0]
    nombre = (top.get('nombre') or 'este producto').strip()
    precio = (top.get('precio_fmt') or '').strip()
    msg = f'Entiendo el problema: {diag}. '
    msg += f'Para eso en ferretería te conviene revisar {nombre}'
    if precio:
        msg += f' (precio de referencia {precio})'
    if top.get('disponible'):
        msg += ', con stock en tienda ahora'
    else:
        msg += '; consulta disponibilidad en tienda'
    msg += '. '
    n = len(items)
    if n > 1:
        msg += f'Te dejé {min(n, 3)} opciones relacionadas al lado para comparar.'
    else:
        msg += 'La ves en el listado al lado.'
    _ = mensaje  # contexto futuro Ollama redacción
    return msg


def _maylen_prompt_ollama(nombre_tienda: str, *, modo_combo: bool = False) -> str:
    """Instrucciones de tono Maylén (vitrina). VITRINA_MAYLEN_PROMPT_EXTRA o VITRINA_LIZ_PROMPT_EXTRA."""
    extra = (os.getenv('VITRINA_MAYLEN_PROMPT_EXTRA') or os.getenv('VITRINA_LIZ_PROMPT_EXTRA') or '').strip()
    base = (
        f"Eres {ASISTENTE_NOMBRE}, agente constructor y vendedora de '{nombre_tienda}' (ferreteria en Chile). "
        'Ayudas con pinturas, electricidad, impermeabilizacion, herramientas y materiales de obra. '
        'Tutea al cliente con tono cariñoso, generoso y profesional (como una colega de confianza en la ferreteria). '
        'PROHIBIDO decir Chilemat, ERP, precio referencial Chilemat o precio referencial. '
        'Para precios di: precio de referencia en la tienda en linea; el valor final se confirma en caja. '
        'NO inventes productos, precios ni stock: solo usa la respuesta base y los candidatos. '
        'Si ningun candidato sirve para la pregunta (ej. piden pala y solo hay cocina), '
        'di que no hay match claro y sugiere otra palabra; NO recomiendes productos irrelevantes.'
    )
    if modo_combo:
        base += (
            ' MODO COMBO ACTIVO: el cliente pregunta por un producto y debes sugerir llevar tambien '
            'los productos relacionados del contexto (comprados juntos en la tienda). '
            'Confirma disponibilidad del producto principal, nombra 1 o 2 complementos con su precio '
            'de referencia y cierra invitando a agregar ambos al carrito de compras. '
            'Maximo 3 oraciones cortas, sin markdown ni listas con guiones.'
        )
    else:
        base += (
            ' Maximo 2 oraciones. Si hay productos en la lista, menciona uno o dos nombres '
            'y di que quedan abajo para ver detalle.'
        )
    if _maestro_constructor_habilitado():
        base += (
            ' Si el cliente describe un problema (gotera, humedad, grieta), actua como asesor tecnico: '
            'explica brevemente la solucion y recomienda productos del listado con precio de referencia.'
        )
    return f'{base} {extra}'.strip()


def _es_solo_saludo(txt: str) -> bool:
    """True si el mensaje no trae termino de producto (ej. solo hola / buenas tardes)."""
    _, tokens = _normalizar_consulta_asistente(txt)
    if tokens:
        return False
    palabras = set(_texto_simple(txt).split())
    if not palabras:
        return True
    return palabras.issubset(_SALUDO_SOLO | _TOKENS_RUIDO_ASISTENTE)


def _url_catalogo_busqueda(slug: str, txt: str) -> str | None:
    normalizado, _tokens = _normalizar_consulta_asistente(txt)
    q = (normalizado or (txt or '').strip())[:80]
    if not q:
        return None
    return url_tienda(slug, q=q, menu=0)


def _es_intencion_excavacion_tierra(simple: str) -> bool:
    if not simple:
        return False
    if 'picar tierra' in simple or 'cavar tierra' in simple:
        return True
    accion = any(x in simple for x in ('picar', 'cavar', 'excavar', 'romper', 'zapar'))
    suelo = any(x in simple for x in ('tierra', 'suelo', 'terreno', 'zanja', 'pozo'))
    return accion and suelo


def _normalizar_consulta_asistente(txt: str) -> tuple[str, list[str]]:
    """
    Convierte frases naturales ('busco pintura impermeabilizante') en términos buscables.
    Retorna (consulta_compacta, tokens_utiles).
    """
    simple = _texto_simple(txt)
    if not simple:
        return '', []
    if _es_intencion_excavacion_tierra(simple):
        tokens_exc = ['pala', 'pico', 'zapapico', 'barreno']
        return 'pala pico', tokens_exc
    tokens = [t for t in simple.split(' ') if len(t) >= 3 and t not in _TOKENS_RUIDO_ASISTENTE]
    if not tokens:
        tokens = [t for t in simple.split(' ') if len(t) >= 3]
    tokens = tokens[:5]
    return ' '.join(tokens), tokens


def _es_intencion_recomendacion(txt: str) -> bool:
    base = _texto_simple(txt)
    if not base:
        return False
    return any(k in base for k in _INTENCION_RECOMENDAR)


def _fallback_sugerencias_ambiguas(txt: str, tokens: list[str]) -> list[dict[str, Any]]:
    """Ante consulta ambigua sin match exacto, buscar alternativas cercanas con stock."""
    candidatos: list[dict[str, Any]] = []
    probes: list[str] = []
    normal = _texto_simple(txt)
    if normal:
        probes.append(normal[:80])
    for tk in tokens[:3]:
        if tk and tk not in probes:
            probes.append(tk)

    for q in probes:
        try:
            block = listar_productos(page=1, per_page=24, q_text=q, solo_disponibles=True)
            candidatos.extend(block.get('productos') or [])
        except Exception:
            continue
        if len(candidatos) >= 12:
            break
    return _rankear_y_filtrar_items(candidatos, tokens, min_score=4, limite=3)


def _merge_items_por_producto(*listas: list[dict[str, Any]], limite: int = 12) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for lista in listas:
        for it in lista or []:
            try:
                pid = int(it.get('producto_id') or 0)
            except Exception:
                pid = 0
            if not pid or pid in seen:
                continue
            seen.add(pid)
            out.append(it)
            if len(out) >= limite:
                return out
    return out


def _resolver_cat_vtex_por_intento(tokens: list[str]) -> int | None:
    """Si el usuario pide «pintura», priorizar rubro Pinturas en Chilemat."""
    from app import ChilematCategoria

    for tok in tokens:
        hints = _INTENCION_CATEGORIA.get(tok)
        if not hints:
            continue
        for hint in hints:
            cat = (
                ChilematCategoria.query.filter(ChilematCategoria.nombre.ilike(f'%{hint}%'))
                .order_by(ChilematCategoria.depth.asc(), ChilematCategoria.nombre.asc())
                .first()
            )
            if cat:
                return int(cat.vtex_id)
    return None


def _score_item_busqueda(item: dict[str, Any], tokens: list[str]) -> int:
    nombre = _texto_simple(item.get('nombre') or '')
    cat = _texto_simple((item.get('categoria') or '') + ' ' + (item.get('categoria_path') or ''))
    score = 0
    for tok in tokens:
        if not tok:
            continue
        if nombre.startswith(tok + ' '):
            score += 45
        elif f' {tok} ' in f' {nombre} ':
            score += 28
        elif tok in nombre:
            score += 10
        if tok in cat:
            score += 18
    if 'pintura' in tokens or 'pinturas' in tokens:
        if any(nombre.startswith(p) for p in ('pintura', 'esmalte', 'latex', 'látex')):
            score += 35
        if any(p in nombre for p in ('impermeabil', 'anticorrosiv', 'sellador', 'fondo')):
            score += 22
        if any(a in nombre for a in _ACCESORIO_PINTURA):
            score -= 50
        if 'bandeja' in nombre and 'pintura' in nombre:
            score -= 40
    if _es_intencion_excavacion_tierra(' '.join(tokens)):
        if any(x in nombre for x in ('pico', 'pala', 'zapapico', 'zapa', 'barreno', 'calderilla', 'azadon')):
            score += 45
        if any(x in nombre for x in ('anafe', 'quemador', 'parrilla', 'cocina', 'camping', 'gas licuado', 'glp')):
            score -= 90
        if any(x in nombre for x in ('pintura', 'brocha', 'rodillo', 'cinta')):
            score -= 25
    return score


def _rankear_y_filtrar_items(
    items: list[dict[str, Any]],
    tokens: list[str],
    *,
    min_score: int = 8,
    limite: int = 24,
) -> list[dict[str, Any]]:
    if not items:
        return []
    if not tokens:
        return items[:limite]
    scored: list[tuple[int, dict[str, Any]]] = []
    seen_names: set[str] = set()
    for it in items:
        nombre_key = _texto_simple(it.get('nombre') or '')[:100]
        if not nombre_key or nombre_key in seen_names:
            continue
        punt = _score_item_busqueda(it, tokens)
        if punt < min_score:
            continue
        seen_names.add(nombre_key)
        scored.append((punt, it))
    scored.sort(key=lambda x: (-x[0], (x[1].get('nombre') or '').lower()))
    return [it for _, it in scored[:limite]]


def _linea_carrito_desde_item(it: dict[str, Any]) -> dict[str, Any]:
    """Payload mínimo para carrito vitrina (localStorage + WhatsApp)."""
    return {
        'producto_id': int(it.get('producto_id') or 0),
        'nombre': (it.get('nombre') or 'Producto')[:100],
        'referencia': (it.get('referencia') or '')[:80],
        'precio': int(it.get('precio') or 0),
        'precio_fmt': (it.get('precio_fmt') or _fmt_clp(it.get('precio') or 0)),
        'imagen_url': it.get('imagen_url'),
        'disponible': bool(it.get('disponible')),
        'stock_tienda': int(it.get('stock_tienda') or 0),
    }


def _contexto_combo_liz(
    items: list[dict[str, Any]],
    slug: str,
    *,
    limite_combo: int = 2,
) -> dict[str, Any]:
    """Relaciones producto_relacion (Chilemat / histórico) para venta cruzada Liz."""
    vacio: dict[str, Any] = {
        'activo': False,
        'ancla': None,
        'relacionados': [],
        'cards_combo': [],
        'lineas_carrito': [],
        'resumen_ollama': '',
    }
    if not items:
        return vacio
    ancla = items[0]
    pid = int(ancla.get('producto_id') or 0)
    if not pid:
        return vacio
    sugeridos = sugeridos_para_detalle(pid, limite=limite_combo)
    if not sugeridos:
        return vacio
    relacionados: list[dict[str, Any]] = []
    for s in sugeridos:
        relacionados.append(
            {
                'producto_id': int(s['producto_id']),
                'nombre': (s.get('nombre') or '')[:100],
                'referencia': '',
                'precio': int(s.get('precio') or 0),
                'precio_fmt': s.get('precio_fmt') or _fmt_clp(s.get('precio') or 0),
                'imagen_url': s.get('imagen_url'),
                'disponible': bool(s.get('disponible')),
                'stock_tienda': int(s.get('stock_tienda') or 0),
            }
        )
    partes = []
    for s in relacionados:
        p = f"{s['nombre']} ({s['precio_fmt']})"
        if not s.get('disponible'):
            p += ' — consultar stock en tienda'
        partes.append(p)
    lineas = [_linea_carrito_desde_item(ancla)]
    vistos = {int(ancla.get('producto_id') or 0)}
    for s in relacionados:
        sid = int(s.get('producto_id') or 0)
        if sid and sid not in vistos:
            lineas.append(_linea_carrito_desde_item(s))
            vistos.add(sid)
    return {
        'activo': True,
        'ancla': ancla,
        'relacionados': relacionados,
        'cards_combo': _cards_desde_items(relacionados, slug, limite=limite_combo),
        'lineas_carrito': lineas,
        'resumen_ollama': '; '.join(partes),
    }


def _reply_combo_reglas(combo_ctx: dict[str, Any], consulta: str) -> str:
    """Respuesta combo sin Ollama (misma intención comercial)."""
    ancla = combo_ctx.get('ancla') or {}
    rels = combo_ctx.get('relacionados') or []
    if not ancla or not rels:
        return _reply_destacado_sodimac([ancla] if ancla else [], consulta)
    nombre = (ancla.get('nombre') or 'este producto').strip()
    precio = (ancla.get('precio_fmt') or '').strip()
    msg = f'¡Hola! Sí, tenemos {nombre}'
    if precio:
        msg += f' disponible en tienda a {precio}'
    msg += '. '
    if len(rels) == 1:
        r0 = rels[0]
        msg += (
            f'Por experiencia, te sugiero llevar también {r0.get("nombre", "un complemento")}'
        )
        if r0.get('precio_fmt'):
            msg += f' ({r0["precio_fmt"]})'
        msg += '.'
    else:
        otros = ', '.join(
            f'{r.get("nombre", "producto")} ({r.get("precio_fmt", "")})'.strip()
            for r in rels[:2]
        )
        msg += f'Por experiencia, si estás en el mismo proyecto, te conviene llevar también {otros}.'
    msg += ' ¿Te gustaría que agregue ambos al carrito de compras?'
    return msg


def _reply_destacado_sodimac(items: list[dict[str, Any]], consulta: str) -> str:
    """Respuesta conversacional con 1 producto estrella (estilo Pedro/Sodimac)."""
    if not items:
        return f'No encontré {consulta} en el catálogo. Prueba con otra palabra o más detalle.'
    top = items[0]
    nombre = (top.get('nombre') or 'este producto').strip()
    precio = (top.get('precio_fmt') or '').strip()
    n = len(items)
    msg = f'Hola, ¡claro! Con gusto te ayudo con {consulta}. '
    msg += f'Una opción destacada es {nombre}'
    if precio:
        msg += f' a {precio}'
    if top.get('disponible'):
        msg += ', con stock en tienda'
    msg += '. '
    if n > 1:
        msg += f'Te dejé {n} opciones en el catálogo al lado para que compares.'
    else:
        msg += 'La ves en el listado al lado.'
    return msg


def buscar_catalogo_vitrina(q_text: str, *, limite: int = 48) -> tuple[list[dict[str, Any]], int]:
    """
    Búsqueda ágil vitrina: tokens, ranking y pocas queries (header, API y Maylén).
    """
    limite = max(1, min(int(limite or 48), 72))
    raw = (q_text or '').strip()
    if not raw:
        return [], 0

    normalizado, tokens = _normalizar_consulta_asistente(raw)
    consulta = (normalizado or raw)[:80]

    # Referencia / código de barras (match directo)
    if 4 <= len(raw) <= 32 and re.match(r'^[\w\-\./]+$', raw, re.I):
        r_cod = listar_productos(page=1, per_page=limite, q_text=raw, solo_disponibles=False)
        items_cod = r_cod.get('productos') or []
        if items_cod:
            ref_low = raw.lower()
            exact = [
                it
                for it in items_cod
                if ref_low in (it.get('referencia') or '').lower()
                or ref_low in (it.get('nombre') or '').lower()
            ]
            if exact:
                return exact[:limite], len(exact)
            if len(items_cod) <= 12:
                return items_cod[:limite], len(items_cod)

    if tokens:
        cat_id = _resolver_cat_vtex_por_intento(tokens)
        if cat_id and len(tokens) == 1:
            r_cat = listar_productos(
                page=1, per_page=limite, q_text='', cat_vtex_id=cat_id, solo_disponibles=False
            )
            items_cat = _rankear_y_filtrar_items(r_cat.get('productos') or [], tokens, limite=limite)
            if items_cat:
                return items_cat, len(items_cat)

        r_tok = listar_productos(
            page=1,
            per_page=min(limite * 2, 72),
            q_text=consulta if len(tokens) < 2 else '',
            q_tokens=tokens,
            solo_disponibles=False,
        )
        items = _rankear_y_filtrar_items(
            r_tok.get('productos') or [],
            tokens,
            min_score=6 if len(tokens) >= 2 else 4,
            limite=limite,
        )
        if items:
            return items, len(items)

    r = listar_productos(page=1, per_page=limite, q_text=consulta, solo_disponibles=False)
    items = r.get('productos') or []
    if tokens:
        items = _rankear_y_filtrar_items(items, tokens, min_score=4, limite=limite)
    return items, len(items)


def _buscar_items_asistente(txt: str) -> tuple[list[dict[str, Any]], int]:
    """Busca productos para Maylén (misma lógica que buscador header)."""
    return buscar_catalogo_vitrina(txt, limite=24)


def _query_base():
    from app import ChilematVtexProducto, Producto, db

    return (
        db.session.query(ChilematVtexProducto, Producto)
        .join(Producto, ChilematVtexProducto.producto_id == Producto.id)
        .filter(
            Producto.activo.is_(True),
            ChilematVtexProducto.producto_id.isnot(None),
        )
    )


def _filtrar_cat_vtex(q, cat_vtex_id: int | None):
    from app import ChilematCategoria, ChilematVtexProducto

    if not cat_vtex_id:
        return q
    cat = ChilematCategoria.query.filter_by(vtex_id=int(cat_vtex_id)).first()
    if not cat or not (cat.nombre or '').strip():
        return q
    seg = cat.nombre.strip()
    return q.filter(
        or_(
            ChilematVtexProducto.categoria_path.ilike(f'%/{seg}/%'),
            ChilematVtexProducto.categoria_path.ilike(f'%{seg}%'),
        )
    )


def _aplicar_filtros(
    q,
    *,
    q_text: str,
    q_tokens: list[str] | None = None,
    marca: str,
    categoria: str,
    cat_vtex_id: int | None,
    precio_min: int | None,
    precio_max: int | None,
):
    from app import ChilematVtexProducto, Producto

    q = _filtrar_cat_vtex(q, cat_vtex_id)

    tokens = [t.strip() for t in (q_tokens or []) if t and len(t.strip()) >= 2]
    if not tokens and q_text:
        _, tokens_from_q = _normalizar_consulta_asistente(q_text)
        if len(tokens_from_q) >= 2:
            tokens = tokens_from_q

    if tokens:
        for tok in tokens[:5]:
            like = f'%{tok}%'
            q = q.filter(
                or_(
                    ChilematVtexProducto.nombre.ilike(like),
                    ChilematVtexProducto.product_reference.ilike(like),
                    ChilematVtexProducto.brand.ilike(like),
                    Producto.nombre.ilike(like),
                    Producto.codigo_barra.ilike(like),
                )
            )
    elif q_text:
        like = f'%{q_text}%'
        q = q.filter(
            or_(
                ChilematVtexProducto.nombre.ilike(like),
                ChilematVtexProducto.product_reference.ilike(like),
                ChilematVtexProducto.brand.ilike(like),
                Producto.nombre.ilike(like),
                Producto.codigo_barra.ilike(like),
            )
        )
    if marca:
        q = q.filter(ChilematVtexProducto.brand == marca)
    if categoria:
        q = q.filter(
            or_(
                ChilematVtexProducto.categoria_path.ilike(f'%/{categoria}/%'),
                ChilematVtexProducto.categoria_path.ilike(f'%{categoria}%'),
                Producto.categoria == categoria,
            )
        )
    if precio_min is not None and precio_min > 0:
        q = q.filter(
            func.coalesce(ChilematVtexProducto.precio_lista, Producto.precio_venta) >= float(precio_min)
        )
    if precio_max is not None and precio_max > 0:
        q = q.filter(
            func.coalesce(ChilematVtexProducto.precio_lista, Producto.precio_venta) <= float(precio_max)
        )
    return q


def _ordenar(q, orden: str):
    from app import ChilematVtexProducto, Producto

    precio_col = func.coalesce(ChilematVtexProducto.precio_lista, Producto.precio_venta)
    orden = (orden or 'recomendados').strip().lower()
    if orden == 'precio_asc':
        return q.order_by(precio_col.asc(), ChilematVtexProducto.nombre.asc())
    if orden == 'precio_desc':
        return q.order_by(precio_col.desc(), ChilematVtexProducto.nombre.asc())
    if orden == 'nombre':
        return q.order_by(ChilematVtexProducto.nombre.asc())
    # recomendados: con stock primero (aprox vía stock total producto), luego nombre
    return q.order_by(Producto.stock.desc(), ChilematVtexProducto.nombre.asc())


def row_a_item(chm, prod, stock_tienda: int) -> dict[str, Any]:
    precio = _precio_mostrar(chm, prod)
    nombre = (chm.nombre or prod.nombre or 'Producto').strip()
    return {
        'producto_id': int(prod.id),
        'vtex_id': chm.vtex_product_id,
        'nombre': nombre[:120],
        'marca': (chm.brand or '').strip()[:80],
        'referencia': (chm.product_reference or prod.codigo_barra or '').strip()[:80],
        'precio': int(round(precio)),
        'precio_fmt': _fmt_clp(precio),
        'precio_fuente': 'chilemat' if (chm.precio_lista or 0) > 0 else 'erp',
        'imagen_url': (chm.imagen_url or '').strip()[:500] or None,
        'categoria': _categoria_label(chm.categoria_path) or (prod.categoria or ''),
        'categoria_path': (chm.categoria_path or '')[:200],
        'stock_tienda': int(stock_tienda),
        'disponible': int(stock_tienda) > 0,
        'link_chilemat': (chm.link or '').strip()[:500] or None,
    }


_ICONO_RAIZ = {
    'construccion': 'fa-hard-hat',
    'construcción': 'fa-hard-hat',
    'herramientas': 'fa-screwdriver-wrench',
    'bano': 'fa-bath',
    'baño': 'fa-bath',
    'cocina': 'fa-kitchen-set',
    'electricidad': 'fa-bolt',
    'iluminacion': 'fa-lightbulb',
    'jardin': 'fa-seedling',
    'hogar': 'fa-house',
    'maquinarias': 'fa-tractor',
    'climatizacion': 'fa-fan',
    'pinturas': 'fa-paint-roller',
    'ferreteria': 'fa-toolbox',
}


def _icono_categoria(nombre: str) -> str:
    n = (nombre or '').lower()
    for key, icon in _ICONO_RAIZ.items():
        if key in n:
            return icon
    return 'fa-box'


def construir_menu_mega(*, slug: str, cat_activa: int | None = None) -> dict[str, Any]:
    """Menú tipo marketplace: raíces Chilemat + columnas hijas (estilo Sodimac, datos propios)."""
    from app import ChilematCategoria

    raices = (
        ChilematCategoria.query.filter(ChilematCategoria.depth == 0)
        .order_by(ChilematCategoria.nombre.asc())
        .all()
    )
    if not raices:
        return {'raices': [], 'paneles': [], 'cat_activa': None}

    if cat_activa is None:
        cat_activa = raices[0].vtex_id
    else:
        cat_activa = int(cat_activa)
        # si es subcategoría, subir a raíz
        row = ChilematCategoria.query.filter_by(vtex_id=cat_activa).first()
        while row and row.parent_vtex_id is not None:
            parent = ChilematCategoria.query.filter_by(vtex_id=row.parent_vtex_id).first()
            if not parent:
                break
            if parent.depth == 0:
                cat_activa = parent.vtex_id
                break
            row = parent

    raices_out = []
    paneles = []

    for raiz in raices:
        rid = int(raiz.vtex_id)
        raices_out.append(
            {
                'vtex_id': rid,
                'nombre': raiz.nombre,
                'icono': _icono_categoria(raiz.nombre),
                'url': url_tienda(slug, cat=rid, menu=0),
                'activa': rid == cat_activa,
            }
        )

        hijos1 = (
            ChilematCategoria.query.filter_by(parent_vtex_id=rid)
            .order_by(ChilematCategoria.nombre.asc())
            .all()
        )
        destacados = []
        columnas = []
        for h1 in hijos1[:10]:
            destacados.append(
                {
                    'nombre': h1.nombre,
                    'url': url_tienda(slug, cat=h1.vtex_id, menu=0),
                }
            )
            links = []
            nietos = (
                ChilematCategoria.query.filter_by(parent_vtex_id=h1.vtex_id)
                .order_by(ChilematCategoria.nombre.asc())
                .limit(12)
                .all()
            )
            for h2 in nietos:
                links.append(
                    {
                        'nombre': h2.nombre,
                        'url': url_tienda(slug, cat=h2.vtex_id, menu=0),
                    }
                )
            columnas.append(
                {
                    'titulo': h1.nombre,
                    'url_ver_todo': url_tienda(slug, cat=h1.vtex_id, menu=0),
                    'links': links,
                }
            )

        paneles.append(
            {
                'vtex_id': rid,
                'nombre': raiz.nombre,
                'url_raiz': url_tienda(slug, cat=rid, menu=0),
                'destacados': destacados[:8],
                'columnas': columnas[:8],
                'visible': rid == cat_activa,
            }
        )

    return {
        'raices': raices_out,
        'paneles': paneles,
        'cat_activa': cat_activa,
    }


def listar_productos(
    *,
    page: int = 1,
    per_page: int = 24,
    q_text: str = '',
    q_tokens: list[str] | None = None,
    marca: str = '',
    categoria: str = '',
    cat_vtex_id: int | None = None,
    precio_min: int | None = None,
    precio_max: int | None = None,
    orden: str = 'recomendados',
    solo_disponibles: bool = False,
) -> dict[str, Any]:
    from app import ChilematVtexProducto, Producto

    page = max(1, int(page or 1))
    per_page = min(48, max(12, int(per_page or 24)))

    q = _aplicar_filtros(
        _query_base(),
        q_text=(q_text or '').strip(),
        q_tokens=q_tokens,
        marca=(marca or '').strip(),
        categoria=(categoria or '').strip(),
        cat_vtex_id=cat_vtex_id,
        precio_min=precio_min,
        precio_max=precio_max,
    )
    # solo_disponibles: filtrar por stock TIENDA después de cargar almacenes (no productos.stock maestro)

    q = _ordenar(q, orden)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    pids = [int(prod.id) for _chm, prod in pagination.items]
    from services.stock_service import stock_tienda_por_producto_ids

    stocks = stock_tienda_por_producto_ids(pids) if pids else {}

    productos = []
    for chm, prod in pagination.items:
        st = int(stocks.get(prod.id, prod.stock or 0))
        if solo_disponibles and st <= 0:
            continue
        productos.append(row_a_item(chm, prod, st))

    return {
        'productos': productos,
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': per_page,
        'total': pagination.total,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'prev_num': pagination.prev_num,
        'next_num': pagination.next_num,
    }


def facetas_filtro() -> dict[str, list[str]]:
    from app import ChilematVtexProducto, Producto, db

    marcas = [
        r[0]
        for r in (
            db.session.query(ChilematVtexProducto.brand)
            .join(Producto, ChilematVtexProducto.producto_id == Producto.id)
            .filter(Producto.activo.is_(True), ChilematVtexProducto.brand.isnot(None))
            .distinct()
            .order_by(ChilematVtexProducto.brand.asc())
            .limit(80)
            .all()
        )
        if r[0] and str(r[0]).strip()
    ]
    cats_erp = [
        c[0]
        for c in db.session.query(Producto.categoria)
        .filter(Producto.activo.is_(True), Producto.categoria.isnot(None))
        .distinct()
        .order_by(Producto.categoria.asc())
        .limit(60)
        .all()
        if c[0]
    ]
    return {'marcas': marcas, 'categorias': cats_erp}


def detalle_producto(producto_id: int) -> dict[str, Any] | None:
    from app import ChilematVtexProducto, Producto

    pid = int(producto_id)
    row = (
        _query_base()
        .filter(Producto.id == pid)
        .order_by(ChilematVtexProducto.synced_at.desc())
        .first()
    )
    if not row:
        return None
    chm, prod = row
    from services.stock_service import stock_disponible_venta_tienda

    item = row_a_item(chm, prod, stock_disponible_venta_tienda(prod))
    desc = _texto_descripcion_producto(chm.descripcion_corta or chm.descripcion_web)
    item['descripcion'] = desc
    item['sugeridos'] = sugeridos_para_detalle(pid)
    return item


def sugeridos_para_detalle(producto_id: int, *, limite: int = 4) -> list[dict[str, Any]]:
    from app import Producto

    try:
        from services.producto_relacion_service import sugerencias_para_carrito
        from services.stock_service import stock_tienda_por_producto_ids

        raw = sugerencias_para_carrito([int(producto_id)], limite=limite)
        if not raw:
            return []
        pids = [int(x['id']) for x in raw]
        stocks = stock_tienda_por_producto_ids(pids)
        out = []
        for it in raw:
            p = Producto.query.get(int(it['id']))
            if not p or p.activo is False:
                continue
            precio = float(it.get('precio') or p.precio_venta or 0)
            img = ''
            ref = p.chilemat_vtex_refs[0] if getattr(p, 'chilemat_vtex_refs', None) else None
            if ref:
                img = (ref.imagen_url or '').strip()
                if (ref.precio_lista or 0) > 0:
                    precio = float(ref.precio_lista)
            out.append(
                {
                    'producto_id': p.id,
                    'nombre': (it.get('nombre') or p.nombre or '')[:100],
                    'precio': int(round(precio)),
                    'precio_fmt': _fmt_clp(precio),
                    'imagen_url': img[:500] if img else None,
                    'stock_tienda': int(stocks.get(p.id, 0)),
                    'disponible': int(stocks.get(p.id, 0)) > 0,
                }
            )
        return out[:limite]
    except Exception:
        return []


def _cards_desde_items(items: list[dict[str, Any]], slug: str, *, limite: int = 3) -> list[dict[str, Any]]:
    out = []
    for it in items[: max(1, limite)]:
        pid = int(it.get('producto_id') or 0)
        if not pid:
            continue
        precio = int(it.get('precio') or 0)
        img = (it.get('imagen_url') or '').strip()
        out.append(
            {
                'producto_id': pid,
                'nombre': (it.get('nombre') or 'Producto')[:100],
                'referencia': (it.get('referencia') or '')[:80],
                'precio': precio,
                'precio_fmt': it.get('precio_fmt') or _fmt_clp(precio),
                'imagen_url': img[:500] if img else None,
                'stock_tienda': int(it.get('stock_tienda') or 0),
                'disponible': bool(it.get('disponible')),
                'url': url_tienda_producto(slug, pid),
            }
        )
    return out


def _es_intencion_cierre_carrito(txt: str) -> bool:
    """Cliente quiere cerrar / retiro / vale con lo que ya tiene en carrito."""
    base = _texto_simple(txt)
    if not base:
        return False
    # No confundir consultas de precio («cuánto vale») con cierre de pedido.
    if any(x in base for x in ('cuanto vale', 'cuánto vale', 'precio', 'cuesta', 'sale')):
        if not any(
            x in base
            for x in (
                'generar vale',
                'vale de retiro',
                'vale retiro',
                'confirmar carrito',
                'cerrar pedido',
                'retiro en tienda',
            )
        ):
            return False
    return any(k in base for k in _INTENCION_CIERRE_CARRITO)


def _normalizar_carrito_cliente(lineas: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Sanitiza payload del carrito enviado por el navegador."""
    out: list[dict[str, Any]] = []
    for ln in lineas or []:
        if not isinstance(ln, dict):
            continue
        pid_raw = ln.get('producto_id') or ln.get('id') or 0
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            pid = 0
        if not pid:
            continue
        try:
            qty = max(1, min(int(ln.get('cantidad') or 1), CARRITO_MAX_CANTIDAD))
        except (TypeError, ValueError):
            qty = 1
        try:
            precio = int(ln.get('precio') or 0)
        except (TypeError, ValueError):
            precio = 0
        out.append(
            {
                'producto_id': pid,
                'nombre': (ln.get('nombre') or 'Producto')[:100],
                'referencia': (ln.get('referencia') or '')[:80],
                'precio': precio,
                'precio_fmt': (ln.get('precio_fmt') or _fmt_clp(precio))[:32],
                'imagen_url': (ln.get('imagen_url') or '')[:500] or None,
                'disponible': bool(ln.get('disponible')),
                'stock_tienda': int(ln.get('stock_tienda') or 0),
                'cantidad': qty,
            }
        )
        if len(out) >= 24:
            break
    return out


def _reply_cierre_carrito(totales: dict[str, Any], nombre_tienda: str = TIENDA_TITULO_DEFAULT) -> str:
    n_lineas = int(totales.get('lineas_count') or 0)
    n_unidades = int(totales.get('items_count') or 0)
    sub = (totales.get('subtotal_fmt') or '').strip()
    tienda = (nombre_tienda or TIENDA_TITULO_DEFAULT).strip()
    if n_lineas <= 0:
        return 'Tu carrito está vacío. Dime qué producto buscas y te ayudo a armarlo.'
    msg = f'¡Listo! Tu carrito tiene {n_lineas} producto'
    if n_lineas != 1:
        msg += 's'
    if n_unidades > n_lineas:
        msg += f' ({n_unidades} unidades en total)'
    msg += f' en {tienda}.'
    if sub:
        msg += f' Subtotal de referencia: {sub}.'
    msg += ' Pincha el botón verde de abajo para generar tu vale PED-WEB en tienda.'
    return msg


def pedido_web_habilitado() -> bool:
    v = (os.getenv('VITRINA_PEDIDO_WEB_HABILITADO') or '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')


def codigo_pedido_web(venta_id: int) -> str:
    return f'PED-WEB-{int(venta_id):06d}'


def crear_vale_pedido_web(
    carrito_lineas: list[dict[str, Any]] | None,
    *,
    cliente_nombre: str = '',
    cliente_telefono: str = '',
    nombre_tienda: str = TIENDA_TITULO_DEFAULT,
    punto_retiro: str = 'Tienda',
) -> dict[str, Any]:
    """
    Crea venta ERP estado Pendiente desde carrito vitrina (retiro en tienda).
    Folio operativo: PED-WEB-###### (id venta). En caja aparece como VL######.
    """
    if not pedido_web_habilitado():
        return {'ok': False, 'error': 'pedido_web_disabled'}

    lineas = _normalizar_carrito_cliente(carrito_lineas)
    if not lineas:
        return {'ok': False, 'error': 'carrito_vacio', 'mensaje': 'No hay productos válidos en el carrito.'}

    from services.ecommerce_pedidos_service import (
        requiere_caja_abierta_pedido_web,
        resolver_cliente_pedido_web,
        validar_stock_lineas_carrito,
    )

    bloquear_sin_stock = (os.getenv('ECOM_PEDIDO_BLOQUEAR_SIN_STOCK') or '1').strip().lower() not in (
        '0',
        'false',
        'no',
    )
    chk = validar_stock_lineas_carrito(lineas, bloquear=bloquear_sin_stock)
    if not chk.get('ok'):
        return {
            'ok': False,
            'error': chk.get('error') or 'sin_stock',
            'mensaje': chk.get('mensaje') or 'Stock insuficiente en tienda.',
            'faltas': chk.get('faltas') or [],
        }

    from datetime import datetime

    from app import DetalleVenta, Producto, Venta, db

    try:
        from app import obtener_caja_activa
    except ImportError:
        return {'ok': False, 'error': 'erp_no_disponible'}

    caja = None
    try:
        caja = obtener_caja_activa()
    except Exception:
        caja = None
    if requiere_caja_abierta_pedido_web() and not caja:
        return {
            'ok': False,
            'error': 'sin_caja',
            'mensaje': 'No hay caja abierta. Abra caja antes de generar pedidos web.',
        }

    cliente = resolver_cliente_pedido_web(cliente_nombre, cliente_telefono)
    if not cliente:
        return {'ok': False, 'error': 'sin_cliente'}

    notas_contacto = []
    cn = (cliente_nombre or '').strip()[:80]
    ct = (cliente_telefono or '').strip()[:30]
    if cn:
        notas_contacto.append(f'Nombre: {cn}')
    if ct:
        notas_contacto.append(f'Tel: {ct}')
    usuario_vale = ASISTENTE_USUARIO_WEB
    if notas_contacto:
        usuario_vale = f"{ASISTENTE_USUARIO_WEB} ({'; '.join(notas_contacto)})"[:50]

    retiro = (punto_retiro or 'Tienda').strip()[:40] or 'Tienda'
    if retiro not in ('Tienda', 'Bodega', 'Despacho', 'Mixto'):
        retiro = 'Tienda'

    venta = Venta(
        fecha=datetime.now(),
        monto_total=0,
        usuario=usuario_vale,
        estado='Pendiente',
        caja_id=int(caja.id) if caja else None,
        cliente_id=int(cliente.id),
        punto_retiro=retiro,
        metodo_pago=None,
        tipo_documento='Boleta',
    )
    db.session.add(venta)
    db.session.flush()

    detalles_ok = 0
    for ln in lineas:
        prod = Producto.query.filter(
            Producto.id == int(ln['producto_id']),
            Producto.activo.isnot(False),
        ).first()
        if not prod:
            continue
        precio = int(round(float(prod.precio_venta or ln.get('precio') or 0)))
        qty = int(ln.get('cantidad') or 1)
        db.session.add(
            DetalleVenta(
                id_venta=int(venta.id),
                id_producto=int(prod.id),
                cantidad=qty,
                precio_unitario=precio,
                subtotal=qty * precio,
                punto_retiro_linea=retiro,
            )
        )
        detalles_ok += 1

    if detalles_ok <= 0:
        db.session.rollback()
        return {
            'ok': False,
            'error': 'sin_productos_validos',
            'mensaje': 'Los productos del carrito no están activos en el ERP.',
        }

    venta.recalcular_total()
    venta.bodega_preparacion_estado = 'PENDIENTE'
    try:
        from app import _asegurar_columnas_ventas_bodega_despacho

        _asegurar_columnas_ventas_bodega_despacho()
    except Exception:
        pass
    db.session.commit()

    codigo = codigo_pedido_web(int(venta.id))
    vale_folio = f'VL{int(venta.id):06d}'
    tot = calcular_totales_carrito(lineas)
    tienda = (nombre_tienda or TIENDA_TITULO_DEFAULT).strip()

    return {
        'ok': True,
        'venta_id': int(venta.id),
        'ped_web_codigo': codigo,
        'vale_folio': vale_folio,
        'monto_total': int(round(float(venta.monto_total or 0))),
        'monto_total_fmt': _fmt_clp(venta.monto_total),
        'items_count': tot.get('items_count'),
        'lineas_count': detalles_ok,
        'mensaje': (
            f'Vale {codigo} creado en {tienda}. Presenta este código en caja para retiro; '
            f'folio interno {vale_folio}.'
        ),
        'instrucciones': (
            'Acércate a caja de Ferretería Santo Domingo con este código. '
            'El precio final se confirma al cobrar.'
        ),
    }


def _construir_ui_respuesta(
    *,
    reply: str,
    cards: list[dict[str, Any]] | None = None,
    catalogo_url: str | None = None,
    consulta: str | None = None,
    modo_combo: bool = False,
    combo_lineas: list[dict[str, Any]] | None = None,
    carrito_totales: dict[str, Any] | None = None,
    cierre_carrito: bool = False,
    vale_pedido: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Bloques UI para el chat (JSON). El front dibuja tarjetas y botones;
    Ollama solo redacta texto — no inventa productos ni precios.
    """
    blocks: list[dict[str, Any]] = []
    texto = (reply or '').strip()
    if texto:
        blocks.append({'type': 'text', 'text': texto})

    card_list = list(cards or [])
    if card_list:
        blocks.append({'type': 'product_cards', 'cards': card_list})

    if modo_combo and combo_lineas:
        blocks.append(
            {
                'type': 'button',
                'variant': 'combo_cart',
                'label': 'Agregar combo al carrito',
                'lineas': combo_lineas,
            }
        )

    tot = carrito_totales or {}
    if int(tot.get('lineas_count') or 0) > 0 and cierre_carrito:
        blocks.append(
            {
                'type': 'cart_summary',
                'items_count': int(tot.get('items_count') or 0),
                'lineas_count': int(tot.get('lineas_count') or 0),
                'subtotal_fmt': tot.get('subtotal_fmt') or '',
                'cta_label': 'Ir a pagar',
                'cta_action': 'open_checkout',
            }
        )

    vp = vale_pedido or {}
    if vp.get('ok') and vp.get('ped_web_codigo'):
        blocks.append(
            {
                'type': 'vale_emitido',
                'ped_web_codigo': vp.get('ped_web_codigo'),
                'vale_folio': vp.get('vale_folio'),
                'monto_total_fmt': vp.get('monto_total_fmt') or '',
                'instrucciones': vp.get('instrucciones') or '',
            }
        )

    if catalogo_url and not consulta:
        blocks.append(
            {
                'type': 'link',
                'label': 'Ver todos en el catálogo',
                'url': catalogo_url,
            }
        )

    return {
        'version': 1,
        'blocks': blocks,
        'actualizar_grilla': bool(consulta),
    }


def ollama_vitrina_disponible() -> bool:
    """Ollama listo para redactar respuestas de Liz en vitrina."""
    try:
        from services.ollama_client import ollama_disponible_vitrina

        return bool(ollama_disponible_vitrina())
    except Exception:
        return False


def chips_asistente(*, producto_id: int | None = None) -> list[str]:
    if producto_id:
        return [
            '¿Hay stock?',
            '¿Cuánto vale?',
            '¿Qué complementos llevo?',
            'Ver productos relacionados',
        ]
    return [
        'Gotera en techo de zinc',
        'Pintura para baño húmedo',
        'Cable y enchufe para ampliación',
        '¿Qué llevo para tabique?',
        'Precio impermeabilizante',
        'Ir a pagar',
    ]


def _respuesta_ollama(
    *,
    mensaje: str,
    respuesta_base: str,
    cards: list[dict[str, Any]],
    nombre_tienda: str = TIENDA_TITULO_DEFAULT,
    combo_context: dict[str, Any] | None = None,
) -> str | None:
    """Refina respuesta de Liz con Ollama local; retorna None si no aplica."""
    try:
        from services.ollama_client import generar_chat_vitrina, ollama_disponible_vitrina
    except Exception:
        return None

    if not ollama_disponible_vitrina():
        return None

    combo_ctx = combo_context or {}
    modo_combo = bool(combo_ctx.get('activo'))

    resumen_cards = []
    for c in cards[:6]:
        resumen_cards.append(
            f"- {c.get('nombre','Producto')}: {c.get('precio_fmt','')} · "
            f"{'Disponible' if c.get('disponible') else 'Sin stock'}"
        )
    contexto = '\n'.join(resumen_cards) if resumen_cards else '- Sin productos sugeridos'
    system = _maylen_prompt_ollama(nombre_tienda, modo_combo=modo_combo)

    if modo_combo:
        ancla = combo_ctx.get('ancla') or {}
        user = (
            f'Consulta cliente: {mensaje}\n'
            f'Producto principal: {ancla.get("nombre", "Producto")} — {ancla.get("precio_fmt", "")} — '
            f'{"con stock en tienda" if ancla.get("disponible") else "sin stock en tienda ahora"}.\n'
            f'Complementos que otros clientes llevan juntos (datos reales): {combo_ctx.get("resumen_ollama", "")}\n'
            f'Respuesta base sugerida: {respuesta_base}\n'
            f'Catalogo candidato:\n{contexto}\n'
            'Redacta la respuesta final para el chat. Debes ofrecer el combo e invitar a agregar al carrito.'
        )
    else:
        user = (
            f'Consulta cliente: {mensaje}\n'
            f'Respuesta base del sistema: {respuesta_base}\n'
            f'Productos candidatos:\n{contexto}\n'
            'Devuelve solo el texto final para el chat (sin markdown ni listas con guiones).'
        )
    out = generar_chat_vitrina(system=system, user=user)
    if not out.get('ok'):
        return None
    txt = (out.get('texto') or '').strip()
    if not txt:
        return None
    lim = 620 if modo_combo else 480
    return txt[:lim]


def _emit_respuesta(
    *,
    mensaje: str,
    reply: str,
    cards: list[dict[str, Any]],
    nombre_tienda: str = TIENDA_TITULO_DEFAULT,
    catalogo_url: str | None = None,
    consulta: str | None = None,
    items_ranked: list[dict[str, Any]] | None = None,
    slug: str | None = None,
    motor_fijo: str | None = None,
    carrito_totales: dict[str, Any] | None = None,
    cierre_carrito: bool = False,
    vale_pedido: dict[str, Any] | None = None,
) -> dict[str, Any]:
    combo_ctx: dict[str, Any] = {}
    if items_ranked and slug and _modo_combo_habilitado() and motor_fijo != 'maestro':
        combo_ctx = _contexto_combo_liz(items_ranked, slug)
    modo_combo = bool(combo_ctx.get('activo'))

    reply_out = reply
    ollama_txt = None
    motor = motor_fijo or 'reglas'

    if motor_fijo == 'maestro':
        reply_out = reply
    elif modo_combo:
        reply_base = _reply_combo_reglas(combo_ctx, (consulta or mensaje or '')[:80])
        # Modo combo forzado por reglas: no reescribir con Ollama.
        reply_out = reply_base
        motor = 'combo'
    elif not cards and not motor_fijo:
        ollama_txt = _respuesta_ollama(
            mensaje=mensaje,
            respuesta_base=reply,
            cards=cards,
            nombre_tienda=nombre_tienda,
        )
        if ollama_txt:
            reply_out = ollama_txt
            motor = 'ollama'

    out: dict[str, Any] = {
        'reply': reply_out,
        'cards': cards,
        'motor': motor,
    }
    if catalogo_url:
        out['catalogo_url'] = catalogo_url
    if consulta:
        out['consulta'] = consulta
    if modo_combo:
        out['modo_combo'] = True
        out['combo_cards'] = combo_ctx.get('cards_combo') or []
        out['combo_lineas'] = combo_ctx.get('lineas_carrito') or []

    combo_lineas_ui = out.get('combo_lineas') if modo_combo else None
    cards_ui = list(out.get('cards') or [])
    if modo_combo and out.get('combo_cards'):
        seen = {int(c.get('producto_id') or 0) for c in cards_ui}
        for cc in out.get('combo_cards') or []:
            pid = int(cc.get('producto_id') or 0)
            if pid and pid not in seen:
                cards_ui.append(cc)
                seen.add(pid)

    out['ui'] = _construir_ui_respuesta(
        reply=reply_out,
        cards=cards_ui,
        catalogo_url=catalogo_url,
        consulta=consulta,
        modo_combo=modo_combo,
        combo_lineas=combo_lineas_ui,
        carrito_totales=carrito_totales,
        cierre_carrito=cierre_carrito,
        vale_pedido=vale_pedido,
    )
    return out


def respuesta_asistente(
    *,
    slug: str,
    mensaje: str,
    producto_id: int | None = None,
    carrito_lineas: list[dict[str, Any]] | None = None,
    cliente_nombre: str = '',
    cliente_telefono: str = '',
) -> dict[str, Any]:
    """Liz — asistente de ventas vitrina (reglas ERP+Chilemat + Ollama opcional)."""
    txt = (mensaje or '').strip()
    q = txt.lower()
    carrito = _normalizar_carrito_cliente(carrito_lineas)
    totales_carrito = calcular_totales_carrito(carrito) if carrito else None

    def _emit_con_carrito(**kwargs):
        kw = dict(kwargs)
        if 'carrito_totales' not in kw:
            kw['carrito_totales'] = totales_carrito
        return _emit_respuesta(**kw)

    if not txt:
        return _emit_respuesta(
            mensaje=txt,
            reply='Cuéntame qué buscas y te muestro opciones con precio de referencia y stock en tienda.',
            cards=[],
            carrito_totales=totales_carrito,
        )

    if _es_intencion_cierre_carrito(txt):
        n_en_carrito = int((totales_carrito or {}).get('lineas_count') or 0)
        if carrito and n_en_carrito > 0:
            vale_res: dict[str, Any] | None = None
            if pedido_web_habilitado():
                vale_res = crear_vale_pedido_web(
                    carrito,
                    cliente_nombre=cliente_nombre,
                    cliente_telefono=cliente_telefono,
                )
            reply_txt = _reply_cierre_carrito(totales_carrito or {})
            if vale_res and vale_res.get('ok'):
                reply_txt = (
                    f"¡Listo! Generé tu vale {vale_res.get('ped_web_codigo')} "
                    f"({vale_res.get('monto_total_fmt')} referencial). "
                    f"Preséntalo en caja ({vale_res.get('vale_folio')}) para retiro en tienda."
                )
            elif vale_res and not vale_res.get('ok'):
                reply_txt += f" ({vale_res.get('mensaje') or 'No pude crear el vale en ERP.'})"
            return _emit_con_carrito(
                mensaje=txt,
                reply=reply_txt,
                cards=[],
                cierre_carrito=True,
                vale_pedido=vale_res,
            )
        return _emit_con_carrito(
            mensaje=txt,
            reply=(
                'No recibí productos válidos en tu carrito (revisa que hayas pulsado '
                '«Añadir al carrito» en la tarjeta verde). Si ya agregaste ítems, '
                'intenta de nuevo o abre el carrito flotante para confirmar.'
            ),
            cards=[],
        )

    if producto_id:
        det = detalle_producto(int(producto_id))
        if det:
            if any(x in q for x in ('stock', 'dispon', 'hay')):
                estado = 'Sí, hay stock en tienda' if det['disponible'] else 'Ahora no hay stock en tienda'
                return _emit_respuesta(
                    mensaje=txt,
                    reply=f'{estado} para {det["nombre"]}.',
                    cards=_cards_desde_items([det], slug, limite=1),
                )
            if any(x in q for x in ('relacion', 'recomend', 'complement', 'llevar', 'combo', 'carrito')):
                sugs = det.get('sugeridos') or []
                if sugs:
                    rel_items = [
                        {
                            'producto_id': x['producto_id'],
                            'nombre': x['nombre'],
                            'precio_fmt': x['precio_fmt'],
                            'precio': x.get('precio', 0),
                            'stock_tienda': x.get('stock_tienda', 0),
                            'disponible': x.get('disponible', False),
                            'imagen_url': x.get('imagen_url'),
                            'referencia': '',
                        }
                        for x in sugs
                    ]
                    items_ctx = [det] + rel_items
                    combo_ctx = _contexto_combo_liz(items_ctx, slug) if _modo_combo_habilitado() else {}
                    if combo_ctx.get('activo'):
                        reply_combo = _reply_combo_reglas(combo_ctx, det.get('nombre') or 'producto')
                        cards = _cards_desde_items(rel_items, slug, limite=3)
                        return _emit_respuesta(
                            mensaje=txt,
                            reply=reply_combo,
                            cards=cards,
                            items_ranked=items_ctx,
                            slug=slug,
                        )
                    cards = _cards_desde_items(rel_items, slug, limite=3)
                    return _emit_respuesta(
                        mensaje=txt,
                        reply='Te sugiero estos complementos para ese producto.',
                        cards=cards,
                    )

    if _es_solo_saludo(txt):
        return _emit_respuesta(
            mensaje=txt,
            reply=(
                f'¡Hola! Soy {ASISTENTE_NOMBRE}, tu agente constructor en línea. '
                'Te ayudo con pinturas, electricidad, materiales y a encontrar productos con precio '
                'de referencia y stock en tienda. Cuéntame tu proyecto o qué necesitas arreglar.'
            ),
            cards=[],
        )

    # Maestro Constructor: problema técnico → términos de catálogo (Ollama + reglas)
    interpret: dict[str, Any] | None = None
    if _maestro_constructor_habilitado() and _es_consulta_por_problema(txt):
        interpret = _interpretar_problema_cliente(txt)
        if interpret.get('ok') and interpret.get('terminos'):
            items_mc, _total_mc = _buscar_items_maestro(interpret['terminos'])
            if items_mc:
                consulta_mc = (interpret['terminos'][0] or '')[:60]
                cat_url_mc = _url_catalogo_busqueda(slug, consulta_mc) or _url_catalogo_busqueda(slug, txt)
                reply_mc = _reply_maestro_constructor(items_mc, interpret, txt)
                cards_mc = _cards_desde_items(items_mc, slug, limite=3)
                return _emit_respuesta(
                    mensaje=txt,
                    reply=reply_mc,
                    cards=cards_mc,
                    catalogo_url=cat_url_mc,
                    consulta=consulta_mc,
                    items_ranked=items_mc,
                    slug=slug,
                    motor_fijo='maestro',
                )

    # búsqueda libre en catálogo (con normalización + fallback por tokens)
    _, tokens = _normalizar_consulta_asistente(txt)
    consulta = ' '.join(tokens) if tokens else txt
    items, total = _buscar_items_asistente(consulta)
    cat_url = _url_catalogo_busqueda(slug, txt)
    if not items:
        if _maestro_constructor_habilitado() and not interpret:
            interpret = _interpretar_problema_cliente(txt)
            if interpret.get('ok') and interpret.get('terminos'):
                items_mc, _total_mc = _buscar_items_maestro(interpret['terminos'])
                if items_mc:
                    consulta_mc = (interpret['terminos'][0] or '')[:60]
                    cat_url_mc = _url_catalogo_busqueda(slug, consulta_mc) or cat_url
                    reply_mc = _reply_maestro_constructor(items_mc, interpret, txt)
                    cards_mc = _cards_desde_items(items_mc, slug, limite=3)
                    return _emit_respuesta(
                        mensaje=txt,
                        reply=reply_mc,
                        cards=cards_mc,
                        catalogo_url=cat_url_mc,
                        consulta=consulta_mc,
                        items_ranked=items_mc,
                        slug=slug,
                        motor_fijo='maestro',
                    )
        sugeridos_ambiguos = _fallback_sugerencias_ambiguas(txt, tokens)
        if sugeridos_ambiguos:
            cards_amb = _cards_desde_items(sugeridos_ambiguos, slug, limite=3)
            nombre_base = (tokens[0] if tokens else (consulta.split(' ')[0] if consulta else 'ese producto')).strip()
            return _emit_respuesta(
                mensaje=txt,
                reply=(
                    f'Sí, tenemos alternativas de {nombre_base} en tienda. '
                    'Te dejé opciones recomendadas con precio y stock para que compares. '
                    'Si quieres, te agrego una al carrito.'
                ),
                cards=cards_amb,
                catalogo_url=cat_url,
                consulta=None,
            )
        if _es_intencion_recomendacion(txt):
            try:
                destacados = listar_productos(page=1, per_page=6, solo_disponibles=True)
                sugeridos = _rankear_y_filtrar_items(destacados.get('productos') or [], [], limite=3)
            except Exception:
                sugeridos = []
            if sugeridos:
                cards_sugeridos = _cards_desde_items(sugeridos, slug, limite=3)
                return _emit_respuesta(
                    mensaje=txt,
                    reply='Claro, te recomiendo estas opciones top con stock en tienda ahora:',
                    cards=cards_sugeridos,
                    catalogo_url=cat_url,
                    consulta=None,
                )
        return _emit_respuesta(
            mensaje=txt,
            reply='No encontré coincidencias exactas. Prueba con otra palabra (ej: cemento, broca, cinta).',
            cards=[],
            catalogo_url=cat_url,
            consulta=consulta,
        )

    if any(x in q for x in ('stock', 'dispon', 'hay')):
        top = _cards_desde_items(items, slug, limite=3)
        return _emit_respuesta(
            mensaje=txt,
            reply='Esto es lo más relevante que encontré con stock en tienda:',
            cards=top,
            catalogo_url=cat_url,
            consulta=consulta,
        )

    if any(x in q for x in ('precio', 'vale', 'cuanto', 'cuánto')):
        top = _cards_desde_items(items, slug, limite=3)
        return _emit_respuesta(
            mensaje=txt,
            reply='Estos son precios de referencia en la tienda para tu búsqueda:',
            cards=top,
            catalogo_url=cat_url,
            consulta=consulta,
        )

    reply = _reply_destacado_sodimac(items, consulta)
    top_cards = _cards_desde_items(items, slug, limite=3)
    return _emit_respuesta(
        mensaje=txt,
        reply=reply,
        cards=top_cards,
        catalogo_url=cat_url,
        consulta=consulta,
        items_ranked=items,
        slug=slug,
        carrito_totales=totales_carrito,
    )


def calcular_totales_carrito(lineas: list[dict[str, Any]]) -> dict[str, Any]:
    """Subtotal referencial y cantidad de unidades en el carrito vitrina."""
    subtotal = 0
    items_count = 0
    for ln in lineas or []:
        try:
            qty = max(1, min(int(ln.get('cantidad') or 1), CARRITO_MAX_CANTIDAD))
        except (TypeError, ValueError):
            qty = 1
        try:
            precio = int(ln.get('precio') or 0)
        except (TypeError, ValueError):
            precio = 0
        subtotal += precio * qty
        items_count += qty
    return {
        'subtotal': subtotal,
        'subtotal_fmt': _fmt_clp(subtotal),
        'items_count': items_count,
        'lineas_count': len(lineas or []),
    }


def mensaje_whatsapp_carrito(
    nombre_tienda: str,
    lineas: list[dict[str, Any]],
    *,
    cliente_nombre: str = '',
    cliente_telefono: str = '',
) -> str:
    """Texto estructurado para pedido web vía WhatsApp (piloto ecom)."""
    tienda = (nombre_tienda or TIENDA_TITULO_DEFAULT).strip()
    partes = [f'Hola, quiero cotizar este pedido desde la web de {tienda}:', '']
    for i, ln in enumerate(lineas or [], start=1):
        nombre = (ln.get('nombre') or 'Producto').strip()[:80]
        try:
            qty = max(1, min(int(ln.get('cantidad') or 1), CARRITO_MAX_CANTIDAD))
        except (TypeError, ValueError):
            qty = 1
        precio_fmt = (ln.get('precio_fmt') or '').strip()
        ref = (ln.get('referencia') or ln.get('producto_id') or '').strip()
        linea = f'{i}) {nombre} x{qty}'
        if precio_fmt:
            linea += f' — {precio_fmt} c/u'
        if ref:
            linea += f' — Ref. {ref}'
        if not ln.get('disponible'):
            linea += ' — (consultar stock en tienda)'
        partes.append(linea)
    tot = calcular_totales_carrito(lineas)
    partes.extend(['', f'Total referencial: {tot["subtotal_fmt"]}'])
    nom = (cliente_nombre or '').strip()
    tel = (cliente_telefono or '').strip()
    if nom:
        partes.append(f'Nombre: {nom[:80]}')
    if tel:
        partes.append(f'Teléfono: {tel[:40]}')
    partes.extend(['', 'Precios y stock se confirman en caja. Gracias.'])
    return '\n'.join(partes)


def whatsapp_pedido_url(*, telefono: str, mensaje: str, max_len: int = 500) -> str | None:
    dig = ''.join(c for c in (telefono or '') if c.isdigit())
    if not dig:
        return None
    from urllib.parse import quote

    lim = max(200, min(int(max_len or 500), 4000))
    msg = re.sub(r'\s+', ' ', (mensaje or '').strip())
    if len(msg) > lim:
        msg = msg[: lim - 3].rstrip() + '...'
    return f'https://wa.me/{dig}?text={quote(msg)}'
