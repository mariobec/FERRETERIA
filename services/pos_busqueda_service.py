"""
Búsqueda manual POS: semáforo de disponibilidad y enriquecimiento JSON.
"""
from __future__ import annotations

SEMAFORO_VERDE = "verde"
SEMAFORO_AMARILLO = "amarillo"
SEMAFORO_AZUL = "azul"

_ETIQUETAS = {
    SEMAFORO_VERDE: "Entrega inmediata",
    SEMAFORO_AMARILLO: "Retiro en bodega",
    SEMAFORO_AZUL: "Venta en verde / A pedido",
}


def pos_permite_venta_verde(cfg: dict | None = None) -> bool:
    if cfg is None:
        from app import obtener_config_empresa

        cfg = obtener_config_empresa()
    return str(cfg.get("pos_permite_venta_verde", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def pos_dias_entrega_estimado(cfg: dict | None = None) -> int:
    if cfg is None:
        from app import obtener_config_empresa

        cfg = obtener_config_empresa()
    try:
        n = int(str(cfg.get("pos_dias_entrega_a_pedido", "5")).strip() or "5")
    except (TypeError, ValueError):
        n = 5
    return max(1, min(n, 90))


def clasificar_semaforo(stock_tienda: int, stock_bodega: int) -> str:
    st_t = int(stock_tienda or 0)
    st_b = int(stock_bodega or 0)
    if st_t > 0:
        return SEMAFORO_VERDE
    if st_b > 0:
        return SEMAFORO_AMARILLO
    return SEMAFORO_AZUL


def etiqueta_semaforo(semaforo: str) -> str:
    return _ETIQUETAS.get(str(semaforo or "").lower(), "Sin clasificar")


def formatear_ubicacion_pos(pasillo, estante, nivel) -> tuple[str, str]:
    """Texto legible + código corto (P-E-N) para POS. Vacío si no hay ubicación."""
    p = (str(pasillo or "")).strip()
    e = (str(estante or "")).strip()
    n = (str(nivel or "")).strip()
    partes = []
    if p:
        partes.append(f"Pasillo {p}")
    if e:
        partes.append(f"Est. {e}")
    if n:
        partes.append(f"Nv. {n}")
    label = " · ".join(partes)
    codigo = "-".join([x for x in (p, e, n) if x])
    return label, codigo


def construir_badges_semaforo(
    item: dict,
    precio_min: float,
    precio_max: float,
) -> list[dict]:
    sem = str(item.get("semaforo") or clasificar_semaforo(
        item.get("stock_tienda"), item.get("stock_bodega")
    ))
    badges = [{"tipo": sem, "label": etiqueta_semaforo(sem)}]
    precio = float(item.get("precio") or 0)
    if precio_max > precio_min:
        if precio <= precio_min:
            badges.append({"tipo": "economica", "label": "Alternativa económica"})
        elif precio >= precio_max:
            badges.append({"tipo": "premium", "label": "Gama premium"})
    return badges


def ordenar_candidatos_busqueda(candidatos: list[dict], query: str | None = None) -> list[dict]:
    orden_semaforo = {SEMAFORO_VERDE: 0, SEMAFORO_AMARILLO: 1, SEMAFORO_AZUL: 2}
    q = (query or "").strip().upper()
    q_digits = "".join(ch for ch in q if ch.isdigit())

    def _rank_codigo(c: dict) -> tuple:
        """0 = código exacto; 1 = código más largo que contiene q; 2 = resto.
        Evita que 11111 gane sobre 111110 cuando se busca/escanea 111110."""
        if not q:
            return (2, 0)
        cod = (str(c.get("codigo") or c.get("codigo_barra") or "")).strip().upper()
        cod_digits = "".join(ch for ch in cod if ch.isdigit())
        if cod == q or (q_digits and cod_digits == q_digits):
            return (0, -len(cod_digits or cod))
        if q_digits and cod_digits and q_digits in cod_digits:
            return (1, -len(cod_digits))
        if q and q in cod:
            return (1, -len(cod))
        return (2, 0)

    def _key(c: dict) -> tuple:
        sem = str(c.get("semaforo") or SEMAFORO_AZUL)
        return (
            _rank_codigo(c),
            orden_semaforo.get(sem, 9),
            -int(c.get("stock_tienda") or 0),
            -int(c.get("stock_bodega") or 0),
            -int(c.get("stock_total") or 0),
        )

    return sorted(candidatos, key=_key)


def enriquecer_item_busqueda_pos(
    *,
    pid: int,
    row: dict,
    cols: set,
    stock_tienda: int,
    stock_bodega: int,
    nombre: str,
    codigo: str,
    precio: float,
    precio_fmt: str,
    marca: str,
    unidad: str,
    cfg: dict | None = None,
) -> dict:
    st_t = int(stock_tienda or 0)
    st_b = int(stock_bodega or 0)
    st_tot = st_t + st_b
    sem = clasificar_semaforo(st_t, st_b)
    permite_verde = pos_permite_venta_verde(cfg)
    dias = pos_dias_entrega_estimado(cfg)
    sufijo = codigo if codigo else f"id {pid}"
    up = (str(row.get("ubicacion_pasillo") or "")).strip()
    ue = (str(row.get("ubicacion_estante") or "")).strip()
    un = (str(row.get("ubicacion_nivel") or "")).strip()
    ubic_label, ubic_codigo = formatear_ubicacion_pos(up, ue, un)
    item = {
        "id": str(pid),
        "producto_id": pid,
        "text": f"{nombre} ({sufijo})",
        "nombre": nombre,
        "codigo": codigo or f"id {pid}",
        "precio": precio,
        "precio_lista": int(round(precio)),
        "precio_fmt": precio_fmt,
        "marca": marca,
        "stock_tienda": st_t,
        "stock_bodega": st_b,
        "stock_total": st_tot,
        "sin_stock": st_tot <= 0,
        "semaforo": sem,
        "semaforo_label": etiqueta_semaforo(sem),
        "permite_venta_verde": bool(permite_verde and sem == SEMAFORO_AZUL),
        "dias_entrega_estimado": dias if sem == SEMAFORO_AZUL else None,
        "unidad": unidad,
        "ubicacion_pasillo": up,
        "ubicacion_estante": ue,
        "ubicacion_nivel": un,
        "ubicacion_codigo": ubic_codigo,
        "ubicacion_label": ubic_label,
    }
    return item


def resolver_filtro_busqueda_pos(request_args) -> str:
    """
    Modos POS: operativo (verde+amarillo+azul vendible), tienda (solo mostrador), catalogo (todo con precio).
    """
    if request_args is None:
        return "catalogo"
    raw = (request_args.get("filtro_pos") or request_args.get("filtro") or "").strip().lower()
    if str(request_args.get("origen") or "").strip().lower() == "enrolamiento":
        if raw in ("operativo", "tienda", "catalogo"):
            return raw
        return "catalogo"
    if raw in ("operativo", "tienda", "catalogo"):
        return raw
    raw_sv = request_args.get("solo_vendibles")
    if raw_sv is not None and str(raw_sv).strip() != "":
        return "tienda" if str(raw_sv).strip().lower() in ("1", "true", "si", "yes", "on") else "catalogo"
    if str(request_args.get("origen") or "").strip().lower() == "pos":
        return "operativo"
    if str(request_args.get("origen") or "").strip().lower() in ("precios_piloto", "precios"):
        return "catalogo"
    return "operativo"


def filtrar_productos_por_filtro_pos(
    productos,
    stock_t_map: dict,
    stock_b_map: dict,
    filtro: str,
    cfg: dict | None = None,
) -> list:
    """Aplica filtro de disponibilidad tras cargar stock por almacén."""
    filtro = str(filtro or "catalogo").lower()
    if filtro == "catalogo":
        return list(productos or [])
    permite_verde = pos_permite_venta_verde(cfg)
    out = []
    for r in productos or []:
        pid = int(r.get("id") or 0)
        if not pid:
            continue
        st_t = int(stock_t_map.get(pid, 0) or 0)
        st_b = int(stock_b_map.get(pid, 0) or 0)
        if filtro == "tienda":
            if st_t > 0:
                out.append(r)
        elif filtro == "operativo":
            if st_t > 0 or st_b > 0:
                out.append(r)
            elif permite_verde:
                out.append(r)
        else:
            out.append(r)
    return out
