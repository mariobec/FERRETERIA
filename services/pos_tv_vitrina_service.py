"""Modo vitrina TV cliente — catálogo + sugerencias Chilemat (sin cámara)."""
from __future__ import annotations

import hashlib
import logging
import random
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

_log = logging.getLogger(__name__)

_MOTIVO_TIPO = {
    'co_comprado': 'Los clientes de la red suelen llevarlo junto',
    'co_visto': 'Combina perfecto en proyectos similares',
    'similar': 'Alternativa de la misma familia',
    'accesorio': 'Accesorio recomendado Chilemat',
    'complemento': 'Complemento ideal para su obra',
}


def _motivo_relacion(tipo: str, fuente: str) -> str:
    t = (tipo or '').strip().lower()
    f = (fuente or '').strip().lower()
    if 'chilemat' in f or f == 'vtex':
        base = _MOTIVO_TIPO.get(t, 'Destacado en catálogo Chilemat')
        return f'{base} · Red Chilemat'
    return _MOTIVO_TIPO.get(t, 'Sugerido en mostrador')


def _normalizar_nombre_key(nombre: str) -> str:
    s = re.sub(r'\s+', ' ', (nombre or '').strip().lower())
    s = re.sub(r'[^\w\s\-./]', '', s, flags=re.UNICODE)
    return s[:96]


def _precio_producto_id(producto_id: int | None) -> int:
    if not producto_id:
        return 0
    try:
        from app import Producto, precio_efectivo_pos_producto

        prod = Producto.query.get(int(producto_id))
        if not prod:
            return 0
        return int(round(float(precio_efectivo_pos_producto(prod) or prod.precio_venta or 0)))
    except Exception:
        return 0


def _enriquecer_precio_item(item: dict[str, Any]) -> dict[str, Any]:
    precio = int(item.get('precio') or 0)
    pid = item.get('id') or item.get('producto_id')
    if precio <= 0 and pid:
        precio = _precio_producto_id(int(pid))
        if precio > 0:
            item = dict(item)
            item['precio'] = precio
    return item


def _dedupe_items_vitrina(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evita repetir el mismo producto o el mismo nombre en un grid TV."""
    out: list[dict[str, Any]] = []
    vistos_id: set[int] = set()
    vistos_nombre: set[str] = set()
    vistos_img: set[str] = set()
    for raw in items or []:
        it = _enriquecer_precio_item(dict(raw))
        pid = it.get('id') or it.get('producto_id')
        try:
            pid_int = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            pid_int = None
        if pid_int is not None and pid_int in vistos_id:
            continue
        nk = _normalizar_nombre_key(it.get('nombre') or '')
        if nk and nk in vistos_nombre:
            continue
        img = (it.get('imagen_url') or '').strip()
        if img and img in vistos_img:
            continue
        if pid_int is not None:
            vistos_id.add(pid_int)
            it['id'] = pid_int
        if nk:
            vistos_nombre.add(nk)
        if img:
            vistos_img.add(img)
        out.append(it)
    return out


def _item_producto(prod, motivo: str = '') -> dict[str, Any] | None:
    if not prod or prod.activo is False:
        return None
    try:
        from app import precio_efectivo_pos_producto

        precio = int(round(float(precio_efectivo_pos_producto(prod) or prod.precio_venta or 0)))
    except Exception:
        precio = int(round(float(getattr(prod, 'precio_venta', 0) or 0)))
    img = (getattr(prod, 'imagen_url', None) or '').strip()
    if not img:
        try:
            from services.chilemat_ficha_service import imagen_url_para_producto_erp

            img = imagen_url_para_producto_erp(prod.id) or ''
        except Exception:
            img = ''
    return {
        'id': int(prod.id),
        'nombre': (prod.nombre or 'Producto')[:100],
        'precio': precio,
        'imagen_url': img[:500] if img else None,
        'motivo': (motivo or '')[:120],
        'categoria': (getattr(prod, 'categoria', None) or '')[:60],
    }


def _asegurar_chilemat() -> None:
    import app as erp

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()


def _relaciones_chilemat_top(limit_filas: int = 160) -> list:
    from app import Producto, ProductoRelacion, db
    from sqlalchemy import or_

    _asegurar_chilemat()
    try:
        return (
            ProductoRelacion.query.filter(
                ProductoRelacion.activo.is_(True),
                or_(
                    ProductoRelacion.fuente.ilike('%chilemat%'),
                    ProductoRelacion.fuente == 'historico_sd',
                    ProductoRelacion.fuente == 'vtex',
                ),
            )
            .order_by(ProductoRelacion.peso.desc(), ProductoRelacion.id.desc())
            .limit(limit_filas)
            .all()
        )
    except Exception as ex:
        _log.debug('relaciones chilemat TV: %s', ex)
        db.session.rollback()
        return []


def _escenas_proyecto_chilemat(max_escenas: int = 8) -> list[dict[str, Any]]:
    from app import Producto, db

    rows = _relaciones_chilemat_top()
    if not rows:
        return []

    por_ancla: dict[int, list] = defaultdict(list)
    for rel in rows:
        por_ancla[int(rel.producto_id)].append(rel)

    escenas: list[dict[str, Any]] = []
    anclas_orden = sorted(
        por_ancla.keys(),
        key=lambda aid: sum(float(r.peso or 0) for r in por_ancla[aid]),
        reverse=True,
    )

    for aid in anclas_orden:
        if len(escenas) >= max_escenas:
            break
        ancla = db.session.get(Producto, aid)
        if not ancla or ancla.activo is False or (ancla.stock or 0) <= 0:
            continue
        hero = _item_producto(ancla, 'Producto ancla · catálogo Chilemat')
        if not hero or not hero.get('imagen_url'):
            continue

        complementos: list[dict[str, Any]] = []
        vistos = {aid}
        for rel in por_ancla[aid]:
            rid = int(rel.relacionado_id)
            if rid in vistos:
                continue
            rel_prod = db.session.get(Producto, rid)
            if not rel_prod or rel_prod.activo is False or (rel_prod.stock or 0) <= 0:
                continue
            motivo = _motivo_relacion(rel.tipo, rel.fuente)
            item = _item_producto(rel_prod, motivo)
            if not item:
                continue
            vistos.add(rid)
            complementos.append(item)
            if len(complementos) >= 3:
                break
        if len(complementos) < 2:
            continue

        cat = (hero.get('categoria') or 'su proyecto').strip()
        titulo = f'Todo para {cat}' if cat and cat.lower() != 'sin categoría' else 'Proyecto completo en mostrador'
        escenas.append(
            {
                'tipo': 'proyecto_chilemat',
                'titulo': titulo[:80],
                'subtitulo': 'Sugerencias capturadas de la red Chilemat',
                'badge': 'Red Chilemat',
                'hero': hero,
                'complementos': complementos,
            }
        )
    return escenas


def _items_desde_catalogo(max_items: int = 24) -> list[dict[str, Any]]:
    try:
        from services.vitrina_tienda_service import listar_productos
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    try:
        for page in (1, 2, 3, 4, 5):
            bloque = listar_productos(
                page=page,
                per_page=32,
                solo_disponibles=True,
                orden='recomendados',
            )
            for p in bloque.get('productos') or []:
                if not (p.get('imagen_url') and p.get('disponible')):
                    continue
                pid = p.get('producto_id')
                items.append(
                    {
                        'id': pid,
                        'nombre': p.get('nombre'),
                        'precio': p.get('precio'),
                        'imagen_url': p.get('imagen_url'),
                        'motivo': (p.get('marca') or 'Disponible en tienda')[:80],
                        'categoria': p.get('categoria'),
                    }
                )
                if len(items) >= max_items * 3:
                    break
            if len(items) >= max_items * 3:
                break
    except Exception as ex:
        _log.debug('items catalogo vitrina TV: %s', ex)
    items = _dedupe_items_vitrina(items)
    items = [it for it in items if int(it.get('precio') or 0) > 0]
    return items[:max_items]


def _escenas_grid_desde_items(
    items: list[dict[str, Any]],
    *,
    max_escenas: int = 6,
    por_escena: int = 8,
    min_items: int = 4,
) -> list[dict[str, Any]]:
    if not items:
        return []
    titulos = (
        'Destacados de hoy',
        'Más vendidos en tienda',
        'Ofertas del mostrador',
        'Selección Chilemat',
        'Stock disponible ahora',
        'Recomendados LhexIA',
    )
    escenas: list[dict[str, Any]] = []
    items = _dedupe_items_vitrina(list(items or []))
    items = [it for it in items if int(it.get('precio') or 0) > 0 and it.get('imagen_url')]
    chunk = max(min_items, por_escena)
    for i in range(0, min(len(items), max_escenas * chunk), chunk):
        grupo = _dedupe_items_vitrina(items[i : i + chunk])
        if len(grupo) < min_items:
            break
        escenas.append(
            {
                'tipo': 'grid_destacados',
                'layout': 'dense',
                'max_items': len(grupo),
                'titulo': titulos[len(escenas) % len(titulos)],
                'subtitulo': 'Stock en tienda · precios de mostrador',
                'badge': 'Catálogo local',
                'items': grupo,
            }
        )
        if len(escenas) >= max_escenas:
            break
    return escenas


def _escenas_destacados_catalogo(max_escenas: int = 6, *, por_escena: int = 8) -> list[dict[str, Any]]:
    con_foto = _items_desde_catalogo(max_escenas * por_escena + 8)
    min_items = min(4, por_escena)
    if len(con_foto) < min_items:
        return []
    return _escenas_grid_desde_items(
        con_foto,
        max_escenas=max_escenas,
        por_escena=por_escena,
        min_items=min_items,
    )


def _escena_marca(empresa_nombre: str, catalogo_url: str | None) -> dict[str, Any]:
    return {
        'tipo': 'marca_local',
        'titulo': (empresa_nombre or 'Ferretería Santo Domingo')[:80],
        'subtitulo': 'Asociado a CHILEMAT — Red de ferreterías',
        'badge': 'LhexIA Experience',
        'catalogo_url': catalogo_url,
        'bullets': [
            'Retiro en tienda y bodega',
            'Despacho a domicilio',
            'Crédito ferretero',
            'Catálogo en línea',
        ],
    }


def _ordenar_escenas(escenas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not escenas:
        return []
    seed_key = datetime.now().strftime('%Y%m%d%H')
    seed = int(hashlib.md5(seed_key.encode('utf-8')).hexdigest()[:8], 16)
    rng = random.Random(seed)
    proyectos = [e for e in escenas if e.get('tipo') == 'proyecto_chilemat']
    otros = [e for e in escenas if e.get('tipo') != 'proyecto_chilemat']
    rng.shuffle(proyectos)
    rng.shuffle(otros)
    out: list[dict[str, Any]] = []
    pi, oi = 0, 0
    while pi < len(proyectos) or oi < len(otros):
        if pi < len(proyectos):
            out.append(proyectos[pi])
            pi += 1
        if oi < len(otros):
            out.append(otros[oi])
            oi += 1
    return out


def _escena_producto_destacado(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'tipo': 'producto_destacado',
        'titulo': (item.get('nombre') or 'Destacado')[:80],
        'subtitulo': (item.get('motivo') or 'Disponible en mostrador')[:120],
        'badge': 'Catálogo local',
        'hero': item,
    }


def _garantizar_minimo_escenas(
    escenas: list[dict[str, Any]],
    *,
    empresa_nombre: str,
    catalogo_url: str | None,
    minimo: int = 6,
) -> list[dict[str, Any]]:
    """Asegura slides suficientes para que el carrusel TV avance siempre."""
    out = list(escenas or [])
    marca: dict[str, Any] | None = None
    if out and out[-1].get('tipo') == 'marca_local':
        marca = out.pop()

    if len(out) >= minimo:
        if marca:
            out.append(marca)
        return out

    items = _items_desde_catalogo(48)
    vistos: set[int | str] = set()
    for e in out:
        hero = e.get('hero') or {}
        if hero.get('id') is not None:
            vistos.add(hero['id'])
        for it in e.get('items') or []:
            if it.get('id') is not None:
                vistos.add(it['id'])

    for it in items:
        if len(out) >= minimo:
            break
        pid = it.get('id')
        if pid is None or pid in vistos or not it.get('imagen_url'):
            continue
        vistos.add(pid)
        out.append(_escena_producto_destacado(it))

    if marca:
        out.append(marca)
    elif not out:
        out = [_escena_marca(empresa_nombre, catalogo_url)]
    return out


_VITRINA_TEST_HERO = '/static/img/vitrina-test/hero-800x600.svg'
_VITRINA_TEST_SPOT = '/static/img/vitrina-test/spot-600x450.svg'
_VITRINA_TEST_MINIS = (
    '/static/img/vitrina-test/mini-a.svg',
    '/static/img/vitrina-test/mini-b.svg',
    '/static/img/vitrina-test/mini-c.svg',
)
_VITRINA_TEST_CARDS = (
    '/static/img/vitrina-test/card-a.svg',
    '/static/img/vitrina-test/card-b.svg',
    '/static/img/vitrina-test/card-c.svg',
    '/static/img/vitrina-test/card-d.svg',
    '/static/img/vitrina-test/card-e.svg',
    '/static/img/vitrina-test/card-f.svg',
)


def _vitrina_test_urls() -> dict[str, Any]:
    """URLs estáticas para SVG de diagnóstico (url_for si hay app context)."""
    names = {
        'hero': 'img/vitrina-test/hero-800x600.svg',
        'spot': 'img/vitrina-test/spot-600x450.svg',
        'minis': [
            'img/vitrina-test/mini-a.svg',
            'img/vitrina-test/mini-b.svg',
            'img/vitrina-test/mini-c.svg',
        ],
        'cards': [
            'img/vitrina-test/card-a.svg',
            'img/vitrina-test/card-b.svg',
            'img/vitrina-test/card-c.svg',
            'img/vitrina-test/card-d.svg',
            'img/vitrina-test/card-e.svg',
            'img/vitrina-test/card-f.svg',
        ],
    }
    try:
        from flask import url_for

        def static_url(rel: str) -> str:
            return url_for('static', filename=rel)

        return {
            'hero': static_url(names['hero']),
            'spot': static_url(names['spot']),
            'minis': [static_url(p) for p in names['minis']],
            'cards': [static_url(p) for p in names['cards']],
        }
    except Exception:
        return {
            'hero': f"/static/{names['hero']}",
            'spot': f"/static/{names['spot']}",
            'minis': [f"/static/{p}" for p in names['minis']],
            'cards': [f"/static/{p}" for p in names['cards']],
        }


def aplicar_imagenes_prueba_vitrina(
    payload: dict[str, Any] | None,
    *,
    urls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reemplaza imagen_url por SVG de prueba con proporciones correctas (diagnóstico TV).
    Mantiene nombres/precios reales; solo cambia la foto.
    """
    if not payload or not payload.get('activo'):
        return payload or {'activo': False, 'escenas': [], 'duracion_seg': 6, 'n_escenas': 0}
    u = urls or _vitrina_test_urls()
    hero_url = u.get('hero') or _VITRINA_TEST_HERO
    spot_url = u.get('spot') or _VITRINA_TEST_SPOT
    mini_urls = u.get('minis') or list(_VITRINA_TEST_MINIS)
    card_urls = u.get('cards') or list(_VITRINA_TEST_CARDS)
    out = dict(payload)
    escenas_out: list[dict[str, Any]] = []
    card_i = 0
    for escena in payload.get('escenas') or []:
        ec = dict(escena)
        tipo = ec.get('tipo') or ''
        if tipo == 'proyecto_chilemat':
            hero = dict(ec.get('hero') or {})
            hero['imagen_url'] = hero_url
            ec['hero'] = hero
            comps: list[dict[str, Any]] = []
            for j, comp in enumerate(ec.get('complementos') or []):
                cc = dict(comp)
                cc['imagen_url'] = mini_urls[j % len(mini_urls)]
                comps.append(cc)
            ec['complementos'] = comps
        elif tipo == 'grid_destacados':
            items: list[dict[str, Any]] = []
            for it in ec.get('items') or []:
                ii = dict(it)
                ii['imagen_url'] = card_urls[card_i % len(card_urls)]
                card_i += 1
                items.append(ii)
            ec['items'] = items
        elif tipo == 'producto_destacado':
            hero = dict(ec.get('hero') or {})
            hero['imagen_url'] = spot_url
            ec['hero'] = hero
        escenas_out.append(ec)
    out['escenas'] = escenas_out
    out['n_escenas'] = len(escenas_out)
    out['fuente'] = 'img_test_diagnostico'
    out['img_test'] = True
    out['badge_test'] = 'Modo prueba imágenes'
    return out


def construir_vitrina_attract(
    *,
    empresa_nombre: str = '',
    catalogo_url: str | None = None,
) -> dict[str, Any]:
    """
    Payload modo vitrina para TV sin venta activa.
    Mezcla proyectos Chilemat (relaciones) + destacados catálogo + slide marca.
    """
    escenas: list[dict[str, Any]] = []
    escenas.extend(_escenas_proyecto_chilemat(max_escenas=10))
    escenas.extend(_escenas_destacados_catalogo(max_escenas=6, por_escena=6))
    escenas.append(_escena_marca(empresa_nombre, catalogo_url))
    escenas = _ordenar_escenas(escenas)

    # Mínimo 2 escenas visibles para que el carrusel avance (p. ej. 2 grids + marca).
    if len([e for e in escenas if e.get('tipo') != 'marca_local']) < 2:
        items = _items_desde_catalogo(24)
        if len(items) >= 4:
            extras = _escenas_grid_desde_items(
                items,
                max_escenas=3,
                por_escena=4,
                min_items=4,
            )
            existentes = {
                (e.get('tipo'), e.get('titulo'))
                for e in escenas
                if e.get('tipo') == 'grid_destacados'
            }
            for ex in extras:
                key = (ex.get('tipo'), ex.get('titulo'))
                if key in existentes:
                    continue
                escenas.insert(0, ex)
                existentes.add(key)
                if len([e for e in escenas if e.get('tipo') != 'marca_local']) >= 2:
                    break
            escenas = _ordenar_escenas(escenas)

    if len(escenas) <= 1:
        items = _items_desde_catalogo(16)
        if len(items) >= 4:
            fallback = _escenas_grid_desde_items(
                items[:8],
                max_escenas=2,
                por_escena=4,
                min_items=4,
            )
            if fallback:
                escenas = fallback + [e for e in escenas if e.get('tipo') != 'grid_destacados']
        elif items:
            escenas.insert(
                0,
                {
                    'tipo': 'grid_destacados',
                    'layout': 'dense',
                    'max_items': len(items),
                    'titulo': 'Bienvenido',
                    'subtitulo': 'Productos disponibles en mostrador',
                    'badge': 'Catálogo',
                    'items': items,
                },
            )

    if not escenas:
        escenas = [_escena_marca(empresa_nombre, catalogo_url)]

    escenas = _garantizar_minimo_escenas(
        escenas,
        empresa_nombre=empresa_nombre,
        catalogo_url=catalogo_url,
        minimo=6,
    )

    return {
        'activo': bool(escenas),
        'duracion_seg': 6,
        'escenas': escenas[:24],
        'n_escenas': len(escenas[:24]),
        'fuente': 'chilemat_catalogo',
    }
