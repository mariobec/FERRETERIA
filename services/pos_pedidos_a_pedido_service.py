"""
Bandeja POS: seguimiento de líneas venta en verde (ventas_a_pedido).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from services.pos_compromiso_entrega_service import formatear_fecha_entrega_cl

ESTADOS_ABIERTOS = ('por_pedir', 'listo', 'avisado')
ESTADOS_TERMINALES = ('entregado', 'anulado')
ESTADOS_VALIDOS = ESTADOS_ABIERTOS + ESTADOS_TERMINALES

ESTADO_LABELS = {
    'por_pedir': 'Por pedir',
    'listo': 'Listo retiro',
    'avisado': 'Cliente avisado',
    'entregado': 'Entregado',
    'anulado': 'Anulado',
}

ESTADO_BADGE = {
    'por_pedir': 'warning',
    'listo': 'info',
    'avisado': 'primary',
    'entregado': 'success',
    'anulado': 'secondary',
}


def _telefono_wa_digits(telefono: str | None) -> str:
    raw = ''.join(ch for ch in (telefono or '') if ch.isdigit())
    if not raw:
        return ''
    if raw.startswith('56'):
        return raw
    if len(raw) == 9 and raw[0] == '9':
        return '56' + raw
    return '56' + raw.lstrip('0')


def _fmt_clp(monto: float | int | None) -> str:
    n = int(round(float(monto or 0)))
    return f'${n:,}'.replace(',', '.')


def mensaje_whatsapp_listo(
    *,
    cliente_nombre: str,
    empresa: str,
    producto_nombre: str,
    cantidad: int,
    vale_id: int,
    retiro_tienda: bool,
    fecha_promesa: date | None,
) -> str:
    entrega = 'retiro en tienda' if retiro_tienda else 'despacho a domicilio'
    fp = ''
    if fecha_promesa:
        fp = f' (compromiso {fecha_promesa.strftime("%d/%m/%Y")})'
    return (
        f'Hola {(cliente_nombre or "cliente").strip()}, '
        f'le avisamos desde {empresa}: su pedido ya está disponible — '
        f'{producto_nombre} x{int(cantidad or 1)}. '
        f'Vale N°{int(vale_id)}. Modalidad: {entrega}{fp}. '
        f'Gracias por su preferencia.'
    )


def url_whatsapp_aviso(telefono: str | None, mensaje: str) -> str | None:
    digits = _telefono_wa_digits(telefono)
    if not digits:
        return None
    return f'https://wa.me/{digits}?text={quote(mensaje)}'


def listar_pedidos_apedido(*, solo_abiertos: bool = True, limite: int = 80):
    import app as m
    from sqlalchemy.orm import joinedload

    if not m._asegurar_tabla_ventas_a_pedido():
        return [], date.today()

    q = (
        m.VentaAPedido.query.options(
            joinedload(m.VentaAPedido.venta).joinedload(m.Venta.cliente),
            joinedload(m.VentaAPedido.producto),
        )
        .join(m.Venta, m.VentaAPedido.venta_id == m.Venta.id)
        .filter(m.Venta.estado.in_(('Pendiente', 'Pagado')))
    )
    if solo_abiertos:
        q = q.filter(m.VentaAPedido.estado_entrega.in_(ESTADOS_ABIERTOS))
    else:
        q = q.filter(~m.VentaAPedido.estado_entrega.in_(('anulado',)))

    hoy = date.today()
    filas = (
        q.order_by(m.VentaAPedido.fecha_promesa.asc(), m.VentaAPedido.id.desc())
        .limit(max(1, min(int(limite or 80), 200)))
        .all()
    )
    return filas, hoy


def contar_pedidos_abiertos() -> dict[str, int]:
    import app as m

    if not m._asegurar_tabla_ventas_a_pedido():
        return {'total': 0, 'vencidos': 0, 'listos': 0}

    hoy = date.today()
    base = (
        m.VentaAPedido.query.join(m.Venta)
        .filter(
            m.Venta.estado.in_(('Pendiente', 'Pagado')),
            m.VentaAPedido.estado_entrega.in_(ESTADOS_ABIERTOS),
        )
    )
    total = base.count()
    vencidos = base.filter(m.VentaAPedido.fecha_promesa < hoy).count()
    listos = base.filter(m.VentaAPedido.estado_entrega == 'listo').count()
    return {'total': total, 'vencidos': vencidos, 'listos': listos}


def serializar_pedido(rec, hoy: date | None, empresa_nombre: str, ticket_url_builder) -> dict:
    venta = rec.venta
    cliente = venta.cliente if venta else None
    producto = rec.producto
    fp = rec.fecha_promesa
    hoy = hoy or date.today()
    tel = (rec.telefono_notificacion or '').strip()
    if not tel and cliente:
        tel = (getattr(cliente, 'telefono', None) or '').strip()

    cliente_nombre = (cliente.nombre if cliente else '') or 'Cliente'
    producto_nombre = (producto.nombre if producto else '') or 'Producto'
    estado = (rec.estado_entrega or 'por_pedir').strip() or 'por_pedir'

    msg = mensaje_whatsapp_listo(
        cliente_nombre=cliente_nombre,
        empresa=empresa_nombre,
        producto_nombre=producto_nombre,
        cantidad=int(rec.cantidad or 1),
        vale_id=int(rec.venta_id),
        retiro_tienda=bool(rec.retiro_tienda),
        fecha_promesa=fp,
    )

    vencido = bool(fp and fp < hoy and estado in ESTADOS_ABIERTOS)
    ticket_url = None
    if venta and ticket_url_builder:
        try:
            ticket_url = ticket_url_builder(int(venta.id))
        except Exception:
            ticket_url = None

    return {
        'id': int(rec.id),
        'venta_id': int(rec.venta_id),
        'detalle_venta_id': int(rec.detalle_venta_id),
        'producto_id': int(rec.producto_id),
        'producto_nombre': producto_nombre,
        'cantidad': int(rec.cantidad or 1),
        'fecha_promesa': fp.isoformat() if fp else None,
        'fecha_promesa_fmt': formatear_fecha_entrega_cl(fp) if fp else '—',
        'estado': estado,
        'estado_label': ESTADO_LABELS.get(estado, estado),
        'estado_badge': ESTADO_BADGE.get(estado, 'secondary'),
        'vencido': vencido,
        'retiro_tienda': bool(rec.retiro_tienda),
        'despacho_domicilio': bool(rec.despacho_domicilio),
        'modalidad_label': 'Retiro tienda' if rec.retiro_tienda else 'Despacho',
        'notificar_whatsapp': bool(rec.notificar_whatsapp),
        'telefono': tel or None,
        'whatsapp_url': url_whatsapp_aviso(tel, msg) if rec.notificar_whatsapp or tel else None,
        'cliente_nombre': cliente_nombre,
        'cliente_rut': (cliente.rut if cliente else '') or '',
        'vale_estado': (venta.estado if venta else '') or '',
        'vale_total_fmt': _fmt_clp(venta.monto_total if venta else 0),
        'ticket_url': ticket_url,
        'usuario': (rec.usuario or '') or '',
        'creado_en': rec.creado_en.isoformat() if getattr(rec, 'creado_en', None) else None,
    }


def actualizar_estado_pedido(rec_id: int, nuevo_estado: str, usuario: str | None = None) -> tuple[bool, str]:
    import app as m

    estado = (nuevo_estado or '').strip().lower()
    if estado not in ESTADOS_VALIDOS:
        return False, 'Estado no válido.'

    if not m._asegurar_tabla_ventas_a_pedido():
        return False, 'Tabla de pedidos no disponible.'

    rec = m.VentaAPedido.query.get(int(rec_id))
    if not rec:
        return False, 'Pedido no encontrado.'

    actual = (rec.estado_entrega or 'por_pedir').strip()
    if actual == estado:
        return True, 'Sin cambios.'

    if actual in ESTADOS_TERMINALES:
        return False, 'El pedido ya está cerrado.'

    rec.estado_entrega = estado
    if usuario:
        rec.usuario = (usuario or '')[:80] or rec.usuario
    return True, ESTADO_LABELS.get(estado, estado)
