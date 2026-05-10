"""Customer 360 — motor etapa obra, ofertas proactivas, ROI dashboard.

Las vistas y modelos siguen en `app`; este módulo usa `import app as m` dentro de las
funciones para evitar dependencias circulares al cargar el módulo.
"""
from __future__ import annotations

import json
import os
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import url_for
from sqlalchemy import func, or_

C360_FASE_OBRA_VALORES = ('OBRA_GRUESA', 'INSTALACIONES', 'ACABADOS', 'TERMINACIONES')
C360_FASE_OBRA_LABELS = {
    'OBRA_GRUESA': 'Fase 1 — Estructura (obra gruesa)',
    'INSTALACIONES': 'Fase 2 — Instalaciones (obra negra/gris)',
    'ACABADOS': 'Fase 3 — Acabados (obra blanca)',
    'TERMINACIONES': 'Fase 4 — Terminaciones',
}
C360_FASE_ORDEN = {'OBRA_GRUESA': 1, 'INSTALACIONES': 2, 'ACABADOS': 3, 'TERMINACIONES': 4}

C360_KIT_SUBCATEGORIA_KEYWORDS = {
    'INSTALACIONES': ['pvc', 'cable', 'caja', 'electric', 'tuber', 'conduc', 'breaker'],
    'ACABADOS': ['ceram', 'pegament', 'grifer', 'acab', 'porcel', 'mosa'],
    'TERMINACIONES': ['pintur', 'led', 'lamp', 'termin', 'accesorio'],
    'OBRA_GRUESA': ['cement', 'hierro', 'mader', 'arena', 'ladr', 'block', 'perfil'],
}


def c360_fase_obra_valida(raw):
    s = (raw or '').strip().upper()
    return s if s in C360_FASE_OBRA_VALORES else None


def c360_fase_orden(fase):
    return C360_FASE_ORDEN.get((fase or '').strip().upper(), 0)


def c360_perfil_dict_desde_cliente(cliente):
    if not cliente or not getattr(cliente, 'c360_perfil_json', None):
        return {}
    try:
        d = json.loads(cliente.c360_perfil_json)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def c360_guardar_perfil_cliente(cliente, perfil_dict):
    cliente.c360_perfil_json = json.dumps(perfil_dict, ensure_ascii=False)


def c360_montos_por_fase_ultimos_dias(cliente_id, dias=30):
    import app as m

    if not cliente_id:
        return {}, 0.0
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        dias = 30
    dias = max(1, min(dias, 120))
    cut = datetime.now() - timedelta(days=dias)
    db = m.db
    Producto = m.Producto
    Venta = m.Venta
    DetalleVenta = m.DetalleVenta
    q = (
        db.session.query(
            func.coalesce(Producto.fase_obra, '').label('fase_raw'),
            func.coalesce(func.sum(DetalleVenta.subtotal), 0.0).label('monto'),
        )
        .select_from(DetalleVenta)
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .join(Producto, Producto.id == DetalleVenta.id_producto)
        .filter(
            Venta.cliente_id == int(cliente_id),
            Venta.fecha >= cut,
            or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
        )
        .group_by(Producto.fase_obra)
    )
    by_fase = {k: 0.0 for k in C360_FASE_OBRA_VALORES}
    sin = 0.0
    total = 0.0
    for fase_raw, monto in q.all():
        mv = float(monto or 0)
        total += mv
        fv = c360_fase_obra_valida(fase_raw)
        if fv:
            by_fase[fv] = by_fase.get(fv, 0.0) + mv
        else:
            sin += mv
    return {'por_fase': by_fase, 'sin_clasificar': sin, 'total': total, 'dias': dias}


def c360_score_puntualidad_cliente(cliente_id):
    import app as m

    hoy = date.today()
    pend = m._sql_cuota_saldo_pendiente()
    VentaCuotaCredito = m.VentaCuotaCredito
    Venta = m.Venta
    n_venc = int(
        m.db.session.query(func.count(VentaCuotaCredito.id))
        .select_from(VentaCuotaCredito)
        .join(Venta, Venta.id == VentaCuotaCredito.venta_id)
        .filter(
            Venta.cliente_id == cliente_id,
            Venta.metodo_pago == 'Credito',
            or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
            pend > 0.01,
            VentaCuotaCredito.fecha_vencimiento < hoy,
        )
        .scalar()
        or 0
    )
    if n_venc <= 0:
        return 96.0
    return float(max(52.0, 94.0 - n_venc * 7.0))


def c360_probabilidad_mora_cliente(cliente_id):
    import app as m

    hoy = date.today()
    pend = m._sql_cuota_saldo_pendiente()
    VentaCuotaCredito = m.VentaCuotaCredito
    Venta = m.Venta
    Cliente = m.Cliente
    monto_venc = float(
        m.db.session.query(func.coalesce(func.sum(pend), 0.0))
        .select_from(VentaCuotaCredito)
        .join(Venta, Venta.id == VentaCuotaCredito.venta_id)
        .filter(
            Venta.cliente_id == cliente_id,
            Venta.metodo_pago == 'Credito',
            or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
            pend > 0.01,
            VentaCuotaCredito.fecha_vencimiento < hoy,
        )
        .scalar()
        or 0.0
    )
    cli = Cliente.query.get(cliente_id)
    lim = float(cli.limite_credito or 1.0) if cli else 1.0
    return float(min(95.0, 18.0 + (monto_venc / max(lim, 1.0)) * 55.0))


def c360_project_predictor_actualizar_cliente(cliente_id, commit=True):
    import app as m

    Cliente = m.Cliente
    db = m.db
    cli = Cliente.query.get(cliente_id)
    if not cli or m._cliente_es_sistema_final(cli):
        return None
    etapa_fase_anterior = (cli.c360_etapa_actual or '').strip().upper() or None
    agg = c360_montos_por_fase_ultimos_dias(cliente_id, 30)
    total = float(agg['total'] or 0)
    por = agg['por_fase']
    perfil = c360_perfil_dict_desde_cliente(cli)
    score = c360_score_puntualidad_cliente(cliente_id)
    prob_mora = c360_probabilidad_mora_cliente(cliente_id)

    def _pct(fk):
        return (por.get(fk, 0.0) / total) if total > 0 else 0.0

    nueva_etapa = None
    alerta = None
    if total <= 0:
        nueva_etapa = (cli.c360_etapa_actual or '').strip() or None
        alerta = 'Sin compras clasificadas en la ventana; asigne fase de obra a productos en inventario.'
    else:
        if _pct('OBRA_GRUESA') > 0.60:
            nueva_etapa = 'INSTALACIONES'
            alerta = (
                'Oportunidad de crédito / fidelización: cliente con fuerte compra de obra gruesa; '
                'priorizar tubería, eléctrico y sanitarios (instalaciones).'
            )
        elif _pct('INSTALACIONES') > 0.55:
            nueva_etapa = 'ACABADOS'
            alerta = 'Proyección a acabados: cerámica, grifería, pegamentos finos.'
        elif _pct('ACABADOS') > 0.45:
            nueva_etapa = 'TERMINACIONES'
            alerta = 'Proyección a terminaciones: pinturas, LED, accesorios baño.'
        elif _pct('TERMINACIONES') > 0.30:
            nueva_etapa = 'TERMINACIONES'
            alerta = 'Cliente en cierre de proyecto (terminaciones).'
        else:
            nueva_etapa = 'OBRA_GRUESA'
            alerta = 'Perfil mixto o etapa inicial; revisar clasificación de productos.'

    cupo_sug = 0.0
    if score > 88.0 and total > 0:
        lim = float(cli.limite_credito or 0)
        cupo_sug = float(min(lim * 0.20, max(50000.0, total * 0.24)))

    cli.c360_etapa_actual = nueva_etapa
    sin_clas = float(agg.get('sin_clasificar') or 0.0)
    ratio_sin = (sin_clas / total) if total > 0 else 0.0
    lim_c = float(cli.limite_credito or 0.0)
    recomendar_avanzado = bool(
        score > 88.0
        and nueva_etapa
        and nueva_etapa in ('INSTALACIONES', 'ACABADOS', 'TERMINACIONES')
        and total > 0
    )
    recomendar_data_quality = bool(
        score > 86.0
        and nueva_etapa == 'OBRA_GRUESA'
        and total >= 20000.0
        and ratio_sin >= 0.30
        and lim_c >= 120000.0
    )
    recomendar = recomendar_avanzado or recomendar_data_quality
    motivo_llamada = None
    if recomendar_avanzado:
        motivo_llamada = 'ETAPA_AVANZADA'
    elif recomendar_data_quality:
        motivo_llamada = 'DATA_QUALITY'
        pct_sin = round(ratio_sin * 100.0, 1)
        alerta = (
            f'Prioridad llamada (calidad de datos): en los últimos {agg["dias"]} días '
            f'el {pct_sin}% del monto corresponde a productos sin fase_obra en catálogo; '
            f'compras relevantes (${int(round(total)):,} CLP) y buen score de puntualidad. '
            'Acción: visitar/llamar para clasificar SKU y afinar etapa real + crédito.'
        ).replace(',', '.')
    perfil.update(
        {
            'etapa_actual': nueva_etapa,
            'probabilidad_mora': round(prob_mora, 2),
            'cupo_sugerido_proxima_fase': int(round(cupo_sug)),
            'score_puntualidad': round(score, 2),
            'alerta_oportunidad_credito': alerta,
            'ultima_prediccion_at': datetime.utcnow().isoformat() + 'Z',
            'ventana_dias': agg['dias'],
            'monto_total_ventana_clp': int(round(total)),
            'share_obra_gruesa': round(_pct('OBRA_GRUESA') * 100, 2) if total > 0 else 0.0,
            'recomendar_llamada': recomendar,
            'motivo_recomendar_llamada': motivo_llamada,
            'share_sin_clasificar_pct': round(ratio_sin * 100.0, 2) if total > 0 else 0.0,
        }
    )
    c360_guardar_perfil_cliente(cli, perfil)
    if commit:
        if recomendar:
            c360_upsert_llamada_snapshot_si_recomendada(cli.id, perfil, datetime.now().date())
        db.session.commit()
        try:
            c360_disparar_whatsapp_proximidad_post_commit(cli.id, etapa_fase_anterior, nueva_etapa)
        except Exception:
            m.app.logger.exception('C360: disparo WhatsApp proximidad fase cliente_id=%s', cliente_id)
    return perfil


def c360_sum_cupo_sugerido_clientes_activos():
    import app as m

    Cliente = m.Cliente
    s = 0.0
    for row in m.db.session.query(Cliente.c360_perfil_json).filter(Cliente.estado_credito == 'Activo').all():
        raw = row[0]
        if not raw:
            continue
        try:
            d = json.loads(raw)
            if isinstance(d, dict):
                s += float(d.get('cupo_sugerido_proxima_fase') or 0)
        except Exception:
            continue
    return int(round(s))


def c360_ocr_mock_actualizar_si_fase_superior(cliente, fase_detectada_raw):
    fv = c360_fase_obra_valida(fase_detectada_raw)
    if not fv:
        return False, 'Fase detectada inválida o vacía.'
    cur = (getattr(cliente, 'c360_etapa_actual', None) or '').strip().upper() or None
    cur_ord = c360_fase_orden(cur) if cur else 1
    if c360_fase_orden(fv) <= cur_ord:
        return False, 'La fase detectada no supera la etapa actual; no se ajustó límite.'
    cliente.c360_etapa_actual = fv
    lim0 = float(cliente.limite_credito or 0)
    bump = min(80000.0, lim0 * 0.10 + 25000.0)
    cliente.limite_credito = float(min(1e9, lim0 + bump))
    perfil = c360_perfil_dict_desde_cliente(cliente)
    perfil['ocr_ultimo'] = {
        'fase': fv,
        'bump_limite_clp': int(round(bump)),
        'ts': datetime.utcnow().isoformat() + 'Z',
    }
    c360_guardar_perfil_cliente(cliente, perfil)
    mtxt = f'${int(round(bump)):,}'.replace(',', '.')
    return True, f'OCR simulado: etapa actualizada a {fv}. Límite +{mtxt} (revisión humana recomendada).'


def c360_cron_secret():
    return (os.getenv('C360_CRON_SECRET') or os.getenv('COBRANZA_DISPATCH_CRON_SECRET') or '').strip()


def c360_lista_llamadas_recomendadas():
    import app as m

    Cliente = m.Cliente
    rows = []
    for c in (
        Cliente.query.filter(Cliente.estado_credito == 'Activo')
        .order_by(Cliente.nombre.asc())
        .limit(400)
        .all()
    ):
        if m._cliente_es_sistema_final(c):
            continue
        perfil = c360_perfil_dict_desde_cliente(c)
        if not perfil.get('recomendar_llamada'):
            continue
        motivo_ll = perfil.get('motivo_recomendar_llamada')
        if not motivo_ll:
            et_inf = ((c.c360_etapa_actual or '') or '').strip().upper()
            if et_inf == 'OBRA_GRUESA':
                motivo_ll = 'DATA_QUALITY'
            elif et_inf in ('INSTALACIONES', 'ACABADOS', 'TERMINACIONES'):
                motivo_ll = 'ETAPA_AVANZADA'
        rows.append(
            {
                'cliente': c,
                'etapa': c.c360_etapa_actual,
                'cupo_sugerido': int(perfil.get('cupo_sugerido_proxima_fase') or 0),
                'alerta': (perfil.get('alerta_oportunidad_credito') or '')[:520],
                'motivo_llamada': motivo_ll,
                'telefono': c.telefono,
                'ultima_prediccion_at': perfil.get('ultima_prediccion_at'),
            }
        )
    rows.sort(key=lambda r: -r['cupo_sugerido'])
    return rows


def c360_cliente_tiene_cuota_credito_vencida(cliente_id):
    import app as m

    if not cliente_id:
        return False
    hoy = date.today()
    pend = m._sql_cuota_saldo_pendiente()
    VentaCuotaCredito = m.VentaCuotaCredito
    Venta = m.Venta
    r = (
        m.db.session.query(VentaCuotaCredito.id)
        .join(Venta, Venta.id == VentaCuotaCredito.venta_id)
        .filter(
            Venta.cliente_id == int(cliente_id),
            Venta.metodo_pago == 'Credito',
            or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
            VentaCuotaCredito.fecha_vencimiento < hoy,
            pend > 0.01,
        )
        .limit(1)
        .first()
    )
    return r is not None


def c360_comercial_permite_oferta_proactiva(cli):
    import app as m

    if not cli:
        return False, 'sin_cliente'
    if (cli.estado_credito or '').strip() != 'Activo':
        return False, 'estado_credito'
    cupo = float(cli.limite_credito or 0) - float(cli.saldo_deudor or 0)
    fav = m._saldo_favor_actual(cli.id)
    if cupo <= 1.0 and fav <= 1.0:
        return False, 'sin_cupo_ni_saldo_favor'
    return True, ''


def c360_public_base_url():
    base = (os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')
    if base.startswith('http'):
        return base
    return ''


def c360_productos_kit_por_etapa(etapa, max_total=12, per_kw=2):
    import app as m

    Producto = m.Producto
    db = m.db
    et = (etapa or '').strip().upper() or 'OBRA_GRUESA'
    kws = C360_KIT_SUBCATEGORIA_KEYWORDS.get(et) or C360_KIT_SUBCATEGORIA_KEYWORDS['OBRA_GRUESA']
    seen = set()
    out = []
    for kw in kws:
        like = f'%{kw}%'
        q = (
            Producto.query.filter(
                Producto.activo == True,
                Producto.stock > 0,
                or_(
                    db.func.lower(db.func.coalesce(Producto.subcategoria, '')).like(like),
                    db.func.lower(db.func.coalesce(Producto.categoria, '')).like(like),
                    db.func.lower(Producto.nombre).like(like),
                ),
            )
            .order_by(Producto.stock.desc())
            .limit(per_kw)
        )
        for p in q.all():
            if p.id not in seen:
                seen.add(p.id)
                out.append(p)
                if len(out) >= max_total:
                    return out
    return out


def c360_wa_proactividad_reciente(cliente_id, dias=6, tipos=('OFERTA_AUTO',)):
    import app as m

    since = datetime.utcnow() - timedelta(days=int(dias))
    C360ProactivaOferta = m.C360ProactivaOferta
    q = C360ProactivaOferta.query.filter(
        C360ProactivaOferta.cliente_id == int(cliente_id),
        C360ProactivaOferta.tipo.in_(tuple(tipos)),
        C360ProactivaOferta.wa_sent_at.isnot(None),
        C360ProactivaOferta.wa_sent_at >= since,
    )
    return q.first() is not None


def generar_oferta_personalizada(
    cliente_id,
    *,
    commit=True,
    usuario_creador=None,
    tipo_oferta='OFERTA_MANUAL',
    etapa_anterior=None,
):
    import app as m

    m._asegurar_columnas_customer_360_legacy()
    if not m._asegurar_tabla_c360_proactiva_ofertas():
        return {'ok': False, 'error': 'tabla_proactiva'}
    Cliente = m.Cliente
    Cotizacion = m.Cotizacion
    CotizacionDetalle = m.CotizacionDetalle
    C360ProactivaOferta = m.C360ProactivaOferta
    db = m.db

    cli = Cliente.query.get(int(cliente_id))
    if not cli or m._cliente_es_sistema_final(cli):
        return {'ok': False, 'error': 'cliente_invalido'}
    etapa = (cli.c360_etapa_actual or 'OBRA_GRUESA').strip().upper()
    if etapa not in C360_FASE_OBRA_VALORES:
        etapa = 'OBRA_GRUESA'
    prods = c360_productos_kit_por_etapa(etapa)
    if not prods:
        return {'ok': False, 'error': 'sin_productos_con_stock'}
    perfil = c360_perfil_dict_desde_cliente(cli)
    score = float(perfil.get('score_puntualidad') or 0)
    pct_line = 0.05 if score > 90.0 else 0.0
    ucre = (usuario_creador or 'Motor C360')[:100]
    validez = 10
    cot = Cotizacion(
        numero=m._siguiente_numero_cotizacion(),
        fecha=datetime.utcnow(),
        validez_dias=validez,
        fecha_vencimiento=date.today() + timedelta(days=validez),
        cliente_id=cli.id,
        cliente_nombre=(cli.nombre or '')[:150] or None,
        cliente_rut=(cli.rut or '')[:20] or None,
        cliente_telefono=(cli.telefono or '')[:40] or None,
        cliente_giro=(cli.giro or '')[:150] if cli.giro else None,
        cliente_direccion=(cli.direccion or '')[:250] if cli.direccion else None,
        cliente_comuna=(cli.comuna or '')[:100] if cli.comuna else None,
        cliente_ciudad=(cli.ciudad or '')[:100] if cli.ciudad else None,
        cliente_correo=(cli.correo or '')[:150] if cli.correo else None,
        descuento_global=0.0,
        notas=f'Oferta proactiva C360 · etapa {etapa} · {tipo_oferta}',
        estado='Vigente',
        usuario_creador=ucre,
    )
    db.session.add(cot)
    db.session.flush()
    for p in prods:
        cant = 1.0
        pu = float(p.precio_venta or 0)
        bruto_line = cant * pu
        desc = round(bruto_line * pct_line, 2) if pct_line > 0 else 0.0
        cod = (p.codigo_interno or p.codigo_barra or p.codigo_chilemat or '')[:80] or None
        det = CotizacionDetalle(
            cotizacion_id=cot.id,
            producto_id=p.id,
            codigo=cod,
            nombre=(p.nombre or 'Producto')[:200],
            cantidad=cant,
            precio_unitario=pu,
            descuento=desc,
            subtotal=max(0.0, bruto_line - desc),
        )
        db.session.add(det)
    db.session.flush()
    neto, iva, total = m._calcular_totales_cotizacion(cot.detalles, cot.descuento_global)
    cot.neto = neto
    cot.iva = iva
    cot.monto_total = total
    token = secrets.token_urlsafe(24)[:48]
    seg = C360ProactivaOferta(
        token=token,
        cliente_id=cli.id,
        cotizacion_id=cot.id,
        etapa_disparo=etapa,
        etapa_anterior=(etapa_anterior or '')[:32] if etapa_anterior else None,
        tipo=(tipo_oferta or 'OFERTA_MANUAL')[:24],
    )
    db.session.add(seg)
    base = c360_public_base_url()
    if base:
        url_abs = f'{base}/p/c360-oferta/{token}'
    else:
        try:
            url_abs = url_for('c360_oferta_publica_landing', token=token, _external=True)
        except Exception:
            url_abs = f'/p/c360-oferta/{token}'
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return {
        'ok': True,
        'cotizacion_id': cot.id,
        'numero': cot.numero,
        'token': token,
        'url_publica_abs': url_abs,
        'monto_total': float(total or 0),
        'n_lineas': len(prods),
        'descuento_kit_pct': int(round(pct_line * 100)),
    }


generarOfertaPersonalizada = generar_oferta_personalizada


def c360_disparar_whatsapp_proximidad_post_commit(cliente_id, etapa_ant, etapa_nueva):
    import app as m

    if (os.getenv('C360_WA_AUTO_PHASE') or '').strip().lower() not in ('1', 'true', 'yes', 'on'):
        return {'ok': False, 'skipped': 'C360_WA_AUTO_PHASE_off'}
    if not etapa_nueva:
        return {'ok': False, 'skipped': 'sin_etapa'}
    ord_a = c360_fase_orden(etapa_ant)
    ord_n = c360_fase_orden(etapa_nueva)
    if ord_n <= ord_a:
        return {'ok': False, 'skipped': 'sin_ascenso_fase'}
    Cliente = m.Cliente
    C360ProactivaOferta = m.C360ProactivaOferta
    db = m.db
    cli = Cliente.query.get(int(cliente_id))
    if not cli or m._cliente_es_sistema_final(cli):
        return {'ok': False, 'error': 'cliente'}
    wa = m._telefono_whatsapp_chile_digits(cli.telefono)
    if not wa:
        return {'ok': False, 'error': 'sin_telefono'}
    if c360_wa_proactividad_reciente(cli.id, dias=6, tipos=('OFERTA_AUTO', 'COBRANZA_AUTO')):
        return {'ok': False, 'skipped': 'throttle'}
    mora = c360_cliente_tiene_cuota_credito_vencida(cli.id)
    permite, _mot = c360_comercial_permite_oferta_proactiva(cli)
    label = C360_FASE_OBRA_LABELS.get(etapa_nueva, etapa_nueva)
    nombre_corto = ((cli.nombre or 'cliente').strip().split() or [''])[0] or 'cliente'
    if mora:
        body = (
            f'Hola {nombre_corto}, le recordamos regularizar documentos a crédito con cuotas vencidas. '
            f'Ante dudas puede responder este mensaje. Gracias.'
        )
        ok, det = m._whatsapp_cloud_send_text(wa, body)
        tok = secrets.token_urlsafe(24)[:48]
        seg = C360ProactivaOferta(
            token=tok,
            cliente_id=cli.id,
            cotizacion_id=None,
            etapa_disparo=etapa_nueva,
            etapa_anterior=etapa_ant,
            tipo='COBRANZA_AUTO',
            wa_sent_at=datetime.utcnow() if ok else None,
            wa_result=(det or '')[:2000],
        )
        db.session.add(seg)
        db.session.commit()
        return {'ok': ok, 'tipo': 'COBRANZA_AUTO', 'detalle': det}
    if not permite:
        return {'ok': False, 'skipped': _mot}
    out = generar_oferta_personalizada(
        cli.id,
        commit=True,
        usuario_creador='Motor C360 (cambio fase)',
        tipo_oferta='OFERTA_AUTO',
        etapa_anterior=etapa_ant,
    )
    if not out.get('ok'):
        return out
    url = out.get('url_publica_abs') or ''
    body = (
        f'Hola {nombre_corto}, detectamos que estás iniciando la fase de {label}. '
        f'Tenemos un kit de materiales listo para despacho con precio especial para ti. '
        f'¿Te lo enviamos? Ver detalle y confirmar: {url}'
    )
    ok, det = m._whatsapp_cloud_send_text(wa, body)
    try:
        seg = (
            C360ProactivaOferta.query.filter_by(cotizacion_id=out['cotizacion_id'])
            .order_by(C360ProactivaOferta.id.desc())
            .first()
        )
        if seg:
            seg.wa_sent_at = datetime.utcnow() if ok else None
            seg.wa_result = (det or '')[:2000]
        db.session.commit()
    except Exception:
        db.session.rollback()
        m.app.logger.exception('C360: no se pudo registrar wa_result oferta auto')
    return {'ok': ok, 'tipo': 'OFERTA_AUTO', 'detalle': det, 'cotizacion_id': out.get('cotizacion_id')}


def c360_worker_recalcular_clientes(max_clientes=300):
    import app as m

    try:
        max_clientes = int(max_clientes)
    except (TypeError, ValueError):
        max_clientes = 300
    max_clientes = max(1, min(max_clientes, 2000))
    if not m._asegurar_columnas_customer_360_legacy():
        return {'ok': False, 'error': 'columnas_c360', 'procesados': 0, 'errores': 0, 'con_llamada': 0}
    procesados = 0
    errores = 0
    con_llamada = 0
    Cliente = m.Cliente
    db = m.db
    q = (
        Cliente.query.filter(Cliente.estado_credito == 'Activo')
        .order_by(Cliente.id.asc())
        .limit(max_clientes)
    )
    for c in q.all():
        if m._cliente_es_sistema_final(c):
            continue
        try:
            perfil = c360_project_predictor_actualizar_cliente(c.id, commit=True)
            procesados += 1
            if perfil and perfil.get('recomendar_llamada'):
                con_llamada += 1
        except Exception:
            db.session.rollback()
            errores += 1
            m.app.logger.exception('C360 worker: fallo cliente_id=%s', c.id)
    return {
        'ok': True,
        'procesados': procesados,
        'errores': errores,
        'con_llamada': con_llamada,
        'max_solicitado': max_clientes,
    }


def c360_upsert_llamada_snapshot_si_recomendada(cliente_id, perfil, fecha_dia):
    import app as m

    if not perfil or not perfil.get('recomendar_llamada'):
        return
    if not m._asegurar_tabla_c360_llamadas_snapshot():
        return
    try:
        fd = fecha_dia if isinstance(fecha_dia, date) else datetime.strptime(str(fecha_dia), '%Y-%m-%d').date()
    except Exception:
        fd = datetime.now().date()
    etapa = (perfil.get('etapa_actual') or perfil.get('etapa_sugerida') or '')[:32] or None
    cupo = int(perfil.get('cupo_sugerido_proxima_fase') or 0)
    score = perfil.get('score_puntualidad')
    try:
        score_f = float(score) if score is not None else None
    except (TypeError, ValueError):
        score_f = None
    C360LlamadaSnapshotDia = m.C360LlamadaSnapshotDia
    db = m.db
    row = C360LlamadaSnapshotDia.query.filter_by(fecha=fd, cliente_id=cliente_id).first()
    now = datetime.utcnow()
    if row:
        row.etapa_sugerida = etapa
        row.cupo_sugerido_clp = cupo
        row.score_snapshot = score_f
        row.run_at = now
    else:
        db.session.add(
            C360LlamadaSnapshotDia(
                fecha=fd,
                cliente_id=cliente_id,
                etapa_sugerida=etapa,
                cupo_sugerido_clp=cupo,
                score_snapshot=score_f,
                run_at=now,
            )
        )


def c360_dashboard_ia_metricas(fecha_ref):
    import app as m

    out = {
        'n_recomendadas': 0,
        'n_convertidas': 0,
        'tasa_pct': None,
        'monto_ventas_clp': 0.0,
        'costo_ia_clp': 0.0,
        'roi_pct': None,
        'roi_na': True,
        'filas': [],
        'tabla_ok': False,
    }
    if not m._asegurar_columnas_customer_360_legacy() or not m._asegurar_tabla_c360_llamadas_snapshot():
        return out
    C360LlamadaSnapshotDia = m.C360LlamadaSnapshotDia
    Venta = m.Venta
    Cliente = m.Cliente
    db = m.db
    snaps = C360LlamadaSnapshotDia.query.filter_by(fecha=fecha_ref).all()
    ids = [s.cliente_id for s in snaps]
    out['n_recomendadas'] = len(ids)
    out['tabla_ok'] = True
    if not ids:
        return out
    conv_rows = (
        db.session.query(Venta.cliente_id)
        .filter(
            db.func.date(Venta.fecha) == fecha_ref,
            Venta.cliente_id.in_(ids),
            Venta.estado != 'Anulada',
            Venta.estado != 'Abierta',
            Venta.monto_total > 0,
        )
        .distinct()
        .all()
    )
    conv_set = {r[0] for r in conv_rows}
    out['n_convertidas'] = len(conv_set)
    if out['n_recomendadas']:
        out['tasa_pct'] = (float(out['n_convertidas']) / float(out['n_recomendadas'])) * 100.0
    sum_clp = 0.0
    ventas_por_cliente = defaultdict(float)
    if conv_set:
        agg = (
            db.session.query(Venta.cliente_id, db.func.sum(Venta.monto_total))
            .filter(
                db.func.date(Venta.fecha) == fecha_ref,
                Venta.cliente_id.in_(list(conv_set)),
                Venta.estado != 'Anulada',
                Venta.estado != 'Abierta',
                Venta.monto_total > 0,
            )
            .group_by(Venta.cliente_id)
            .all()
        )
        for cid, sm in agg:
            ventas_por_cliente[cid] = float(sm or 0)
            sum_clp += float(sm or 0)
    out['monto_ventas_clp'] = sum_clp
    raw_cost = (os.getenv('C360_COSTO_IA_DIARIO_CLP') or '').strip()
    try:
        costo = float(raw_cost) if raw_cost else 0.0
    except ValueError:
        costo = 0.0
    out['costo_ia_clp'] = costo
    if costo > 0:
        out['roi_na'] = False
        out['roi_pct'] = ((sum_clp - costo) / costo) * 100.0
    clientes = {c.id: c for c in Cliente.query.filter(Cliente.id.in_(ids)).all()}
    filas = []
    for s in sorted(snaps, key=lambda x: (-(x.cupo_sugerido_clp or 0), x.cliente_id)):
        cid = s.cliente_id
        cli = clientes.get(cid)
        conv = cid in conv_set
        filas.append(
            {
                'cliente_id': cid,
                'nombre': cli.nombre if cli else f'#{cid}',
                'etapa': s.etapa_sugerida,
                'cupo_sugerido': s.cupo_sugerido_clp,
                'score': s.score_snapshot,
                'convertida': conv,
                'monto_dia_clp': ventas_por_cliente.get(cid, 0.0) if conv else 0.0,
            }
        )
    out['filas'] = filas
    return out


def c360_command_center_stats():
    import app as m

    rut_fin = m._rut_cliente_final_normalizado()
    out = {
        'tabla_ok': False,
        'n_clientes_activos': 0,
        'n_perfil_calculado': 0,
        'n_prioridad_llamada': 0,
        'cupo_sugerido_sigma_clp': 0,
        'dist_etapas': [],
        'serie_snapshots': [],
        'productos_sin_fase_activos': 0,
        'motor_max_default': 400,
    }
    if not m._asegurar_columnas_customer_360_legacy():
        return out
    out['tabla_ok'] = bool(m._asegurar_tabla_c360_llamadas_snapshot())
    Cliente = m.Cliente
    Producto = m.Producto
    C360LlamadaSnapshotDia = m.C360LlamadaSnapshotDia
    db = m.db
    try:
        base = Cliente.query.filter(Cliente.estado_credito == 'Activo', Cliente.rut != rut_fin)
        out['n_clientes_activos'] = int(base.count())
        out['n_perfil_calculado'] = int(
            base.filter(Cliente.c360_perfil_json.isnot(None), Cliente.c360_perfil_json != '').count()
        )
    except Exception:
        pass
    try:
        out['n_prioridad_llamada'] = len(c360_lista_llamadas_recomendadas())
    except Exception:
        out['n_prioridad_llamada'] = 0
    try:
        out['cupo_sugerido_sigma_clp'] = int(c360_sum_cupo_sugerido_clientes_activos())
    except Exception:
        out['cupo_sugerido_sigma_clp'] = 0
    try:
        rows = (
            db.session.query(Cliente.c360_etapa_actual, func.count(Cliente.id))
            .filter(Cliente.estado_credito == 'Activo', Cliente.rut != rut_fin)
            .group_by(Cliente.c360_etapa_actual)
            .all()
        )
        dist = [{'etapa': ((et or '') or 'Sin etapa').strip() or 'Sin etapa', 'n': int(cnt or 0)} for et, cnt in rows]
        dist.sort(key=lambda x: -x['n'])
        out['dist_etapas'] = dist
    except Exception:
        out['dist_etapas'] = []
    if out['tabla_ok']:
        try:
            hoy = datetime.now().date()
            since = hoy - timedelta(days=13)
            snap_rows = (
                db.session.query(C360LlamadaSnapshotDia.fecha, func.count(C360LlamadaSnapshotDia.id))
                .filter(C360LlamadaSnapshotDia.fecha >= since)
                .group_by(C360LlamadaSnapshotDia.fecha)
                .all()
            )
            byd = {r[0]: int(r[1]) for r in snap_rows}
            serie = []
            for i in range(13, -1, -1):
                d = hoy - timedelta(days=i)
                serie.append(
                    {'fecha': d.strftime('%Y-%m-%d'), 'label': d.strftime('%d/%m'), 'snapshots': byd.get(d, 0)}
                )
            out['serie_snapshots'] = serie
        except Exception:
            out['serie_snapshots'] = []
    try:
        out['productos_sin_fase_activos'] = int(
            Producto.query.filter(
                Producto.activo == True,
                or_(Producto.fase_obra.is_(None), Producto.fase_obra == ''),
            ).count()
        )
    except Exception:
        out['productos_sin_fase_activos'] = 0
    return out
