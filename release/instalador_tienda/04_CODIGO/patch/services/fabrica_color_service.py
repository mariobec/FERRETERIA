"""
Fábrica de Color LhexIA — wizard pinturas (módulo cliente Santo Domingo).
Cartilla Kölor/Topex + productos ERP rubro Pinturas + complementos producto_relacion.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any

from services import pintura_cartilla_service as cartilla
from services import pintura_stock_palette_service as stock_palette

RENDIMIENTO_M2_GALON = 35.0
MANOS_DEFAULT = 2
LITROS_POR_GALON = 3.785

_SCENE_BG = {
    'interior': 'img/fabrica-color/scene-living.svg',
    'bano': 'img/fabrica-color/scene-bano.svg',
    'cocina': 'img/fabrica-color/scene-cocina.svg',
    'fachada': 'img/fabrica-color/scene-fachada.svg',
}


def _ambiente_photo(ambiente_id: str) -> str:
    return f'img/fabrica-color/ambientes/{ambiente_id}.jpg'


def _ambiente_mask(ambiente_id: str) -> str:
    return f'img/fabrica-color/masks/{ambiente_id}.png'


AMBIENTES: list[dict[str, Any]] = [
    {
        "id": "comedor",
        "nombre": "Comedor",
        "icono": "fa-utensils",
        "uso": "interior",
        "scene": "interior",
        "scene_bg": _SCENE_BG['interior'],
        "photo": _ambiente_photo('comedor'),
        "mask": _ambiente_mask('comedor'),
        "grid_class": "fc-amb-card--hero",
        "wall_polygons": [
            [[0.0, 0.0], [1.0, 0.0], [1.0, 0.48], [0.0, 0.48]],
        ],
        "wall_exclusions": [
            [0.50, 0.78, 0.42, 0.18],
            [0.15, 0.82, 0.12, 0.10],
        ],
        "tip": "Ideal para espacios de reunión con buena luz natural.",
    },
    {
        "id": "cocina",
        "nombre": "Cocina",
        "icono": "fa-kitchen-set",
        "uso": "interior",
        "scene": "cocina",
        "scene_bg": _SCENE_BG['cocina'],
        "photo": _ambiente_photo('cocina'),
        "mask": _ambiente_mask('cocina'),
        "wall_polygons": [
            [[0.0, 0.0], [1.0, 0.0], [1.0, 0.40], [0.0, 0.40]],
        ],
        "wall_exclusions": [
            [0.70, 0.65, 0.22, 0.30],
            [0.30, 0.72, 0.25, 0.20],
        ],
        "tip": "Satinado facilita limpieza de salpicaduras.",
    },
    {
        "id": "dormitorio",
        "nombre": "Dormitorio",
        "icono": "fa-bed",
        "uso": "interior",
        "scene": "interior",
        "scene_bg": _SCENE_BG['interior'],
        "photo": _ambiente_photo('dormitorio'),
        "mask": _ambiente_mask('dormitorio'),
        "wall_polygons": [
            [[0.0, 0.0], [0.79, 0.0], [0.79, 0.66], [0.46, 0.62], [0.0, 0.52]],
            [[0.74, 0.0], [1.0, 0.0], [1.0, 0.92], [0.74, 0.92]],
            [[0.44, 0.44], [0.66, 0.44], [0.66, 0.70], [0.44, 0.70]],
        ],
        "wall_exclusions": [
            [0.30, 0.78, 0.40, 0.18],
            [0.62, 0.80, 0.16, 0.18],
        ],
        "smart_wall_tint": True,
        "wall_tint": {"lum_min": 58, "sat_max": 255},
        "tip": "Prefiera tonos suaves y acabado mate para descanso.",
    },
    {
        "id": "bano",
        "nombre": "Baño",
        "icono": "fa-bath",
        "uso": "interior",
        "scene": "bano",
        "scene_bg": _SCENE_BG['bano'],
        "photo": _ambiente_photo('bano'),
        "mask": _ambiente_mask('bano'),
        "wall_polygons": [
            # Muro fondo detrás de la tina
            [[0.12, 0.0], [0.66, 0.0], [0.66, 0.47], [0.12, 0.47]],
            # Muro izquierdo (toallero)
            [[0.0, 0.0], [0.13, 0.0], [0.13, 0.40], [0.0, 0.40]],
            # Franja sobre ventana
            [[0.66, 0.0], [0.79, 0.0], [0.79, 0.28], [0.66, 0.28]],
            # Franja sobre espejo (derecha)
            [[0.79, 0.0], [1.0, 0.0], [1.0, 0.24], [0.79, 0.24]],
        ],
        "wall_exclusions": [
            [0.055, 0.27, 0.04, 0.085],
            [0.055, 0.39, 0.04, 0.075],
        ],
        "tip": "Use pintura lavable o satinada por humedad.",
    },
    {
        "id": "living",
        "nombre": "Living",
        "icono": "fa-couch",
        "uso": "interior",
        "scene": "interior",
        "scene_bg": _SCENE_BG['interior'],
        "photo": _ambiente_photo('living'),
        "mask": _ambiente_mask('living'),
        "wall_polygons": [
            [[0.0, 0.0], [1.0, 0.0], [1.0, 0.34], [0.0, 0.34]],
            [[0.0, 0.0], [0.14, 0.0], [0.14, 0.58], [0.0, 0.58]],
            [[0.86, 0.0], [1.0, 0.0], [1.0, 0.50], [0.86, 0.50]],
        ],
        "wall_exclusions": [
            [0.22, 0.14, 0.08, 0.07],
            [0.50, 0.11, 0.10, 0.07],
            [0.42, 0.56, 0.52, 0.36],
            [0.58, 0.74, 0.24, 0.14],
            [0.10, 0.60, 0.14, 0.20],
        ],
        "tip": "Combine color de acento en muro principal.",
    },
    {
        "id": "fachada",
        "nombre": "Fachada",
        "icono": "fa-house-chimney",
        "uso": "exterior",
        "scene": "fachada",
        "scene_bg": _SCENE_BG['fachada'],
        "photo": _ambiente_photo('fachada'),
        "mask": _ambiente_mask('fachada'),
        "wall_polygons": [
            [[0.12, 0.22], [0.88, 0.22], [0.88, 0.76], [0.12, 0.76]],
        ],
        "wall_exclusions": [
            [0.50, 0.52, 0.08, 0.14],
            [0.28, 0.58, 0.06, 0.10],
            [0.72, 0.58, 0.06, 0.10],
        ],
        "tip": "Elija pintura exterior con protección UV.",
    },
]

BRILLOS: list[dict[str, Any]] = [
    {
        "id": "mate",
        "nombre": "Mate",
        "desc": "Sin reflejo · disimula imperfecciones",
        "ideal": "Paredes y cielos · dormitorios y living",
    },
    {
        "id": "satinado",
        "nombre": "Satinado",
        "desc": "Brillo suave · fácil de limpiar",
        "ideal": "Cocina, baño y zonas de paso",
    },
    {
        "id": "semi_brillo",
        "nombre": "Semi brillo",
        "desc": "Mayor luminosidad · resistente",
        "ideal": "Detalles, muebles y madera pintada",
    },
]

CALIDADES: list[dict[str, Any]] = [
    {"id": "economica", "nombre": "Económica", "badge": "Mejor precio"},
    {"id": "standard", "nombre": "Estándar", "badge": "Más elegida"},
    {"id": "premium", "nombre": "Premium", "badge": "Máxima cobertura"},
]

_FAMILIAS_INTERIOR = ('blanco', 'beige', 'amarillo', 'verde', 'azul', 'gris', 'rojo', 'neutro')


def _fuente_colores() -> str:
    """stock_erp = solo productos con stock tienda (fase 1). cartilla = tintometría (fase 2)."""
    return (os.getenv('FABRICA_COLOR_FUENTE', 'stock_erp') or 'stock_erp').strip().lower()


def _modo_stock() -> bool:
    return _fuente_colores() in ('stock', 'stock_erp', 'erp', 'inventario')


def _fmt_clp(n: float) -> str:
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        v = 0
    return f"${v:,}".replace(",", ".")


def _color_por_id(color_id: str) -> dict[str, Any] | None:
    if _modo_stock():
        c = stock_palette.color_por_id(color_id)
        if c:
            return c
    return cartilla.color_por_id(color_id)


def _ambiente_por_id(ambiente_id: str) -> dict[str, Any] | None:
    aid = (ambiente_id or "").strip().lower()
    for a in AMBIENTES:
        if a["id"] == aid:
            return dict(a)
    return None


def _brillo_por_id(brillo_id: str) -> dict[str, Any] | None:
    bid = (brillo_id or "").strip().lower()
    for b in BRILLOS:
        if b["id"] == bid:
            return dict(b)
    return None


def familias_colores(*, uso: str = 'interior') -> list[dict[str, Any]]:
    if _modo_stock():
        return stock_palette.familias_desde_stock(uso=uso, solo_con_stock=True)
    return cartilla.familias_colores(uso=uso)


def _paleta_default_id(uso: str = 'interior') -> str:
    fams = familias_colores(uso=uso)
    if fams and fams[0].get('colores'):
        return fams[0]['colores'][0]['id']
    if _modo_stock():
        return ''
    cols = cartilla.paleta_completa()
    return cols[0]['id'] if cols else ''


def payload_inicial(*, uso: str = 'interior') -> dict[str, Any]:
    fams_int = familias_colores(uso='interior')
    fams_ext = familias_colores(uso='exterior')
    fams = fams_ext if uso == 'exterior' else fams_int
    if _modo_stock():
        cols = stock_palette.paleta_desde_stock(uso=uso, solo_con_stock=True)
        meta = stock_palette.resumen_stock()
    else:
        cols = cartilla.paleta_completa(solo_exterior=True if uso == 'exterior' else False)
        meta = cartilla.meta_cartilla()
    sin_stock = _modo_stock() and len(cols) == 0
    return {
        "modo": "stock_erp" if _modo_stock() else "cartilla",
        "ambientes": AMBIENTES,
        "brillos": BRILLOS,
        "calidades": [] if _modo_stock() else CALIDADES,
        "familias": fams,
        "familias_interior": fams_int,
        "familias_exterior": fams_ext,
        "colores": cols,
        "cartilla": meta,
        "sin_stock": sin_stock,
        "defaults": {
            "manos": MANOS_DEFAULT,
            "rendimiento_m2_galon": RENDIMIENTO_M2_GALON,
            "litros_por_galon": LITROS_POR_GALON,
            "color_id": _paleta_default_id(uso=uso),
        },
        "scene_assets": dict(_SCENE_BG),
    }


def calcular_cantidad(*, m2: float, manos: int | None = None, rendimiento: float | None = None) -> dict[str, Any]:
    try:
        superficie = max(1.0, float(m2 or 0))
    except (TypeError, ValueError):
        superficie = 1.0
    n_manos = max(1, min(int(manos or MANOS_DEFAULT), 4))
    rend = max(10.0, float(rendimiento or RENDIMIENTO_M2_GALON))
    litros = (superficie * n_manos) / rend * LITROS_POR_GALON
    galones = litros / LITROS_POR_GALON
    galones_ceil = max(1, math.ceil(galones * 4) / 4)  # redondeo a 1/4 galón
    return {
        "m2": round(superficie, 1),
        "manos": n_manos,
        "rendimiento_m2_galon": rend,
        "litros_estimados": round(litros, 2),
        "galones_estimados": round(galones, 2),
        "galones_sugeridos": galones_ceil,
        "galones_sugeridos_fmt": f"{galones_ceil:.2f}".replace(".", ","),
    }


def _es_pintura_row(prod) -> bool:
    if stock_palette.es_pintura_con_color(prod):
        return True
    nombre = (prod.nombre or "").lower()
    cat = (prod.categoria or "").lower()
    sub = (prod.subcategoria or "").lower()
    if any(x in nombre for x in ("rodillo", "brocha", "bandeja", "cinta masking", "lija", "thinner", "diluyente", "cinta", "fibra")):
        return False
    if "pintur" in cat or "pintur" in sub or "esmalte" in nombre or "latex" in nombre or "látex" in nombre:
        return True
    if nombre.startswith("pintura ") or " pintura " in nombre:
        return True
    return False


def _producto_pintura_por_id(producto_id: int) -> dict[str, Any] | None:
    from app import ChilematVtexProducto, Producto
    from services.stock_service import stock_tienda_por_producto_ids

    p = Producto.query.get(int(producto_id))
    if not p or not p.activo:
        return None
    st = stock_tienda_por_producto_ids([p.id]).get(p.id, 0)
    chm = ChilematVtexProducto.query.filter_by(producto_id=p.id).first()
    if _modo_stock():
        return stock_palette._serializar_item(p, int(st or 0), chm)
    return _serializar_producto_pintura(p, chm, int(st or 0))


def _serializar_producto_pintura(prod, chm=None, stock: int = 0) -> dict[str, Any]:
    precio = float(prod.precio_venta or prod.precio_mayoreo or 0)
    img = (prod.imagen_url or "").strip()
    ref = (prod.codigo_chilemat or prod.codigo_interno or prod.codigo_barra or "").strip()
    marca = (prod.marca or "").strip() if hasattr(prod, "marca") else ""
    if chm:
        if not img:
            img = (getattr(chm, "imagen_url", None) or "").strip()
        if (getattr(chm, "precio_lista", None) or 0) > 0:
            precio = float(chm.precio_lista)
        ref = (chm.product_reference or ref or "").strip()
        marca = (chm.brand or marca or "").strip()
    return {
        "producto_id": prod.id,
        "nombre": (prod.nombre or "")[:120],
        "precio": int(round(precio)),
        "precio_fmt": _fmt_clp(precio),
        "imagen_url": img[:500] if img else None,
        "referencia": ref[:80],
        "marca": marca[:60],
        "stock_tienda": int(stock or 0),
        "disponible": int(stock or 0) > 0,
    }


def productos_pintura_por_calidad(
    *,
    calidad_id: str,
    uso: str = "interior",
    limite: int = 12,
    marca_preferida: str | None = None,
) -> list[dict[str, Any]]:
    from app import ChilematVtexProducto, Producto
    from services.stock_service import stock_tienda_por_producto_ids

    calidad_id = (calidad_id or "standard").strip().lower()
    uso = (uso or "interior").strip().lower()

    q = (
        Producto.query.filter(Producto.activo.is_(True))
        .filter((Producto.precio_venta > 0) | (Producto.precio_mayoreo > 0))
        .order_by(Producto.precio_venta.asc())
    )
    rows = q.limit(400).all()
    candidatos = [p for p in rows if _es_pintura_row(p)]

    if uso == "exterior":
        ext = [
            p
            for p in candidatos
            if "exterior" in (p.nombre or "").lower() or "fachada" in (p.nombre or "").lower()
        ]
        if ext:
            candidatos = ext

    if len(candidatos) < 3:
        candidatos = rows[:80]

    candidatos.sort(key=lambda p: float(p.precio_venta or p.precio_mayoreo or 0))
    marca_pref = (marca_preferida or '').strip().lower()
    if marca_pref:
        con_marca = [
            p for p in candidatos
            if marca_pref in (getattr(p, 'marca', None) or '').lower()
            or marca_pref in (p.nombre or '').lower()
        ]
        if con_marca:
            candidatos = con_marca + [p for p in candidatos if p not in con_marca]
    n = len(candidatos)
    if n == 0:
        return []

    if calidad_id == "economica":
        slice_rows = candidatos[: max(3, n // 3)]
    elif calidad_id == "premium":
        slice_rows = candidatos[max(0, n - max(3, n // 3)) :]
    else:
        mid = n // 3
        slice_rows = candidatos[mid : mid + max(3, n // 3)] or candidatos

    pids = [p.id for p in slice_rows[:limite]]
    stocks = stock_tienda_por_producto_ids(pids) if pids else {}
    chm_map: dict[int, Any] = {}
    for chm in ChilematVtexProducto.query.filter(ChilematVtexProducto.producto_id.in_(pids)).all():
        if chm.producto_id and int(chm.producto_id) not in chm_map:
            chm_map[int(chm.producto_id)] = chm

    out = []
    for p in slice_rows[:limite]:
        out.append(_serializar_producto_pintura(p, chm_map.get(p.id), stocks.get(p.id, 0)))
    out.sort(key=lambda x: x["precio"])
    return out


def complementos_pintura(producto_id: int | None, *, limite: int = 4) -> list[dict[str, Any]]:
    if not producto_id:
        return []
    try:
        from services.producto_relacion_service import sugerencias_para_carrito
        from services.stock_service import stock_tienda_por_producto_ids
        from app import Producto

        raw = sugerencias_para_carrito([int(producto_id)], limite=limite)
        if not raw:
            return []
        pids = [int(x["id"]) for x in raw]
        stocks = stock_tienda_por_producto_ids(pids)
        out = []
        for it in raw:
            p = Producto.query.get(int(it["id"]))
            if not p:
                continue
            precio = int(round(float(it.get("precio") or p.precio_venta or 0)))
            out.append(
                {
                    "producto_id": p.id,
                    "nombre": (it.get("nombre") or p.nombre or "")[:100],
                    "precio": precio,
                    "precio_fmt": _fmt_clp(precio),
                    "stock_tienda": int(stocks.get(p.id, 0)),
                    "disponible": int(stocks.get(p.id, 0)) > 0,
                }
            )
        return out[:limite]
    except Exception:
        return []


def cotizar_proyecto(
    *,
    ambiente_id: str,
    color_id: str,
    brillo_id: str,
    m2: float,
    calidad_id: str = "standard",
    producto_id: int | None = None,
) -> dict[str, Any]:
    amb = _ambiente_por_id(ambiente_id) or AMBIENTES[0]
    color = _color_por_id(color_id)
    if not color and _modo_stock():
        color = {'nombre': 'Pintura', 'codigo': '', 'marca': '', 'hex': '#B0BEC5'}
    elif not color:
        color = cartilla.paleta_completa()[0]
    brillo = _brillo_por_id(brillo_id) or BRILLOS[0]
    cant = calcular_cantidad(m2=m2)

    pid_color = stock_palette.producto_id_desde_color(color_id) if _modo_stock() else None
    if pid_color:
        producto_id = pid_color
    elegido = None
    if producto_id:
        raw = _producto_pintura_por_id(int(producto_id))
        if raw:
            elegido = {
                'producto_id': raw['producto_id'],
                'nombre': raw.get('nombre_completo') or raw['nombre'],
                'precio': raw['precio'],
                'precio_fmt': raw['precio_fmt'],
                'imagen_url': raw.get('imagen_url'),
                'referencia': raw.get('referencia') or raw.get('codigo'),
                'marca': raw.get('marca'),
                'stock_tienda': raw.get('stock_tienda', 0),
                'disponible': raw.get('disponible', False),
            }

    productos: list[dict[str, Any]] = []
    if not elegido:
        productos = productos_pintura_por_calidad(
            calidad_id=calidad_id,
            uso=amb.get("uso", "interior"),
            marca_preferida=color.get("marca"),
        )
        if producto_id:
            for p in productos:
                if int(p["producto_id"]) == int(producto_id):
                    elegido = p
                    break
        if not elegido and productos:
            con_stock = [p for p in productos if p.get("disponible")]
            elegido = (con_stock or productos)[0]

    comps = complementos_pintura(elegido["producto_id"] if elegido else None)

    titulo = f"Proyecto {amb['nombre']} · {color.get('nombre') or 'Pintura'}"
    codigo_ref = color.get('codigo') or (elegido or {}).get('referencia') or ''
    marca_ref = color.get('marca') or (elegido or {}).get('marca') or ''
    resumen = (
        f"{cant['galones_sugeridos_fmt']} gal (≈{cant['m2']} m² × {cant['manos']} manos) · "
        f"{codigo_ref} {marca_ref} · {brillo['nombre']}"
    )

    liz_prompt = (
        f"Estoy configurando pintura para {amb['nombre']}: "
        f"{color.get('nombre') or 'pintura'} ({codigo_ref}), "
        f"acabado {brillo['nombre']}, {cant['m2']} m². ¿Qué más debería llevar?"
    )

    wa_lineas = [
        f"Hola, cotizo pintura — {titulo}",
        resumen,
    ]
    if elegido:
        wa_lineas.append(f"Base sugerida: {elegido['nombre']} ({elegido['precio_fmt']})")
    wa_lineas.append("Retiro en tienda Santo Domingo.")

    galones_qty = int(cant.get("galones_sugeridos") or 1)
    precio_pintura = int(elegido["precio"]) if elegido else 0
    subtotal_pintura = precio_pintura * galones_qty
    subtotal_comps = sum(int(c.get("precio") or 0) for c in comps)
    total_proyecto = subtotal_pintura + subtotal_comps

    return {
        "ok": True,
        "titulo": titulo,
        "resumen": resumen,
        "ambiente": amb,
        "color": color,
        "brillo": brillo,
        "cantidad": cant,
        "calidad_id": calidad_id,
        "producto": elegido,
        "productos_alternativas": productos[:6],
        "complementos": comps,
        "liz_prompt": liz_prompt,
        "mensaje_whatsapp": "\n".join(wa_lineas),
        "modo": "stock_erp" if _modo_stock() else "cartilla",
        "totales": {
            "galones": galones_qty,
            "subtotal_pintura": subtotal_pintura,
            "subtotal_pintura_fmt": _fmt_clp(subtotal_pintura),
            "subtotal_complementos": subtotal_comps,
            "subtotal_complementos_fmt": _fmt_clp(subtotal_comps),
            "total_proyecto": total_proyecto,
            "total_proyecto_fmt": _fmt_clp(total_proyecto),
        },
        "tinte": {
            "codigo": codigo_ref,
            "nombre": color.get("nombre"),
            "marca": marca_ref,
            "hex": color.get("hex"),
            "modo": "stock_erp" if _modo_stock() else "cartilla",
        },
        "bases_erp": [] if _modo_stock() else cartilla.bases_pintura_erp(marca=color.get("marca"), limite=4),
    }


def _tip_reglas(
    *,
    step: int,
    ambiente_id: str,
    color_id: str,
    brillo_id: str,
    m2: float,
) -> str:
    amb = _ambiente_por_id(ambiente_id) or AMBIENTES[0]
    color = _color_por_id(color_id)
    brillo = _brillo_por_id(brillo_id)
    try:
        superficie = max(1.0, float(m2 or 0))
    except (TypeError, ValueError):
        superficie = 12.0

    if step == 1:
        if amb.get('id') == 'bano':
            return 'En baños recomiendo satinado: aguanta humedad y se limpia con paño húmedo.'
        if amb.get('id') == 'fachada':
            return 'Para fachada elija colores marcados para exterior y pintura con filtro UV.'
        if amb.get('id') == 'dormitorio':
            return 'Tonos suaves y mate ayudan a un ambiente de descanso.'
        return amb.get('tip') or 'Elija el ambiente y vea la vista previa con su color.'

    if step == 2:
        if amb.get('id') == 'bano' and brillo_id == 'mate':
            return 'En baño el mate puede marcar manchas. Satinado es la opción más usada en ferretería.'
        if amb.get('id') == 'cocina' and brillo_id == 'mate':
            return 'Cocina + satinado = menos grasa adherida. Fácil de pasar paño después de cocinar.'
        if color and color.get('exterior') and amb.get('uso') != 'exterior':
            return f'{color.get("codigo")} es tono exterior; para interior elija otro de la cartilla.'
        if brillo:
            return brillo.get('ideal', '') + '. Cambie brillo y mire la vista previa arriba.'
        if _modo_stock():
            return 'Elija un color de los que hay hoy en tienda. Cada muestra es un producto con stock real.'
        return 'Combine color Kölor/Topex con el brillo según el uso del espacio.'

    if step == 3:
        cant = calcular_cantidad(m2=superficie)
        if superficie <= 10:
            return f'~{cant["galones_sugeridos_fmt"]} galones para {superficie} m². Típico de dormitorio pequeño.'
        if superficie >= 25:
            return f'Proyecto grande: {cant["galones_sugeridos_fmt"]} gal estimados. Considere margen para repasos.'
        return f'Con {superficie} m² calculamos {cant["galones_sugeridos_fmt"]} gal a 2 manos. Ajuste si incluye cielo.'

    return ''


def _sanitizar_tip(txt: str) -> str:
    t = re.sub(r'\s+', ' ', (txt or '').strip())
    t = t.replace('\n', ' ')
    if len(t) > 320:
        t = t[:317].rstrip() + '…'
    return t


def liz_tip_wizard(
    *,
    step: int,
    ambiente_id: str,
    color_id: str,
    brillo_id: str,
    m2: float,
) -> dict[str, Any]:
    """Tip corto Liz — Ollama vitrina con fallback reglas SD."""
    regla = _tip_reglas(
        step=step,
        ambiente_id=ambiente_id,
        color_id=color_id,
        brillo_id=brillo_id,
        m2=m2,
    )
    if step >= 4 or step < 1:
        return {'ok': True, 'tip': '', 'fuente': 'reglas'}

    amb = _ambiente_por_id(ambiente_id) or AMBIENTES[0]
    color = _color_por_id(color_id)
    brillo = _brillo_por_id(brillo_id)
    cant = calcular_cantidad(m2=m2)

    try:
        from services.ollama_client import generar_chat_vitrina, ollama_disponible_vitrina

        if ollama_disponible_vitrina(requiere_modelo=False):
            system = (
                'Eres Liz, asesora de pinturas en ferretería Santo Domingo (Chile). '
                'Responde UN solo consejo práctico en español chileno, máximo 2 oraciones, sin saludo. '
                'No inventes precios ni stock. Solo recomienda según ambiente, brillo y m². '
                'Los colores mostrados ya son productos con stock en tienda (no tintometría aún).'
            )
            user = (
                f'Paso wizard {step}/4. Ambiente: {amb.get("nombre")}. '
                f'Color: {color.get("codigo") if color else "?"} {color.get("nombre") if color else ""} '
                f'({color.get("marca") if color else ""}). Brillo: {brillo.get("nombre") if brillo else "?"}. '
                f'Superficie: {cant.get("m2")} m², ~{cant.get("galones_sugeridos_fmt")} galones.'
            )
            out = generar_chat_vitrina(system=system, user=user, timeout=25)
            if out.get('ok') and out.get('texto'):
                return {'ok': True, 'tip': _sanitizar_tip(out['texto']), 'fuente': 'ollama'}
    except Exception:
        pass

    return {'ok': True, 'tip': regla, 'fuente': 'reglas'}
