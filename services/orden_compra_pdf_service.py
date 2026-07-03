"""Presentación HTML/PDF para órdenes de compra (mismo layout que cotización)."""


def subtotal_linea_oc(cantidad, precio_unitario):
    return float(cantidad or 0) * float(precio_unitario or 0)


def codigo_impresion_linea_oc(oc, det, indice_linea):
    """Código visible en PDF: código de barras/catálogo; si no, ref. única de OC."""
    prod = getattr(det, 'producto', None)
    if prod:
        cod = (getattr(prod, 'codigo_barra', None) or getattr(prod, 'codigo', None) or '').strip()
        if cod:
            return cod, False
    num = (getattr(oc, 'numero', None) or 'OC').strip()
    return f'{num}-L{int(indice_linea):02d}', True


def lineas_presentacion_oc(oc):
    """Filas enriquecidas para detalle/PDF (código impresión, subtotal)."""
    detalles = sorted(oc.detalles or [], key=lambda d: d.id or 0)
    lineas = []
    for i, d in enumerate(detalles, start=1):
        prod = d.producto
        codigo_imp, codigo_es_ref = codigo_impresion_linea_oc(oc, d, i)
        lineas.append({
            'det': d,
            'indice': i,
            'codigo_impresion': codigo_imp,
            'codigo_es_ref': codigo_es_ref,
            'nombre': prod.nombre if prod else '—',
            'subtotal': subtotal_linea_oc(d.cantidad, d.precio_unitario),
        })
    return lineas


def presentacion_totales_oc(oc):
    """Totales para PDF: neto = suma líneas; total = neto + IVA 19%."""
    from core.domain.shared.iva_chile import iva_desde_neto_clp

    suma_lineas = sum(
        subtotal_linea_oc(d.cantidad, d.precio_unitario) for d in (oc.detalles or [])
    )
    neto = int(round(suma_lineas))
    iva = iva_desde_neto_clp(neto)
    total = neto + iva
    return {
        'suma_lineas': int(round(suma_lineas)),
        'descuento_global': 0,
        'neto': neto,
        'iva': iva,
        'total': total,
        'n_lineas': len(oc.detalles or []),
    }


def paginas_pdf_lineas(lineas, lineas_p1=24, lineas_sig=34):
    """Parte líneas del PDF: pág.1 con encabezado completo; pág.2+ con continuación."""
    items = list(lineas or [])
    if not items:
        return [{
            'lineas': [],
            'numero': 1,
            'total': 1,
            'es_primera': True,
            'es_ultima': True,
        }]

    paginas = []
    first = items[:lineas_p1]
    rest = items[lineas_p1:]

    if not rest:
        paginas.append({
            'lineas': first,
            'numero': 1,
            'total': 1,
            'es_primera': True,
            'es_ultima': True,
        })
        return paginas

    paginas.append({
        'lineas': first,
        'numero': 1,
        'total': 0,
        'es_primera': True,
        'es_ultima': False,
    })

    for i in range(0, len(rest), lineas_sig):
        chunk = rest[i:i + lineas_sig]
        paginas.append({
            'lineas': chunk,
            'numero': len(paginas) + 1,
            'total': 0,
            'es_primera': False,
            'es_ultima': False,
        })

    total = len(paginas)
    for p in paginas:
        p['total'] = total
        p['es_ultima'] = p['numero'] == total
    return paginas
