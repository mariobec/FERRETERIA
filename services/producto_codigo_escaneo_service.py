"""Alias de códigos escaneados en mostrador (POS) → producto maestro."""
from __future__ import annotations

from typing import Any


def normalizar_codigo_escaneo(codigo: str | None) -> str:
    return (codigo or '').strip().upper()[:50]


def asegurar_tabla_producto_codigo_escaneo(app, db) -> bool:
    """Crea `producto_codigo_escaneo` si no existe."""
    if app.config.get('_PRODUCTO_CODIGO_ESCANEO_TABLE_OK'):
        return True
    try:
        from app import ProductoCodigoEscaneo

        ProductoCodigoEscaneo.__table__.create(bind=db.engine, checkfirst=True)
        db.session.commit()
        app.config['_PRODUCTO_CODIGO_ESCANEO_TABLE_OK'] = True
        return True
    except Exception as ex:
        db.session.rollback()
        app.logger.warning('No se pudo crear tabla producto_codigo_escaneo: %s', ex)
        return False


def buscar_producto_por_alias(
    codigo: str,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
) -> Any | None:
    """Resuelve producto activo por fila en producto_codigo_escaneo."""
    if not asegurar_tabla_producto_codigo_escaneo(app, db):
        return None
    cnorm = normalizar_codigo_escaneo(codigo)
    if not cnorm:
        return None
    row = (
        ProductoCodigoEscaneo.query.filter_by(codigo=cnorm, activo=True)
        .first()
    )
    if not row:
        return None
    p = Producto.query.get(int(row.producto_id))
    if not p or not getattr(p, 'activo', True):
        return None
    return p


def codigo_escaneo_ocupado(
    codigo: str,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
    excluir_producto_id: int | None = None,
) -> bool:
    """True si el código está en codigo_barra de otro producto o en alias activo."""
    cnorm = normalizar_codigo_escaneo(codigo)
    if not cnorm:
        return False
    q = Producto.query.filter(
        db.func.upper(db.func.trim(Producto.codigo_barra)) == cnorm
    )
    if excluir_producto_id:
        q = q.filter(Producto.id != int(excluir_producto_id))
    if q.first():
        return True
    if not asegurar_tabla_producto_codigo_escaneo(app, db):
        return False
    aq = ProductoCodigoEscaneo.query.filter_by(codigo=cnorm, activo=True)
    if excluir_producto_id:
        aq = aq.filter(ProductoCodigoEscaneo.producto_id != int(excluir_producto_id))
    return aq.first() is not None


def producto_que_ocupa_codigo(
    codigo: str,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
) -> Any | None:
    """Producto que ya usa este código (maestro o alias), para mensajes de conflicto."""
    cnorm = normalizar_codigo_escaneo(codigo)
    if not cnorm:
        return None
    p = (
        Producto.query.filter(
            db.func.upper(db.func.trim(Producto.codigo_barra)) == cnorm
        )
        .first()
    )
    if p:
        return p
    if not asegurar_tabla_producto_codigo_escaneo(app, db):
        return None
    row = ProductoCodigoEscaneo.query.filter_by(codigo=cnorm, activo=True).first()
    if row:
        return Producto.query.get(int(row.producto_id))
    return None


def vincular_codigo_a_producto(
    codigo: str,
    producto_id: int,
    *,
    Producto,
    ProductoCodigoEscaneo,
    db,
    app,
    usuario: str | None = None,
    tipo: str = 'pos_vinculo',
    origen: str = 'pos',
) -> dict:
    """
    Persiste alias escaneado → producto. No mueve stock.
    Retorna dict con ok, error, mensaje, producto_id, codigo.
    """
    cnorm = normalizar_codigo_escaneo(codigo)
    if not cnorm:
        return {'ok': False, 'error': 'codigo_requerido', 'mensaje': 'Código vacío.'}
    try:
        pid = int(producto_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'producto_invalido', 'mensaje': 'Producto inválido.'}
    p = Producto.query.get(pid)
    if not p or not getattr(p, 'activo', True):
        return {'ok': False, 'error': 'producto_no_encontrado', 'mensaje': 'Producto no encontrado.'}
    maestro = (p.codigo_barra or '').strip().upper()
    if maestro and maestro == cnorm:
        return {
            'ok': True,
            'ya_era_maestro': True,
            'producto_id': pid,
            'codigo': cnorm,
            'mensaje': 'El código ya es el SKU maestro de este producto.',
        }
    if codigo_escaneo_ocupado(
        cnorm,
        Producto=Producto,
        ProductoCodigoEscaneo=ProductoCodigoEscaneo,
        db=db,
        app=app,
        excluir_producto_id=pid,
    ):
        otro = producto_que_ocupa_codigo(
            cnorm,
            Producto=Producto,
            ProductoCodigoEscaneo=ProductoCodigoEscaneo,
            db=db,
            app=app,
        )
        nom = (otro.nombre if otro else '') or 'otro producto'
        return {
            'ok': False,
            'error': 'barras_duplicado',
            'mensaje': f'El código ya está en «{nom[:60]}».',
            'producto_conflicto_id': int(otro.id) if otro else None,
        }
    if not asegurar_tabla_producto_codigo_escaneo(app, db):
        return {
            'ok': False,
            'error': 'tabla_no_disponible',
            'mensaje': 'Tabla de vínculos no disponible. Avise a soporte.',
        }
    row = ProductoCodigoEscaneo.query.filter_by(codigo=cnorm).first()
    if row:
        if int(row.producto_id) != pid:
            otro = Producto.query.get(int(row.producto_id))
            nom = (otro.nombre if otro else '') or 'otro producto'
            return {
                'ok': False,
                'error': 'barras_duplicado',
                'mensaje': f'El código ya está vinculado a «{nom[:60]}».',
            }
        row.activo = True
        row.tipo = (tipo or 'pos_vinculo')[:32]
        row.origen = (origen or 'pos')[:32]
        row.usuario = (usuario or '')[:100] or None
    else:
        row = ProductoCodigoEscaneo(
            codigo=cnorm,
            producto_id=pid,
            tipo=(tipo or 'pos_vinculo')[:32],
            activo=True,
            origen=(origen or 'pos')[:32],
            usuario=(usuario or '')[:100] or None,
        )
        db.session.add(row)
    db.session.flush()
    return {
        'ok': True,
        'producto_id': pid,
        'codigo': cnorm,
        'producto_nombre': (p.nombre or '').strip(),
        'codigo_maestro': maestro or (p.codigo_interno or '').strip(),
    }
