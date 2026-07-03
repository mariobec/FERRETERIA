"""Maestro de marcas y tonos/color para pinturas (catálogo + informes)."""
from __future__ import annotations

from typing import Any

_TONOS_INICIALES: tuple[tuple[str, str | None], ...] = (
    ('Blanco', '#F8FAFC'),
    ('Negro', '#1E293B'),
    ('Gris', '#94A3B8'),
    ('Verde Oliva', '#556B2F'),
    ('Azul Naval', '#1E3A5F'),
    ('Rojo Colonial', '#8B2500'),
    ('Amarillo', '#EAB308'),
    ('Arena', '#C2B280'),
)

_HEX_POR_TONO = {n.lower(): h for n, h in _TONOS_INICIALES if h}

# Variantes frecuentes en descripción comercial → nombre canónico del maestro
_ALIASES_TONO_CANONICO: dict[str, str] = {
    'AZUL MARINO': 'Azul Naval',
    'AZUL NAVAL': 'Azul Naval',
    'AZUL': 'Azul Naval',
    'VERDE OLIVA': 'Verde Oliva',
    'VERDE INGLES': 'Verde Oliva',
    'VERDE INGLÉS': 'Verde Oliva',
    'VERDE': 'Verde Oliva',
    'ROJO TEJA': 'Rojo Colonial',
    'ROJO COLONIAL': 'Rojo Colonial',
    'ROJO FERRARI': 'Rojo Colonial',
    'ROJO': 'Rojo Colonial',
    'BEIGE': 'Arena',
    'HUESO': 'Arena',
    'CREMA': 'Arena',
    'ALMENDRA': 'Arena',
    'TERRACOTA': 'Arena',
    'OCRE': 'Amarillo',
    'BLANCO MATE': 'Blanco',
    'BLANCO SATIN': 'Blanco',
    'BLANCO BRILL': 'Blanco',
    'BLANCO': 'Blanco',
    'NEGRO': 'Negro',
    'GRIS': 'Gris',
    'AMARILLO': 'Amarillo',
    'CELESTE': 'Azul Naval',
    'MARRON': 'Rojo Colonial',
    'MARRÓN': 'Rojo Colonial',
    'CAOBA': 'Rojo Colonial',
}


def _norm_nombre(val: str | None) -> str:
    return (val or '').strip()[:80]


def _hex_para_tono(nombre: str) -> str | None:
    return _HEX_POR_TONO.get(_norm_nombre(nombre).lower())


def _resolver_nombre_maestro(texto: str, maestro_nombres: list[str]) -> str:
    """Mapea texto inferido al nombre canónico del maestro (si existe)."""
    raw = _norm_nombre(texto)
    if not raw:
        return ''
    up = raw.upper()
    maestro_up = {m.lower(): m for m in maestro_nombres if m}

    if raw.lower() in maestro_up:
        return maestro_up[raw.lower()]

    for alias, canon in sorted(_ALIASES_TONO_CANONICO.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in up:
            cl = canon.lower()
            if cl in maestro_up:
                return maestro_up[cl]
            return canon

    for nom in sorted(maestro_nombres, key=len, reverse=True):
        nl = nom.lower()
        if nl in raw.lower() or raw.lower() in nl:
            return nom

    return raw.title()


def inferir_tono_desde_descripcion(
    descripcion: str,
    tono_actual: str = '',
    *,
    maestro_nombres: list[str] | None = None,
) -> dict[str, Any]:
    """
    Infiere tono canónico desde nombre/descripción del producto.
    Devuelve tono_sugerido, confianza (0–1) y método.
    """
    from services.stock_valorizado_informe_service import _inferir_tono_color

    if maestro_nombres is None:
        maestro_nombres = [t['nombre'] for t in listar_tonos(solo_activas=False)]

    tono_db = _norm_nombre(tono_actual)
    if tono_db:
        canon = _resolver_nombre_maestro(tono_db, maestro_nombres)
        return {
            'tono_sugerido': canon,
            'confianza': 1.0,
            'metodo': 'campo_producto',
            'hex_color': _hex_para_tono(canon) or '',
        }

    up = (descripcion or '').upper()

    # 1) Nombres compuestos del maestro en la descripción
    for nom in sorted(maestro_nombres, key=len, reverse=True):
        if ' ' in (nom or '') and nom.upper() in up:
            return {
                'tono_sugerido': nom,
                'confianza': 0.96,
                'metodo': 'maestro_en_texto',
                'hex_color': _hex_para_tono(nom) or '',
            }

    # 2) Alias comerciales → canónico
    for alias, canon in sorted(_ALIASES_TONO_CANONICO.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in up:
            resolved = _resolver_nombre_maestro(canon, maestro_nombres)
            return {
                'tono_sugerido': resolved,
                'confianza': 0.93,
                'metodo': 'alias',
                'hex_color': _hex_para_tono(resolved) or '',
            }

    # 3) Palabras simples del maestro (Blanco, Gris, …)
    for nom in sorted(maestro_nombres, key=len, reverse=True):
        if nom and nom.upper() in up:
            return {
                'tono_sugerido': nom,
                'confianza': 0.88,
                'metodo': 'maestro_palabra',
                'hex_color': _hex_para_tono(nom) or '',
            }

    bruto = _inferir_tono_color(descripcion or '', '')
    if not bruto or bruto == 'Sin tono':
        return {'tono_sugerido': '', 'confianza': 0.0, 'metodo': 'sin_match', 'hex_color': ''}

    canon = _resolver_nombre_maestro(bruto, maestro_nombres)
    conf = 0.92 if canon.lower() in {m.lower() for m in maestro_nombres} else 0.72
    if canon != bruto.title():
        conf = min(0.95, conf + 0.05)
    return {
        'tono_sugerido': canon,
        'confianza': round(conf, 2),
        'metodo': 'descripcion',
        'hex_color': _hex_para_tono(canon) or '',
    }


def _es_producto_pintura(categoria: str, subcategoria: str, nombre: str) -> bool:
    from services.pinturas_compras_remates_service import _es_pintura
    return _es_pintura(categoria or '', subcategoria or '', nombre or '')


def previsualizar_asignacion_tonos(
    *,
    solo_sin_tono: bool = True,
    limite: int = 150,
) -> dict[str, Any]:
    """Lista productos pintura con tono sugerido desde la descripción."""
    import app as m

    m._asegurar_tablas_catalogo_pinturas_maestro()
    maestro = [t['nombre'] for t in listar_tonos(solo_activas=False)]

    q = m.Producto.query.filter(m.Producto.activo.isnot(False))
    if solo_sin_tono:
        q = q.filter(
            m.db.or_(
                m.Producto.tono_color.is_(None),
                m.db.func.trim(m.Producto.tono_color) == '',
            )
        )

    propuestas: list[dict[str, Any]] = []
    escaneados = 0
    for p in q.order_by(m.Producto.nombre.asc()).limit(4000).all():
        escaneados += 1
        if not _es_producto_pintura(p.categoria or '', p.subcategoria or '', p.nombre or ''):
            continue
        tono_act = _norm_nombre(getattr(p, 'tono_color', None))
        if not solo_sin_tono and tono_act:
            inf = inferir_tono_desde_descripcion(p.nombre or '', tono_act, maestro_nombres=maestro)
            if inf['tono_sugerido'].lower() == tono_act.lower():
                continue
        else:
            inf = inferir_tono_desde_descripcion(p.nombre or '', '', maestro_nombres=maestro)
        sugerido = inf.get('tono_sugerido') or ''
        if not sugerido:
            continue
        propuestas.append({
            'id': p.id,
            'codigo': (p.codigo_barra or p.codigo_interno or str(p.id))[:32],
            'nombre': (p.nombre or '')[:90],
            'tono_actual': tono_act or '—',
            'tono_sugerido': sugerido,
            'confianza': inf.get('confianza') or 0,
            'metodo': inf.get('metodo') or '',
            'hex_color': inf.get('hex_color') or _hex_para_tono(sugerido) or '',
        })
        if len(propuestas) >= limite:
            break

    return {
        'propuestas': propuestas,
        'total': len(propuestas),
        'escaneados': escaneados,
        'solo_sin_tono': solo_sin_tono,
    }


def aplicar_asignacion_tonos(
    producto_ids: list[int] | None = None,
    *,
    solo_sin_tono: bool = True,
    limite: int = 500,
) -> dict[str, int]:
    """Escribe tono_color en productos y asegura entrada en maestro."""
    import app as m

    preview = previsualizar_asignacion_tonos(solo_sin_tono=solo_sin_tono, limite=limite)
    ids_ok = set(int(x) for x in (producto_ids or []) if x)
    aplicar_todos = not ids_ok
    n = 0
    for prop in preview['propuestas']:
        pid = int(prop['id'])
        if not aplicar_todos and pid not in ids_ok:
            continue
        p = m.Producto.query.get(pid)
        if not p:
            continue
        tono = _norm_nombre(prop.get('tono_sugerido'))
        if not tono:
            continue
        hx = prop.get('hex_color') or _hex_para_tono(tono)
        asegurar_tono(tono, hx)
        p.tono_color = tono
        n += 1
    m.db.session.commit()
    return {'actualizados': n, 'propuestas': len(preview['propuestas'])}


def listar_marcas(*, solo_activas: bool = True) -> list[str]:
    import app as m

    m._asegurar_tablas_catalogo_pinturas_maestro()
    q = m.CatalogoMarca.query
    if solo_activas:
        q = q.filter_by(activo=True)
    rows = q.order_by(m.CatalogoMarca.orden.asc(), m.CatalogoMarca.nombre.asc()).all()
    return [r.nombre for r in rows if (r.nombre or '').strip()]


def listar_tonos(*, solo_activas: bool = True) -> list[dict[str, Any]]:
    import app as m

    m._asegurar_tablas_catalogo_pinturas_maestro()
    q = m.CatalogoTonoColor.query
    if solo_activas:
        q = q.filter_by(activo=True)
    rows = q.order_by(m.CatalogoTonoColor.orden.asc(), m.CatalogoTonoColor.nombre.asc()).all()
    return [
        {'id': r.id, 'nombre': r.nombre, 'hex_color': r.hex_color or ''}
        for r in rows
        if (r.nombre or '').strip()
    ]


def contar_productos_marca(nombre: str) -> int:
    import app as m

    nom = _norm_nombre(nombre)
    if not nom:
        return 0
    return (
        m.Producto.query.filter(
            m.db.func.lower(m.db.func.trim(m.Producto.marca)) == nom.lower(),
            m.Producto.activo.isnot(False),
        ).count()
    )


def contar_productos_tono(nombre: str) -> int:
    import app as m

    nom = _norm_nombre(nombre)
    if not nom:
        return 0
    return (
        m.Producto.query.filter(
            m.db.func.lower(m.db.func.trim(m.Producto.tono_color)) == nom.lower(),
            m.Producto.activo.isnot(False),
        ).count()
    )


def asegurar_marca(nombre: str, *, commit: bool = False) -> str:
    """Crea marca en maestro si no existe. Devuelve nombre canónico."""
    import app as m

    nom = _norm_nombre(nombre)
    if not nom:
        return ''
    m._asegurar_tablas_catalogo_pinturas_maestro()
    existente = m.CatalogoMarca.query.filter(
        m.db.func.lower(m.db.func.trim(m.CatalogoMarca.nombre)) == nom.lower(),
    ).first()
    if existente:
        if not existente.activo:
            existente.activo = True
        return (existente.nombre or nom)[:80]
    max_ord = m.db.session.query(m.db.func.coalesce(m.db.func.max(m.CatalogoMarca.orden), 0)).scalar()
    m.db.session.add(m.CatalogoMarca(nombre=nom, orden=int(max_ord or 0) + 1, activo=True))
    if commit:
        m.db.session.commit()
    else:
        m.db.session.flush()
    return nom


def asegurar_tono(nombre: str, hex_color: str | None = None, *, commit: bool = False) -> str:
    import app as m

    nom = _norm_nombre(nombre)
    if not nom:
        return ''
    m._asegurar_tablas_catalogo_pinturas_maestro()
    existente = m.CatalogoTonoColor.query.filter(
        m.db.func.lower(m.db.func.trim(m.CatalogoTonoColor.nombre)) == nom.lower(),
    ).first()
    hx = (hex_color or '').strip()[:7] or None
    if existente:
        if not existente.activo:
            existente.activo = True
        if hx and not (existente.hex_color or '').strip():
            existente.hex_color = hx
        return (existente.nombre or nom)[:80]
    max_ord = m.db.session.query(m.db.func.coalesce(m.db.func.max(m.CatalogoTonoColor.orden), 0)).scalar()
    m.db.session.add(
        m.CatalogoTonoColor(nombre=nom, hex_color=hx, orden=int(max_ord or 0) + 1, activo=True)
    )
    if commit:
        m.db.session.commit()
    else:
        m.db.session.flush()
    return nom


def sembrar_desde_productos() -> dict[str, int]:
    """Importa marcas/tonos distintos ya usados en productos."""
    import app as m

    m._asegurar_tablas_catalogo_pinturas_maestro()
    n_m = n_t = 0
    marcas = {
        (row[0] or '').strip()
        for row in m.db.session.query(m.Producto.marca)
        .filter(m.Producto.marca.isnot(None), m.Producto.marca != '')
        .distinct()
        .all()
        if (row[0] or '').strip()
    }
    tonos = {
        (row[0] or '').strip()
        for row in m.db.session.query(m.Producto.tono_color)
        .filter(m.Producto.tono_color.isnot(None), m.Producto.tono_color != '')
        .distinct()
        .all()
        if (row[0] or '').strip()
    }
    for marca in sorted(marcas, key=str.lower):
        antes = m.CatalogoMarca.query.filter(
            m.db.func.lower(m.db.func.trim(m.CatalogoMarca.nombre)) == marca.lower(),
        ).first()
        asegurar_marca(marca)
        if not antes:
            n_m += 1
    hex_map = {n.lower(): h for n, h in _TONOS_INICIALES}
    for tono in sorted(tonos, key=str.lower):
        antes = m.CatalogoTonoColor.query.filter(
            m.db.func.lower(m.db.func.trim(m.CatalogoTonoColor.nombre)) == tono.lower(),
        ).first()
        canon = _resolver_nombre_maestro(tono, [t['nombre'] for t in listar_tonos(solo_activas=False)])
        asegurar_tono(canon or tono, hex_map.get((canon or tono).lower()))
        if not antes:
            n_t += 1
    m.db.session.commit()
    return {'marcas_nuevas': n_m, 'tonos_nuevos': n_t}


def sembrar_inicial_si_vacio() -> None:
    import app as m

    if m.CatalogoMarca.query.first() is not None or m.CatalogoTonoColor.query.first() is not None:
        return
    for i, (nombre, hx) in enumerate(_TONOS_INICIALES, start=1):
        m.db.session.add(m.CatalogoTonoColor(nombre=nombre, hex_color=hx, orden=i, activo=True))
    m.db.session.commit()
