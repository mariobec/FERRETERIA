"""Cotización → venta POS: preview del asistente y conversión con líneas ajustables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

ESTADOS_CONVERTIBLES = frozenset({'Vigente', 'Aceptada', 'Vencida'})
TOLERANCIA_PROYECTO_CLP = 1


def _app():
    import app as m

    return m


def _iva():
    from core.domain.shared.iva_chile import iva_desde_neto_clp

    return iva_desde_neto_clp


def _stock_linea(producto, cantidad_venta) -> dict:
    m = _app()
    if not producto:
        return {'disponible': 0, 'requiere': 0, 'ok': False, 'sin_sku': True}
    consumo = int(round((cantidad_venta or 0) * m._factor_venta_a_stock(producto))) or 1
    disp = m.stock_disponible_venta_tienda(producto)
    return {
        'disponible': int(disp),
        'requiere': consumo,
        'ok': disp >= consumo,
        'sin_sku': False,
    }


def _subtotal_neto_linea(cantidad, precio_unitario, descuento) -> int:
    m = _app()
    return m._subtotal_linea_cotizacion_clp(cantidad, precio_unitario, descuento)


def _neto_linea_a_bruto(cantidad, precio_neto, descuento_neto) -> tuple[int, float, float]:
    """Convierte línea cotización (neto) a subtotal bruto POS + precio unitario bruto."""
    iva_desde_neto = _iva()
    cant_i = max(1, int(round(float(cantidad or 0)))) or 1
    neto = _subtotal_neto_linea(cant_i, precio_neto, descuento_neto)
    bruto = neto + iva_desde_neto(neto)
    pu_bruto = int(round(bruto / cant_i)) if cant_i else bruto
    return bruto, float(pu_bruto), float(bruto)


def _totales_cotizacion(cot) -> dict:
    m = _app()
    return m._presentacion_totales_cotizacion(cot)


def _linea_preview_desde_detalle(det) -> dict:
    m = _app()
    prod = det.producto if det.producto_id else None
    cant = float(det.cantidad or 0) or 1
    stock = _stock_linea(prod, cant) if det.producto_id else {
        'disponible': 0,
        'requiere': 0,
        'ok': False,
        'sin_sku': True,
    }
    sub_neto = _subtotal_neto_linea(det.cantidad, det.precio_unitario, det.descuento)
    bruto_est, _, _ = _neto_linea_a_bruto(det.cantidad, det.precio_unitario, det.descuento)
    sem = 'ok'
    if stock.get('sin_sku'):
        sem = 'sin_sku'
    elif not stock.get('ok'):
        sem = 'falta_stock'
    return {
        'detalle_id': int(det.id),
        'producto_id': int(det.producto_id) if det.producto_id else None,
        'codigo': (det.codigo or '')[:80],
        'nombre': (det.nombre or '')[:200],
        'cantidad': cant,
        'precio_unitario': float(det.precio_unitario or 0),
        'descuento': float(det.descuento or 0),
        'subtotal_neto': int(sub_neto),
        'subtotal_bruto_est': int(bruto_est),
        'stock_disponible': stock['disponible'],
        'stock_requiere': stock['requiere'],
        'stock_ok': bool(stock['ok']),
        'sin_sku': bool(stock['sin_sku']),
        'semaforo': sem,
        'accion_default': 'incluir' if not stock.get('sin_sku') else 'excluir',
        'a_pedido': False,
        'incluir': not stock.get('sin_sku'),
    }


def preview_conversion(cot_id: int) -> dict:
    """Estado inicial del asistente (GET)."""
    m = _app()
    cot = m.Cotizacion.query.get(cot_id)
    if not cot:
        return {'ok': False, 'error': 'Cotización no encontrada.'}
    estado = (cot.estado or '').strip()
    if estado == 'Convertida':
        return {
            'ok': False,
            'error': 'Esta cotización ya fue convertida.',
            'venta_id': cot.venta_id,
        }
    if estado == 'Rechazada':
        return {'ok': False, 'error': 'No se puede convertir una cotización rechazada.'}
    if estado not in ESTADOS_CONVERTIBLES:
        return {'ok': False, 'error': f'Estado «{estado}» no permite conversión.'}

    venta_abierta = None
    if cot.venta_id:
        v = m.Venta.query.get(cot.venta_id)
        if v and (v.estado or '').strip() == 'Abierta':
            venta_abierta = int(v.id)

    tot = _totales_cotizacion(cot)
    lineas = [_linea_preview_desde_detalle(d) for d in (cot.detalles or [])]
    return {
        'ok': True,
        'cotizacion': {
            'id': cot.id,
            'numero': cot.numero,
            'estado': estado,
            'cliente_nombre': cot.cliente_nombre,
            'cliente_rut': cot.cliente_rut,
            'descuento_global': float(cot.descuento_global or 0),
            'modo_proyecto_disponible': estado == 'Aceptada' or estado in ('Vigente', 'Vencida'),
        },
        'totales': tot,
        'lineas': lineas,
        'venta_abierta_id': venta_abierta,
        'pos_dias_entrega_a_pedido': __import__(
            'services.pos_busqueda_service', fromlist=['pos_dias_entrega_estimado']
        ).pos_dias_entrega_estimado(),
    }


def _normalizar_lineas_payload(cot, lineas_raw: list | None) -> tuple[list[dict], list[str]]:
    """Valida y normaliza líneas del body JSON."""
    errores: list[str] = []
    if not lineas_raw:
        return [], ['Debe incluir al menos una línea en la conversión.']

    det_map = {int(d.id): d for d in (cot.detalles or [])}
    normalizadas: list[dict] = []

    for idx, raw in enumerate(lineas_raw):
        if not isinstance(raw, dict):
            errores.append(f'Línea {idx + 1}: formato inválido.')
            continue
        accion = (raw.get('accion') or 'incluir').strip().lower()
        if accion == 'excluir':
            continue
        if accion not in ('incluir',):
            errores.append(f'Línea {idx + 1}: acción «{accion}» no reconocida.')
            continue

        det_id = raw.get('detalle_id')
        producto_id = raw.get('producto_id')
        det = det_map.get(int(det_id)) if det_id is not None else None

        if det:
            producto_id = det.producto_id
            nombre = det.nombre
            codigo = det.codigo
            pu_def = float(det.precio_unitario or 0)
            desc_def = float(det.descuento or 0)
        else:
            if not producto_id:
                errores.append(f'Línea {idx + 1}: falta producto.')
                continue
            prod = _app().Producto.query.get(int(producto_id))
            if not prod:
                errores.append(f'Línea {idx + 1}: producto no encontrado.')
                continue
            nombre = prod.nombre
            codigo = prod.codigo_barra or ''
            bruto_cat = float(prod.precio_venta_sd or prod.precio_venta or 0)
            pu_def = float(_app()._precio_neto_cotizacion_desde_catalogo(bruto_cat))
            desc_def = 0.0

        try:
            cantidad = float(raw.get('cantidad', det.cantidad if det else 1))
        except (TypeError, ValueError):
            cantidad = 1.0
        if cantidad <= 0:
            errores.append(f'Línea {idx + 1}: cantidad debe ser mayor a 0.')
            continue

        try:
            pu = float(raw.get('precio_unitario', pu_def))
        except (TypeError, ValueError):
            pu = pu_def
        try:
            desc = float(raw.get('descuento', desc_def))
        except (TypeError, ValueError):
            desc = desc_def

        a_pedido = bool(raw.get('a_pedido', False))
        if not producto_id:
            errores.append(f'Línea {idx + 1} ({nombre}): sin SKU — quítela o vincule producto.')
            continue

        prod = _app().Producto.query.get(int(producto_id))
        stock = _stock_linea(prod, cantidad)
        if not a_pedido and not stock['ok']:
            errores.append(
                f'«{nombre[:40]}»: stock insuficiente ({stock["disponible"]} vs {stock["requiere"]}). '
                'Marque a pedido, baje cantidad o quite la línea.'
            )
            continue

        normalizadas.append({
            'detalle_id': int(det.id) if det else None,
            'producto_id': int(producto_id),
            'nombre': nombre,
            'codigo': codigo,
            'cantidad': cantidad,
            'precio_unitario': pu,
            'descuento': desc,
            'a_pedido': a_pedido,
        })

    if not normalizadas and not errores:
        errores.append('No quedaron líneas para convertir.')
    return normalizadas, errores


def _calcular_total_bruto_lineas(lineas: list[dict]) -> int:
    total = 0
    for ln in lineas:
        bruto, _, _ = _neto_linea_a_bruto(ln['cantidad'], ln['precio_unitario'], ln['descuento'])
        total += bruto
    return total


def _ajustar_lineas_a_total_cot(cot, lineas: list[dict]) -> None:
    """Cuadra subtotales bruto con total cotizado (dto global / redondeo IVA)."""
    if not lineas:
        return
    target = int(_totales_cotizacion(cot).get('total') or 0)
    if target <= 0:
        return
    brutos = []
    for ln in lineas:
        b, _, _ = _neto_linea_a_bruto(ln['cantidad'], ln['precio_unitario'], ln['descuento'])
        brutos.append(b)
    suma = sum(brutos)
    delta = suma - target
    if delta == 0:
        return
    # Absorber diferencia en la última línea vía descuento bruto implícito en subtotal.
    last = lineas[-1]
    b_last, pu, sub = _neto_linea_a_bruto(last['cantidad'], last['precio_unitario'], last['descuento'])
    nuevo_sub = max(0, b_last - delta)
    last['_subtotal_bruto'] = nuevo_sub
    last['_precio_unitario_bruto'] = pu
    if nuevo_sub != b_last:
        last['_ajuste_cuadre'] = delta


def _resolver_cliente_cotizacion(cot):
    """Enlaza o crea cliente maestro desde snapshot cotización."""
    m = _app()
    cliente_origen = m.Cliente.query.get(cot.cliente_id) if cot.cliente_id else None
    if not cliente_origen and cot.cliente_rut:
        variantes = m._rut_variantes_busqueda(cot.cliente_rut)
        cliente_origen = m.Cliente.query.filter(m.Cliente.rut.in_(variantes)).first()
        if not cliente_origen and cot.cliente_nombre:
            rut_norm = m._rut_sin_formato(cot.cliente_rut)
            cliente_origen = m.Cliente(
                rut=(cot.cliente_rut or rut_norm)[:12],
                nombre=(cot.cliente_nombre or rut_norm)[:100],
                giro=(cot.cliente_giro or None) and cot.cliente_giro[:100],
                direccion=(cot.cliente_direccion or None) and cot.cliente_direccion[:200],
                telefono=(cot.cliente_telefono or None) and cot.cliente_telefono[:20],
                correo=(cot.cliente_correo or None) and cot.cliente_correo[:100],
                comuna=(cot.cliente_comuna or None) and cot.cliente_comuna[:80],
                ciudad=(cot.cliente_ciudad or None) and cot.cliente_ciudad[:80],
                saldo_deudor=0.0,
                limite_credito=0.0,
                estado_credito='Activo',
            )
            m.db.session.add(cliente_origen)
            m.db.session.flush()
        if cliente_origen:
            cot.cliente_id = cliente_origen.id

    if cliente_origen:
        if not cliente_origen.giro and cot.cliente_giro:
            cliente_origen.giro = cot.cliente_giro[:100]
        if not cliente_origen.direccion and cot.cliente_direccion:
            cliente_origen.direccion = cot.cliente_direccion[:200]
        if not cliente_origen.telefono and cot.cliente_telefono:
            cliente_origen.telefono = cot.cliente_telefono[:20]
        if not cliente_origen.correo and cot.cliente_correo:
            cliente_origen.correo = cot.cliente_correo[:100]
        if not cliente_origen.comuna and cot.cliente_comuna:
            cliente_origen.comuna = cot.cliente_comuna[:80]
        if not cliente_origen.ciudad and cot.cliente_ciudad:
            cliente_origen.ciudad = cot.cliente_ciudad[:80]
    return cliente_origen


def validar_conversion(cot, payload: dict) -> tuple[bool, list[str], list[dict]]:
    """Valida payload completo antes de persistir."""
    errores: list[str] = []
    if not payload.get('confirmacion_cliente'):
        errores.append('Confirme que el cliente aceptó montos y plazos.')

    lineas, err_ln = _normalizar_lineas_payload(cot, payload.get('lineas'))
    errores.extend(err_ln)

    modo_proyecto = bool(payload.get('modo_proyecto'))
    if modo_proyecto and lineas:
        monto_acordado = payload.get('monto_acordado_clp')
        if monto_acordado is None:
            monto_acordado = int(_totales_cotizacion(cot).get('total') or 0)
        else:
            try:
                monto_acordado = int(round(float(monto_acordado)))
            except (TypeError, ValueError):
                monto_acordado = int(_totales_cotizacion(cot).get('total') or 0)
        total_bruto = _calcular_total_bruto_lineas(lineas)
        delta = abs(total_bruto - monto_acordado)
        autoriza = bool(payload.get('autorizar_diferencia_monto'))
        if delta > TOLERANCIA_PROYECTO_CLP and not autoriza:
            errores.append(
                f'Modo proyecto: total venta ${total_bruto:,} ≠ monto acordado ${monto_acordado:,} '
                f'(Δ ${delta:,}). Ajuste precios o autorice la diferencia.'
                .replace(',', '.')
            )

    return (len(errores) == 0, errores, lineas)


def convertir_cotizacion_a_venta(
    cot_id: int,
    payload: dict,
    *,
    caja,
    vendedor: str,
) -> dict[str, Any]:
    """Crea venta Abierta desde cotización con líneas normalizadas."""
    m = _app()
    cot = m.Cotizacion.query.get(cot_id)
    if not cot:
        return {'ok': False, 'error': 'Cotización no encontrada.'}

    estado = (cot.estado or '').strip()
    if estado == 'Convertida':
        return {
            'ok': False,
            'error': 'Cotización ya convertida.',
            'venta_id': cot.venta_id,
        }
    if estado == 'Rechazada':
        return {'ok': False, 'error': 'Cotización rechazada.'}
    if estado not in ESTADOS_CONVERTIBLES:
        return {'ok': False, 'error': f'Estado «{estado}» no permite conversión.'}

    if cot.venta_id:
        v_prev = m.Venta.query.get(cot.venta_id)
        if v_prev and (v_prev.estado or '').strip() == 'Abierta':
            return {
                'ok': True,
                'venta_id': v_prev.id,
                'reutilizada': True,
                'redirect': m.url_for('punto_venta', cot_emitir_guia=1),
            }

    ok, errores, lineas = validar_conversion(cot, payload or {})
    if not ok:
        return {'ok': False, 'errors': errores}

    _ajustar_lineas_a_total_cot(cot, lineas)
    cliente_origen = _resolver_cliente_cotizacion(cot)

    venta = m.Venta(
        usuario=vendedor,
        estado='Abierta',
        monto_total=0,
        caja_id=caja.id,
        fecha=m.db.func.current_timestamp(),
    )
    if cliente_origen:
        venta.cliente_id = cliente_origen.id
    venta.cotizacion_origen_id = cot.id
    m.db.session.add(venta)
    m.db.session.flush()

    for ln in lineas:
        bruto, pu_bruto, sub = _neto_linea_a_bruto(
            ln['cantidad'], ln['precio_unitario'], ln['descuento']
        )
        if '_subtotal_bruto' in ln:
            sub = float(ln['_subtotal_bruto'])
        if '_precio_unitario_bruto' in ln:
            pu_bruto = float(ln['_precio_unitario_bruto'])
        det = m.DetalleVenta(
            id_venta=venta.id,
            id_producto=ln['producto_id'],
            cantidad=max(1, int(round(ln['cantidad']))),
            precio_unitario=pu_bruto,
            descuento=0.0,
            subtotal=float(sub),
            a_pedido=bool(ln.get('a_pedido')),
        )
        m.db.session.add(det)

    if hasattr(venta, 'recalcular_total'):
        venta.recalcular_total()

    # Trazabilidad: Aceptada hasta emitir vale; no Convertida aún.
    if estado in ('Vigente', 'Vencida'):
        cot.estado = 'Aceptada'
    cot.venta_id = venta.id
    cot.fecha_estado = datetime.utcnow()

    try:
        from services.audit_service import audit_log

        audit_log(
            'cotizacion_convertida',
            'cotizacion',
            entidad_id=cot.id,
            usuario=vendedor,
            datos_despues={
                'venta_id': venta.id,
                'lineas': len(lineas),
                'modo_proyecto': bool(payload.get('modo_proyecto')),
                'total_venta': int(round(float(venta.monto_total or 0))),
            },
        )
    except Exception:
        m.app.logger.exception('audit cotizacion_convertida cot=%s', cot.id)

    try:
        if m._asegurar_tabla_c360_proactiva_ofertas():
            off = m.C360ProactivaOferta.query.filter_by(cotizacion_id=cot.id).first()
            if off:
                off.venta_id = venta.id
                off.convertida_at = datetime.utcnow()
    except Exception:
        m.app.logger.exception('C360 oferta proactiva cot=%s', cot.id)

    m.db.session.commit()

    return {
        'ok': True,
        'venta_id': venta.id,
        'cotizacion_numero': cot.numero,
        'total_venta': int(round(float(venta.monto_total or 0))),
        'redirect': m.url_for('punto_venta', cot_emitir_guia=1),
    }


def marcar_cotizacion_convertida_al_emitir_vale(venta) -> None:
    """Hook en finalizar_venta: cotización pasa a Convertida cuando el vale es Pendiente."""
    m = _app()
    cot_id = getattr(venta, 'cotizacion_origen_id', None)
    if not cot_id:
        return
    cot = m.Cotizacion.query.get(cot_id)
    if not cot:
        return
    if (cot.estado or '').strip() == 'Convertida':
        return
    cot.estado = 'Convertida'
    cot.venta_id = venta.id
    cot.fecha_estado = datetime.utcnow()
    try:
        from services.audit_service import audit_log

        audit_log(
            'cotizacion_vale_emitido',
            'cotizacion',
            entidad_id=cot.id,
            usuario=getattr(venta, 'usuario', None),
            datos_despues={'venta_id': venta.id, 'estado_venta': venta.estado},
        )
    except Exception:
        m.app.logger.exception('audit cotizacion_vale_emitido cot=%s', cot.id)
