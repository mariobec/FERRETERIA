"""Fase 2 — kardex + bitácoras opcionales de costos/precios (lógica centralizada)."""

from datetime import datetime

from sqlalchemy import text

from services import stock_service as ss


def bitacora_costos_disponible():
    import app as m

    estado = m.app.config.get('_BITACORA_COSTOS_OK')
    if estado is not None:
        return bool(estado)
    try:
        ok = m.db.session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'bitacora_costos_compra' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    m.app.config['_BITACORA_COSTOS_OK'] = bool(ok)
    return bool(ok)


def registrar_bitacora_costo(
    producto_id,
    proveedor_id,
    recepcion_id,
    costo_anterior,
    costo_nuevo,
    precio_venta_referencia,
    usuario,
    observacion=None,
):
    import app as m

    if not bitacora_costos_disponible():
        return
    try:
        ca = float(costo_anterior or 0)
        cn = float(costo_nuevo or 0)
        pv = float(precio_venta_referencia or 0)
        variacion = ((cn - ca) / ca) if ca > 0 else None
        margen_proj = ((pv - cn) / cn) if cn > 0 and pv > 0 else None
        m.db.session.add(
            m.BitacoraCostoCompra(
                producto_id=producto_id,
                proveedor_id=proveedor_id,
                recepcion_id=recepcion_id,
                costo_anterior=ca,
                costo_nuevo=cn,
                variacion_pct=variacion,
                precio_venta_referencia=pv if pv > 0 else None,
                margen_proyectado=margen_proj,
                usuario=(usuario or '')[:100] if usuario else None,
                observacion=(observacion or '')[:255] if observacion else None,
            )
        )
    except Exception:
        # Nunca bloquea la recepción por bitácora auxiliar.
        pass


def bitacora_precios_disponible():
    import app as m

    estado = m.app.config.get('_BITACORA_PRECIOS_OK')
    if estado is not None:
        return bool(estado)
    try:
        ok = m.db.session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'bitacora_precios_venta' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    m.app.config['_BITACORA_PRECIOS_OK'] = bool(ok)
    return bool(ok)


def registrar_bitacora_precio(
    producto_id,
    precio_anterior,
    precio_nuevo,
    costo_referencia,
    margen_objetivo,
    usuario,
    motivo,
):
    import app as m

    if not bitacora_precios_disponible():
        return
    try:
        m.db.session.add(
            m.BitacoraPrecioVenta(
                producto_id=producto_id,
                precio_anterior=float(precio_anterior or 0),
                precio_nuevo=float(precio_nuevo or 0),
                costo_referencia=float(costo_referencia or 0) if costo_referencia is not None else None,
                margen_objetivo=float(margen_objetivo or 0) if margen_objetivo is not None else None,
                usuario=(usuario or '')[:100] if usuario else None,
                motivo=(motivo or '')[:255] if motivo else None,
            )
        )
    except Exception:
        pass


def registrar_movimiento_kardex(
    id_producto,
    tipo_movimiento,
    cantidad,
    motivo,
    usuario=None,
    id_almacen=1,
    referencia_tipo=None,
    referencia_id=None,
    stock_saldo=None,
):
    """Registra una línea de kardex. La cantidad se guarda siempre como entero positivo."""
    import app as m

    try:
        c = int(cantidad)
    except (TypeError, ValueError):
        return
    if c <= 0:
        return
    ref_t = (referencia_tipo or '')[:40] if referencia_tipo else None
    ref_id = int(referencia_id) if referencia_id is not None else None
    almacen_id = None
    if ss.tablas_inventario_almacen_existen():
        try:
            if id_almacen:
                existe = m.db.session.execute(
                    text('SELECT 1 FROM almacenes WHERE id = :id LIMIT 1'),
                    {'id': int(id_almacen)},
                ).scalar()
                if existe:
                    almacen_id = int(id_almacen)
            if not almacen_id:
                almacen_id = m.db.session.execute(
                    text('SELECT id FROM almacenes ORDER BY id ASC LIMIT 1')
                ).scalar()
        except Exception:
            almacen_id = None
        if not almacen_id:
            return
    else:
        try:
            almacen_id = int(id_almacen) if id_almacen else 1
        except (TypeError, ValueError):
            almacen_id = 1

    saldo = int(stock_saldo) if stock_saldo is not None else None
    if ss.tablas_inventario_almacen_existen():
        s_alm = ss.stock_producto_en_almacen(int(id_producto), int(almacen_id))
        if s_alm is not None:
            saldo = s_alm
    elif saldo is None:
        try:
            p = m.Producto.query.get(int(id_producto))
            saldo = int(p.stock) if p and p.stock is not None else 0
        except Exception:
            saldo = None

    mov = m.MovimientoInventario(
        id_producto=id_producto,
        id_almacen=almacen_id,
        tipo_movimiento=(tipo_movimiento or '')[:20],
        cantidad=c,
        motivo=(motivo or '')[:500] if motivo else None,
        usuario=(usuario or '')[:100] if usuario else None,
        fecha=datetime.now(),
        referencia_tipo=ref_t or None,
        referencia_id=ref_id,
        stock_saldo=saldo,
    )
    m.db.session.add(mov)
