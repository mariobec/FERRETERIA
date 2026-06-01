"""Carga manual precio venta SD + stock piloto mostrador (fase SD-1, sin Radar)."""
from __future__ import annotations

from typing import Any

MOTIVO_PREFIJO = 'Piloto SD'
MODOS_STOCK_VALIDOS = frozenset({'inicial', 'reemplazar', 'sumar', 'solo_precio', 'no_tocar'})


def _asegurar_bitacora_piloto_mostrador() -> bool:
    from app import BitacoraPilotoMostrador, app, db
    from sqlalchemy import inspect

    if app.config.get('_BITACORA_PILOTO_MOSTRADOR_OK'):
        return True
    try:
        if 'bitacora_piloto_mostrador' not in inspect(db.engine).get_table_names():
            BitacoraPilotoMostrador.__table__.create(db.engine, checkfirst=True)
        app.config['_BITACORA_PILOTO_MOSTRADOR_OK'] = True
        return True
    except Exception:
        return False


def stats_precios_piloto() -> dict[str, int]:
    from app import Producto, db
    from sqlalchemy import func

    q = Producto.query.filter(Producto.activo == True)  # noqa: E712
    total = q.count()
    sin_precio = q.filter(
        db.or_(Producto.precio_venta_sd.is_(None), Producto.precio_venta_sd <= 0)
    ).count()
    con_precio = (
        db.session.query(func.count(Producto.id))
        .filter(Producto.activo == True)  # noqa: E712
        .filter(Producto.precio_venta_sd > 0)
        .scalar()
        or 0
    )
    return {
        'total_activos': int(total),
        'sin_precio': int(sin_precio),
        'con_precio': int(con_precio),
    }


def ultima_carga_piloto_producto(producto_id: int) -> dict[str, Any] | None:
    from app import BitacoraPilotoMostrador

    if not _asegurar_bitacora_piloto_mostrador():
        return None
    row = (
        BitacoraPilotoMostrador.query.filter_by(producto_id=int(producto_id))
        .order_by(BitacoraPilotoMostrador.id.desc())
        .first()
    )
    if not row:
        return None
    fecha = row.fecha
    return {
        'fecha': fecha.strftime('%d-%m-%Y %H:%M') if fecha else '—',
        'usuario': (row.usuario or '—').strip(),
        'sector': (row.sector_ubicacion or '').strip() or '—',
        'modo_stock': (row.modo_stock or '').strip(),
        'stock_tienda_despues': int(row.stock_tienda_despues or 0),
        'stock_bodega_despues': int(row.stock_bodega_despues or 0),
        'precio_nuevo': float(row.precio_nuevo or 0),
        'delta_tienda': int(row.delta_tienda or 0),
        'delta_bodega': int(row.delta_bodega or 0),
    }


def serializar_producto_precios_piloto(producto) -> dict[str, Any]:
    from app import _stock_ui_producto, precio_efectivo_pos_producto

    st = _stock_ui_producto(producto)
    lista = float(producto.precio_venta or 0)
    pm = float(producto.precio_mayoreo or 0)
    sd = float(getattr(producto, 'precio_venta_sd', None) or 0)
    ef = float(precio_efectivo_pos_producto(producto) or 0)
    codigo = (
        (producto.codigo_barra or '').strip()
        or (producto.codigo_interno or '').strip()
        or (producto.codigo_chilemat or '').strip()
        or '—'
    )
    ultima = ultima_carga_piloto_producto(int(producto.id))
    return {
        'id': producto.id,
        'nombre': producto.nombre or '',
        'codigo': codigo,
        'costo': float(producto.precio_compra or 0),
        'precio_lista': lista,
        'precio_mayoreo': pm,
        'precio_venta_sd': sd,
        'precio_efectivo': ef,
        'sin_precio': ef <= 0,
        'stock_tienda': int(st.get('tienda') or 0),
        'stock_bodega': int(st.get('bodega') or 0),
        'categoria': (producto.categoria or '').strip() or '—',
        'ultima_carga_piloto': ultima,
        'tiene_carga_previa': ultima is not None,
        'modo_stock_sugerido': 'sumar' if ultima else 'inicial',
    }


def aplicar_precio_venta_sd(producto, precio_nuevo: float) -> float:
    precio_nuevo = float(precio_nuevo)
    if precio_nuevo <= 0:
        raise ValueError('precio_invalido')
    producto.precio_venta_sd = precio_nuevo
    return precio_nuevo


def _parse_stock_opcional(val) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if s == '':
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _aplicar_stock_piloto(
    producto,
    *,
    modo_stock: str,
    stock_tienda: int | None,
    stock_bodega: int | None,
    usuario: str | None,
    motivo_kardex: str,
) -> tuple[dict[str, int], dict[str, int], str | None]:
    """Devuelve (antes, despues, error)."""
    from app import (
        _refrescar_stock_total_producto,
        _stock_ui_producto,
        _tablas_inventario_almacen_existen,
        ajustar_stock_almacen,
        id_almacen_bodega,
        id_almacen_tienda,
        registrar_movimiento_kardex,
    )

    modo = (modo_stock or 'no_tocar').strip().lower()
    if modo in ('no_tocar', 'solo_precio'):
        st = _stock_ui_producto(producto)
        tienda = int(st.get('tienda') or 0)
        bodega = int(st.get('bodega') or 0)
        return (
            {'tienda': tienda, 'bodega': bodega},
            {'tienda': tienda, 'bodega': bodega},
            None,
        )

    if not _tablas_inventario_almacen_existen():
        return {}, {}, 'Inventario por almacén no disponible en esta base.'

    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    st = _stock_ui_producto(producto)
    antes = {'tienda': int(st.get('tienda') or 0), 'bodega': int(st.get('bodega') or 0)}
    despues = dict(antes)
    delta_t = delta_b = 0

    if modo in ('inicial', 'reemplazar'):
        if stock_tienda is not None:
            delta_t = int(stock_tienda) - antes['tienda']
        if stock_bodega is not None:
            delta_b = int(stock_bodega) - antes['bodega']
    elif modo == 'sumar':
        delta_t = int(stock_tienda or 0)
        delta_b = int(stock_bodega or 0)
    else:
        return antes, despues, 'Modo de stock inválido.'

    pid = int(producto.id)
    user = (usuario or 'piloto')[:100]

    if delta_t != 0 and aid_t:
        _, err = ajustar_stock_almacen(pid, aid_t, delta_t)
        if err:
            return antes, despues, f'Tienda: {err}'
        registrar_movimiento_kardex(
            pid,
            'Ajuste' if delta_t > 0 else 'Salida',
            abs(delta_t),
            motivo_kardex[:250],
            usuario=user,
            id_almacen=aid_t,
        )
        despues['tienda'] = antes['tienda'] + delta_t

    if delta_b != 0 and aid_b:
        _, err = ajustar_stock_almacen(pid, aid_b, delta_b)
        if err:
            return antes, despues, f'Bodega: {err}'
        registrar_movimiento_kardex(
            pid,
            'Ajuste' if delta_b > 0 else 'Salida',
            abs(delta_b),
            motivo_kardex[:250],
            usuario=user,
            id_almacen=aid_b,
        )
        despues['bodega'] = antes['bodega'] + delta_b

    _refrescar_stock_total_producto(producto)
    return antes, despues, None


def guardar_carga_piloto_mostrador(
    *,
    producto_id: int,
    precio_nuevo: float | None,
    motivo: str,
    usuario: str | None,
    modo_stock: str = 'no_tocar',
    stock_tienda: int | None = None,
    stock_bodega: int | None = None,
    sector_ubicacion: str | None = None,
) -> dict[str, Any]:
    from app import (
        Producto,
        _stock_ui_producto,
        _tablas_inventario_almacen_existen,
        db,
        precio_efectivo_pos_producto,
    )
    from app import BitacoraPilotoMostrador

    p = Producto.query.get(producto_id)
    if not p:
        return {'ok': False, 'error': 'producto_no_encontrado'}
    if not p.activo:
        return {'ok': False, 'error': 'producto_inactivo'}

    _asegurar_bitacora_piloto_mostrador()

    motivo_txt = (motivo or '').strip()
    if not motivo_txt:
        return {'ok': False, 'error': 'motivo_requerido'}
    if not motivo_txt.lower().startswith(MOTIVO_PREFIJO.lower()):
        motivo_txt = f'{MOTIVO_PREFIJO}: {motivo_txt}'

    modo = (modo_stock or 'no_tocar').strip().lower()
    if modo not in MODOS_STOCK_VALIDOS:
        return {'ok': False, 'error': 'modo_stock_invalido'}

    sector = (sector_ubicacion or '').strip()[:120] or None
    precio_anterior = float(precio_efectivo_pos_producto(p) or 0)
    cambio_precio = False
    nuevo_ef = precio_anterior
    delta_t = delta_b = 0
    despues_st = {'tienda': 0, 'bodega': 0}

    if modo == 'solo_precio':
        if precio_nuevo is None or float(precio_nuevo) <= 0:
            return {'ok': False, 'error': 'precio_invalido'}

    if precio_nuevo is not None and float(precio_nuevo) > 0:
        try:
            nuevo_ef = aplicar_precio_venta_sd(p, float(precio_nuevo))
            cambio_precio = abs(precio_anterior - nuevo_ef) >= 0.01
        except ValueError:
            return {'ok': False, 'error': 'precio_invalido'}
    elif modo != 'solo_precio' and float(precio_anterior or 0) <= 0:
        return {'ok': False, 'error': 'precio_invalido'}

    if modo != 'solo_precio' and stock_tienda is None and stock_bodega is None:
        if not cambio_precio and modo in ('inicial', 'reemplazar', 'sumar'):
            return {'ok': False, 'error': 'stock_requerido'}

    try:
        err_stock = None
        antes_st = despues_st = {'tienda': 0, 'bodega': 0}
        delta_t = delta_b = 0

        if modo not in ('solo_precio', 'no_tocar'):
            antes_st, despues_st, err_stock = _aplicar_stock_piloto(
                p,
                modo_stock=modo,
                stock_tienda=stock_tienda,
                stock_bodega=stock_bodega,
                usuario=usuario,
                motivo_kardex=motivo_txt,
            )
            if err_stock:
                raise ValueError(err_stock)
            delta_t = despues_st['tienda'] - antes_st['tienda']
            delta_b = despues_st['bodega'] - antes_st['bodega']
        elif _tablas_inventario_almacen_existen():
            st = _stock_ui_producto(p)
            antes_st = despues_st = {
                'tienda': int(st.get('tienda') or 0),
                'bodega': int(st.get('bodega') or 0),
            }

        hay_cambio_stock = delta_t != 0 or delta_b != 0
        if (cambio_precio or hay_cambio_stock) and _asegurar_bitacora_piloto_mostrador():
            db.session.add(
                BitacoraPilotoMostrador(
                    producto_id=p.id,
                    precio_anterior=precio_anterior if cambio_precio else None,
                    precio_nuevo=nuevo_ef if cambio_precio else None,
                    stock_tienda_antes=antes_st['tienda'],
                    stock_bodega_antes=antes_st['bodega'],
                    stock_tienda_despues=despues_st['tienda'],
                    stock_bodega_despues=despues_st['bodega'],
                    delta_tienda=delta_t,
                    delta_bodega=delta_b,
                    modo_stock=modo,
                    sector_ubicacion=sector,
                    usuario=usuario,
                    motivo=motivo_txt,
                )
            )
        db.session.commit()
    except ValueError as ve:
        db.session.rollback()
        return {'ok': False, 'error': 'stock', 'mensaje': str(ve)}
    except Exception:
        db.session.rollback()
        raise

    if not cambio_precio and delta_t == 0 and delta_b == 0:
        return {
            'ok': True,
            'sin_cambio': True,
            'producto': serializar_producto_precios_piloto(p),
        }

    return {
        'ok': True,
        'sin_cambio': False,
        'precio_anterior': precio_anterior,
        'precio_nuevo': nuevo_ef,
        'stock': despues_st,
        'delta_tienda': delta_t,
        'delta_bodega': delta_b,
        'modo_stock': modo,
        'producto': serializar_producto_precios_piloto(p),
    }


def guardar_precio_piloto(
    *,
    producto_id: int,
    precio_nuevo: float,
    motivo: str,
    usuario: str | None,
) -> dict[str, Any]:
    """Compatibilidad: solo precio SD."""
    return guardar_carga_piloto_mostrador(
        producto_id=producto_id,
        precio_nuevo=precio_nuevo,
        motivo=motivo,
        usuario=usuario,
        modo_stock='solo_precio',
    )


def bitacora_reciente_piloto(limite: int = 20) -> list:
    from app import BitacoraPilotoMostrador, BitacoraPrecioVenta, _bitacora_precios_disponible
    from sqlalchemy.orm import joinedload

    filas: list = []
    if _asegurar_bitacora_piloto_mostrador():
        lim = max(1, min(int(limite or 20), 100))
        filas = (
            BitacoraPilotoMostrador.query.options(joinedload(BitacoraPilotoMostrador.producto))
            .order_by(BitacoraPilotoMostrador.id.desc())
            .limit(lim)
            .all()
        )
    if filas:
        return filas
    if not _bitacora_precios_disponible():
        return []
    limite = max(1, min(int(limite or 20), 100))
    return (
        BitacoraPrecioVenta.query.options(joinedload(BitacoraPrecioVenta.producto))
        .filter(BitacoraPrecioVenta.motivo.ilike(f'{MOTIVO_PREFIJO}%'))
        .order_by(BitacoraPrecioVenta.id.desc())
        .limit(limite)
        .all()
    )
