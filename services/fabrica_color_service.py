"""
Fábrica de Color LhexIA — wizard pinturas (vitrina web Santo Domingo).
Paleta curada + productos ERP rubro Pinturas + complementos producto_relacion.
"""
from __future__ import annotations

import math
from typing import Any

RENDIMIENTO_M2_GALON = 35.0
MANOS_DEFAULT = 2
LITROS_POR_GALON = 3.785

AMBIENTES: list[dict[str, Any]] = [
    {
        "id": "comedor",
        "nombre": "Comedor",
        "icono": "fa-utensils",
        "uso": "interior",
        "tip": "Ideal para espacios de reunión con buena luz natural.",
    },
    {
        "id": "dormitorio",
        "nombre": "Dormitorio",
        "icono": "fa-bed",
        "uso": "interior",
        "tip": "Prefiera tonos suaves y acabado mate para descanso.",
    },
    {
        "id": "living",
        "nombre": "Living",
        "icono": "fa-couch",
        "uso": "interior",
        "tip": "Combine color de acento en muro principal.",
    },
    {
        "id": "bano",
        "nombre": "Baño",
        "icono": "fa-bath",
        "uso": "interior",
        "tip": "Use pintura lavable o satinada por humedad.",
    },
    {
        "id": "fachada",
        "nombre": "Fachada",
        "icono": "fa-house-chimney",
        "uso": "exterior",
        "tip": "Elija pintura exterior con protección UV.",
    },
    {
        "id": "cocina",
        "nombre": "Cocina",
        "icono": "fa-kitchen-set",
        "uso": "interior",
        "tip": "Satinado facilita limpieza de salpicaduras.",
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

# Paleta referencial (códigos tipo cartilla). hex para visualizador.
_PALETA: list[dict[str, Any]] = [
    {"id": "v-055", "codigo": "V-055", "nombre": "Bangalore", "familia": "amarillo", "hex": "#D4E157", "marca": "Kolor"},
    {"id": "v-010", "codigo": "V-010", "nombre": "Limón suave", "familia": "amarillo", "hex": "#FFF59D", "marca": "Kolor"},
    {"id": "b-001", "codigo": "B-001", "nombre": "Blanco nieve", "familia": "blanco", "hex": "#FAFAFA", "marca": "Topex"},
    {"id": "b-012", "codigo": "B-012", "nombre": "Blanco hueso", "familia": "blanco", "hex": "#F5F0E6", "marca": "Topex"},
    {"id": "g-040", "codigo": "G-040", "nombre": "Gris urbano", "familia": "gris", "hex": "#9E9E9E", "marca": "Kolor"},
    {"id": "g-028", "codigo": "G-028", "nombre": "Gris perla", "familia": "gris", "hex": "#ECEFF1", "marca": "Topex"},
    {"id": "a-018", "codigo": "A-018", "nombre": "Azul pacífico", "familia": "azul", "hex": "#64B5F6", "marca": "Kolor"},
    {"id": "a-032", "codigo": "A-032", "nombre": "Azul noche", "familia": "azul", "hex": "#1A237E", "marca": "Topex"},
    {"id": "vd-015", "codigo": "VD-015", "nombre": "Verde sage", "familia": "verde", "hex": "#A5D6A7", "marca": "Kolor"},
    {"id": "vd-022", "codigo": "VD-022", "nombre": "Verde bosque", "familia": "verde", "hex": "#2E7D32", "marca": "Topex"},
    {"id": "r-008", "codigo": "R-008", "nombre": "Terracota", "familia": "rojo", "hex": "#D84315", "marca": "Kolor"},
    {"id": "r-003", "codigo": "R-003", "nombre": "Rosa empolvado", "familia": "rojo", "hex": "#F8BBD0", "marca": "Topex"},
    {"id": "n-001", "codigo": "N-001", "nombre": "Negro grafito", "familia": "neutro", "hex": "#37474F", "marca": "Topex"},
    {"id": "be-010", "codigo": "BE-010", "nombre": "Beige arena", "familia": "beige", "hex": "#D7CCC8", "marca": "Kolor"},
    {"id": "be-018", "codigo": "BE-018", "nombre": "Arena cálida", "familia": "beige", "hex": "#EFEBE9", "marca": "Topex"},
]

_FAMILIAS_ORDEN = ("blanco", "beige", "amarillo", "verde", "azul", "gris", "rojo", "neutro")


def _fmt_clp(n: float) -> str:
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        v = 0
    return f"${v:,}".replace(",", ".")


def _color_por_id(color_id: str) -> dict[str, Any] | None:
    cid = (color_id or "").strip().lower()
    for c in _PALETA:
        if c["id"] == cid:
            return dict(c)
    return None


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


def familias_colores() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fam in _FAMILIAS_ORDEN:
        cols = [c for c in _PALETA if c.get("familia") == fam]
        if cols:
            out.append({"id": fam, "nombre": fam.capitalize(), "colores": cols})
    return out


def payload_inicial() -> dict[str, Any]:
    return {
        "ambientes": AMBIENTES,
        "brillos": BRILLOS,
        "calidades": CALIDADES,
        "familias": familias_colores(),
        "colores": list(_PALETA),
        "defaults": {
            "manos": MANOS_DEFAULT,
            "rendimiento_m2_galon": RENDIMIENTO_M2_GALON,
            "litros_por_galon": LITROS_POR_GALON,
        },
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
    nombre = (prod.nombre or "").lower()
    cat = (prod.categoria or "").lower()
    sub = (prod.subcategoria or "").lower()
    if any(x in nombre for x in ("rodillo", "brocha", "bandeja", "cinta masking", "lija", "thinner", "diluyente")):
        return False
    if "pintur" in cat or "pintur" in sub or "esmalte" in nombre or "latex" in nombre or "látex" in nombre:
        return True
    if nombre.startswith("pintura ") or " pintura " in nombre:
        return True
    return False


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


def productos_pintura_por_calidad(*, calidad_id: str, uso: str = "interior", limite: int = 12) -> list[dict[str, Any]]:
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
            out.append(
                {
                    "producto_id": p.id,
                    "nombre": (it.get("nombre") or p.nombre or "")[:100],
                    "precio_fmt": _fmt_clp(it.get("precio") or p.precio_venta or 0),
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
    color = _color_por_id(color_id) or _PALETA[0]
    brillo = _brillo_por_id(brillo_id) or BRILLOS[0]
    cant = calcular_cantidad(m2=m2)

    productos = productos_pintura_por_calidad(calidad_id=calidad_id, uso=amb.get("uso", "interior"))
    elegido = None
    if producto_id:
        for p in productos:
            if int(p["producto_id"]) == int(producto_id):
                elegido = p
                break
    if not elegido and productos:
        con_stock = [p for p in productos if p.get("disponible")]
        elegido = (con_stock or productos)[0]

    comps = complementos_pintura(elegido["producto_id"] if elegido else None)

    titulo = f"Proyecto {amb['nombre']} · {color['nombre']}"
    resumen = (
        f"{cant['galones_sugeridos_fmt']} gal (≈{cant['m2']} m² × {cant['manos']} manos) · "
        f"{color['codigo']} {color['marca']} · {brillo['nombre']}"
    )

    liz_prompt = (
        f"Estoy configurando pintura para {amb['nombre']}: color {color['nombre']} ({color['codigo']}), "
        f"acabado {brillo['nombre']}, {cant['m2']} m². ¿Qué más debería llevar?"
    )

    wa_lineas = [
        f"Hola, cotizo pintura — {titulo}",
        resumen,
    ]
    if elegido:
        wa_lineas.append(f"Base sugerida: {elegido['nombre']} ({elegido['precio_fmt']})")
    wa_lineas.append("Retiro en tienda Santo Domingo.")

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
    }
