"""Orquestación impresión vale POS — navegador o térmica ESC/POS."""
from __future__ import annotations

import os
from typing import Any

from services.ticket_impresion_escpos import (
    build_retiro_escpos_bytes,
    build_vale_escpos_bytes,
    enviar_raw_escpos,
    listar_impresoras_windows,
    resolver_nombre_impresora,
)


def telefono_ticket_display(raw: str | None) -> str:
    """Formato +569XXXXXXXX para pie de ticket."""
    d = ''.join(ch for ch in (raw or '') if ch.isdigit())
    if not d:
        return ''
    if d.startswith('56') and len(d) >= 11:
        return f'+{d}'
    if len(d) == 9:
        return f'+56{d}'
    return f'+{d}'


def pos_impresion_modo() -> str:
    """
    browser = solo ventana imprimir (actual)
    escpos = solo térmica Windows (XP-80T)
    both = térmica + navegador
    """
    raw = (os.getenv('POS_IMPRESION_MODO') or 'browser').strip().lower()
    if raw in ('escpos', 'termica', 'thermal', 'xprinter'):
        return 'escpos'
    if raw in ('both', 'ambos', 'mixto'):
        return 'both'
    return 'browser'


def pos_impresion_termica_habilitada() -> bool:
    return pos_impresion_modo() in ('escpos', 'both')


def pos_impresion_browser_habilitada() -> bool:
    return pos_impresion_modo() in ('browser', 'both')


def construir_contexto_vale_impresion(venta, *, empresa_cfg: dict | None = None) -> dict[str, Any]:
    """Contexto plano alineado a ticket_vale.html."""
    from app import (
        _detalle_punto_retiro_efectivo,
        _ticket_agrupar_detalles_por_retiro,
        _ticket_linea_subtotal_clp,
        _ticket_usar_bloques_por_retiro,
        obtener_config_empresa,
    )

    if empresa_cfg is None:
        empresa_cfg = obtener_config_empresa()
    empresa_nom = (
        (empresa_cfg.get('nombre_comercial') or empresa_cfg.get('razon_social') or 'Ferreteria')
    ).strip()

    cliente_nom = '—'
    if getattr(venta, 'cliente', None) and venta.cliente.nombre:
        cliente_nom = venta.cliente.nombre.strip()

    etiqueta = {'Tienda': '[T]', 'Bodega': '[B]', 'Despacho': '[D]'}
    buckets, subtotales, _orden = _ticket_agrupar_detalles_por_retiro(venta)
    usar_bloques = _ticket_usar_bloques_por_retiro(venta, buckets)

    def _linea_dict(d):
        kk = _detalle_punto_retiro_efectivo(d, venta)
        sub = _ticket_linea_subtotal_clp(d)
        nom = (d.producto.nombre if d.producto else '—') or '—'
        return {
            'prefijo': etiqueta.get(kk, '[T]'),
            'nombre': nom,
            'cantidad': int(d.cantidad or 0),
            'subtotal': sub,
        }

    ctx: dict[str, Any] = {
        'venta_id': venta.id,
        'empresa': empresa_nom,
        'fecha_fmt': venta.fecha.strftime('%d/%m/%Y %H:%M') if venta.fecha else '',
        'prioridad': venta.prioridad,
        'vendedor': venta.usuario,
        'cliente': cliente_nom,
        'punto_retiro': (venta.punto_retiro or '').strip(),
        'es_borrador': (venta.estado or '').strip() == 'Abierta',
        'total': float(venta.monto_total or 0),
        'lineas': [],
        'bloques': [],
        'telefono_contacto': telefono_ticket_display(
            empresa_cfg.get('telefono') or os.getenv('EMPRESA_TELEFONO')
        ),
        'direccion_empresa': (
            (empresa_cfg.get('direccion') or os.getenv('EMPRESA_DIRECCION') or '').strip()
        ),
    }

    if usar_bloques:
        titulos = {
            'Tienda': 'PRODUCTOS DE TIENDA',
            'Bodega': 'PRODUCTOS DE BODEGA',
            'Despacho': 'PRODUCTOS DESPACHO',
        }
        for key, tit in titulos.items():
            rows = buckets.get(key) or []
            if not rows:
                continue
            ctx['bloques'].append({
                'titulo': tit,
                'lineas': [_linea_dict(d) for d in rows],
            })
        ctx['subtotales'] = {
            k: float(subtotales.get(k) or 0) for k in ('Tienda', 'Bodega', 'Despacho')
        }
    else:
        ctx['lineas'] = [_linea_dict(d) for d in (venta.detalles or [])]

    ctx['folio_barcode'] = f'VL{int(venta.id):06d}'
    ctx['qr_url'] = None

    try:
        from services.promociones_service import listar_aplicaciones_venta
        from app import db as _db

        apps = listar_aplicaciones_venta(_db, int(venta.id))
        ctx['promociones'] = apps
        ctx['descuento_promos'] = sum(int(a.get('monto_descuento') or 0) for a in apps)
        if ctx['descuento_promos'] > 0:
            sub = sum(int(_ticket_linea_subtotal_clp(d)) for d in (venta.detalles or []))
            ctx['subtotal_lineas'] = sub
            ctx['total'] = float(max(0, sub - ctx['descuento_promos']))
    except Exception:
        ctx['promociones'] = []
        ctx['descuento_promos'] = 0

    cot_id = getattr(venta, 'cotizacion_origen_id', None)
    if cot_id:
        try:
            from app import Cotizacion

            cot = Cotizacion.query.get(int(cot_id))
            if cot and getattr(cot, 'numero', None):
                ctx['cotizacion_origen'] = cot.numero
        except Exception:
            pass

    return ctx


def construir_contexto_retiro_impresion(venta, *, empresa_cfg: dict | None = None) -> dict[str, Any]:
    """Contexto plano alineado a ticket_retiro_qr.html (slices Tienda/Bodega)."""
    from app import (
        _ticket_agrupar_detalles_por_retiro,
        _ticket_usar_bloques_por_retiro,
        obtener_config_empresa,
        pos_despacho_vale_token_create,
    )
    from services.despacho_qr_service import url_despacho_qr_corta
    from services.ticket_retiro_service import build_slices_retiro_ticket

    if empresa_cfg is None:
        empresa_cfg = obtener_config_empresa()
    empresa_nom = (
        (empresa_cfg.get('nombre_comercial') or empresa_cfg.get('razon_social') or 'Ferreteria')
    ).strip()

    cliente_nom = 'Cliente final'
    if getattr(venta, 'cliente', None) and venta.cliente.nombre:
        cliente_nom = venta.cliente.nombre.strip()

    slices_raw = build_slices_retiro_ticket(
        venta,
        agrupar_fn=_ticket_agrupar_detalles_por_retiro,
        usar_bloques_fn=_ticket_usar_bloques_por_retiro,
        token_create_fn=pos_despacho_vale_token_create,
        url_qr_fn=url_despacho_qr_corta,
        qr_png_fn=lambda _u: None,
    )
    slices: list[dict[str, Any]] = []
    for sl in slices_raw or []:
        lineas = []
        for d in sl.get('detalles') or []:
            prod = getattr(d, 'producto', None)
            nom = (prod.nombre if prod else None) or f"#{getattr(d, 'id_producto', '')}"
            lineas.append({
                'nombre': nom,
                'cantidad': int(getattr(d, 'cantidad', 0) or 0),
            })
        slices.append({
            'canal': sl.get('canal'),
            'canal_label': sl.get('canal_label'),
            'subtotal': float(sl.get('subtotal') or 0),
            'qr_url': (sl.get('qr_url') or '').strip() or None,
            'lineas': lineas,
        })

    return {
        'venta_id': venta.id,
        'empresa': empresa_nom,
        'fecha_fmt': venta.fecha.strftime('%d/%m/%Y %H:%M') if venta.fecha else '',
        'cliente': cliente_nom,
        'folio_barcode': f'VL{int(venta.id):06d}',
        'slices': slices,
        'direccion_empresa': (
            (empresa_cfg.get('direccion') or os.getenv('EMPRESA_DIRECCION') or '').strip()
        ),
        'telefono_contacto': telefono_ticket_display(
            empresa_cfg.get('telefono') or os.getenv('EMPRESA_TELEFONO')
        ),
    }


def imprimir_vale_termica(venta, *, printer_name: str | None = None) -> dict[str, Any]:
    """Imprime vale en impresora térmica ESC/POS (Windows)."""
    if not pos_impresion_termica_habilitada():
        return {'ok': False, 'error': 'modo_browser', 'mensaje': 'Modo impresión no es térmica.'}
    ctx = construir_contexto_vale_impresion(venta)
    data = build_vale_escpos_bytes(ctx)
    return enviar_raw_escpos(data, printer_name=printer_name)


def imprimir_vale_termica_por_id(venta_id: int, *, printer_name: str | None = None) -> dict[str, Any]:
    from app import DetalleVenta, Venta
    from sqlalchemy.orm import joinedload

    venta = Venta.query.options(
        joinedload(Venta.cliente),
        joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
    ).get(int(venta_id))
    if not venta:
        return {'ok': False, 'error': 'no_venta', 'mensaje': 'Vale no encontrado.'}
    st = (venta.estado or '').strip()
    if st not in ('Pendiente', 'Abierta'):
        return {'ok': False, 'error': 'estado', 'mensaje': f'Estado «{st}» no admite ticket vale.'}
    return imprimir_vale_termica(venta, printer_name=printer_name)


def imprimir_retiro_termica(venta, *, printer_name: str | None = None) -> dict[str, Any]:
    """Imprime ticket(s) de retiro en térmica ESC/POS tras cobro."""
    if not pos_impresion_termica_habilitada():
        return {'ok': False, 'error': 'modo_browser', 'mensaje': 'Modo impresión no es térmica.'}
    st = (getattr(venta, 'estado', None) or '').strip()
    if st != 'Pagado':
        return {
            'ok': False,
            'error': 'estado',
            'mensaje': f'Estado «{st}» no admite ticket de retiro (debe estar Pagado).',
        }
    ctx = construir_contexto_retiro_impresion(venta)
    if not (ctx.get('slices') or []):
        return {'ok': False, 'error': 'sin_slices', 'mensaje': 'No hay productos para ticket de retiro.'}
    data = build_retiro_escpos_bytes(ctx)
    return enviar_raw_escpos(data, printer_name=printer_name)


def imprimir_retiro_termica_por_id(venta_id: int, *, printer_name: str | None = None) -> dict[str, Any]:
    from app import DetalleVenta, Venta
    from sqlalchemy.orm import joinedload

    venta = Venta.query.options(
        joinedload(Venta.cliente),
        joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
    ).get(int(venta_id))
    if not venta:
        return {'ok': False, 'error': 'no_venta', 'mensaje': 'Venta no encontrada.'}
    return imprimir_retiro_termica(venta, printer_name=printer_name)


def diagnostico_impresora() -> dict[str, Any]:
    from services.ticket_impresion_escpos import (
        _candidatos_impresora_termica,
        _es_impresora_virtual,
        _impresora_abrible,
    )

    lista = listar_impresoras_windows()
    cfg = os.getenv('POS_IMPRESORA_NOMBRE', '').strip() or None
    resuelta = resolver_nombre_impresora()
    return {
        'modo': pos_impresion_modo(),
        'plataforma': os.name,
        'impresora_configurada': cfg,
        'impresora_resuelta': resuelta,
        'impresoras_windows': lista,
        'impresoras_usables': [
            p for p in lista if _impresora_abrible(p) and not _es_impresora_virtual(p)
        ],
        'candidatos_orden': _candidatos_impresora_termica(cfg)[:10],
        'termica_habilitada': pos_impresion_termica_habilitada(),
        'hint': (
            'Modo browser solo abre ventana Imprimir del navegador. '
            'Para XP-80 directo: POS_IMPRESION_MODO=escpos o both y POS_IMPRESORA_NOMBRE=XP-80'
        ),
    }
