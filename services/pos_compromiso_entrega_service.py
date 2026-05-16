"""
Compromiso de entrega (venta en verde): fechas estimadas y persistencia ventas_a_pedido.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from services.pos_busqueda_service import pos_dias_entrega_estimado

_MESES_ES = (
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)
_DIAS_ES = (
    'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo',
)


def sumar_dias_habiles(desde: date | None, dias: int) -> date:
    """Suma días hábiles (lun–vie). v1 sin feriados Chile."""
    base = desde or date.today()
    try:
        n = int(dias)
    except (TypeError, ValueError):
        n = 5
    n = max(1, min(n, 90))
    cursor = base
    added = 0
    while added < n:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            added += 1
    return cursor


def fecha_entrega_estimada(desde: date | None = None, cfg: dict | None = None) -> date:
    return sumar_dias_habiles(desde, pos_dias_entrega_estimado(cfg))


def formatear_fecha_entrega_cl(fecha: date) -> str:
    return f'{_DIAS_ES[fecha.weekday()]}, {fecha.day} de {_MESES_ES[fecha.month - 1]}'


def parse_fecha_iso(valor: str | None) -> date | None:
    raw = (valor or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _form_bool(valor) -> bool:
    return str(valor or '').strip().lower() in ('1', 'true', 'si', 'yes', 'on')


def persistir_ventas_a_pedido(venta, form_data, usuario: str | None = None) -> list:
    """
    Crea filas en ventas_a_pedido por cada DetalleVenta.a_pedido del vale emitido.
    Idempotente por detalle_venta_id.
    """
    import app as m

    if not venta:
        return []
    lineas = [
        d for d in (venta.detalles or [])
        if getattr(d, 'a_pedido', False)
    ]
    if not lineas:
        return []

    fecha_prom = parse_fecha_iso(
        (form_data or {}).get('fecha_entrega_prometida')
        if hasattr(form_data, 'get')
        else None
    )
    if not fecha_prom:
        fecha_prom = fecha_entrega_estimada()

    retiro_tienda = _form_bool((form_data or {}).get('compromiso_retiro_tienda'))
    despacho = _form_bool((form_data or {}).get('compromiso_despacho'))
    if despacho:
        retiro_tienda = False
    elif not retiro_tienda and not despacho:
        retiro_tienda = True

    notificar = _form_bool((form_data or {}).get('notificar_whatsapp'))
    telefono = (
        (form_data or {}).get('telefono_notificacion')
        or (form_data or {}).get('cliente_telefono')
        or ''
    )
    telefono = str(telefono or '').strip()[:30] or None
    usuario_s = (usuario or '').strip()[:80] or None

    creados = []
    for det in lineas:
        existente = m.VentaAPedido.query.filter_by(detalle_venta_id=int(det.id)).first()
        if existente:
            creados.append(existente)
            continue
        rec = m.VentaAPedido(
            venta_id=int(venta.id),
            detalle_venta_id=int(det.id),
            producto_id=int(det.id_producto),
            cantidad=int(det.cantidad or 1),
            fecha_promesa=fecha_prom,
            estado_entrega='por_pedir',
            retiro_tienda=bool(retiro_tienda),
            despacho_domicilio=bool(despacho),
            notificar_whatsapp=bool(notificar),
            telefono_notificacion=telefono,
            usuario=usuario_s,
            creado_en=datetime.now(),
        )
        m.db.session.add(rec)
        creados.append(rec)
    return creados
