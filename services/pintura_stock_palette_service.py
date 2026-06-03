"""Paleta Fábrica de Color desde stock ERP (fase 1 — sin tintometría)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# familia → (palabras clave en nombre, hex visualizador)
_REGLAS_COLOR: list[tuple[str, tuple[str, ...], str]] = [
    ('blanco', ('blanco', 'ng gl', ' ng '), '#F5F5F5'),
    ('beige', ('beige', 'crema', 'hueso', 'lino', 'arena', 'damasco'), '#EFEBE9'),
    ('amarillo', ('amarillo', 'oro', 'maiz', 'limon'), '#FFEB3B'),
    ('verde', ('verde',), '#4CAF50'),
    ('azul', ('azul', 'celeste', 'piscina'), '#42A5F5'),
    ('gris', ('gris', 'galvanizado', 'zinc'), '#9E9E9E'),
    ('rojo', ('rojo', 'colonial', 'terracota', 'ladrillo', 'coral'), '#E53935'),
    ('neutro', ('negro', ' ng ', 'ng ', 'calorkote ng', 'cafe', 'moro', 'ocre', 'roble', 'pajarito'), '#455A64'),
]

_FAMILIAS_ORDEN = ('blanco', 'beige', 'amarillo', 'verde', 'azul', 'gris', 'rojo', 'neutro')

_EXCLUIR_NOMBRE = (
    'rodillo', 'brocha', 'bandeja', 'thinner', 'diluyente', 'lija', 'cinta',
    'fibra de vidrio', 'masking', 'pinceleta', 'espatula', 'aerosol',
    'acido', 'muriatico', 'cloro', 'hipoclorito', 'desincrust', 'detergente',
    'antihongo', 'antimoho', 'sellador', 'impermeabil', 'barniz marino',
)

_EXCLUIR_CATEGORIA_ACC = ('brocha', 'rodillo', 'accesorio')


def _norm_txt(s: str) -> str:
    t = unicodedata.normalize('NFKD', (s or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return t.lower()


def es_pintura_con_color(prod) -> bool:
    """SKU vendible como color (latex/esmalte/oleo/pintura), no accesorio."""
    nombre = _norm_txt(prod.nombre or '')
    cat = _norm_txt(prod.categoria or '')
    sub = _norm_txt(prod.subcategoria or '')
    if any(x in nombre for x in _EXCLUIR_NOMBRE):
        return False
    if any(x in sub for x in _EXCLUIR_CATEGORIA_ACC):
        return False
    if 'pintur' in cat or 'pintur' in sub or 'piso y pared' in cat:
        pass
    elif not any(x in nombre for x in ('latex', 'látex', 'esmalte', 'oleo', 'óleo', 'pintura', 'anticorrosivo')):
        return False
    return any(
        kw in nombre
        for _fam, kws, _hx in _REGLAS_COLOR
        for kw in kws
    ) or 'blanco' in nombre or 'color' in nombre


def _clasificar_color(nombre: str) -> tuple[str, str, str]:
    n = _norm_txt(nombre)
    for familia, keywords, hexv in _REGLAS_COLOR:
        for kw in keywords:
            if kw in n:
                label = _label_desde_nombre(nombre, familia)
                return familia, label, hexv
    return 'neutro', (nombre or 'Pintura')[:40], '#B0BEC5'


def _label_desde_nombre(nombre: str, familia: str) -> str:
    raw = (nombre or '').strip()
    if len(raw) <= 42:
        return raw
    n = _norm_txt(nombre)
    for _fam, keywords, _hx in _REGLAS_COLOR:
        for kw in keywords:
            if kw in n:
                idx = n.find(kw)
                # tomar ventana alrededor de la palabra color
                parts = re.split(r'\s+', raw)
                for i, p in enumerate(parts):
                    if kw in _norm_txt(p):
                        start = max(0, i - 1)
                        return ' '.join(parts[start : i + 2])[:42]
                return kw.capitalize()
    return raw[:42]


def _fmt_clp(n: float) -> str:
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        v = 0
    return f'${v:,}'.replace(',', '.')


def _serializar_item(prod, stock: int, chm=None) -> dict[str, Any]:
    from services.fabrica_color_service import _serializar_producto_pintura

    base = _serializar_producto_pintura(prod, chm, stock)
    fam, label, hexv = _clasificar_color(prod.nombre or '')
    base.update({
        'id': f'p{prod.id}',
        'familia': fam,
        'nombre': label,
        'nombre_completo': (prod.nombre or '')[:120],
        'hex': hexv,
        'codigo': (prod.codigo_chilemat or prod.codigo_interno or prod.codigo_barra or str(prod.id))[:40],
        'marca': base.get('marca') or _marca_desde_nombre(prod.nombre or ''),
    })
    return base


def _marca_desde_nombre(nombre: str) -> str:
    n = nombre or ''
    for m in ('Ceresita', 'Soquina', 'Sipa', 'Sherwin', 'Kolor', 'Topex', 'Romeral'):
        if m.lower() in n.lower():
            return m
    return ''


def _filtro_uso(nombre: str, uso: str) -> bool:
    n = _norm_txt(nombre)
    if uso == 'exterior':
        return any(x in n for x in ('exterior', 'fachada', 'anticorrosivo', 'galvanizado', 'piscina'))
    if uso == 'interior':
        if any(x in n for x in ('piscina', 'galvanizado', 'anticorrosivo')):
            return False
    return True


def paleta_desde_stock(*, uso: str = 'interior', solo_con_stock: bool = True) -> list[dict[str, Any]]:
    from app import ChilematVtexProducto, Producto
    from services.stock_service import stock_tienda_por_producto_ids

    uso = (uso or 'interior').strip().lower()
    q = (
        Producto.query.filter(Producto.activo.is_(True))
        .filter((Producto.precio_venta > 0) | (Producto.precio_mayoreo > 0))
    )
    rows = q.limit(3000).all()
    candidatos = [p for p in rows if es_pintura_con_color(p) and _filtro_uso(p.nombre or '', uso)]
    pids = [p.id for p in candidatos]
    stocks = stock_tienda_por_producto_ids(pids) if pids else {}

    if solo_con_stock:
        candidatos = [p for p in candidatos if int(stocks.get(p.id, 0) or 0) > 0]

    candidatos.sort(key=lambda p: (-int(stocks.get(p.id, 0) or 0), p.nombre or ''))

    chm_map: dict[int, Any] = {}
    if pids:
        for chm in ChilematVtexProducto.query.filter(ChilematVtexProducto.producto_id.in_(pids)).all():
            if chm.producto_id and int(chm.producto_id) not in chm_map:
                chm_map[int(chm.producto_id)] = chm

    out = []
    for p in candidatos:
        st = int(stocks.get(p.id, 0) or 0)
        out.append(_serializar_item(p, st, chm_map.get(p.id)))
    return out


def familias_desde_stock(*, uso: str = 'interior', solo_con_stock: bool = True) -> list[dict[str, Any]]:
    cols = paleta_desde_stock(uso=uso, solo_con_stock=solo_con_stock)
    out: list[dict[str, Any]] = []
    for fam in _FAMILIAS_ORDEN:
        fam_cols = [c for c in cols if c.get('familia') == fam]
        if fam_cols:
            out.append({'id': fam, 'nombre': fam.capitalize(), 'colores': fam_cols})
    # familia "otros" si quedaron sin clasificar
    usados = {c['id'] for f in out for c in f.get('colores', [])}
    otros = [c for c in cols if c['id'] not in usados]
    if otros:
        out.append({'id': 'otros', 'nombre': 'Otros', 'colores': otros})
    return out


def color_por_id(color_id: str) -> dict[str, Any] | None:
    cid = (color_id or '').strip().lower()
    if cid.startswith('p') and cid[1:].isdigit():
        pid = int(cid[1:])
        from app import Producto
        from services.stock_service import stock_tienda_por_producto_ids

        p = Producto.query.get(pid)
        if not p or not es_pintura_con_color(p):
            return None
        st = stock_tienda_por_producto_ids([pid]).get(pid, 0)
        return _serializar_item(p, int(st or 0))
    return None


def producto_id_desde_color(color_id: str) -> int | None:
    cid = (color_id or '').strip().lower()
    if cid.startswith('p') and cid[1:].isdigit():
        return int(cid[1:])
    c = color_por_id(cid)
    if c and c.get('producto_id'):
        return int(c['producto_id'])
    return None


def resumen_stock() -> dict[str, Any]:
    int_cols = paleta_desde_stock(uso='interior', solo_con_stock=True)
    ext_cols = paleta_desde_stock(uso='exterior', solo_con_stock=True)
    return {
        'modo': 'stock_erp',
        'total_interior': len(int_cols),
        'total_exterior': len(ext_cols),
        'total': len({c['producto_id'] for c in int_cols + ext_cols}),
        'solo_stock_tienda': True,
    }
