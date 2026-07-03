"""Conciliación transferencias caja — confirmar abono antes de autorizar entrega (SD-1)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

METODO_TRANSFERENCIA = 'Transferencia'


def es_metodo_transferencia(metodo: str | None) -> bool:
    return (metodo or '').strip() == METODO_TRANSFERENCIA


def es_transferencia_pendiente_confirmacion(venta) -> bool:
    """Vale Pagado por transferencia sin confirmación de abono."""
    if not venta:
        return False
    if (venta.estado or '').strip() != 'Pagado':
        return False
    if not es_metodo_transferencia(getattr(venta, 'metodo_pago', None)):
        return False
    return getattr(venta, 'transferencia_confirmada_at', None) is None


def transferencia_autoriza_entrega(venta) -> bool:
    """True si la venta puede registrar entrega (QR / mostrador)."""
    if not venta or (venta.estado or '').strip() != 'Pagado':
        return False
    if not es_metodo_transferencia(getattr(venta, 'metodo_pago', None)):
        return True
    return getattr(venta, 'transferencia_confirmada_at', None) is not None


def query_transferencias_pendientes(*, caja_id: int | None = None, limit: int = 200):
    from app import Venta, _asegurar_columnas_transferencia_caja

    _asegurar_columnas_transferencia_caja()
    q = (
        Venta.query.filter(
            Venta.estado == 'Pagado',
            Venta.metodo_pago == METODO_TRANSFERENCIA,
            Venta.transferencia_confirmada_at.is_(None),
        )
        .order_by(Venta.fecha.desc(), Venta.id.desc())
    )
    if caja_id is not None:
        q = q.filter(Venta.caja_id == int(caja_id))
    return q.limit(max(1, min(int(limit or 200), 500)))


def contar_transferencias_pendientes(*, caja_id: int | None = None) -> int:
    return query_transferencias_pendientes(caja_id=caja_id, limit=500).count()


def _venta_tiene_entregas_registradas(venta) -> bool:
    for d in venta.detalles or []:
        if int(getattr(d, 'cantidad_entregada_retiro_tienda', 0) or 0) > 0:
            return True
        if int(getattr(d, 'cantidad_entregada_retiro_bodega', 0) or 0) > 0:
            return True
    return False


def confirmar_transferencia_venta(venta_id: int, usuario: str) -> dict[str, Any]:
    from app import Venta, _asegurar_columnas_transferencia_caja, _audit_log, db
    from services.venta_service import transaccion_critica

    _asegurar_columnas_transferencia_caja()
    venta = Venta.query.get(int(venta_id))
    if not venta:
        return {'ok': False, 'error': 'Venta no encontrada.'}
    if not es_transferencia_pendiente_confirmacion(venta):
        return {'ok': False, 'error': 'Esta venta no está pendiente de confirmación de transferencia.'}

    usr = (usuario or '')[:80] or 'Caja'
    now = datetime.now()
    with transaccion_critica():
        venta.transferencia_confirmada_at = now
        venta.transferencia_confirmada_por = usr
        _audit_log(
            'confirmar_transferencia_caja',
            'venta',
            venta.id,
            usuario=usr,
            datos_despues={
                'transferencia_confirmada_at': now.isoformat(),
                'referencia': (venta.transferencia_referencia or '')[:80],
            },
        )
    db.session.commit()
    return {
        'ok': True,
        'venta_id': venta.id,
        'mensaje': f'Transferencia confirmada — vale #{venta.id} autorizado para entrega.',
    }


def revertir_cobro_transferencia(venta_id: int, usuario: str, motivo: str = '') -> dict[str, Any]:
    """
    Revierte un cobro por transferencia no confirmado: stock, saldo a favor y vuelve a Pendiente.
    """
    from app import (
        Cliente,
        Producto,
        Venta,
        _aplicar_mov_saldo_favor,
        _asegurar_columnas_transferencia_caja,
        _audit_log,
        _factor_venta_a_stock,
        _registrar_movimiento_caja_devolucion_venta,
        _venta_stock_ya_descontado,
        db,
        id_almacen_tienda,
        incrementar_stock_venta_tienda,
        registrar_movimiento_kardex,
    )
    from services.venta_service import transaccion_critica
    from sqlalchemy.orm import joinedload

    _asegurar_columnas_transferencia_caja()
    venta = Venta.query.options(joinedload(Venta.detalles)).get(int(venta_id))
    if not venta:
        return {'ok': False, 'error': 'Venta no encontrada.'}
    if not es_transferencia_pendiente_confirmacion(venta):
        return {'ok': False, 'error': 'Solo se puede revertir transferencias sin confirmar.'}
    if _venta_tiene_entregas_registradas(venta):
        return {
            'ok': False,
            'error': 'Ya hay entregas registradas en este vale; no se puede revertir el cobro.',
        }

    usr = (usuario or '')[:80] or 'Caja'
    motivo_txt = (motivo or 'Transferencia no recibida / revertir cobro').strip()[:500]
    vid = int(venta.id)

    try:
        with transaccion_critica():
            if _venta_stock_ya_descontado(venta):
                for d in venta.detalles or []:
                    if getattr(d, 'a_pedido', False):
                        continue
                    producto = Producto.query.get(d.id_producto)
                    if not producto:
                        raise ValueError(f'Producto no encontrado en línea #{d.id}.')
                    factor = _factor_venta_a_stock(producto)
                    consumo = int(round((d.cantidad or 0) * factor))
                    if consumo <= 0:
                        continue
                    err = incrementar_stock_venta_tienda(producto, consumo)
                    if err:
                        raise ValueError(err)
                    registrar_movimiento_kardex(
                        producto.id,
                        'ENTRADA',
                        consumo,
                        f'Reversa transferencia no confirmada #{vid}',
                        usuario=usr,
                        id_almacen=id_almacen_tienda() or 1,
                        referencia_tipo='venta_reversa_transferencia',
                        referencia_id=vid,
                        stock_saldo=None,
                    )

            sf = float(venta.saldo_favor_usado or 0)
            if sf > 0 and venta.cliente_id:
                _aplicar_mov_saldo_favor(
                    venta.cliente_id,
                    None,
                    'CREDITO',
                    sf,
                    f'Reversa transferencia vale #{vid}',
                )

            _registrar_movimiento_caja_devolucion_venta(venta, usr)

            datos_antes = {
                'estado': venta.estado,
                'metodo_pago': venta.metodo_pago,
                'referencia': (venta.transferencia_referencia or '')[:80],
            }
            venta.estado = 'Pendiente'
            venta.metodo_pago = None
            venta.monto_recibido = None
            venta.vuelto = None
            venta.transferencia_referencia = None
            venta.transferencia_confirmada_at = None
            venta.transferencia_confirmada_por = None
            venta.entrega_ticket_estado = None
            venta.entrega_ticket_cerrado_at = None
            venta.bodega_preparacion_estado = None
            venta.bodega_preparacion_usuario = None
            venta.bodega_preparacion_at = None
            venta.bodega_preparacion_cobrado_at = None

            _audit_log(
                'revertir_transferencia_caja',
                'venta',
                vid,
                usuario=usr,
                datos_antes=datos_antes,
                datos_despues={'estado': 'Pendiente', 'motivo': motivo_txt},
            )
        db.session.commit()
    except ValueError as ex:
        db.session.rollback()
        return {'ok': False, 'error': str(ex)}
    except Exception as ex:
        db.session.rollback()
        return {'ok': False, 'error': str(ex)[:240]}

    return {
        'ok': True,
        'venta_id': vid,
        'mensaje': f'Cobro por transferencia revertido — vale #{vid} volvió a cola de cobro.',
    }
