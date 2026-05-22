"""Listado / filtros / archivado masivo RCV — recepciones SD-1."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, extract, or_

from services.rcv_sii_import_service import ESTADO_ARCHIVADO_RCV

PER_PAGE_RECEPCIONES = 50
ANIOS_FILTRO = (2025, 2026)
ORDEN_FECHA = 'fecha'
ORDEN_MONTO = 'monto'


def _modelo_recepcion():
    from app import RecepcionCompra

    return RecepcionCompra


def _filtro_anio(q, year: int):
    R = _modelo_recepcion()
    return q.filter(
        or_(
            extract('year', R.fecha_documento) == year,
            and_(
                R.fecha_documento.is_(None),
                extract('year', R.fecha_recepcion) == year,
            ),
        )
    )


def query_lista_recepciones(
    *,
    estado: str | None = None,
    anio: int | None = None,
    orden: str = ORDEN_FECHA,
    ocultar_archivado: bool = True,
):
    """Query base para /recepciones (joinedload proveedor aplicado en ruta)."""
    from app import RecepcionCompra, _asegurar_columnas_recepcion_rcv

    _asegurar_columnas_recepcion_rcv()
    q = RecepcionCompra.query
    est = (estado or '').strip()
    if est == '__todos__':
        pass
    elif est:
        q = q.filter(RecepcionCompra.estado == est)
    elif ocultar_archivado:
        q = q.filter(RecepcionCompra.estado != ESTADO_ARCHIVADO_RCV)

    if anio in ANIOS_FILTRO:
        q = _filtro_anio(q, anio)

    orden = (orden or ORDEN_FECHA).strip().lower()
    if orden == ORDEN_MONTO:
        q = q.order_by(
            RecepcionCompra.monto_total.desc().nullslast(),
            RecepcionCompra.id.desc(),
        )
    else:
        q = q.order_by(
            RecepcionCompra.fecha_documento.desc().nullslast(),
            RecepcionCompra.fecha_recepcion.desc(),
            RecepcionCompra.id.desc(),
        )
    return q


def archivar_recepciones_lote(
    *,
    anio: int | None = None,
    ids: list[int] | None = None,
    solo_pendiente_items: bool = True,
) -> dict[str, Any]:
    """
    Marca recepciones como Archivado RCV (cola tributaria, fuera de bodega).
    Solo actualiza filas en Pendiente de Items por defecto.
    """
    from app import RecepcionCompra, _asegurar_columnas_recepcion_rcv, db
    from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS

    _asegurar_columnas_recepcion_rcv()
    R = RecepcionCompra
    q = R.query
    if solo_pendiente_items:
        q = q.filter(R.estado == ESTADO_PENDIENTE_ITEMS)
    else:
        q = q.filter(R.estado != ESTADO_ARCHIVADO_RCV)
    if ids:
        q = q.filter(R.id.in_(ids))
    elif anio in ANIOS_FILTRO:
        q = _filtro_anio(q, anio)
    else:
        return {'ok': False, 'error': 'Indique año o IDs', 'actualizadas': 0}

    filas = q.all()
    for rec in filas:
        rec.estado = ESTADO_ARCHIVADO_RCV
    db.session.commit()
    return {'ok': True, 'actualizadas': len(filas), 'anio': anio, 'ids': ids or []}


def resumen_filtros_actuales(estado: str | None, anio: int | None) -> dict[str, Any]:
    """Conteos ligeros para badges en cabecera (una query agregada opcional — simplificado)."""
    from app import RecepcionCompra, db
    from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS

    R = RecepcionCompra
    base = R.query.filter(R.estado != ESTADO_ARCHIVADO_RCV)
    pendientes = base.filter(R.estado == ESTADO_PENDIENTE_ITEMS).count()
    p2026 = _filtro_anio(
        base.filter(R.estado == ESTADO_PENDIENTE_ITEMS), 2026
    ).count()
    return {'pendiente_items': pendientes, 'pendiente_items_2026': p2026}
