"""Carga manual precio venta SD + stock piloto mostrador (fase SD-1, sin Radar)."""
from __future__ import annotations

from typing import Any

MOTIVO_PREFIJO = 'Piloto SD'
MODOS_STOCK_VALIDOS = frozenset({'inicial', 'reemplazar', 'sumar', 'restar', 'solo_precio', 'no_tocar'})
EXCLUIR_BARRA_PILOTO = ('TEST-%', 'DEMO_%', 'DEMO-%')


def _query_productos_piloto_stats(Producto, db):
    """Activos del maestro excluyendo QA/DEMO (no son piloto mostrador)."""
    from sqlalchemy import or_

    q = Producto.query.filter(Producto.activo == True)  # noqa: E712
    conds = []
    for pat in EXCLUIR_BARRA_PILOTO:
        conds.append(Producto.codigo_barra.ilike(pat))
        conds.append(Producto.codigo_interno.ilike(pat))
    if conds:
        q = q.filter(~or_(*conds))
    return q


def _normalizar_ref_documento(val: str | None, max_len: int = 64) -> str | None:
    s = (val or '').strip()
    if not s:
        return None
    return s[:max_len]


def _asegurar_columnas_bitacora_piloto(db, app) -> None:
    """ALTER legacy: factura y guía proveedor (trazabilidad piloto / SII resumen)."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(db.engine)
        if 'bitacora_piloto_mostrador' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('bitacora_piloto_mostrador')}
        dn = (db.engine.dialect.name or '').lower()
        cambios = False
        if 'numero_factura' not in cols:
            if dn == 'postgresql':
                db.session.execute(text(
                    'ALTER TABLE bitacora_piloto_mostrador '
                    'ADD COLUMN IF NOT EXISTS numero_factura VARCHAR(64)'
                ))
            else:
                db.session.execute(text(
                    'ALTER TABLE bitacora_piloto_mostrador '
                    'ADD COLUMN numero_factura VARCHAR(64)'
                ))
            cambios = True
        if 'numero_guia' not in cols:
            if dn == 'postgresql':
                db.session.execute(text(
                    'ALTER TABLE bitacora_piloto_mostrador '
                    'ADD COLUMN IF NOT EXISTS numero_guia VARCHAR(64)'
                ))
            else:
                db.session.execute(text(
                    'ALTER TABLE bitacora_piloto_mostrador '
                    'ADD COLUMN numero_guia VARCHAR(64)'
                ))
            cambios = True
        if cambios:
            db.session.commit()
    except Exception as ex:
        db.session.rollback()
        app.logger.warning('Columnas bitacora piloto (factura/guía): %s', ex)


def _asegurar_bitacora_piloto_mostrador() -> bool:
    from app import BitacoraPilotoMostrador, app, db
    from sqlalchemy import inspect

    if app.config.get('_BITACORA_PILOTO_MOSTRADOR_OK'):
        return True
    try:
        if 'bitacora_piloto_mostrador' not in inspect(db.engine).get_table_names():
            BitacoraPilotoMostrador.__table__.create(db.engine, checkfirst=True)
        _asegurar_columnas_bitacora_piloto(db, app)
        app.config['_BITACORA_PILOTO_MOSTRADOR_OK'] = True
        return True
    except Exception:
        return False


def stats_precios_piloto() -> dict[str, int]:
    from app import Producto, db

    q = _query_productos_piloto_stats(Producto, db)
    total = q.count()
    sin_precio = q.filter(
        db.or_(Producto.precio_venta_sd.is_(None), Producto.precio_venta_sd <= 0)
    ).count()
    con_precio = q.filter(Producto.precio_venta_sd > 0).count()
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
        'numero_factura': (getattr(row, 'numero_factura', None) or '').strip() or None,
        'numero_guia': (getattr(row, 'numero_guia', None) or '').strip() or None,
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
    costo = float(producto.precio_compra or 0)
    ref_venta = lista if lista > 0 else (pm if pm > 0 else ef)
    costo_incoherente = False
    costo_alerta = ''
    if costo > 0 and ref_venta > 0 and costo > ref_venta * 1.25:
        costo_incoherente = True

    # Calculate stock valorizado
    total_stock_disponible = int(st.get('tienda') or 0) + int(st.get('bodega') or 0)
    stock_valorizado = total_stock_disponible * sd if sd > 0 else 0
    if costo_incoherente:
        costo_alerta = (
            f'El costo en catálogo (${costo:,.0f}) supera la lista/mayoreo '
            f'(${ref_venta:,.0f}). Revise precio_compra en maestro o última compra.'
        ).replace(',', '.')
    margen_cat = None
    if costo > 0 and ref_venta > 0 and ref_venta >= costo:
        margen_cat = round((ref_venta - costo) / ref_venta * 100, 1)
    return {
        'id': producto.id,
        'nombre': producto.nombre or '',
        'codigo': codigo,
        'costo': costo,
        'costo_incoherente': costo_incoherente,
        'costo_alerta': costo_alerta,
        'margen_catalogo_pct': margen_cat,
        'precio_lista': lista,
        'precio_mayoreo': pm,
        'precio_venta_sd': sd,
        'precio_efectivo': ef,
        'precio_sd_sugerido': int(round(lista if lista > 0 else (pm if pm > 0 else 0))),
        'sin_precio': ef <= 0,
        'stock_tienda': int(st.get('tienda') or 0),
        'stock_bodega': int(st.get('bodega') or 0),
        'stock_valorizado': stock_valorizado,
        'categoria': (producto.categoria or '').strip() or '—',
        'ubicacion_pasillo': (getattr(producto, 'ubicacion_pasillo', '') or '').strip() or '—',
        'unidad_venta': (getattr(producto, 'unidad_venta', '') or getattr(producto, 'unidad', '') or '').strip() or '—',
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

    from app import fijar_stock_almacen

    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    st = _stock_ui_producto(producto)
    antes = {'tienda': int(st.get('tienda') or 0), 'bodega': int(st.get('bodega') or 0)}
    despues = dict(antes)
    delta_t = delta_b = 0

    pid = int(producto.id)
    user = (usuario or 'piloto')[:100]

    if modo in ('inicial', 'reemplazar'):
        if stock_tienda is not None and aid_t:
            objetivo_t = max(0, int(stock_tienda))
            fijar_stock_almacen(pid, aid_t, objetivo_t)
            delta_t = objetivo_t - antes['tienda']
            despues['tienda'] = objetivo_t
            if delta_t != 0:
                registrar_movimiento_kardex(
                    pid,
                    'Ajuste' if delta_t > 0 else 'Salida',
                    abs(delta_t),
                    motivo_kardex[:250],
                    usuario=user,
                    id_almacen=aid_t,
                )
        if stock_bodega is not None and aid_b:
            objetivo_b = max(0, int(stock_bodega))
            fijar_stock_almacen(pid, aid_b, objetivo_b)
            delta_b = objetivo_b - antes['bodega']
            despues['bodega'] = objetivo_b
            if delta_b != 0:
                registrar_movimiento_kardex(
                    pid,
                    'Ajuste' if delta_b > 0 else 'Salida',
                    abs(delta_b),
                    motivo_kardex[:250],
                    usuario=user,
                    id_almacen=aid_b,
                )
    elif modo in ('sumar', 'restar'):
        factor = -1 if modo == 'restar' else 1
        delta_t = int(stock_tienda or 0) * factor
        delta_b = int(stock_bodega or 0) * factor
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
    else:
        return antes, despues, 'Modo de stock inválido.'

    _refrescar_stock_total_producto(producto)
    return antes, despues, None


def guardar_carga_piloto_mostrador(
    *,
    producto_id: int,
    precio_nuevo: float | None = None,
    motivo: str | None = None,
    usuario: str | None,
    modo_stock: str = 'no_tocar',
    stock_tienda: int | None = None,
    stock_bodega: int | None = None,
    sector_ubicacion: str | None = None,
    categoria: str | None = None,
    ubicacion_pasillo: str | None = None,
    unidad_venta: str | None = None,
    numero_factura: str | None = None,
    numero_guia: str | None = None,
    nombre: str | None = None,
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

    motivo_txt = (motivo or 'Ajuste rápido desde vista productos').strip()
    if motivo_txt and not motivo_txt.lower().startswith(MOTIVO_PREFIJO.lower()):
        motivo_txt = f'{MOTIVO_PREFIJO}: {motivo_txt}'

    modo = (modo_stock or 'no_tocar').strip().lower()
    if modo not in MODOS_STOCK_VALIDOS:
        return {'ok': False, 'error': 'modo_stock_invalido'}

    sector = (sector_ubicacion or '').strip()[:120] or None
    ref_factura = _normalizar_ref_documento(numero_factura)
    ref_guia = _normalizar_ref_documento(numero_guia)
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

    # Actualización de metadatos del producto (Gestión SD-1)
    if categoria:
        p.categoria = categoria.strip()[:50]
    if nombre:
        p.nombre = nombre.strip()[:150]
    if ubicacion_pasillo is not None:
        p.ubicacion_pasillo = ubicacion_pasillo.strip()[:12]
    if unidad_venta:
        p.unidad_venta = unidad_venta.strip()[:20]

    modo_stock_efectivo = modo
    st_t = stock_tienda
    st_b = stock_bodega
    if modo == 'solo_precio' and (stock_tienda is not None or stock_bodega is not None):
        modo_stock_efectivo = 'sumar'
        st_t = int(stock_tienda or 0)
        st_b = int(stock_bodega or 0)

    if modo_stock_efectivo in ('inicial', 'reemplazar', 'sumar', 'restar'):
        if st_t is None and st_b is None:
            return {
                'ok': False,
                'error': 'stock_requerido',
                'mensaje': 'Indique stock tienda y/o bodega para este modo.',
            }

    try:
        err_stock = None
        antes_st = despues_st = {'tienda': 0, 'bodega': 0}
        delta_t = delta_b = 0

        if modo_stock_efectivo not in ('solo_precio', 'no_tocar'):
            antes_st, despues_st, err_stock = _aplicar_stock_piloto(
                p,
                modo_stock=modo_stock_efectivo,
                stock_tienda=st_t,
                stock_bodega=st_b,
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
                    modo_stock=modo_stock_efectivo,
                    sector_ubicacion=sector,
                    numero_factura=ref_factura,
                    numero_guia=ref_guia,
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
        'modo_stock': modo_stock_efectivo,
        'numero_factura': ref_factura,
        'numero_guia': ref_guia,
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


def actualizar_producto_enrolado(
    *,
    producto_id: int,
    categoria: str | None = None,
    ubicacion_pasillo: str | None = None,
    stock_tienda: int | None = None,
    stock_bodega: int | None = None,
    precio_venta_sd: float | None = None,
    nombre: str | None = None,
    usuario: str | None = None,
    motivo: str = 'Ajuste enrolado',
) -> dict[str, Any]:
    """
    Actualiza campos de un producto desde la vista de ajuste de productos enrolados.
    Utiliza guardar_carga_piloto_mostrador para aplicar los cambios.
    """
    # Determine the effective modo_stock. If any stock is provided, we'll use 'reemplazar'.
    # Otherwise, 'solo_precio' or 'no_tocar' if only metadata/price is updated.
    modo_stock_efectivo = 'no_tocar'
    if stock_tienda is not None or stock_bodega is not None:
        modo_stock_efectivo = 'reemplazar'
    elif precio_venta_sd is not None:
        modo_stock_efectivo = 'solo_precio'

    return guardar_carga_piloto_mostrador(
        producto_id=producto_id,
        precio_nuevo=precio_venta_sd,
        motivo=motivo,
        usuario=usuario,
        modo_stock=modo_stock_efectivo,
        stock_tienda=stock_tienda,
        stock_bodega=stock_bodega,
        categoria=categoria,
        ubicacion_pasillo=ubicacion_pasillo,
        unidad_venta=None,  # unidad_venta no es un campo solicitado para edición aquí
        numero_factura=None,
        numero_guia=None,
        nombre=nombre,
    )


def _codigo_producto_bitacora(producto) -> str:
    if not producto:
        return '—'
    return (
        (producto.codigo_barra or '').strip()
        or (producto.codigo_interno or '').strip()
        or (producto.codigo_chilemat or '').strip()
        or '—'
    )


def _fmt_fecha_informe(dt) -> str:
    if not dt:
        return '—'
    try:
        return dt.strftime('%d-%m-%Y %H:%M')
    except Exception:
        return '—'


def resumen_facturas_piloto(*, q: str | None = None, limite: int = 200) -> dict[str, Any]:
    """Agrupa bitácora piloto por número de factura proveedor."""
    from app import BitacoraPilotoMostrador, db
    from sqlalchemy import func

    vacio = {'facturas': [], 'sin_factura_lineas': 0, 'total_facturas': 0}
    if not _asegurar_bitacora_piloto_mostrador():
        return vacio

    sin_factura = (
        BitacoraPilotoMostrador.query.filter(
            db.or_(
                BitacoraPilotoMostrador.numero_factura.is_(None),
                BitacoraPilotoMostrador.numero_factura == '',
            )
        ).count()
    )

    qn = (q or '').strip()
    lim = max(1, min(int(limite or 200), 500))
    query = (
        db.session.query(
            BitacoraPilotoMostrador.numero_factura.label('numero_factura'),
            func.count(BitacoraPilotoMostrador.id).label('lineas'),
            func.count(func.distinct(BitacoraPilotoMostrador.producto_id)).label('productos'),
            func.min(BitacoraPilotoMostrador.fecha).label('fecha_primera'),
            func.max(BitacoraPilotoMostrador.fecha).label('fecha_ultima'),
            func.sum(BitacoraPilotoMostrador.precio_nuevo).label('suma_precio_sd'),
            func.max(BitacoraPilotoMostrador.numero_guia).label('numero_guia'),
            func.max(BitacoraPilotoMostrador.usuario).label('usuario_reciente'),
        )
        .filter(
            BitacoraPilotoMostrador.numero_factura.isnot(None),
            BitacoraPilotoMostrador.numero_factura != '',
        )
        .group_by(BitacoraPilotoMostrador.numero_factura)
        .order_by(func.max(BitacoraPilotoMostrador.fecha).desc())
    )
    if qn:
        query = query.filter(BitacoraPilotoMostrador.numero_factura.ilike(f'%{qn}%'))

    filas = []
    for row in query.limit(lim).all():
        nf = (row.numero_factura or '').strip()
        if not nf:
            continue
        filas.append({
            'numero_factura': nf,
            'numero_guia': (row.numero_guia or '').strip() or None,
            'lineas': int(row.lineas or 0),
            'productos': int(row.productos or 0),
            'fecha_primera': _fmt_fecha_informe(row.fecha_primera),
            'fecha_ultima': _fmt_fecha_informe(row.fecha_ultima),
            'fecha_ultima_raw': row.fecha_ultima,
            'suma_precio_sd': float(row.suma_precio_sd or 0),
            'usuario_reciente': (row.usuario_reciente or '').strip() or '—',
        })

    return {
        'facturas': filas,
        'sin_factura_lineas': int(sin_factura),
        'total_facturas': len(filas),
    }


def detalle_informe_factura_piloto(numero_factura: str) -> dict[str, Any] | None:
    """Líneas de bitácora asociadas a una factura."""
    from app import BitacoraPilotoMostrador
    from sqlalchemy.orm import joinedload

    ref = _normalizar_ref_documento(numero_factura)
    if not ref or not _asegurar_bitacora_piloto_mostrador():
        return None

    rows = (
        BitacoraPilotoMostrador.query.options(joinedload(BitacoraPilotoMostrador.producto))
        .filter(BitacoraPilotoMostrador.numero_factura == ref)
        .order_by(BitacoraPilotoMostrador.fecha.desc(), BitacoraPilotoMostrador.id.desc())
        .all()
    )
    if not rows:
        return None

    lineas = []
    productos_ids: set[int] = set()
    suma_sd = 0.0
    guias: set[str] = set()
    usuarios: set[str] = set()

    for r in rows:
        pid = int(r.producto_id or 0)
        productos_ids.add(pid)
        pn = float(r.precio_nuevo or 0)
        suma_sd += pn
        g = (r.numero_guia or '').strip()
        if g:
            guias.add(g)
        u = (r.usuario or '').strip()
        if u:
            usuarios.add(u)
        p = r.producto
        lineas.append({
            'id': r.id,
            'fecha': _fmt_fecha_informe(r.fecha),
            'producto_id': pid,
            'nombre': (p.nombre if p else '') or f'#{pid}',
            'codigo': _codigo_producto_bitacora(p),
            'precio_anterior': float(r.precio_anterior or 0),
            'precio_nuevo': pn,
            'stock_tienda_despues': int(r.stock_tienda_despues or 0),
            'stock_bodega_despues': int(r.stock_bodega_despues or 0),
            'delta_tienda': int(r.delta_tienda or 0),
            'delta_bodega': int(r.delta_bodega or 0),
            'modo_stock': (r.modo_stock or '').strip(),
            'sector': (r.sector_ubicacion or '').strip() or '—',
            'numero_guia': g or '—',
            'usuario': u or '—',
            'motivo': (r.motivo or '').strip() or '—',
        })

    return {
        'numero_factura': ref,
        'lineas': lineas,
        'resumen': {
            'lineas': len(lineas),
            'productos': len(productos_ids),
            'suma_precio_sd': suma_sd,
            'guias': sorted(guias),
            'usuarios': sorted(usuarios),
            'fecha_primera': _fmt_fecha_informe(rows[-1].fecha),
            'fecha_ultima': _fmt_fecha_informe(rows[0].fecha),
        },
    }


def filas_csv_informe_facturas_piloto(
    *,
    numero_factura: str | None = None,
    q: str | None = None,
) -> tuple[list[str], list[list]]:
    """Cabecera + filas CSV (detalle de una factura o listado resumido)."""
    headers_detalle = [
        'numero_factura',
        'numero_guia',
        'fecha',
        'producto_id',
        'codigo',
        'nombre',
        'precio_anterior',
        'precio_nuevo',
        'stock_tienda',
        'stock_bodega',
        'delta_tienda',
        'delta_bodega',
        'modo_stock',
        'sector',
        'usuario',
        'motivo',
    ]
    ref = _normalizar_ref_documento(numero_factura)
    if ref:
        det = detalle_informe_factura_piloto(ref)
        if not det:
            return headers_detalle, []
        filas = []
        for ln in det['lineas']:
            filas.append([
                ref,
                ln['numero_guia'] if ln['numero_guia'] != '—' else '',
                ln['fecha'],
                ln['producto_id'],
                ln['codigo'],
                ln['nombre'],
                f"{ln['precio_anterior']:.0f}",
                f"{ln['precio_nuevo']:.0f}",
                ln['stock_tienda_despues'],
                ln['stock_bodega_despues'],
                ln['delta_tienda'],
                ln['delta_bodega'],
                ln['modo_stock'],
                ln['sector'] if ln['sector'] != '—' else '',
                ln['usuario'] if ln['usuario'] != '—' else '',
                ln['motivo'] if ln['motivo'] != '—' else '',
            ])
        return headers_detalle, filas

    headers_resumen = [
        'numero_factura',
        'numero_guia',
        'lineas',
        'productos',
        'fecha_primera',
        'fecha_ultima',
        'suma_precio_sd',
        'usuario_reciente',
    ]
    data = resumen_facturas_piloto(q=q, limite=500)
    filas = []
    for f in data['facturas']:
        filas.append([
            f['numero_factura'],
            f['numero_guia'] or '',
            f['lineas'],
            f['productos'],
            f['fecha_primera'],
            f['fecha_ultima'],
            f"{f['suma_precio_sd']:.0f}",
            f['usuario_reciente'],
        ])
    return headers_resumen, filas


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
