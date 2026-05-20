# -*- coding: utf-8 -*-
"""
Cuadratura de caja — teórico gaveta, indicadores SII y arqueo ciego (fusión en tabla caja).

No altera el core de ventas; opera sobre instancias ORM ya cargadas del turno.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_DTE_ESTADOS_EMITIDOS = frozenset(
    {
        'ENVIADO',
        'ACEPTADO',
        'PENDIENTE_ENVIO',
        'FALLO_MATEMATICO',
        'RECHAZADO',
    }
)
_DTE_ESTADOS_TRACK_EXITOSO = frozenset({'ENVIADO', 'ACEPTADO'})


def _metodo_pago_normalizado(metodo: Optional[str]) -> str:
    m = (metodo or '').strip()
    if m.lower() == 'credito':
        return 'Credito'
    return m


def _monto_cobrado_venta_clp(venta: Any) -> int:
    bruto = max(0, int(round(float(getattr(venta, 'monto_total', 0) or 0))))
    favor = max(0, int(round(float(getattr(venta, 'saldo_favor_usado', 0) or 0))))
    return max(0, bruto - favor)


def calcular_monto_teorico_gaveta_turno(
    *,
    monto_inicial: float,
    total_efectivo: float,
    total_abonos_efectivo: float,
    cambios_efectivo_recibido: float,
    ingresos_manuales: float,
    cambios_efectivo_devuelto: float,
    egresos: float,
) -> float:
    """
    Misma fórmula que cerrar_caja: fondo + efectivo ventas + abonos efectivo
    + cambios recibidos + ingresos manuales − devoluciones efectivo − egresos.
    """
    return float(
        monto_inicial
        + total_efectivo
        + total_abonos_efectivo
        + cambios_efectivo_recibido
        + ingresos_manuales
        - cambios_efectivo_devuelto
        - egresos
    )


def calcular_indicadores_sii_turno(ventas_cuadre: List[Any]) -> Dict[str, int]:
    """
    Contadores tributarios del turno.

    - boletas_emitidas_qty: ventas con folio DTE o estado DTE conocido.
    - boletas_sincronizadas_qty / monto_total_sii: ventas con Track ID exitoso en BD.
    - monto_total_ventas: suma de montos cobrados en cuadre (referencia ERP).
    """
    emitidas = 0
    sincronizadas = 0
    total_ventas = 0
    total_sii = 0

    for v in ventas_cuadre or []:
        monto = _monto_cobrado_venta_clp(v)
        total_ventas += monto

        dte_estado = (getattr(v, 'dte_estado', None) or '').strip().upper()
        folio = getattr(v, 'nro_documento', None)
        track = (getattr(v, 'dte_track_id', None) or '').strip()

        tiene_emision = bool(folio) or dte_estado in _DTE_ESTADOS_EMITIDOS
        if tiene_emision:
            emitidas += 1

        track_exitoso = bool(track) and dte_estado in _DTE_ESTADOS_TRACK_EXITOSO
        if track_exitoso:
            sincronizadas += 1
            total_sii += monto

    return {
        'boletas_emitidas_qty': emitidas,
        'boletas_sincronizadas_qty': sincronizadas,
        'monto_total_ventas': total_ventas,
        'monto_total_sii': total_sii,
    }


def aplicar_indicadores_sii_caja(caja: Any, ventas_cuadre: List[Any]) -> Dict[str, int]:
    """Persiste en la instancia Caja los contadores SII del turno."""
    datos = calcular_indicadores_sii_turno(ventas_cuadre)
    caja.boletas_emitidas_qty = datos['boletas_emitidas_qty']
    caja.boletas_sincronizadas_qty = datos['boletas_sincronizadas_qty']
    caja.monto_total_sii = datos['monto_total_sii']
    return datos
