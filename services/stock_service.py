"""Stock bodega / tienda / invariantes por vale (Fase 2 — extracción desde app)."""
import json
import os

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

_ID_ALMACEN_TIENDA = None
_ID_ALMACEN_BODEGA = None
_INV_ALMACEN_TABLAS_OK = None


def tablas_inventario_almacen_existen():
    """True si existen tablas multi-almacén (cache por proceso)."""
    global _INV_ALMACEN_TABLAS_OK

    import app as m

    if _INV_ALMACEN_TABLAS_OK is not None:
        return _INV_ALMACEN_TABLAS_OK
    try:
        insp = sa_inspect(m.db.engine)
        _INV_ALMACEN_TABLAS_OK = bool(
            insp.has_table('almacenes') and insp.has_table('stock_por_almacen')
        )
    except Exception:
        _INV_ALMACEN_TABLAS_OK = False
    return _INV_ALMACEN_TABLAS_OK


def codigo_almacen_tienda():
    return (os.getenv('ALMACEN_CODIGO_TIENDA') or 'TIENDA').strip().upper() or 'TIENDA'


def codigo_almacen_bodega():
    return (os.getenv('ALMACEN_CODIGO_BODEGA') or 'BODEGA').strip().upper() or 'BODEGA'


def resolver_id_almacen_por_codigo(codigo):
    import app as m

    if not codigo or not tablas_inventario_almacen_existen():
        return None
    try:
        row = m.db.session.execute(
            text(
                'SELECT id FROM almacenes '
                'WHERE UPPER(TRIM(codigo)) = :c AND activo IS NOT FALSE '
                'ORDER BY id ASC LIMIT 1'
            ),
            {'c': codigo.strip().upper()},
        ).scalar()
        return int(row) if row is not None else None
    except Exception:
        m.db.session.rollback()
        return None


def id_almacen_tienda():
    """Almacén desde el que vende el POS (por defecto TIENDA)."""
    global _ID_ALMACEN_TIENDA

    if _ID_ALMACEN_TIENDA is not None:
        return _ID_ALMACEN_TIENDA
    env_id = (os.getenv('ALMACEN_ID_TIENDA') or '').strip()
    if env_id.isdigit():
        _ID_ALMACEN_TIENDA = int(env_id)
        return _ID_ALMACEN_TIENDA
    _ID_ALMACEN_TIENDA = resolver_id_almacen_por_codigo(codigo_almacen_tienda())
    return _ID_ALMACEN_TIENDA


def id_almacen_bodega():
    """Almacén donde ingresa mercadería por recepción (por defecto BODEGA)."""
    global _ID_ALMACEN_BODEGA

    if _ID_ALMACEN_BODEGA is not None:
        return _ID_ALMACEN_BODEGA
    env_id = (os.getenv('ALMACEN_ID_BODEGA') or '').strip()
    if env_id.isdigit():
        _ID_ALMACEN_BODEGA = int(env_id)
        return _ID_ALMACEN_BODEGA
    _ID_ALMACEN_BODEGA = resolver_id_almacen_por_codigo(codigo_almacen_bodega())
    return _ID_ALMACEN_BODEGA


def invalidar_cache_ids_almacen():
    """Tras cambiar codigo/activo de almacenes, forzar nueva resolución TIENDA/BODEGA."""
    global _ID_ALMACEN_TIENDA, _ID_ALMACEN_BODEGA

    _ID_ALMACEN_TIENDA = None
    _ID_ALMACEN_BODEGA = None


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

    from services import kardex_service as kx

    Producto = m.Producto
    DetalleVenta = m.DetalleVenta
    mp = venta_bodega_despacho_map(venta)
    if not mp:
        venta.bodega_despacho_json = None
        venta.bodega_despacho_estado = None
        venta.bodega_despacho_ultimo_at = None
        return
    aid_b = id_almacen_bodega()
    if not aid_b or not tablas_inventario_almacen_existen():
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
        _, err = ajustar_stock_almacen(producto.id, aid_b, int(qty))
        if err:
            raise ValueError(err)
        kx.registrar_movimiento_kardex(
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
        refrescar_stock_total_producto(producto)
    venta.bodega_despacho_json = None
    venta.bodega_despacho_estado = None
    venta.bodega_despacho_ultimo_at = None


def stock_producto_en_almacen(id_producto, id_almacen):
    import app as m

    if not id_almacen or not tablas_inventario_almacen_existen():
        return None
    try:
        v = m.db.session.execute(
            text(
                'SELECT cantidad FROM stock_por_almacen '
                'WHERE id_producto = :p AND id_almacen = :a LIMIT 1'
            ),
            {'p': int(id_producto), 'a': int(id_almacen)},
        ).scalar()
        return None if v is None else int(v)
    except Exception:
        m.db.session.rollback()
        return None


def refrescar_stock_total_producto(producto):
    """Mantiene productos.stock = suma por almacén cuando aplica."""
    import app as m

    if not producto or not tablas_inventario_almacen_existen():
        return
    try:
        m.db.session.flush()
        s = m.db.session.execute(
            text('SELECT COALESCE(SUM(cantidad), 0) FROM stock_por_almacen WHERE id_producto = :p'),
            {'p': int(producto.id)},
        ).scalar()
        producto.stock = int(s or 0)
    except Exception:
        m.db.session.rollback()
        pass


def stock_disponible_venta_tienda(producto):
    import app as m

    if not producto:
        return 0
    aid = id_almacen_tienda()
    if aid and tablas_inventario_almacen_existen():
        v = stock_producto_en_almacen(producto.id, aid)
        return int(v or 0)
    return int(producto.stock or 0)


def stock_disponible_bodega(producto):
    import app as m

    if not producto:
        return 0
    aid = id_almacen_bodega()
    if aid and tablas_inventario_almacen_existen():
        v = stock_producto_en_almacen(producto.id, aid)
        return int(v or 0)
    return int(producto.stock or 0)


def stock_almacen_por_producto_ids(ids, id_almacen):
    """Stock en un almacén para muchos productos (1 query)."""
    import app as m

    StockPorAlmacen = m.StockPorAlmacen
    ids = [int(x) for x in ids if x is not None]
    if not ids or not id_almacen:
        return {}
    rows = (
        m.db.session.query(StockPorAlmacen.id_producto, StockPorAlmacen.cantidad)
        .filter(
            StockPorAlmacen.id_almacen == int(id_almacen),
            StockPorAlmacen.id_producto.in_(ids),
        )
        .all()
    )
    out = {int(pid): int(cant or 0) for pid, cant in rows}
    for pid in ids:
        out.setdefault(int(pid), 0)
    return out


def stock_tienda_por_producto_ids(ids):
    import app as m

    StockPorAlmacen = m.StockPorAlmacen
    Producto = m.Producto
    ids = [int(x) for x in ids if x is not None]
    if not ids:
        return {}
    aid = id_almacen_tienda()
    if aid and tablas_inventario_almacen_existen():
        rows = (
            m.db.session.query(StockPorAlmacen.id_producto, StockPorAlmacen.cantidad)
            .filter(
                StockPorAlmacen.id_almacen == aid,
                StockPorAlmacen.id_producto.in_(ids),
            )
            .all()
        )
        por_id = {int(pid): int(cant or 0) for pid, cant in rows}
        faltan = [i for i in ids if i not in por_id]
        for pid in faltan:
            por_id[int(pid)] = 0
        return por_id
    prods = Producto.query.filter(Producto.id.in_(ids)).all()
    return {p.id: int(p.stock or 0) for p in prods}


def stock_ui_producto(producto):
    """Resumen tienda/bodega/total para UI inventario."""
    import app as m

    total_maestro = int(producto.stock or 0)
    if not producto or not tablas_inventario_almacen_existen():
        return {
            'tienda': total_maestro,
            'bodega': 0,
            'total_almacenes': total_maestro,
            'total_maestro': total_maestro,
            'desajustado': False,
        }
    tid = id_almacen_tienda()
    bid = id_almacen_bodega()
    tienda = int(stock_producto_en_almacen(producto.id, tid) or 0) if tid else 0
    bodega = int(stock_producto_en_almacen(producto.id, bid) or 0) if bid else 0
    try:
        total_almacenes = int(
            m.db.session.execute(
                text('SELECT COALESCE(SUM(cantidad), 0) FROM stock_por_almacen WHERE id_producto = :p'),
                {'p': int(producto.id)},
            ).scalar()
            or 0
        )
    except Exception:
        m.db.session.rollback()
        total_almacenes = total_maestro
    return {
        'tienda': tienda,
        'bodega': bodega,
        'total_almacenes': total_almacenes,
        'total_maestro': total_maestro,
        'desajustado': total_almacenes != total_maestro,
    }


def stock_ui_por_producto_ids(ids):
    """Versión batch de stock_ui_producto: {producto_id: resumen UI}.

    Evita N+1 consultas al listar catálogo/inventario.
    """
    import app as m

    ids = [int(x) for x in ids if x is not None]
    if not ids:
        return {}
    Producto = m.Producto
    prods = Producto.query.filter(Producto.id.in_(ids)).all()
    maestro = {int(p.id): int(p.stock or 0) for p in prods}

    if not tablas_inventario_almacen_existen():
        out = {}
        for pid in ids:
            tot = maestro.get(pid, 0)
            out[pid] = {
                'tienda': tot,
                'bodega': 0,
                'total_almacenes': tot,
                'total_maestro': tot,
                'desajustado': False,
            }
        return out

    StockPorAlmacen = m.StockPorAlmacen
    tid = id_almacen_tienda()
    bid = id_almacen_bodega()

    tienda_map = {}
    bodega_map = {}
    total_map = {}
    try:
        rows = (
            m.db.session.query(
                StockPorAlmacen.id_producto,
                StockPorAlmacen.id_almacen,
                StockPorAlmacen.cantidad,
            )
            .filter(StockPorAlmacen.id_producto.in_(ids))
            .all()
        )
    except Exception:
        m.db.session.rollback()
        rows = []
    for pid, aid, cant in rows:
        pid = int(pid)
        c = int(cant or 0)
        total_map[pid] = total_map.get(pid, 0) + c
        if tid and aid == tid:
            tienda_map[pid] = c
        elif bid and aid == bid:
            bodega_map[pid] = c

    out = {}
    for pid in ids:
        tot_maestro = maestro.get(pid, 0)
        total_alm = total_map.get(pid, 0)
        out[pid] = {
            'tienda': tienda_map.get(pid, 0),
            'bodega': bodega_map.get(pid, 0),
            'total_almacenes': total_alm,
            'total_maestro': tot_maestro,
            'desajustado': total_alm != tot_maestro,
        }
    return out


def ajustar_stock_almacen(producto_id, id_almacen, delta, allow_negative=False):
    """
    delta > 0 suma stock en el almacén; delta < 0 resta.
    Usa UPDATE atómico (PostgreSQL) para eliminar la condición de carrera
    read-modify-write bajo concurrencia POS/caja/e-commerce.
    Devuelve (nuevo_stock_almacén|None, error_str|None).
    """
    import app as m

    StockPorAlmacen = m.StockPorAlmacen
    if not id_almacen or not tablas_inventario_almacen_existen():
        return None, None
    try:
        d = int(delta)
    except (TypeError, ValueError):
        return None, 'Delta de stock inválido.'
    pid = int(producto_id)
    aid = int(id_almacen)

    # UPDATE atómico: elimina la ventana de carrera entre SELECT y UPDATE.
    # allow_negative=False → la cláusula AND impide resultado negativo sin SELECT previo.
    if allow_negative:
        sql = text(
            'UPDATE stock_por_almacen SET cantidad = cantidad + :d '
            'WHERE id_producto = :pid AND id_almacen = :aid '
            'RETURNING cantidad'
        )
    else:
        sql = text(
            'UPDATE stock_por_almacen SET cantidad = cantidad + :d '
            'WHERE id_producto = :pid AND id_almacen = :aid '
            '  AND (cantidad + :d) >= 0 '
            'RETURNING cantidad'
        )
    updated = m.db.session.execute(sql, {'d': d, 'pid': pid, 'aid': aid}).fetchone()
    if updated is not None:
        return int(updated[0]), None

    # Sin fila actualizada: la fila no existe aún, o resultaría negativa.
    existing = m.db.session.execute(
        text(
            'SELECT cantidad FROM stock_por_almacen '
            'WHERE id_producto = :pid AND id_almacen = :aid LIMIT 1'
        ),
        {'pid': pid, 'aid': aid},
    ).scalar()
    if existing is not None:
        # La fila existe pero el delta la dejaría en negativo.
        return int(existing), 'Stock insuficiente en almacén.'

    # Primera asignación de stock en este almacén: INSERT.
    nuevo = d
    if not allow_negative and nuevo < 0:
        return 0, 'Stock insuficiente en almacén.'
    m.db.session.add(StockPorAlmacen(id_producto=pid, id_almacen=aid, cantidad=int(nuevo)))
    return int(nuevo), None


def fijar_stock_almacen(producto_id, id_almacen, cantidad):
    """Ajuste absoluto de stock en un almacén (auditoría)."""
    import app as m

    StockPorAlmacen = m.StockPorAlmacen
    if not id_almacen or not tablas_inventario_almacen_existen():
        return None
    try:
        c = int(cantidad)
    except (TypeError, ValueError):
        return None
    pid = int(producto_id)
    aid = int(id_almacen)
    row = StockPorAlmacen.query.filter_by(id_producto=pid, id_almacen=aid).first()
    if row:
        row.cantidad = c
    else:
        m.db.session.add(StockPorAlmacen(id_producto=pid, id_almacen=aid, cantidad=c))
    return c


def descontar_stock_venta_tienda(producto, consumo_stock):
    """Descuenta TIENDA; devuelve mensaje de error o None."""
    import app as m

    if consumo_stock <= 0:
        return 'Consumo de stock inválido.'
    aid = id_almacen_tienda()
    if aid and tablas_inventario_almacen_existen():
        _, err = ajustar_stock_almacen(producto.id, aid, -int(consumo_stock))
        if err:
            return err
        refrescar_stock_total_producto(producto)
    else:
        if (producto.stock or 0) < consumo_stock:
            return 'Stock insuficiente.'
        producto.stock = (producto.stock or 0) - int(consumo_stock)
    return None


def incrementar_stock_venta_tienda(producto, consumo_stock):
    """Devuelve mercadería a TIENDA (reversa descuento venta)."""
    import app as m

    if consumo_stock <= 0:
        return 'Cantidad de reversión inválida.'
    aid = id_almacen_tienda()
    if aid and tablas_inventario_almacen_existen():
        _, err = ajustar_stock_almacen(producto.id, aid, int(consumo_stock))
        if err:
            return err
        refrescar_stock_total_producto(producto)
    else:
        producto.stock = (producto.stock or 0) + int(consumo_stock)
    return None


def descontar_stock_venta_bodega(producto, consumo_stock):
    """Descuenta BODEGA (almacén estándar); devuelve mensaje de error o None."""
    import app as m

    if consumo_stock <= 0:
        return 'Consumo de stock inválido.'
    aid = id_almacen_bodega()
    if aid and tablas_inventario_almacen_existen():
        _, err = ajustar_stock_almacen(producto.id, aid, -int(consumo_stock))
        if err:
            return err
        refrescar_stock_total_producto(producto)
    else:
        if (producto.stock or 0) < consumo_stock:
            return 'Stock insuficiente.'
        producto.stock = (producto.stock or 0) - int(consumo_stock)
    return None


def incrementar_stock_venta_bodega(producto, consumo_stock):
    """Devuelve mercadería a BODEGA (reversa retiro parcial/total)."""
    import app as m

    if consumo_stock <= 0:
        return 'Cantidad de reversión inválida.'
    aid = id_almacen_bodega()
    if aid and tablas_inventario_almacen_existen():
        _, err = ajustar_stock_almacen(producto.id, aid, int(consumo_stock))
        if err:
            return err
        refrescar_stock_total_producto(producto)
    else:
        producto.stock = (producto.stock or 0) + int(consumo_stock)
    return None


def _punto_retiro_efectivo_linea(venta, detalle):
    """Tienda / Bodega / Despacho por línea (mixto) o cabecera del vale."""
    import app as m

    pr = (getattr(venta, 'punto_retiro', None) or '').strip()
    if m._pos_retiro_por_linea_empresa():
        pl = (getattr(detalle, 'punto_retiro_linea', None) or '').strip()
        if pl:
            return pl
        if pr == 'Mixto':
            return 'Tienda'
    return pr or 'Tienda'


def _consumo_stock_linea(detalle, producto, factor_venta_stock=None):
    """Consumo entero en unidades stock base (invariante peso/fricción)."""
    from services import unidades_service as _us

    return _us.consumo_stock_entero_desde_cantidad(getattr(detalle, 'cantidad', 0), producto)


def _consumo_tienda_linea(venta, detalle, factor_venta_stock):
    """Unidades stock base que esa línea exige de TIENDA (misma regla que cobro)."""
    import app as m

    producto = detalle.producto or m.Producto.query.get(detalle.id_producto)
    consumo_stock = _consumo_stock_linea(detalle, producto, factor_venta_stock)
    if consumo_stock <= 0:
        return 0
    if _punto_retiro_efectivo_linea(venta, detalle) == 'Bodega':
        return 0
    ya_bod = venta_consumo_ya_despachado_bodega(venta, detalle.id)
    return max(0, consumo_stock - ya_bod)


def consumo_stock_comprometido_tienda_producto(producto, excluir_venta_id=None, caja_id=None):
    """
    Stock base en tienda ya comprometido en otros vales Abierta o Pendiente (sin cobrar).
    No cuenta la venta excluida (vale POS actual). Opcional: solo la misma caja.
    """
    import app as m

    DetalleVenta = m.DetalleVenta
    Venta = m.Venta
    if not producto:
        return 0
    factor = m._factor_venta_a_stock(producto)
    if factor <= 0:
        return 0
    pid = int(producto.id)
    q = (
        m.db.session.query(DetalleVenta, Venta)
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(
            DetalleVenta.id_producto == pid,
            Venta.estado.in_(('Pendiente', 'Abierta')),
        )
    )
    if caja_id:
        q = q.filter(Venta.caja_id == int(caja_id))
    if excluir_venta_id:
        q = q.filter(Venta.id != int(excluir_venta_id))
    total = 0
    for det, venta in q.all():
        if getattr(det, 'a_pedido', False):
            continue
        total += _consumo_tienda_linea(venta, det, factor)
    return int(total)


def venta_pendiente_con_producto(producto_id, excluir_venta_id=None, caja_id=None):
    """Primer vale Pendiente en cola de caja que incluye el producto (aviso POS)."""
    import app as m

    q = (
        m.db.session.query(m.Venta)
        .join(m.DetalleVenta, m.DetalleVenta.id_venta == m.Venta.id)
        .filter(
            m.DetalleVenta.id_producto == int(producto_id),
            m.Venta.estado == 'Pendiente',
        )
        .order_by(m.Venta.prioridad.asc().nulls_last(), m.Venta.id.asc())
    )
    if caja_id:
        q = q.filter(m.Venta.caja_id == int(caja_id))
    if excluir_venta_id:
        q = q.filter(m.Venta.id != int(excluir_venta_id))
    return q.first()


def consumo_tienda_agrupado_por_producto(venta):
    """
    Suma consumo en tienda (unidades stock base) por id_producto en el vale.
    Retorna dict {producto_id: {'consumo': int, 'nombre': str}}.
    """
    import app as m
    from collections import defaultdict

    Producto = m.Producto
    agrupado = defaultdict(lambda: {'consumo': 0, 'nombre': ''})
    if not venta:
        return {}
    try:
        detalles = list(venta.detalles or [])
    except Exception:
        m.db.session.rollback()
        return {}
    for d in detalles:
        if getattr(d, 'a_pedido', False):
            continue
        producto = d.producto or Producto.query.get(d.id_producto)
        if not producto:
            continue
        factor_venta_stock = m._factor_venta_a_stock(producto)
        consumo_stock = _consumo_stock_linea(d, producto, factor_venta_stock)
        consumo_tienda = _consumo_tienda_linea(venta, d, factor_venta_stock)
        if consumo_stock <= 0:
            agrupado[producto.id]['invalido'] = True
            agrupado[producto.id]['nombre'] = producto.nombre
            continue
        agrupado[producto.id]['consumo'] += consumo_tienda
        agrupado[producto.id]['nombre'] = producto.nombre
    return dict(agrupado)


def venta_validar_stock_tienda(venta):
    """Lista de mensajes de faltantes para cobrar vale en tienda (vacía si ok)."""
    import app as m

    Producto = m.Producto
    faltantes = []
    if not venta:
        return faltantes
    try:
        agrupado = consumo_tienda_agrupado_por_producto(venta)
    except Exception as ex:
        m.db.session.rollback()
        m.app.logger.exception(
            'No se pudo cargar detalle de venta %s para validar stock: %s',
            getattr(venta, 'id', None),
            ex,
        )
        return ['No se pudo validar stock del vale (revise detalle).']
    for pid, info in agrupado.items():
        try:
            if info.get('invalido'):
                faltantes.append(f'{info.get("nombre") or pid}: conversión inválida.')
                continue
            need = int(info.get('consumo') or 0)
            if need <= 0:
                continue
            producto = Producto.query.get(pid)
            if not producto:
                faltantes.append('Producto no encontrado en línea de venta.')
                continue
            disp = stock_disponible_venta_tienda(producto)
            comprometido = consumo_stock_comprometido_tienda_producto(
                producto,
                excluir_venta_id=getattr(venta, 'id', None),
                caja_id=getattr(venta, 'caja_id', None),
            )
            if disp < comprometido + need:
                faltantes.append(
                    f'{producto.nombre} (disponible tienda: {disp}, '
                    f'comprometido otros vales: {comprometido}, requerido este vale: {need})'
                )
        except Exception as ex:
            m.db.session.rollback()
            m.app.logger.exception('No se pudo validar stock producto %s: %s', pid, ex)
            faltantes.append('No se pudo validar una línea del vale.')
    return faltantes
