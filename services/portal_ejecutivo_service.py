"""Portal ejecutivo SD Constructor — KPIs gerencia/dueño (P1: resumen + activos)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

_EXCLUIR_CODIGO = ('TEST-%', 'DEMO_%', 'DEMO-%')
_PERIODOS = frozenset({'mes', 'trim', 'anio'})


def _m():
    import app as app_module
    return app_module


def _int_clp(val: float | int | None) -> int:
    return int(round(float(val or 0)))


def _fmt_clp(val: float | int | None) -> str:
    n = _int_clp(val)
    return f'${abs(n):,}'.replace(',', '.')


def portal_config() -> dict[str, Any]:
    """Lee parámetros del portal desde empresa_config (claves portal_*)."""
    m = _m()
    cfg = m.obtener_config_empresa()
    marca = (cfg.get('portal_marca') or 'SD Constructor').strip() or 'SD Constructor'
    gastos = _int_clp(cfg.get('portal_gastos_op_mensual_clp') or 0)
    activos_fijos = _int_clp(cfg.get('portal_activos_fijos_clp') or 0)
    meta_anual = _int_clp(cfg.get('portal_meta_ventas_anual_clp') or 0)
    return {
        'marca': marca,
        'gastos_op_mensual_clp': gastos,
        'activos_fijos_clp': activos_fijos,
        'meta_ventas_anual_clp': meta_anual,
    }


def rango_periodo(periodo: str) -> tuple[datetime, datetime, str, date, date, str]:
    """Retorna (dt_inicio, dt_fin_excl, periodo_norm, fecha_inicio, fecha_fin_incl)."""
    p = (periodo or 'mes').strip().lower()
    if p not in _PERIODOS:
        p = 'mes'
    hoy = date.today()
    if p == 'anio':
        start = date(hoy.year, 1, 1)
        label = f'Año {hoy.year}'
    elif p == 'trim':
        q = (hoy.month - 1) // 3
        start = date(hoy.year, q * 3 + 1, 1)
        label = f'Trimestre Q{q + 1} {hoy.year}'
    else:
        start = date(hoy.year, hoy.month, 1)
        label = hoy.strftime('%B %Y').capitalize()
    dt_inicio = datetime.combine(start, datetime.min.time())
    dt_fin_excl = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    return dt_inicio, dt_fin_excl, p, start, hoy, label


def _meses_en_periodo(periodo: str) -> int:
    if periodo == 'anio':
        return 12
    if periodo == 'trim':
        return 3
    return 1


def _gastos_op_periodo(periodo: str, cfg: dict[str, Any]) -> int:
    return cfg['gastos_op_mensual_clp'] * _meses_en_periodo(periodo)


def _ventas_y_cmv_periodo(dt_inicio: datetime, dt_fin_excl: datetime) -> tuple[int, int]:
    m = _m()
    ventas = (
        m.db.session.query(func.sum(m.Venta.monto_total))
        .filter(
            m.Venta.estado == 'Pagado',
            m.Venta.fecha >= dt_inicio,
            m.Venta.fecha < dt_fin_excl,
        )
        .scalar()
    )
    cmv = (
        m.db.session.query(
            func.sum(m.DetalleVenta.cantidad * func.coalesce(m.Producto.precio_compra, 0))
        )
        .join(m.Venta, m.Venta.id == m.DetalleVenta.id_venta)
        .join(m.Producto, m.Producto.id == m.DetalleVenta.id_producto)
        .filter(
            m.Venta.estado == 'Pagado',
            m.Venta.fecha >= dt_inicio,
            m.Venta.fecha < dt_fin_excl,
        )
        .scalar()
    )
    return _int_clp(ventas), _int_clp(cmv)


def _valor_inventario_compra() -> int:
    """Valor inventario al costo via SQL JOIN: evita cargar todos los productos en memoria."""
    m = _m()
    from sqlalchemy import text as _text
    try:
        val = m.db.session.execute(
            _text(
                """
                SELECT COALESCE(SUM(s.cantidad * p.precio_compra), 0)
                FROM stock_por_almacen s
                JOIN productos p ON p.id = s.id_producto
                WHERE p.activo = TRUE
                  AND (p.precio_compra IS NULL OR p.precio_compra >= 0)
                  AND (p.codigo_barra IS NULL
                       OR (p.codigo_barra NOT ILIKE 'TEST-%'
                           AND p.codigo_barra NOT ILIKE 'DEMO-%'
                           AND p.codigo_barra NOT ILIKE 'DEMO_%'))
                """
            )
        ).scalar()
        return _int_clp(float(val or 0))
    except Exception:
        return 0


def _cxc_total() -> int:
    m = _m()
    val = (
        m.db.session.query(func.sum(m.Cliente.saldo_deudor))
        .filter(m.Cliente.saldo_deudor > 0)
        .scalar()
    )
    return _int_clp(val)


def _caja_snapshot() -> int:
    m = _m()
    caja = m.Caja.query.filter_by(estado='Abierta').order_by(m.Caja.id.desc()).first()
    if not caja:
        return 0
    return _int_clp(caja.monto_inicial)


def _comprometido_compras() -> tuple[int, int]:
    """Monto y cantidad OC pendientes (estimado, no AP contable).
    total_estimado es un @property Python (cantidad×precio_unitario por línea),
    así que lo calculamos vía JOIN SQL directo sobre detalle_orden_compra.
    """
    m = _m()
    if not m._tablas_orden_compra_existen():
        return 0, 0
    from sqlalchemy import text as _text
    oc_estados = ('Borrador', 'Enviada', 'Parcial')
    try:
        row = m.db.session.execute(
            _text(
                """
                SELECT
                    COUNT(DISTINCT oc.id),
                    COALESCE(SUM(d.cantidad * d.precio_unitario), 0)
                FROM ordenes_compra oc
                LEFT JOIN detalle_orden_compra d ON d.orden_compra_id = oc.id
                WHERE oc.estado IN :estados
                """
            ),
            {'estados': tuple(oc_estados)},
        ).first()
        count = int(row[0] or 0)
        monto = float(row[1] or 0)
        return _int_clp(monto), count
    except Exception:
        return 0, 0


def _ventas_semanales_ultimas(n: int = 4) -> list[dict[str, Any]]:
    m = _m()
    hoy = date.today()
    out: list[dict[str, Any]] = []
    for i in range(n - 1, -1, -1):
        fin = hoy - timedelta(days=i * 7)
        inicio = fin - timedelta(days=6)
        dt0 = datetime.combine(inicio, datetime.min.time())
        dt1 = datetime.combine(fin + timedelta(days=1), datetime.min.time())
        val = (
            m.db.session.query(func.sum(m.Venta.monto_total))
            .filter(
                m.Venta.estado == 'Pagado',
                m.Venta.fecha >= dt0,
                m.Venta.fecha < dt1,
            )
            .scalar()
        )
        out.append({
            'semana': f'{inicio.strftime("%d/%m")}–{fin.strftime("%d/%m")}',
            'ventas_clp': _int_clp(val),
        })
    return out


def construir_resumen(periodo: str = 'mes') -> dict[str, Any]:
    cfg = portal_config()
    dt_inicio, dt_fin_excl, p, _, _, label = rango_periodo(periodo)
    ventas, cmv = _ventas_y_cmv_periodo(dt_inicio, dt_fin_excl)
    margen_bruto = ventas - cmv
    margen_pct = round((margen_bruto / ventas) * 100, 1) if ventas > 0 else 0.0
    gastos_op = _gastos_op_periodo(p, cfg)
    utilidad_est = margen_bruto - gastos_op

    inventario = _valor_inventario_compra()
    cxc = _cxc_total()
    caja = _caja_snapshot()
    activos_fijos = cfg['activos_fijos_clp']
    comprometido, oc_count = _comprometido_compras()
    inversion = inventario + cxc + caja + activos_fijos

    meta_anual = cfg['meta_ventas_anual_clp']
    meta_semana = _int_clp(meta_anual / 52) if meta_anual > 0 else 0

    return {
        'ok': True,
        'marca': cfg['marca'],
        'periodo': p,
        'periodo_label': label,
        'ventas_clp': ventas,
        'ventas_fmt': _fmt_clp(ventas),
        'cmv_clp': cmv,
        'margen_bruto_clp': margen_bruto,
        'margen_bruto_pct': margen_pct,
        'gastos_op_clp': gastos_op,
        'gastos_op_fmt': _fmt_clp(gastos_op),
        'utilidad_operativa_est_clp': utilidad_est,
        'utilidad_operativa_est_fmt': _fmt_clp(utilidad_est),
        'inversion_total_clp': inversion,
        'inversion_total_fmt': _fmt_clp(inversion),
        'desglose_inversion': {
            'inventario_clp': inventario,
            'cxc_clp': cxc,
            'caja_clp': caja,
            'activos_fijos_clp': activos_fijos,
        },
        'comprometido_compras_clp': comprometido,
        'oc_pendientes_count': oc_count,
        'ventas_semanales': _ventas_semanales_ultimas(4),
        'meta_ventas_semana_clp': meta_semana,
        'notas': [
            'Ventas: solo documentos en estado Pagado.',
            'CMV: cantidad vendida × precio compra del producto.',
            'Gasto operacional: monto fijo mensual configurado (× meses del período).',
            'Comprometido compras: estimado desde órdenes Borrador/Enviada/Parcial.',
            'Resultado operativo estimado = margen bruto − gasto operacional.',
        ],
    }


def construir_activos(periodo: str = 'mes') -> dict[str, Any]:
    cfg = portal_config()
    dt_inicio, dt_fin_excl, p, _, hoy, label = rango_periodo(periodo)
    ventas, cmv = _ventas_y_cmv_periodo(dt_inicio, dt_fin_excl)
    inventario = _valor_inventario_compra()
    cxc = _cxc_total()
    caja = _caja_snapshot()
    activos_fijos = cfg['activos_fijos_clp']
    comprometido, oc_count = _comprometido_compras()
    inversion = inventario + cxc + caja + activos_fijos

    dias = max(1, (hoy - dt_inicio.date()).days + 1)
    cmv_diario = cmv / dias if cmv else 0.0
    rotacion = round(cmv / inventario, 2) if inventario > 0 and cmv > 0 else 0.0
    dsi = round(inventario / cmv_diario, 0) if cmv_diario > 0 else None
    ventas_diario = ventas / dias if ventas else 0.0
    dias_cxc = round(cxc / ventas_diario, 0) if ventas_diario > 0 and cxc > 0 else None
    pasivos_est = cxc + comprometido
    apalancamiento = round((pasivos_est / inversion) * 100, 1) if inversion > 0 else 0.0

    return {
        'ok': True,
        'marca': cfg['marca'],
        'periodo': p,
        'periodo_label': label,
        'inventario_clp': inventario,
        'cxc_clp': cxc,
        'caja_clp': caja,
        'activos_fijos_clp': activos_fijos,
        'comprometido_compras_clp': comprometido,
        'oc_pendientes_count': oc_count,
        'inversion_operativa_clp': inversion,
        'rotacion_inventario': rotacion,
        'dias_stock_inventario': dsi,
        'dias_cxc_est': dias_cxc,
        'apalancamiento_operativo_pct': apalancamiento,
        'notas': [
            'Activos fijos: valor manual en configuración (sin módulo AF aún).',
            'Rotación inventario = CMV del período ÷ valor inventario a costo.',
            'Días stock = inventario ÷ (CMV/día del período).',
            'Apalancamiento = (CxC + comprometido compras) ÷ inversión operativa.',
        ],
    }
