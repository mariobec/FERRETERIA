# -*- coding: utf-8 -*-
"""
Parser XML DTE compra (facturas recibidas de proveedores — Chile SII).

Extrae cabecera e ítems desde archivos EnvioDTE / DTE estándar o variantes con
<Detalle><Item>…</Item></Detalle> (sets de certificación).

Uso típico en recepciones:
    from services.parser_xml_compra import parsear_archivo_dte_compra, lineas_a_payload_detalle_recepcion

    dte = parsear_archivo_dte_compra('uploads/factura_proveedor.xml')
    filas = lineas_a_payload_detalle_recepcion(dte)
    # filas → aplicar en DetalleRecepcion tras match de producto_id
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, BinaryIO, Union
from xml.etree import ElementTree as ET

NS_SII_DTE = 'http://www.sii.cl/SiiDte'

PathLike = Union[str, Path]


class ParserXmlCompraError(ValueError):
    """XML inválido, DTE no reconocido o datos obligatorios ausentes."""


@dataclass
class CabeceraDteCompra:
    rut_emisor: str
    rut_receptor: str
    razon_social_emisor: str | None
    razon_social_receptor: str | None
    folio: int
    tipo_dte: int
    fecha_emision: date | None
    monto_neto: float | None = None
    monto_iva: float | None = None
    monto_total: float | None = None


@dataclass
class LineaDteCompra:
    nro_linea: int
    nombre: str
    cantidad: float
    precio_unitario: float
    monto_linea: float
    codigo_item: str | None = None
    unidad_medida: str | None = None
    descripcion_extra: str | None = None


@dataclass
class DteCompraParseado:
    cabecera: CabeceraDteCompra
    lineas: list[LineaDteCompra] = field(default_factory=list)
    archivo_origen: str | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            'cabecera': asdict(self.cabecera),
            'lineas': [asdict(ln) for ln in self.lineas],
            'archivo_origen': self.archivo_origen,
        }


def _local_name(tag: str | None) -> str:
    if not tag:
        return ''
    if '}' in tag:
        return tag.rsplit('}', 1)[-1]
    return tag


def _texto_elem(elem: ET.Element | None) -> str | None:
    if elem is None:
        return None
    txt = (elem.text or '').strip()
    if not txt and len(elem):
        # Algunos emisores anidan el valor en subnodos
        parts = [(c.text or '').strip() for c in elem.iter() if (c.text or '').strip()]
        txt = ' '.join(parts).strip()
    return txt or None


def _find_first(parent: ET.Element, local: str) -> ET.Element | None:
    for el in parent.iter():
        if _local_name(el.tag) == local:
            return el
    return None


def _find_child(parent: ET.Element, local: str) -> ET.Element | None:
    for el in list(parent):
        if _local_name(el.tag) == local:
            return el
    return None


def _find_text(parent: ET.Element, local: str, default: str | None = None) -> str | None:
    el = _find_first(parent, local)
    val = _texto_elem(el)
    return val if val is not None else default


def _parse_numero(raw: str | None, *, entero: bool = False) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace(' ', '').replace(',', '.')
    try:
        val = float(s)
    except ValueError:
        return None
    if entero:
        return float(int(round(val)))
    return val


def _parse_fecha(raw: str | None) -> date | None:
    if not raw:
        return None
    s = str(raw).strip()[:10]
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int_obligatorio(raw: str | None, campo: str) -> int:
    val = _parse_numero(raw, entero=True)
    if val is None:
        raise ParserXmlCompraError(f'Campo obligatorio inválido o vacío: {campo}')
    return int(val)


def _localizar_documento(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if _local_name(el.tag) == 'Documento':
            return el
    raise ParserXmlCompraError('No se encontró el nodo <Documento> en el XML DTE.')


def _extraer_cabecera(documento: ET.Element) -> CabeceraDteCompra:
    enc = _find_first(documento, 'Encabezado')
    if enc is None:
        raise ParserXmlCompraError('Falta <Encabezado> en el DTE.')

    id_doc = _find_first(enc, 'IdDoc') or enc
    emisor = _find_first(enc, 'Emisor') or enc
    receptor = _find_first(enc, 'Receptor') or enc
    totales = _find_first(enc, 'Totales')

    rut_emisor = _find_text(emisor, 'RUTEmisor')
    rut_receptor = _find_text(receptor, 'RUTRecep') or _find_text(receptor, 'RUTReceptor')
    if not rut_emisor:
        raise ParserXmlCompraError('Falta <RUTEmisor> en el XML.')
    if not rut_receptor:
        raise ParserXmlCompraError('Falta <RUTRecep> / <RUTReceptor> en el XML.')

    folio = _parse_int_obligatorio(_find_text(id_doc, 'Folio'), 'Folio')
    tipo_dte = _parse_int_obligatorio(_find_text(id_doc, 'TipoDTE'), 'TipoDTE')
    fecha = _parse_fecha(_find_text(id_doc, 'FchEmis'))

    mnt_neto = _parse_numero(_find_text(totales, 'MntNeto') if totales is not None else None)
    mnt_iva = _parse_numero(_find_text(totales, 'IVA') if totales is not None else None)
    mnt_total = _parse_numero(_find_text(totales, 'MntTotal') if totales is not None else None)

    return CabeceraDteCompra(
        rut_emisor=_normalizar_rut(rut_emisor),
        rut_receptor=_normalizar_rut(rut_receptor),
        razon_social_emisor=_find_text(emisor, 'RznSoc') or _find_text(emisor, 'RznSocEmisor'),
        razon_social_receptor=_find_text(receptor, 'RznSocRecep') or _find_text(receptor, 'RznSocReceptor'),
        folio=folio,
        tipo_dte=tipo_dte,
        fecha_emision=fecha,
        monto_neto=mnt_neto,
        monto_iva=mnt_iva,
        monto_total=mnt_total,
    )


def _normalizar_rut(rut: str) -> str:
    s = re.sub(r'\s+', '', (rut or '').strip().upper())
    if not s:
        return s
    if '-' not in s and len(s) > 1:
        s = f'{s[:-1]}-{s[-1]}'
    return s


def _codigo_item_linea(nodo: ET.Element) -> str | None:
    cdg = _find_child(nodo, 'CdgItem') or _find_first(nodo, 'CdgItem')
    if cdg is not None:
        for tag in ('VlrCodigo', 'TpoCodigo'):
            v = _find_text(cdg, tag)
            if v and tag == 'VlrCodigo':
                return v.strip()
        v = _texto_elem(cdg)
        if v:
            return v
    return _find_text(nodo, 'CdgItem')


def _parse_linea_item(nodo: ET.Element, idx_fallback: int) -> LineaDteCompra | None:
    nombre = _find_text(nodo, 'NmbItem')
    if not nombre:
        dsc = _find_text(nodo, 'DscItem')
        nombre = dsc
    if not nombre:
        return None

    nro_raw = _find_text(nodo, 'NroLinDet')
    if nro_raw is None and 'NroLinDet' in nodo.attrib:
        nro_raw = nodo.attrib.get('NroLinDet')
    nro_linea = int(_parse_numero(nro_raw, entero=True) or idx_fallback)

    cantidad = _parse_numero(_find_text(nodo, 'QtyItem'))
    if cantidad is None or cantidad <= 0:
        cantidad = 1.0

    precio = _parse_numero(_find_text(nodo, 'PrcItem'))
    monto = _parse_numero(_find_text(nodo, 'MontoItem'))

    if precio is None and monto is not None and cantidad:
        precio = monto / cantidad
    if monto is None and precio is not None:
        monto = precio * cantidad
    if precio is None:
        precio = 0.0
    if monto is None:
        monto = precio * cantidad

    return LineaDteCompra(
        nro_linea=nro_linea,
        nombre=nombre.strip(),
        cantidad=cantidad,
        precio_unitario=precio,
        monto_linea=monto,
        codigo_item=_codigo_item_linea(nodo),
        unidad_medida=_find_text(nodo, 'UnmdItem'),
        descripcion_extra=_find_text(nodo, 'DscItem'),
    )


def _extraer_lineas(documento: ET.Element) -> list[LineaDteCompra]:
    """
    Soporta:
    - Estándar SII: varios <Detalle> hermanos con NmbItem directo.
    - Envío/certificación: <Detalle><Item NroLinDet="n">…</Item></Detalle>.
    - Items sueltos bajo Documento.
    """
    lineas: list[LineaDteCompra] = []
    vistos: set[int] = set()

    # 1) Nodos Item (formato anidado)
    for i, nodo in enumerate(
        (el for el in documento.iter() if _local_name(el.tag) == 'Item'),
        start=1,
    ):
        if _find_first(nodo, 'NmbItem') is None and _find_text(nodo, 'DscItem') is None:
            continue
        ln = _parse_linea_item(nodo, i)
        if ln and ln.nro_linea not in vistos:
            lineas.append(ln)
            vistos.add(ln.nro_linea)

    if lineas:
        lineas.sort(key=lambda x: x.nro_linea)
        return lineas

    # 2) Detalle = una línea (formato más común en XML de proveedores)
    for i, det in enumerate(
        (el for el in documento.iter() if _local_name(el.tag) == 'Detalle'),
        start=1,
    ):
        if any(_local_name(c.tag) == 'Item' for c in det):
            continue
        if _find_text(det, 'NmbItem') is None and _find_text(det, 'DscItem') is None:
            continue
        ln = _parse_linea_item(det, i)
        if ln and ln.nro_linea not in vistos:
            lineas.append(ln)
            vistos.add(ln.nro_linea)

    if not lineas:
        raise ParserXmlCompraError('No se encontraron líneas <Detalle>/<Item> con <NmbItem>.')

    lineas.sort(key=lambda x: x.nro_linea)
    return lineas


def parsear_xml_dte_compra(
    xml_source: Union[str, bytes],
    *,
    archivo_origen: str | None = None,
) -> DteCompraParseado:
    """
    Parsea XML DTE de compra desde string o bytes UTF-8/latin-1.
    """
    if isinstance(xml_source, bytes):
        raw = xml_source
    else:
        raw = xml_source.encode('utf-8')

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as ex:
        raise ParserXmlCompraError(f'XML mal formado: {ex}') from ex

    documento = _localizar_documento(root)
    cabecera = _extraer_cabecera(documento)
    lineas = _extraer_lineas(documento)
    return DteCompraParseado(cabecera=cabecera, lineas=lineas, archivo_origen=archivo_origen)


def parsear_archivo_dte_compra(path: PathLike) -> DteCompraParseado:
    """Lee un archivo .xml local y devuelve cabecera + líneas."""
    p = Path(path)
    if not p.is_file():
        raise ParserXmlCompraError(f'Archivo no encontrado: {p}')
    data = p.read_bytes()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = data.decode('latin-1', errors='replace')
    return parsear_xml_dte_compra(text, archivo_origen=str(p))


def parsear_stream_dte_compra(stream: BinaryIO, *, archivo_origen: str | None = None) -> DteCompraParseado:
    data = stream.read()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = data.decode('latin-1', errors='replace')
    return parsear_xml_dte_compra(text, archivo_origen=archivo_origen)


def lineas_a_payload_detalle_recepcion(
    dte: DteCompraParseado,
    *,
    producto_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Estructura lista para crear/actualizar DetalleRecepcion (sin persistir).

    Requiere producto_id por línea antes de insertar en BD (match catálogo aparte).
    """
    out: list[dict[str, Any]] = []
    for ln in dte.lineas:
        cant = int(round(ln.cantidad)) if ln.cantidad else 0
        if cant <= 0:
            continue
        fila: dict[str, Any] = {
            'descripcion_factura': ln.nombre,
            'codigo_factura': ln.codigo_item,
            'cantidad_documento': cant,
            'cantidad_recibida': cant,
            'costo_unitario': ln.precio_unitario if ln.precio_unitario > 0 else None,
            'monto_linea': ln.monto_linea,
            'nro_linea_dte': ln.nro_linea,
            'unidad_medida': ln.unidad_medida,
        }
        if producto_id is not None:
            fila['producto_id'] = producto_id
        out.append(fila)
    return out


def a_dataframe(dte: DteCompraParseado):
    """Devuelve pandas DataFrame con cabecera repetida + columnas de línea."""
    import pandas as pd

    cab = asdict(dte.cabecera)
    rows = []
    for ln in dte.lineas:
        row = {**cab, **asdict(ln)}
        rows.append(row)
    return pd.DataFrame(rows)


def procesar_xml_dte(
    ruta_xml: PathLike,
    *,
    guardar_json: bool = True,
    carpeta_json: PathLike | None = None,
) -> dict[str, Any]:
    """
    Punto de entrada operativo: parsea un XML DTE de compra y devuelve payload ERP.

    Usado por scripts/lector_correo_dte.py tras descargar adjuntos.
    Opcionalmente guarda un .json con cabecera + líneas junto al XML.
    """
    import json

    p = Path(ruta_xml)
    dte = parsear_archivo_dte_compra(p)
    payload = lineas_a_payload_detalle_recepcion(dte)
    resultado: dict[str, Any] = {
        'ok': True,
        'archivo_xml': str(p.resolve()),
        'cabecera': asdict(dte.cabecera),
        'total_lineas': len(dte.lineas),
        'lineas': [asdict(ln) for ln in dte.lineas],
        'detalle_recepcion': payload,
    }
    if guardar_json:
        dest = Path(carpeta_json) if carpeta_json else p.parent
        dest.mkdir(parents=True, exist_ok=True)
        json_path = dest / f'{p.stem}_dte.json'
        json_path.write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False, default=str),
            encoding='utf-8',
        )
        resultado['archivo_json'] = str(json_path.resolve())
    return resultado


def _ejemplo_xml_compra_minimo() -> str:
    """XML de prueba (factura 33 — formato estándar Detalle por línea)."""
    return f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE version="1.0" xmlns="{NS_SII_DTE}">
  <Documento ID="F33T5005433">
    <Encabezado>
      <IdDoc>
        <TipoDTE>33</TipoDTE>
        <Folio>5005433</Folio>
        <FchEmis>2026-06-01</FchEmis>
      </IdDoc>
      <Emisor>
        <RUTEmisor>96516560-5</RUTEmisor>
        <RznSoc>CHILEMAT CENTRAL DE COMPRAS S A</RznSoc>
      </Emisor>
      <Receptor>
        <RUTRecep>76123456-7</RUTRecep>
        <RznSocRecep>FERRETERIA SANTO DOMINGO SPA</RznSocRecep>
      </Receptor>
      <Totales>
        <MntNeto>58160</MntNeto>
        <TasaIVA>19</TasaIVA>
        <IVA>11050</IVA>
        <MntTotal>69210</MntTotal>
      </Totales>
    </Encabezado>
    <Detalle>
      <NroLinDet>1</NroLinDet>
      <CdgItem><TpoCodigo>INT</TpoCodigo><VlrCodigo>INT-110109</VlrCodigo></CdgItem>
      <NmbItem>ALAMBRE GALV N18 1KG</NmbItem>
      <QtyItem>10</QtyItem>
      <PrcItem>1498</PrcItem>
      <MontoItem>14980</MontoItem>
    </Detalle>
    <Detalle>
      <NroLinDet>2</NroLinDet>
      <NmbItem>CLAVO PULIDO 2 1/2 X 10 KG</NmbItem>
      <QtyItem>2</QtyItem>
      <PrcItem>8990</PrcItem>
      <MontoItem>17980</MontoItem>
    </Detalle>
  </Documento>
</DTE>
"""


if __name__ == '__main__':
    import json
    import sys

    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if ruta and ruta.is_file():
        resultado = parsear_archivo_dte_compra(ruta)
        print(f'Archivo: {ruta}')
    else:
        resultado = parsear_xml_dte_compra(_ejemplo_xml_compra_minimo(), archivo_origen='(ejemplo embebido)')
        print('Demo con XML embebido (sin archivo). Uso: python services/parser_xml_compra.py factura.xml')

    print('--- Cabecera ---')
    print(json.dumps(asdict(resultado.cabecera), indent=2, default=str))
    print('--- Líneas ---')
    for ln in resultado.lineas:
        print(
            f'  #{ln.nro_linea} | {ln.codigo_item or "-"} | {ln.nombre[:40]} | '
            f'cant={ln.cantidad} prc={ln.precio_unitario} monto={ln.monto_linea}'
        )
    print('--- Payload DetalleRecepcion ---')
    print(json.dumps(lineas_a_payload_detalle_recepcion(resultado), indent=2, ensure_ascii=False))
    try:
        df = a_dataframe(resultado)
        print('--- DataFrame ---')
        print(df.to_string(index=False))
    except ImportError:
        print('(pandas no instalado — omitiendo DataFrame)')
