"""Vinculación manual ERP ↔ catálogo Chilemat (VTEX)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from services.chilemat_catalogo_service import _match_producto_erp
from services.chilemat_catalogo_ui_service import (
    estadisticas_explorador,
    listar_productos,
    resolver_proveedor_chilemat,
)

_log = logging.getLogger(__name__)


def _asegurar() -> None:
    import app as erp

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()


def _producto_a_dict(p) -> dict[str, Any]:
    return {
        'id': p.id,
        'nombre': (p.nombre or '')[:120],
        'codigo_barra': (p.codigo_barra or '').strip(),
        'codigo_interno': (p.codigo_interno or '').strip(),
        'codigo_chilemat': (p.codigo_chilemat or '').strip(),
        'precio_compra': float(p.precio_compra or 0),
        'precio_venta': float(p.precio_venta or 0),
    }


def buscar_productos_erp(q: str = '', *, limit: int = 20) -> list[dict[str, Any]]:
    from app import Producto, db
    from sqlalchemy import or_

    _asegurar()
    q_norm = (q or '').strip()
    if len(q_norm) < 2:
        return []

    limit = max(5, min(int(limit or 20), 40))
    like = f'%{q_norm}%'
    rows = (
        Producto.query.filter(
            Producto.activo.isnot(False),
            or_(
                Producto.nombre.ilike(like),
                Producto.codigo_barra.ilike(like),
                Producto.codigo_interno.ilike(like),
                Producto.codigo_chilemat.ilike(like),
            ),
        )
        .order_by(Producto.nombre.asc())
        .limit(limit)
        .all()
    )
    return [_producto_a_dict(p) for p in rows]


def sugerencias_para_vtex(vtex_product_id: str) -> list[dict[str, Any]]:
    from app import ChilematVtexProducto, Producto

    _asegurar()
    row = ChilematVtexProducto.query.get((vtex_product_id or '').strip())
    if not row:
        return []

    out: list[dict[str, Any]] = []
    seen: set[int] = set()

    def _push(p, metodo: str, confianza: float) -> None:
        if not p or p.id in seen:
            return
        seen.add(p.id)
        out.append({**_producto_a_dict(p), 'metodo': metodo, 'confianza': confianza})

    p = _match_producto_erp(row.product_reference, row.ean)
    if p:
        _push(p, 'codigo_web', 0.95)

    ref = (row.product_reference or '').strip()
    if ref:
        for p in Producto.query.filter(
            Producto.activo.isnot(False),
            Producto.codigo_chilemat == ref,
        ).limit(3):
            _push(p, 'codigo_chilemat', 0.9)

    nombre = (row.nombre or '').strip()
    if len(nombre) >= 4:
        like = f'%{nombre[:50]}%'
        candidatos = (
            Producto.query.filter(Producto.activo.isnot(False), Producto.nombre.ilike(like))
            .limit(5)
            .all()
        )
        if len(candidatos) == 1:
            _push(candidatos[0], 'nombre_unico', 0.75)
        elif candidatos:
            _push(candidatos[0], 'nombre_parcial', 0.45)

    out.sort(key=lambda x: -float(x.get('confianza') or 0))
    return out[:8]


def listar_pendientes_vinculacion(
    *,
    q: str = '',
    rubro_vtex_id: int | None = None,
    sub_vtex_id: int | None = None,
    page: int = 1,
    per_page: int = 30,
    con_sugerencias: bool = True,
) -> dict[str, Any]:
    data = listar_productos(
        q=q,
        rubro_vtex_id=rubro_vtex_id,
        sub_vtex_id=sub_vtex_id,
        solo_sin_vincular=True,
        page=page,
        per_page=per_page,
    )
    if con_sugerencias:
        for it in data.get('items') or []:
            vid = it.get('vtex_id')
            sugs = sugerencias_para_vtex(vid) if vid else []
            it['sugerencias'] = sugs
            it['mejor_sugerencia'] = sugs[0] if sugs else None
    return data


def vincular_producto(
    *,
    vtex_product_id: str,
    producto_id: int,
    usuario: str | None = None,
    actualizar_codigo_chilemat: bool = True,
    registrar_codigo_factura: bool = True,
    copiar_imagen: bool = True,
) -> dict[str, Any]:
    from app import ChilematVtexProducto, Producto, ProductoCodigoProveedor, db

    _asegurar()
    vid = (vtex_product_id or '').strip()
    if not vid:
        return {'ok': False, 'error': 'vtex_id_requerido'}

    try:
        pid = int(producto_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'producto_id_invalido'}

    row = ChilematVtexProducto.query.get(vid)
    if not row:
        return {'ok': False, 'error': 'vtex_no_encontrado'}

    producto = Producto.query.get(pid)
    if not producto or producto.activo is False:
        return {'ok': False, 'error': 'producto_erp_no_encontrado'}

    ref_web = (row.product_reference or row.ean or '').strip()
    otro = (
        ChilematVtexProducto.query.filter(
            ChilematVtexProducto.producto_id == pid,
            ChilematVtexProducto.vtex_product_id != vid,
        )
        .first()
    )
    if otro:
        return {
            'ok': False,
            'error': 'producto_ya_vinculado_otro_vtex',
            'mensaje': f'Ese producto ERP ya está ligado al VTEX {otro.vtex_product_id}.',
        }

    row.producto_id = pid
    row.synced_at = datetime.utcnow()

    if actualizar_codigo_chilemat and ref_web:
        if not (producto.codigo_chilemat or '').strip():
            producto.codigo_chilemat = ref_web[:80]

    codigo_factura = None
    if registrar_codigo_factura and ref_web:
        prov = resolver_proveedor_chilemat()
        if prov:
            codigo_factura = ref_web[:80]
            link = ProductoCodigoProveedor.query.filter_by(
                proveedor_id=prov.id,
                codigo_factura_proveedor=codigo_factura,
            ).first()
            if link and link.producto_id != pid:
                return {
                    'ok': False,
                    'error': 'codigo_factura_ocupado',
                    'mensaje': (
                        f'El código web {codigo_factura} ya está asignado a otro producto ERP '
                        f'(id {link.producto_id}).'
                    ),
                }
            if not link:
                db.session.add(
                    ProductoCodigoProveedor(
                        proveedor_id=prov.id,
                        codigo_factura_proveedor=codigo_factura,
                        producto_id=pid,
                        usuario=(usuario or '')[:100] or None,
                    )
                )

    db.session.commit()

    imagen_aplicada = None
    if copiar_imagen:
        try:
            from services.chilemat_ficha_service import aplicar_ficha_a_producto_erp

            ar = aplicar_ficha_a_producto_erp(pid, vtex_product_id=vid, copiar_imagen=True)
            if ar.get('ok'):
                imagen_aplicada = (ar.get('imagen_url') or '').strip() or None
        except Exception as ex:
            _log.warning('copiar imagen chilemat producto %s: %s', pid, ex)

    stats = estadisticas_explorador()
    return {
        'ok': True,
        'vtex_product_id': vid,
        'producto_id': pid,
        'codigo_chilemat': (producto.codigo_chilemat or '').strip(),
        'codigo_factura': codigo_factura,
        'imagen_aplicada': imagen_aplicada,
        'stats': stats,
    }


def desvincular_producto(*, vtex_product_id: str) -> dict[str, Any]:
    from app import ChilematVtexProducto, db

    _asegurar()
    vid = (vtex_product_id or '').strip()
    row = ChilematVtexProducto.query.get(vid)
    if not row:
        return {'ok': False, 'error': 'vtex_no_encontrado'}
    row.producto_id = None
    row.synced_at = datetime.utcnow()
    db.session.commit()
    return {'ok': True, 'stats': estadisticas_explorador()}


def auto_vincular_sugerencias(
    *,
    max_items: int = 40,
    confianza_min: float = 0.7,
    usuario: str | None = None,
) -> dict[str, Any]:
    """Vincula automáticamente filas con una sugerencia de confianza >= umbral."""
    max_items = max(1, min(int(max_items or 40), 200))
    data = listar_pendientes_vinculacion(page=1, per_page=max_items, con_sugerencias=True)
    vinculados = 0
    omitidos = 0
    errores: list[str] = []

    for it in data.get('items') or []:
        sug = it.get('mejor_sugerencia')
        if not sug or float(sug.get('confianza') or 0) < confianza_min:
            omitidos += 1
            continue
        res = vincular_producto(
            vtex_product_id=it['vtex_id'],
            producto_id=int(sug['id']),
            usuario=usuario,
            actualizar_codigo_chilemat=True,
            registrar_codigo_factura=True,
        )
        if res.get('ok'):
            vinculados += 1
        else:
            omitidos += 1
            errores.append(f"{it.get('vtex_id')}: {res.get('error')}")

    return {
        'ok': True,
        'vinculados': vinculados,
        'omitidos': omitidos,
        'errores': errores[:15],
        'stats': estadisticas_explorador(),
    }
