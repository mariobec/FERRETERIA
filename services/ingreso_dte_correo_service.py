# -*- coding: utf-8 -*-
"""
DTE XML compra (correo) → RecepcionCompra documental sin stock.

Paso 2 SD: cabecera + líneas esperadas del XML; cantidad_recibida=0 hasta confirmación física.
No llama a _aplicar_linea_recepcion ni ajustar_stock_almacen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from services.parser_xml_compra import (
    DteCompraParseado,
    ParserXmlCompraError,
    parsear_archivo_dte_compra,
)
from services.rcv_sii_import_service import ESTADO_PENDIENTE_ITEMS, _proveedor_por_rut_o_nombre

ORIGEN_DTE_CORREO = 'dte_correo'

PathLike = str | Path


@dataclass
class LineaSinMatch:
    nro_linea: int
    nombre: str
    codigo_factura: str | None
    cantidad: float
    precio_unitario: float | None


@dataclass
class ResultadoIngresoDteCorreo:
    ok: bool
    recepcion_id: int | None = None
    recepcion_creada: bool = False
    recepcion_actualizada: bool = False
    folio: str | None = None
    proveedor_id: int | None = None
    lineas_documentales: int = 0
    lineas_sin_match: list[LineaSinMatch] = field(default_factory=list)
    omitida_duplicado: bool = False
    errores: list[str] = field(default_factory=list)
    archivo_xml: str | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            'ok': self.ok,
            'recepcion_id': self.recepcion_id,
            'recepcion_creada': self.recepcion_creada,
            'recepcion_actualizada': self.recepcion_actualizada,
            'folio': self.folio,
            'proveedor_id': self.proveedor_id,
            'lineas_documentales': self.lineas_documentales,
            'lineas_sin_match': [
                {
                    'nro_linea': x.nro_linea,
                    'nombre': x.nombre,
                    'codigo_factura': x.codigo_factura,
                    'cantidad': x.cantidad,
                    'precio_unitario': x.precio_unitario,
                }
                for x in self.lineas_sin_match
            ],
            'omitida_duplicado': self.omitida_duplicado,
            'errores': self.errores,
            'archivo_xml': self.archivo_xml,
        }


def _tipo_documento_recepcion(tipo_dte: int) -> str:
    if int(tipo_dte) in (52,):
        return 'Guia de Despacho'
    return 'Factura'


def _folio_str(folio: int) -> str:
    return str(int(folio)).strip()


def _persistir_lineas_documento_xml(
    rec_id: int,
    lineas_dte,
    *,
    proveedor_id: int,
    _codigo_linea_factura,
    _matchear_producto_linea_factura,
    RecepcionLineaDocumento,
    DetalleRecepcion,
    db,
    res: ResultadoIngresoDteCorreo,
) -> None:
    """Guarda todas las líneas del XML; crea DetalleRecepcion solo si hay match SKU."""
    for ln in lineas_dte:
        cant_doc = float(ln.cantidad or 0)
        if cant_doc <= 0:
            continue

        cod_norm = _codigo_linea_factura(ln.codigo_item, ln.nombre)
        producto, _how = _matchear_producto_linea_factura(
            cod_norm,
            ln.nombre,
            proveedor_id=proveedor_id,
        )
        costo = ln.precio_unitario if ln.precio_unitario and ln.precio_unitario > 0 else None
        monto = ln.monto_linea if ln.monto_linea and ln.monto_linea > 0 else None

        doc_ln = RecepcionLineaDocumento.query.filter_by(
            recepcion_id=rec_id,
            nro_linea=int(ln.nro_linea or 0) or 1,
        ).first()
        if not doc_ln:
            doc_ln = RecepcionLineaDocumento(
                recepcion_id=rec_id,
                nro_linea=int(ln.nro_linea or 0) or 1,
            )
            db.session.add(doc_ln)

        doc_ln.codigo_factura = (cod_norm or ln.codigo_item or '')[:80] or None
        doc_ln.nombre = (ln.nombre or 'Ítem sin nombre')[:500]
        doc_ln.cantidad = cant_doc
        doc_ln.precio_unitario = costo
        doc_ln.monto_linea = monto
        doc_ln.producto_id = int(producto.id) if producto else None
        res.lineas_documentales += 1

        if not producto:
            res.lineas_sin_match.append(
                LineaSinMatch(
                    nro_linea=ln.nro_linea,
                    nombre=ln.nombre,
                    codigo_factura=cod_norm or ln.codigo_item,
                    cantidad=ln.cantidad,
                    precio_unitario=costo,
                )
            )
            continue

        cant_int = int(round(cant_doc))
        det = DetalleRecepcion.query.filter_by(
            recepcion_id=rec_id,
            producto_id=producto.id,
        ).first()
        if det:
            det.cantidad_documento = max(int(det.cantidad_documento or 0), cant_int)
            if int(det.cantidad_recibida or 0) == 0 and costo is not None:
                det.costo_unitario = costo
        else:
            det = DetalleRecepcion(
                recepcion_id=rec_id,
                producto_id=producto.id,
                cantidad_documento=cant_int,
                cantidad_recibida=0,
                costo_unitario=costo,
            )
            db.session.add(det)


def persistir_recepcion_desde_dte(
    dte: DteCompraParseado,
    *,
    usuario_bodega: str = 'DTE-Correo',
    commit: bool = True,
) -> ResultadoIngresoDteCorreo:
    """
    Crea o actualiza recepción «Pendiente de Items» con líneas documentales (sin stock).

    Requiere contexto Flask (app.app_context) para acceso a BD.
    """
    from app import (
        DetalleRecepcion,
        RecepcionCompra,
        RecepcionLineaDocumento,
        _asegurar_tabla_recepcion_linea_documento,
        _codigo_linea_factura,
        _matchear_producto_linea_factura,
        db,
    )
    from app import Proveedor

    _asegurar_tabla_recepcion_linea_documento()

    res = ResultadoIngresoDteCorreo(ok=True, archivo_xml=dte.archivo_origen)
    cab = dte.cabecera
    folio = _folio_str(cab.folio)
    res.folio = folio

    from services.dte_rut_receptor_service import rut_receptor_permitido

    if not rut_receptor_permitido(cab.rut_receptor):
        res.ok = False
        res.omitida_duplicado = False
        res.errores.append(
            f'DTE omitido: receptor {cab.rut_receptor} no es empresa permitida '
            f'(configure DTE_RUT_RECEPTOR / EMPRESA_RUT).'
        )
        return res

    cache: dict[str, int] = {}
    try:
        prov_id = _proveedor_por_rut_o_nombre(
            rut=cab.rut_emisor,
            razon=cab.razon_social_emisor or '',
            Proveedor=Proveedor,
            db=db,
            cache=cache,
        )
    except Exception as ex:
        res.ok = False
        res.errores.append(f'Proveedor: {ex}')
        return res

    if not prov_id:
        res.ok = False
        res.errores.append(f'No se pudo resolver proveedor para RUT {cab.rut_emisor}')
        return res

    res.proveedor_id = prov_id
    doc_tipo = _tipo_documento_recepcion(cab.tipo_dte)

    rec = RecepcionCompra.query.filter_by(
        proveedor_id=prov_id,
        documento_tipo=doc_tipo,
        documento_numero=folio,
    ).first()

    if rec and rec.estado not in (ESTADO_PENDIENTE_ITEMS, 'Pendiente', 'Incompleta'):
        res.omitida_duplicado = True
        res.recepcion_id = rec.id
        res.errores.append(
            f'Ya existe recepción #{rec.id} en estado «{rec.estado}» para folio {folio}.'
        )
        return res

    if not rec:
        rec = RecepcionCompra(
            proveedor_id=prov_id,
            documento_tipo=doc_tipo,
            documento_numero=folio,
            usuario_bodega=(usuario_bodega or 'DTE-Correo')[:100],
            estado=ESTADO_PENDIENTE_ITEMS,
            origen_importacion=ORIGEN_DTE_CORREO,
        )
        res.recepcion_creada = True
        db.session.add(rec)
    else:
        res.recepcion_actualizada = True

    rec.rut_proveedor_doc = cab.rut_emisor
    rec.razon_social_doc = cab.razon_social_emisor
    if cab.monto_neto is not None:
        rec.monto_neto = cab.monto_neto
    if cab.monto_total is not None:
        rec.monto_total = cab.monto_total
    if cab.fecha_emision:
        rec.fecha_documento = cab.fecha_emision
        rec.fecha_recepcion = datetime.combine(cab.fecha_emision, datetime.min.time())
    if not (rec.origen_importacion or '').strip():
        rec.origen_importacion = ORIGEN_DTE_CORREO

    db.session.flush()
    res.recepcion_id = int(rec.id)

    _persistir_lineas_documento_xml(
        rec.id,
        dte.lineas,
        proveedor_id=prov_id,
        _codigo_linea_factura=_codigo_linea_factura,
        _matchear_producto_linea_factura=_matchear_producto_linea_factura,
        RecepcionLineaDocumento=RecepcionLineaDocumento,
        DetalleRecepcion=DetalleRecepcion,
        db=db,
        res=res,
    )

    if commit:
        try:
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            res.ok = False
            res.errores.append(f'Commit: {ex}')
    return res


def persistir_recepcion_desde_xml_dte(
    ruta_xml: PathLike,
    *,
    usuario_bodega: str = 'DTE-Correo',
    commit: bool = True,
) -> ResultadoIngresoDteCorreo:
    """Parsea XML local y persiste recepción documental (sin stock)."""
    p = Path(ruta_xml)
    try:
        dte = parsear_archivo_dte_compra(p)
    except ParserXmlCompraError as ex:
        return ResultadoIngresoDteCorreo(
            ok=False,
            archivo_xml=str(p),
            errores=[str(ex)],
        )
    return persistir_recepcion_desde_dte(
        dte,
        usuario_bodega=usuario_bodega,
        commit=commit,
    )
