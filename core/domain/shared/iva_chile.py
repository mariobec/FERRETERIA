# -*- coding: utf-8 -*-
"""
IVA Chile 19% incluido (precios brutos retail) — única fuente de verdad.

Política: neto = round(bruto / 1.19), IVA = round(neto × 19%), total = neto + IVA.
Solo Decimal + ROUND_HALF_UP; sin float ni round() nativo en cálculos.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

IVA_TASA = Decimal('0.19')
IVA_FACTOR = Decimal('1.19')


class ErrorFallaMatematicaDTE(Exception):
    """Descuadre tributario detectado antes de firmar/enviar al SII."""

    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


def desglosar_iva_clp(total_bruto: int) -> tuple[int, int, int]:
    """
    Desglosa un monto bruto (IVA incluido) a neto, IVA y total coherentes con SII.

    Returns:
        (monto_neto, monto_iva, monto_total) con monto_total = neto + iva.
    """
    tb = max(0, int(total_bruto or 0))
    if tb == 0:
        return (0, 0, 0)
    bruto = Decimal(tb)
    neto = int((bruto / IVA_FACTOR).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    iva = int((Decimal(neto) * IVA_TASA).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    total = neto + iva
    return (neto, iva, total)


def iva_desde_neto_clp(monto_neto: int) -> int:
    """IVA 19% del neto (entero CLP)."""
    n = max(0, int(monto_neto or 0))
    if n == 0:
        return 0
    return int((Decimal(n) * IVA_TASA).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def subtotal_linea_bruto_clp(cantidad: int, precio_unitario, descuento_pct=0) -> int:
    """Subtotal línea en CLP (precio mostrador con IVA incluido × cantidad − descuento %)."""
    cant = Decimal(max(0, int(cantidad or 0)))
    pu = Decimal(str(precio_unitario or 0))
    desc = Decimal(str(descuento_pct or 0))
    val = cant * pu * (Decimal('1') - desc / Decimal('100'))
    return max(0, int(val.quantize(Decimal('1'), rounding=ROUND_HALF_UP)))


def distribuir_neto_en_lineas(subtotales_brutos: list[int], neto_header: int) -> list[int]:
    """Reparte neto de encabezado en líneas proporcional al bruto (última línea absorbe resto)."""
    if not subtotales_brutos:
        return []
    total_bruto = sum(max(0, int(x)) for x in subtotales_brutos)
    nh = max(0, int(neto_header or 0))
    if total_bruto <= 0:
        return [0] * len(subtotales_brutos)
    netos: list[int] = []
    asignado = 0
    n = len(subtotales_brutos)
    for i, bruto in enumerate(subtotales_brutos):
        bruto_i = max(0, int(bruto))
        if i == n - 1:
            netos.append(max(0, nh - asignado))
        else:
            parte = int(
                (Decimal(bruto_i) / Decimal(total_bruto) * Decimal(nh)).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP
                )
            )
            netos.append(parte)
            asignado += parte
    return netos


def linea_dte_item(
    nombre: str,
    cantidad: int,
    subtotal_bruto_linea: int,
    dte_tipo: int,
    *,
    neto_linea_asignado: int | None = None,
) -> dict:
    """
    Ítem para XML DTE: cumple PrcItem × Qty = monto de línea.

    Factura 33: PrcItem = precio unitario neto; monto_linea = neto de la línea.
    Boleta 39: PrcItem = precio unitario bruto (IVA incluido en mostrador).
    """
    qty = max(1, int(cantidad or 1))
    bruto_lin = max(0, int(subtotal_bruto_linea or 0))
    if int(dte_tipo) == 33:
        neto_lin = max(0, int(neto_linea_asignado if neto_linea_asignado is not None else desglosar_iva_clp(bruto_lin)[0]))
        prc = int((Decimal(neto_lin) / Decimal(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        monto = prc * qty
        if monto != neto_lin:
            prc = int((Decimal(neto_lin) / Decimal(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            monto = neto_lin
        return {
            'nombre': nombre,
            'cantidad': qty,
            'prc_item': prc,
            'monto_linea': monto,
            'monto_bruto_linea': bruto_lin,
        }
    prc_bruto = int((Decimal(bruto_lin) / Decimal(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    monto_bruto = prc_bruto * qty
    if monto_bruto != bruto_lin:
        monto_bruto = bruto_lin
        prc_bruto = int((Decimal(bruto_lin) / Decimal(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return {
        'nombre': nombre,
        'cantidad': qty,
        'prc_item': prc_bruto,
        'monto_linea': monto_bruto,
        'monto_bruto_linea': bruto_lin,
    }


def validar_contexto_dte_matematico(contexto: dict, *, dte_tipo_factura: int = 33) -> None:
    """
    Pre-flight antes de firmar XML. Factura afecta (33): Neto+IVA=Total e IVA=19% del neto.
    Verifica PrcItem × Qty = monto_linea en cada ítem.
    """
    neto = int(contexto.get('monto_neto') or 0)
    iva = int(contexto.get('monto_iva') or 0)
    total = int(contexto.get('monto_total') or 0)
    dte = int(contexto.get('dte_tipo') or 0)

    if neto + iva != total:
        raise ErrorFallaMatematicaDTE('Error: Descuadre en ecuación Neto + IVA')

    if dte == int(dte_tipo_factura):
        if iva != iva_desde_neto_clp(neto):
            raise ErrorFallaMatematicaDTE('Error: IVA no corresponde al 19% del Neto')

    suma_lineas_neto = 0
    suma_lineas_bruto = 0
    for it in contexto.get('items') or []:
        qty = max(1, int(it.get('cantidad', 1) or 1))
        prc = int(it.get('prc_item', it.get('precio', 0)) or 0)
        monto = int(it.get('monto_linea', prc * qty) or 0)
        if prc * qty != monto:
            raise ErrorFallaMatematicaDTE(
                'Error: PrcItem×QtyItem distinto al monto de línea (%s×%s≠%s)' % (prc, qty, monto)
            )
        if dte == int(dte_tipo_factura):
            suma_lineas_neto += monto
        suma_lineas_bruto += int(it.get('monto_bruto_linea', monto) or 0)

    if dte == int(dte_tipo_factura) and suma_lineas_neto != neto:
        raise ErrorFallaMatematicaDTE(
            'Error: Suma netos de línea (%s) distinta a MntNeto (%s)' % (suma_lineas_neto, neto)
        )
