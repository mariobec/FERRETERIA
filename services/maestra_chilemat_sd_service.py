"""
Carga maestro SD → ERP con Chilemat como único proveedor de factura.

Escaneo codigo_barra → producto → precio_compra / precio_venta
Factura/OC Chilemat → producto_codigo_proveedor (codigo factura → producto_id)
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

USUARIO = "maestra-chilemat-sd"


def norm_cod_factura(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip().upper()


def obtener_proveedor_chilemat_id(*, crear: bool = False, dry_run: bool = False) -> int | None:
    from services.chilemat_catalogo_ui_service import resolver_proveedor_chilemat

    p = resolver_proveedor_chilemat()
    if p:
        return int(p.id)
    if not crear or dry_run:
        return -1 if dry_run else None
    from app import Proveedor, db

    p = Proveedor(nombre="Chilemat")
    db.session.add(p)
    db.session.flush()
    return int(p.id)


def index_vtex_por_ean() -> dict[str, dict[str, Any]]:
    from app import ChilematVtexProducto

    out: dict[str, dict[str, Any]] = {}
    for row in ChilematVtexProducto.query.filter(ChilematVtexProducto.ean.isnot(None)).all():
        ean = re.sub(r"\D", "", str(row.ean or ""))
        if len(ean) < 8:
            continue
        if ean not in out:
            out[ean] = _vtex_row_dict(row)
    return out


def index_vtex_por_referencia() -> dict[str, dict[str, Any]]:
    from app import ChilematVtexProducto

    out: dict[str, dict[str, Any]] = {}
    for row in ChilematVtexProducto.query.filter(ChilematVtexProducto.product_reference.isnot(None)).all():
        ref = norm_cod_factura(row.product_reference)
        if ref and ref not in out:
            out[ref] = _vtex_row_dict(row)
    return out


def _vtex_row_dict(row) -> dict[str, Any]:
    return {
        "vtex_product_id": row.vtex_product_id,
        "product_reference": (row.product_reference or "").strip(),
        "producto_id": row.producto_id,
        "precio_lista": float(row.precio_lista or 0),
        "nombre": row.nombre or "",
        "ean": re.sub(r"\D", "", str(row.ean or "")),
    }


def buscar_vtex_producto(
    *,
    ean: str = "",
    codigo_factura: str = "",
    codigo_chilemat: str = "",
    codigo_barra: str = "",
    vtex_ean: dict[str, dict[str, Any]] | None = None,
    vtex_ref: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    from services.maestra_unificado_loaders import norm_ean

    if vtex_ean is None:
        vtex_ean = index_vtex_por_ean()
    if vtex_ref is None:
        vtex_ref = index_vtex_por_referencia()

    for raw in (ean, codigo_barra):
        en = norm_ean(raw)
        if en and en in vtex_ean:
            return vtex_ean[en]

    for raw in (codigo_factura, codigo_chilemat):
        ref = norm_cod_factura(raw)
        if ref.startswith("INT-"):
            ref = ref[4:].strip()
        if ref and ref in vtex_ref:
            return vtex_ref[ref]
    return None


def resolver_precio_lista(
    *,
    precio_venta_actual: float,
    vtex: dict[str, Any] | None,
    costo: float,
    margen: float = 0.35,
) -> tuple[float, str]:
    """Devuelve (precio_lista, fuente). Catálogo: lista VTEX aunque no haya costo."""
    pv = float(precio_venta_actual or 0)
    if pv > 0:
        return pv, "erp_existente"
    if vtex and float(vtex.get("precio_lista") or 0) > 0:
        return float(vtex["precio_lista"]), "chilemat_vtex"
    if costo > 0:
        return round(costo * (1 + margen), 0), "costo_mas_margen"
    return 0.0, "sin_precio"


def vincular_vtex_a_producto(producto, vtex: dict[str, Any] | None, *, dry_run: bool) -> bool:
    """Enlaza ficha VTEX al producto ERP (e-commerce vitrina)."""
    if not vtex or not vtex.get("vtex_product_id"):
        return False
    from app import ChilematVtexProducto, db

    vid = str(vtex["vtex_product_id"]).strip()
    row = ChilematVtexProducto.query.get(vid)
    if not row:
        return False
    if row.producto_id and int(row.producto_id) != int(producto.id):
        return False
    if row.producto_id == producto.id:
        return True
    if dry_run:
        return True
    row.producto_id = int(producto.id)
    db.session.flush()
    return True


def codigo_chilemat_desde_codigo(codigo: str) -> str | None:
    c = norm_cod_factura(codigo)
    if not c:
        return None
    if c.startswith("INT-"):
        return c[4:].strip()[:80] or None
    return None


def elegir_barra(codigo_factura: str, ean: str, ocupados: set[str]) -> str | None:
    from services.maestra_unificado_loaders import norm_cod, norm_ean

    for cand in (norm_ean(ean), norm_cod(codigo_factura)):
        if cand and len(cand) >= 4 and cand not in ocupados:
            return cand[:50]
    cf = norm_cod(codigo_factura)
    if cf and len(cf) >= 4:
        alt = f"M-{cf}"[:50]
        if alt not in ocupados:
            return alt
    en = norm_ean(ean)
    if en:
        alt = f"EAN-{en}"[:50]
        if alt not in ocupados:
            return alt
    return None


def inicializar_stock_cero(producto) -> None:
    from app import fijar_stock_almacen, id_almacen_bodega, id_almacen_tienda

    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    if aid_t:
        fijar_stock_almacen(producto.id, aid_t, 0)
    if aid_b:
        fijar_stock_almacen(producto.id, aid_b, 0)
    producto.stock = 0


def enriquecer_producto(
    producto,
    *,
    codigo_factura: str,
    costo: float | None,
    ean: str,
    categoria: str,
    subcategoria: str,
    vtex: dict[str, Any] | None,
    chilemat_id: int,
    ocupados_barra: set[str],
    puentes: set[tuple[int, str]],
    dry_run: bool,
    actualizar_barra: bool = True,
    margen_venta: float = 0.35,
) -> dict[str, Any]:
    from app import guardar_producto_codigo_proveedor
    from services.maestra_unificado_loaders import norm_ean

    reg: dict[str, Any] = {
        "producto_id": producto.id,
        "codigo_factura_chilemat": norm_cod_factura(codigo_factura),
        "accion": "enriquecer",
    }

    if costo and costo > 0:
        reg["precio_compra"] = costo
        if not dry_run:
            producto.precio_compra = float(costo)

    if categoria and not (producto.categoria or "").strip() and not dry_run:
        producto.categoria = categoria[:50]
        reg["categoria"] = categoria[:50]
    if subcategoria and not (producto.subcategoria or "").strip() and not dry_run:
        producto.subcategoria = subcategoria[:50]
        reg["subcategoria"] = subcategoria[:50]

    ean_n = norm_ean(ean)
    if actualizar_barra and ean_n and ean_n not in ocupados_barra:
        barra_actual = norm_cod_factura(producto.codigo_barra or "")
        if barra_actual != ean_n:
            reg["codigo_barra"] = ean_n
            if not dry_run:
                producto.codigo_barra = ean_n
                ocupados_barra.add(ean_n)

    cm = codigo_chilemat_desde_codigo(codigo_factura)
    if vtex and vtex.get("product_reference"):
        cm = str(vtex["product_reference"]).strip()[:80]
    if cm and not (producto.codigo_chilemat or "").strip():
        reg["codigo_chilemat"] = cm
        if not dry_run:
            producto.codigo_chilemat = cm

    pv = float(producto.precio_venta or 0)
    costo_f = float(costo or 0) if costo else float(producto.precio_compra or 0)
    pv_nuevo, fuente = resolver_precio_lista(
        precio_venta_actual=pv,
        vtex=vtex,
        costo=costo_f,
        margen=margen_venta,
    )
    if pv_nuevo > 0 and pv <= 0:
        reg["precio_venta"] = pv_nuevo
        reg["precio_fuente"] = fuente
        if not dry_run:
            producto.precio_venta = pv_nuevo

    if vtex:
        if vincular_vtex_a_producto(producto, vtex, dry_run=dry_run):
            reg["vtex_vinculado"] = vtex.get("vtex_product_id")

    cod = norm_cod_factura(codigo_factura)
    key = (int(chilemat_id), cod)
    if cod and key not in puentes:
        if dry_run:
            reg["puente_chilemat"] = "dry_run"
        else:
            ok, err = guardar_producto_codigo_proveedor(
                chilemat_id, cod, producto.id, usuario=USUARIO, commit=False
            )
            if ok:
                puentes.add(key)
                reg["puente_chilemat"] = "ok"
            else:
                reg["puente_chilemat"] = f"error:{err}"

    return reg


def crear_producto_sd(
    *,
    codigo_factura: str,
    nombre: str,
    costo: float,
    ean: str,
    categoria: str,
    subcategoria: str,
    vtex: dict[str, Any] | None,
    chilemat_id: int,
    ocupados_barra: set[str],
    activo: bool,
    margen_venta: float,
    dry_run: bool,
    prefijo_interno: str = "CM-",
) -> tuple[dict[str, Any] | None, str | None]:
    from app import Producto, db, guardar_producto_codigo_proveedor

    cod_f = norm_cod_factura(codigo_factura)
    if not cod_f:
        return None, "codigo_vacio"

    interno = f"{prefijo_interno}{cod_f}"[:32]
    if Producto.query.filter_by(codigo_interno=interno).first():
        return None, "interno_existe"

    barra = elegir_barra(cod_f, ean, ocupados_barra)
    if not barra:
        return None, "sin_barra"

    pv, fuente = resolver_precio_lista(precio_venta_actual=0, vtex=vtex, costo=costo, margen=margen_venta)

    cm = codigo_chilemat_desde_codigo(cod_f)
    if vtex and vtex.get("product_reference"):
        cm = str(vtex["product_reference"]).strip()[:80]

    reg = {
        "codigo_factura_chilemat": cod_f,
        "codigo_barra": barra,
        "codigo_interno": interno,
        "codigo_chilemat": cm or "",
        "nombre": nombre[:100],
        "precio_compra": costo,
        "precio_venta": pv,
        "precio_fuente": fuente,
        "activo": activo,
    }

    if dry_run:
        reg["dry_run"] = True
        reg["accion"] = "crear"
        return reg, None

    p = Producto(
        nombre=nombre[:100],
        codigo_barra=barra,
        codigo_interno=interno,
        codigo_chilemat=cm,
        precio_compra=costo if costo > 0 else 0,
        precio_venta=pv,
        categoria=categoria[:50] or None,
        subcategoria=subcategoria[:50] or None,
        stock=0,
        activo=activo,
    )
    db.session.add(p)
    db.session.flush()
    inicializar_stock_cero(p)
    ocupados_barra.add(norm_cod_factura(barra))

    ok, err = guardar_producto_codigo_proveedor(chilemat_id, cod_f, p.id, usuario=USUARIO, commit=False)
    if not ok:
        db.session.rollback()
        return None, err

    reg["producto_id"] = p.id
    reg["accion"] = "crear"
    return reg, None
