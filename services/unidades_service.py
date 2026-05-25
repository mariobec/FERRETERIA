"""Catálogo unidades de medida (detección de tabla, seed base, factores compra/venta → stock)."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text

_UNIDADES_PESO = frozenset({'KG', 'KILO', 'KILOGRAMO', 'GR', 'G', 'GRAMO', 'GRAMOS'})


def unidades_disponibles():
    import app as m

    estado = m.app.config.get('_UNIDADES_OK')
    if estado is not None:
        return bool(estado)
    try:
        ok = m.db.session.execute(
            text(
                'SELECT 1 FROM information_schema.tables '
                "WHERE table_schema = DATABASE() AND table_name = 'unidades_medida' LIMIT 1"
            )
        ).scalar() is not None
    except Exception:
        ok = False
    m.app.config['_UNIDADES_OK'] = bool(ok)
    return bool(ok)


def seed_unidades_base():
    import app as m

    UnidadMedida = m.UnidadMedida
    if not unidades_disponibles():
        return
    base = [
        ('UN', 'Unidad', 'unidad'),
        ('KG', 'Kilogramo', 'peso'),
        ('M', 'Metro', 'longitud'),
        ('CJ', 'Caja', 'empaque'),
        ('SC', 'Saco', 'empaque'),
        ('RL', 'Rollo', 'empaque'),
        ('LT', 'Litro', 'volumen'),
    ]
    cambios = False
    for codigo, nombre, tipo in base:
        ex = UnidadMedida.query.filter_by(codigo=codigo).first()
        if not ex:
            m.db.session.add(UnidadMedida(codigo=codigo, nombre=nombre, tipo=tipo, activo=True))
            cambios = True
    if cambios:
        m.db.session.commit()


def factor_compra_a_stock(producto):
    """
    Define cuánto stock (unidad de venta/base) ingresa por 1 unidad de compra.
    Prioriza tabla de conversiones; si no existe, usa factor_conversion del producto.
    """
    import app as m

    UnidadMedida = m.UnidadMedida
    ConversionUnidad = m.ConversionUnidad
    if not producto:
        return 1.0

    uc = (producto.unidad_compra or '').strip().upper()
    uv = (producto.unidad_venta or producto.unidad or '').strip().upper()
    if uc and uv and uc == uv:
        return 1.0

    if unidades_disponibles() and uc and uv:
        try:
            u_origen = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uc) | (UnidadMedida.nombre.ilike(uc))
            ).first()
            u_destino = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uv) | (UnidadMedida.nombre.ilike(uv))
            ).first()
            if u_origen and u_destino:
                conv = ConversionUnidad.query.filter_by(
                    unidad_origen_id=u_origen.id,
                    unidad_destino_id=u_destino.id,
                    activo=True,
                ).first()
                if conv and float(conv.factor or 0) > 0:
                    return float(conv.factor)
        except Exception:
            pass

    try:
        f = float(producto.factor_conversion or 1)
    except Exception:
        f = 1
    return f if f > 0 else 1.0


def factor_venta_a_stock(producto):
    """
    Cuánto stock base se descuenta por 1 unidad de venta.
    Prioriza catálogo de conversiones (unidad_venta -> unidad base/legacy).
    Fallback: 1 (comportamiento actual), para no romper operación existente.
    """
    import app as m

    UnidadMedida = m.UnidadMedida
    ConversionUnidad = m.ConversionUnidad
    if not producto:
        return 1.0

    uv = (producto.unidad_venta or producto.unidad or '').strip().upper()
    ub = (producto.unidad or producto.unidad_venta or '').strip().upper()
    if uv and ub and uv == ub:
        return 1.0

    if unidades_disponibles() and uv and ub:
        try:
            u_origen = UnidadMedida.query.filter(
                (UnidadMedida.codigo == uv) | (UnidadMedida.nombre.ilike(uv))
            ).first()
            u_destino = UnidadMedida.query.filter(
                (UnidadMedida.codigo == ub) | (UnidadMedida.nombre.ilike(ub))
            ).first()
            if u_origen and u_destino:
                conv = ConversionUnidad.query.filter_by(
                    unidad_origen_id=u_origen.id,
                    unidad_destino_id=u_destino.id,
                    activo=True,
                ).first()
                if conv and float(conv.factor or 0) > 0:
                    return float(conv.factor)
        except Exception:
            pass
    return 1.0


def _codigo_unidad_producto(producto, campo: str = 'venta') -> str:
    if not producto:
        return ''
    if campo == 'compra':
        raw = producto.unidad_compra or producto.unidad or ''
    else:
        raw = producto.unidad_venta or producto.unidad or ''
    return (raw or '').strip().upper()


def es_unidad_peso_producto(producto) -> bool:
    """True si la unidad de venta es peso (pernería, clavos por kg, alambre)."""
    uv = _codigo_unidad_producto(producto, 'venta')
    if uv in _UNIDADES_PESO:
        return True
    return uv.startswith('KG') or uv.startswith('GR')


def consumo_stock_entero_desde_cantidad(cantidad, producto) -> int:
    """
    Invariante LhexIA: consumo de stock en enteros (gramos/unidades puras).
    Evita mermas fantasma por float en productos fraccionables por peso.
    """
    qty = Decimal(str(cantidad or 0))
    if qty <= 0:
        return 0
    factor = Decimal(str(factor_venta_a_stock(producto)))
    consumo = qty * factor
    if es_unidad_peso_producto(producto):
        uv = _codigo_unidad_producto(producto, 'venta')
        if uv in ('KG', 'KILO', 'KILOGRAMO'):
            consumo = qty * Decimal('1000') * factor
        return max(0, int(consumo.to_integral_value(rounding=ROUND_HALF_UP)))
    return max(0, int(consumo.to_integral_value(rounding=ROUND_HALF_UP)))
