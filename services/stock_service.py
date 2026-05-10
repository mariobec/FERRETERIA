"""Stock bodega / invariantes por vale (Fase 2 — extracción desde app)."""
import json


def venta_bodega_despacho_map(venta):
    raw = getattr(venta, 'bodega_despacho_json', None) or ''
    if not (raw or '').strip():
        return {}
    try:
        m = json.loads(raw)
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def venta_consumo_ya_despachado_bodega(venta, detalle_id):
    m = venta_bodega_despacho_map(venta)
    v = m.get(str(detalle_id))
    if v is None:
        return 0
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def venta_actualizar_estado_despacho_bodega(venta):
    """Sincroniza bodega_despacho_estado: SALIDA_PARCIAL / DESPACHADO según JSON vs líneas."""
    import app as m

    Producto = m.Producto
    detalles = list(venta.detalles or [])
    if not detalles:
        venta.bodega_despacho_estado = None
        return
    mp = venta_bodega_despacho_map(venta)
    any_ship = any(int(mp.get(str(d.id), 0) or 0) > 0 for d in detalles)
    if not any_ship:
        venta.bodega_despacho_estado = None
        return
    all_full = True
    for d in detalles:
        producto = d.producto or Producto.query.get(d.id_producto)
        if not producto:
            all_full = False
            continue
        factor = m._factor_venta_a_stock(producto)
        need = int(round((d.cantidad or 0) * factor))
        got = int(mp.get(str(d.id), 0) or 0)
        if need > 0 and got < need:
            all_full = False
            break
    venta.bodega_despacho_estado = 'DESPACHADO' if all_full else 'SALIDA_PARCIAL'


def venta_tiene_despacho_bodega(venta):
    if not venta:
        return False
    if (getattr(venta, 'bodega_despacho_estado', None) or '').strip():
        return True
    mp = venta_bodega_despacho_map(venta)
    return any(int(v or 0) > 0 for v in mp.values())


def stock_validar_invariante_venta(venta):
    """
    Garantiza: por cada línea, consumo registrado en bodega (JSON) ≤ consumo total de línea (stock base).
    Raises ValueError si violación.
    """
    import app as m

    Producto = m.Producto
    if not venta:
        return
    for d in list(venta.detalles or []):
        producto = d.producto or Producto.query.get(d.id_producto)
        if not producto:
            continue
        factor = m._factor_venta_a_stock(producto)
        need = int(round((d.cantidad or 0) * factor))
        got = venta_consumo_ya_despachado_bodega(venta, d.id)
        if got > need:
            raise ValueError(
                f'Invariante stock vale #{venta.id} línea {d.id}: bodega acumulada {got} > requerido {need} ({producto.nombre}).'
            )


def revertir_stock_bodega_por_anulacion(venta, usuario_nom):
    """
    Revierte salidas de bodega registradas en bodega_despacho_json (idempotente si JSON vacío).
    No hace commit.
    """
    import app as m

    Producto = m.Producto
    DetalleVenta = m.DetalleVenta
    mp = venta_bodega_despacho_map(venta)
    if not mp:
        venta.bodega_despacho_json = None
        venta.bodega_despacho_estado = None
        venta.bodega_despacho_ultimo_at = None
        return
    aid_b = m.id_almacen_bodega()
    if not aid_b or not m._tablas_inventario_almacen_existen():
        raise ValueError('No hay almacén bodega configurado para revertir despacho.')
    usr = (usuario_nom or '')[:100] or 'Sistema'
    for det_id_str, qty_raw in list(mp.items()):
        try:
            qty = int(qty_raw or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        if not str(det_id_str).isdigit():
            continue
        det = DetalleVenta.query.get(int(det_id_str))
        if not det or det.id_venta != venta.id:
            continue
        producto = Producto.query.get(det.id_producto)
        if not producto:
            continue
        _, err = m.ajustar_stock_almacen(producto.id, aid_b, int(qty))
        if err:
            raise ValueError(err)
        m.registrar_movimiento_kardex(
            producto.id,
            'ENTRADA',
            int(qty),
            f'Reversión anulación vale #{venta.id} (devuelve a bodega despacho voz) por {usr}',
            usuario=usr,
            id_almacen=aid_b,
            referencia_tipo='venta',
            referencia_id=venta.id,
            stock_saldo=None,
        )
        m._refrescar_stock_total_producto(producto)
    venta.bodega_despacho_json = None
    venta.bodega_despacho_estado = None
    venta.bodega_despacho_ultimo_at = None
