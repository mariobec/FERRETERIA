"""Listado / filtros / archivado masivo RCV — recepciones SD-1."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, extract, or_

from services.rcv_sii_import_service import ESTADO_ARCHIVADO_RCV

PER_PAGE_RECEPCIONES = 50
ANIOS_FILTRO = (2023, 2024, 2025, 2026)
ORDEN_FECHA = 'fecha'
ORDEN_MONTO = 'monto'


def _fecha_doc_expr():
    """Coalesce fecha_documento / fecha_recepcion para filtros."""
    from app import RecepcionCompra
    from sqlalchemy import func

    R = RecepcionCompra
    return func.coalesce(R.fecha_documento, func.date(R.fecha_recepcion))


def _filtro_mes_anio(q, year: int, month: int | None = None):
    R = _modelo_recepcion()
    fd = _fecha_doc_expr()
    if month:
        return q.filter(extract('year', fd) == year, extract('month', fd) == month)
    return _filtro_anio(q, year)


def _filtro_rango_fechas(q, fecha_desde, fecha_hasta):
    if not fecha_desde and not fecha_hasta:
        return q
    fd = _fecha_doc_expr()
    if fecha_desde:
        q = q.filter(fd >= fecha_desde)
    if fecha_hasta:
        q = q.filter(fd <= fecha_hasta)
    return q


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


def normalizar_folio_busqueda(folio: str | None) -> str:
    """Folio SII: solo dígitos y letras, sin puntos ni espacios extra."""
    s = (folio or '').strip()
    if not s:
        return ''
    return ''.join(ch for ch in s if ch.isalnum())


def query_lista_recepciones(
    *,
    estado: str | None = None,
    anio: int | None = None,
    mes: int | None = None,
    fecha_desde=None,
    fecha_hasta=None,
    folio: str | None = None,
    producto: str | None = None,
    origen: str | None = None,
    orden: str = ORDEN_FECHA,
    ocultar_archivado: bool = True,
    sin_oc: bool = False,
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
        if mes and 1 <= int(mes) <= 12:
            q = _filtro_mes_anio(q, int(anio), int(mes))
        else:
            q = _filtro_anio(q, anio)

    q = _filtro_rango_fechas(q, fecha_desde, fecha_hasta)

    origen_q = (origen or '').strip()
    if origen_q:
        q = q.filter(RecepcionCompra.origen_importacion == origen_q)

    folio_q = normalizar_folio_busqueda(folio)
    if folio_q:
        patron = f'%{folio_q}%'
        q = q.filter(RecepcionCompra.documento_numero.ilike(patron))

    if sin_oc:
        q = q.filter(RecepcionCompra.orden_compra_id.is_(None))

    prod_q = (producto or '').strip()
    if prod_q:
        from services.compras_busqueda_service import filtro_recepcion_por_producto

        q = filtro_recepcion_por_producto(q, prod_q)

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
    sin_oc = base.filter(R.orden_compra_id.is_(None)).filter(
        R.estado.in_(('Pendiente de Items', 'Pendiente', 'Incompleta'))
    ).count()
    limpiables_rcv_2026 = _query_recepciones_limpiables(anio=2026, origen='rcv_sii').count()
    return {
        'pendiente_items': pendientes,
        'pendiente_items_2026': p2026,
        'sin_oc_activas': sin_oc,
        'limpiables_rcv_2026': limpiables_rcv_2026,
    }


def _query_recepciones_limpiables(
    *,
    anio: int | None = None,
    mes: int | None = None,
    ids: list[int] | None = None,
    origen: str | None = 'rcv_sii',
    solo_sin_lineas: bool = True,
    estados: tuple[str, ...] | None = None,
):
    """Recepciones documentales eliminables (sin stock recibido)."""
    from sqlalchemy import exists, inspect as sa_inspect

    from app import (
        DetalleRecepcion,
        RecepcionCompra,
        RecepcionLineaDocumento,
        _asegurar_columnas_recepcion_rcv,
        _asegurar_tabla_recepcion_linea_documento,
        db,
    )
    from services.rcv_sii_import_service import ESTADO_ARCHIVADO_RCV, ESTADO_PENDIENTE_ITEMS

    _asegurar_columnas_recepcion_rcv()
    _asegurar_tabla_recepcion_linea_documento()

    R = RecepcionCompra
    estados_ok = estados or (ESTADO_PENDIENTE_ITEMS, ESTADO_ARCHIVADO_RCV)
    q = R.query.filter(R.estado.in_(estados_ok))

    origen_q = (origen or '').strip()
    if origen_q:
        q = q.filter(R.origen_importacion == origen_q)

    if ids:
        q = q.filter(R.id.in_(ids))
    elif anio in ANIOS_FILTRO:
        if mes and 1 <= int(mes) <= 12:
            q = _filtro_mes_anio(q, int(anio), int(mes))
        else:
            q = _filtro_anio(q, int(anio))

    insp = sa_inspect(db.engine)
    tiene_tabla_doc = insp.has_table('recepcion_linea_documento')

    if solo_sin_lineas:
        q = q.filter(~exists().where(DetalleRecepcion.recepcion_id == R.id))
        if tiene_tabla_doc:
            q = q.filter(~exists().where(RecepcionLineaDocumento.recepcion_id == R.id))
    else:
        q = q.filter(
            ~exists().where(
                and_(
                    DetalleRecepcion.recepcion_id == R.id,
                    DetalleRecepcion.cantidad_recibida > 0,
                )
            )
        )

    return q


def preview_limpiar_recepciones_documentales(**kwargs) -> dict[str, Any]:
    q = _query_recepciones_limpiables(**kwargs)
    return {'ok': True, 'candidatas': q.count(), **kwargs}


def limpiar_recepciones_documentales(
    *,
    dry_run: bool = False,
    borrar_adjunto_fn=None,
    **kwargs,
) -> dict[str, Any]:
    """
    Elimina recepciones documentales vacías (típico import RCV sin ítems).
    No toca filas con stock recibido ni estados operativos (Pendiente/Incompleta/Finalizada).
    """
    from app import (
        DetalleRecepcion,
        RecepcionCompra,
        RecepcionLineaDocumento,
        db,
    )
    from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS

    if not kwargs.get('ids') and kwargs.get('anio') not in ANIOS_FILTRO:
        return {'ok': False, 'error': 'Indique año o IDs', 'eliminadas': 0}

    q = _query_recepciones_limpiables(**kwargs)
    filas = q.all()
    preview = len(filas)
    if dry_run:
        return {
            'ok': True,
            'dry_run': True,
            'candidatas': preview,
            'eliminadas': 0,
            **{k: v for k, v in kwargs.items() if k != 'borrar_adjunto_fn'},
        }

    eliminadas = 0
    omitidas: list[str] = []
    for rec in filas:
        dets = DetalleRecepcion.query.filter_by(recepcion_id=rec.id).all()
        if any(int(d.cantidad_recibida or 0) > 0 for d in dets):
            omitidas.append(f'#{rec.id}: stock recibido')
            continue
        if rec.estado not in (ESTADO_PENDIENTE_ITEMS, ESTADO_ARCHIVADO_RCV):
            omitidas.append(f'#{rec.id}: estado {rec.estado}')
            continue

        DetalleRecepcion.query.filter_by(recepcion_id=rec.id).delete(synchronize_session=False)
        RecepcionLineaDocumento.query.filter_by(recepcion_id=rec.id).delete(synchronize_session=False)
        if borrar_adjunto_fn:
            try:
                borrar_adjunto_fn(rec.id)
            except Exception:
                pass
        db.session.delete(rec)
        eliminadas += 1

    db.session.commit()
    return {
        'ok': True,
        'dry_run': False,
        'candidatas': preview,
        'eliminadas': eliminadas,
        'omitidas': omitidas,
        **{k: v for k, v in kwargs.items() if k not in ('dry_run', 'borrar_adjunto_fn')},
    }
