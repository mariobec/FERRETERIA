"""Vitrina pública piloto: catálogo Chilemat + stock ERP (Ferretería Santo Domingo)."""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

from sqlalchemy import and_, func, or_

TIENDA_SLUG_SD = 'ferreteria-santo-domingo'
TIENDA_TITULO_DEFAULT = 'Ferretería Santo Domingo'

_TOKENS_RUIDO_ASISTENTE = {
    'busco', 'buscar', 'quiero', 'necesito', 'dame', 'mostrar', 'muestrame', 'muestrame',
    'tienes', 'tenis', 'hay', 'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos',
    'unas', 'por', 'para', 'con', 'favor', 'porfa', 'me', 'cotiza', 'cotizar', 'precio',
    'stock', 'cuanto', 'cuánto',
    'hola', 'buenas', 'buen', 'dia', 'tardes', 'noches', 'ayuda', 'asesor', 'liz', 'tal',
}
_SALUDO_SOLO = {'hola', 'buenas', 'buen', 'dia', 'tardes', 'noches', 'ayuda', 'asesor', 'liz', 'tal', 'que'}
_INTENCION_RECOMENDAR = (
    'recomiend', 'recomendar', 'recomendacion', 'suger', 'sugerencia',
    'alternativa', 'alternativas', 'opcion', 'opciones', 'que me recomiendas',
)

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
    pl = getattr(chm, 'precio_lista', None)
    if pl is not None and float(pl) > 0:
        return float(pl)
    return float(getattr(prod, 'precio_venta', None) or 0)


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


def _liz_prompt_ollama(nombre_tienda: str, *, modo_combo: bool = False) -> str:
    """Instrucciones de tono Liz (vitrina). Ajustar con VITRINA_LIZ_PROMPT_EXTRA en .env."""
    extra = (os.getenv('VITRINA_LIZ_PROMPT_EXTRA') or '').strip()
    base = (
        f"Eres Liz, asistente de ventas de '{nombre_tienda}' (ferreteria en Chile). "
        'Tutea al cliente, tono cercano y profesional. '
        'PROHIBIDO decir Chilemat, ERP, precio referencial Chilemat o precio referencial. '
        'Para precios di: precio de referencia en la tienda en linea; el valor final se confirma en caja. '
        'NO inventes productos, precios ni stock: solo usa la respuesta base y los candidatos.'
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


def _normalizar_consulta_asistente(txt: str) -> tuple[str, list[str]]:
    """
    Convierte frases naturales ('busco pintura impermeabilizante') en términos buscables.
    Retorna (consulta_compacta, tokens_utiles).
    """
    simple = _texto_simple(txt)
    if not simple:
        return '', []
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


def _buscar_items_asistente(txt: str) -> tuple[list[dict[str, Any]], int]:
    """
    Busca productos para Liz:
    1) rubro Chilemat si aplica (pintura → categoría Pinturas),
    2) texto + tokens,
    3) ranking (pintura real vs bandeja/rodillo).
    """
    normalizado, tokens = _normalizar_consulta_asistente(txt)
    consulta = normalizado or (txt or '').strip()

    cat_id = _resolver_cat_vtex_por_intento(tokens) if tokens else None
    if cat_id:
        r_cat = listar_productos(
            page=1, per_page=48, q_text='', cat_vtex_id=cat_id, solo_disponibles=False
        )
        items_cat = _rankear_y_filtrar_items(r_cat.get('productos') or [], tokens, limite=24)
        if items_cat:
            return items_cat, len(items_cat)

    lotes: list[list[dict[str, Any]]] = []
    if consulta:
        r = listar_productos(page=1, per_page=36, q_text=consulta, solo_disponibles=False)
        if r.get('productos'):
            lotes.append(r['productos'])

    if not tokens:
        merged = _merge_items_por_producto(*lotes, limite=24)
        return merged, len(merged)

    for tok in tokens[:3]:
        r = listar_productos(page=1, per_page=24, q_text=tok, solo_disponibles=False)
        if r.get('productos'):
            lotes.append(r['productos'])

    merged = _merge_items_por_producto(*lotes, limite=48)
    ranked = _rankear_y_filtrar_items(merged, tokens, limite=24)
    return ranked, len(ranked)


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
    marca: str,
    categoria: str,
    cat_vtex_id: int | None,
    precio_min: int | None,
    precio_max: int | None,
):
    from app import ChilematVtexProducto, Producto

    q = _filtrar_cat_vtex(q, cat_vtex_id)

    if q_text:
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
        marca=(marca or '').strip(),
        categoria=(categoria or '').strip(),
        cat_vtex_id=cat_vtex_id,
        precio_min=precio_min,
        precio_max=precio_max,
    )
    if solo_disponibles:
        q = q.filter(Producto.stock > 0)

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
    desc = (chm.descripcion_corta or chm.descripcion_web or '').strip()
    if desc and len(desc) > 2000:
        desc = desc[:1999] + '…'
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
        out.append(
            {
                'producto_id': pid,
                'nombre': (it.get('nombre') or 'Producto')[:100],
                'precio_fmt': it.get('precio_fmt') or _fmt_clp(it.get('precio') or 0),
                'stock_tienda': int(it.get('stock_tienda') or 0),
                'disponible': bool(it.get('disponible')),
                'url': url_tienda_producto(slug, pid),
            }
        )
    return out


def ollama_vitrina_disponible() -> bool:
    """Ollama listo para redactar respuestas de Liz en vitrina."""
    try:
        from services.ollama_client import ollama_disponible

        return bool(ollama_disponible())
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
        'Precio pintura impermeabilizante',
        '¿Hay stock cemento?',
        'Broca para hormigón',
        'Cinta masking',
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
        from services.ollama_client import generar_chat, ollama_disponible
    except Exception:
        return None

    if not ollama_disponible():
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
    system = _liz_prompt_ollama(nombre_tienda, modo_combo=modo_combo)

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
    out = generar_chat(system=system, user=user)
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
) -> dict[str, Any]:
    combo_ctx: dict[str, Any] = {}
    if items_ranked and slug and _modo_combo_habilitado():
        combo_ctx = _contexto_combo_liz(items_ranked, slug)
    modo_combo = bool(combo_ctx.get('activo'))

    reply_out = reply
    ollama_txt = None
    motor = 'reglas'

    if modo_combo:
        reply_base = _reply_combo_reglas(combo_ctx, (consulta or mensaje or '')[:80])
        # Modo combo forzado por reglas: no reescribir con Ollama.
        reply_out = reply_base
        motor = 'combo'
    elif not cards:
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
    return out


def respuesta_asistente(
    *,
    slug: str,
    mensaje: str,
    producto_id: int | None = None,
) -> dict[str, Any]:
    """Liz — asistente de ventas vitrina (reglas ERP+Chilemat + Ollama opcional)."""
    txt = (mensaje or '').strip()
    q = txt.lower()
    if not txt:
        return _emit_respuesta(
            mensaje=txt,
            reply='Cuéntame qué buscas y te muestro opciones con precio de referencia y stock en tienda.',
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
                'Hola, soy Liz. Dime qué producto necesitas y te muestro opciones '
                'con precio de referencia y disponibilidad en tienda.'
            ),
            cards=[],
        )

    # búsqueda libre en catálogo (con normalización + fallback por tokens)
    _, tokens = _normalizar_consulta_asistente(txt)
    consulta = ' '.join(tokens) if tokens else txt
    items, total = _buscar_items_asistente(consulta)
    cat_url = _url_catalogo_busqueda(slug, txt)
    if not items:
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
    return _emit_respuesta(
        mensaje=txt,
        reply=reply,
        cards=[],
        catalogo_url=cat_url,
        consulta=consulta,
        items_ranked=items,
        slug=slug,
    )


CARRITO_MAX_CANTIDAD = 99
CARRITO_STORAGE_KEY = 'sd_vitrina_carrito_v1'


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
