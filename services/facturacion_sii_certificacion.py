# -*- coding: utf-8 -*-
"""
Set de pruebas SII (certificación) — generación XML DTE estructurado + persistencia local.

No sustituye CAF/TED oficiales del SII; prepara artefactos para revisión y envío manual.
"""
from __future__ import annotations

import io
import os
import zipfile
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from services import facturacion_electronica_service as fe

NS = 'http://www.sii.cl/SiiDte'
DTE_39 = fe.DTE_TIPO_BOLETA_AFECTA
DTE_33 = fe.DTE_TIPO_FACTURA_AFECTA
DTE_61 = 61

# RUT receptor de prueba habitual en certificación SII (contribuyente ficticio)
RUT_RECEPTOR_PRUEBA_SII = '55.555.555-5'


def _ns(tag: str) -> str:
    return '{%s}%s' % (NS, tag)


def _sub(parent: Any, tag: str, text: Optional[str] = None) -> Any:
    from lxml import etree

    el = etree.SubElement(parent, _ns(tag))
    if text is not None:
        el.text = str(text)
    return el


def _dte_root() -> Tuple[Any, Any]:
    from lxml import etree

    nsmap = {None: NS}
    root = etree.Element(_ns('DTE'), nsmap=nsmap)
    root.set('version', '1.0')
    doc = etree.SubElement(root, _ns('Documento'))
    return root, doc


def _to_xml_bytes(root: Any) -> bytes:
    from lxml import etree

    return etree.tostring(root, xml_declaration=True, encoding='utf-8', pretty_print=True)


def directorio_pruebas_sii(app_root: str) -> str:
    d = os.path.join(app_root, 'storage', 'dtes', 'pruebas_sii')
    os.makedirs(d, exist_ok=True)
    return d


def nombre_archivo_dte(dte_tipo: int, folio: int) -> str:
    return 'DTE_%s_FOLIO_%s.xml' % (int(dte_tipo), int(folio))


def guardar_xml_dte_certificacion(app_root: str, dte_tipo: int, folio: int, xml_bytes: bytes) -> str:
    """Escribe XML firmado (o base) bajo storage/dtes/pruebas_sii/."""
    d = directorio_pruebas_sii(app_root)
    fn = nombre_archivo_dte(dte_tipo, folio)
    path = os.path.join(d, fn)
    with open(path, 'wb') as fh:
        fh.write(xml_bytes)
    return path


def generar_xml_caso1_boleta_39_exento_afecto(
    *,
    folio: int,
    rut_emisor: str,
    razon_emisor: str,
    fecha: str,
) -> bytes:
    """
    Caso 1: Boleta electrónica (39) con ítem exento + ítem afecto.
    IVA 19% exacto sobre la base neta declarada en totales.
    """
    from lxml import etree

    root, doc = _dte_root()
    enc = etree.SubElement(doc, _ns('Encabezado'))
    idd = etree.SubElement(enc, _ns('IdDoc'))
    _sub(idd, 'TipoDTE', DTE_39)
    _sub(idd, 'Folio', folio)
    _sub(idd, 'FchEmis', fecha)

    em = etree.SubElement(enc, _ns('Emisor'))
    _sub(em, 'RUTEmisor', rut_emisor)
    _sub(em, 'RznSoc', razon_emisor)

    rec = etree.SubElement(enc, _ns('Receptor'))
    _sub(rec, 'RUTRecep', '66666666-6')
    _sub(rec, 'RznSocRecep', 'BOLETA ELECTRONICA CERT')

    # Línea exenta 25.000 + línea afecta neto 70.000 -> IVA 13.300 (19%)
    mnt_exe = 25000
    mnt_neto = 70000
    iva = int(round(mnt_neto * 0.19))
    mnt_total = mnt_exe + mnt_neto + iva

    tot = etree.SubElement(enc, _ns('Totales'))
    _sub(tot, 'MntExe', str(mnt_exe))
    _sub(tot, 'MntNeto', str(mnt_neto))
    _sub(tot, 'TasaIVA', '19')
    _sub(tot, 'IVA', str(iva))
    _sub(tot, 'MntTotal', str(mnt_total))

    det = etree.SubElement(doc, _ns('Detalle'))
    it1 = etree.SubElement(det, _ns('Item'))
    it1.set('NroLinDet', '1')
    _sub(it1, 'NmbItem', 'Producto exento certificacion')
    _sub(it1, 'QtyItem', '1')
    _sub(it1, 'PrcItem', str(mnt_exe))
    _sub(it1, 'MontoItem', str(mnt_exe))
    _sub(it1, 'IndExe', '1')

    it2 = etree.SubElement(det, _ns('Item'))
    it2.set('NroLinDet', '2')
    _sub(it2, 'NmbItem', 'Producto afecto certificacion')
    _sub(it2, 'QtyItem', '2')
    _sub(it2, 'PrcItem', '35000')
    _sub(it2, 'MontoItem', str(mnt_neto))

    com = etree.SubElement(doc, _ns('Comentario'))
    com.text = 'Caso1_SET_SII_BE39_exento_afecto_MOCK'
    return _to_xml_bytes(root)


def generar_xml_caso2_factura_33(
    *,
    folio: int,
    rut_emisor: str,
    razon_emisor: str,
    fecha: str,
) -> bytes:
    """Caso 2: Factura electrónica (33) a RUT de prueba SII con montos netos declarados."""
    from lxml import etree

    root, doc = _dte_root()
    enc = etree.SubElement(doc, _ns('Encabezado'))
    idd = etree.SubElement(enc, _ns('IdDoc'))
    _sub(idd, 'TipoDTE', DTE_33)
    _sub(idd, 'Folio', folio)
    _sub(idd, 'FchEmis', fecha)

    em = etree.SubElement(enc, _ns('Emisor'))
    _sub(em, 'RUTEmisor', rut_emisor)
    _sub(em, 'RznSoc', razon_emisor)
    _sub(em, 'GiroEmis', 'FERRETERIA')
    _sub(em, 'Acteco', fe.ACTECO_FERRETERIA_RETAIL)

    rec = etree.SubElement(enc, _ns('Receptor'))
    _sub(rec, 'RUTRecep', RUT_RECEPTOR_PRUEBA_SII)
    _sub(rec, 'RznSocRecep', 'SERVICIO DE IMPUESTOS INTERNOS PRUEBA')
    _sub(rec, 'GiroRecep', 'PRUEBA')
    _sub(rec, 'DirRecep', 'SANTIAGO')
    _sub(rec, 'CmnaRecep', 'SANTIAGO')
    _sub(rec, 'CiudadRecep', 'SANTIAGO')

    mnt_neto = 100000
    iva = int(round(mnt_neto * 0.19))
    mnt_total = mnt_neto + iva

    tot = etree.SubElement(enc, _ns('Totales'))
    _sub(tot, 'MntNeto', str(mnt_neto))
    _sub(tot, 'TasaIVA', '19')
    _sub(tot, 'IVA', str(iva))
    _sub(tot, 'MntTotal', str(mnt_total))

    det = etree.SubElement(doc, _ns('Detalle'))
    it = etree.SubElement(det, _ns('Item'))
    it.set('NroLinDet', '1')
    _sub(it, 'NmbItem', 'Venta factura certificacion')
    _sub(it, 'QtyItem', '1')
    _sub(it, 'PrcItem', str(mnt_neto))
    _sub(it, 'MontoItem', str(mnt_neto))

    com = etree.SubElement(doc, _ns('Comentario'))
    com.text = 'Caso2_SET_SII_F33_RUT_PRUEBA_MOCK'
    return _to_xml_bytes(root)


def generar_xml_caso3_nota_credito_61(
    *,
    folio_nc: int,
    folio_factura_ref: int,
    fecha_nc: str,
    fecha_factura_ref: str,
    rut_emisor: str,
    razon_emisor: str,
) -> bytes:
    """Caso 3: Nota de crédito (61) que referencia la factura (33) del caso 2."""
    from lxml import etree

    root, doc = _dte_root()
    enc = etree.SubElement(doc, _ns('Encabezado'))
    idd = etree.SubElement(enc, _ns('IdDoc'))
    _sub(idd, 'TipoDTE', DTE_61)
    _sub(idd, 'Folio', folio_nc)
    _sub(idd, 'FchEmis', fecha_nc)

    em = etree.SubElement(enc, _ns('Emisor'))
    _sub(em, 'RUTEmisor', rut_emisor)
    _sub(em, 'RznSoc', razon_emisor)

    rec = etree.SubElement(enc, _ns('Receptor'))
    _sub(rec, 'RUTRecep', RUT_RECEPTOR_PRUEBA_SII)
    _sub(rec, 'RznSocRecep', 'SERVICIO DE IMPUESTOS INTERNOS PRUEBA')

    refs = etree.SubElement(doc, _ns('Referencias'))
    ref = etree.SubElement(refs, _ns('Referencia'))
    _sub(ref, 'NroLinRef', '1')
    _sub(ref, 'TpoDocRef', str(DTE_33))
    _sub(ref, 'FolioRef', str(folio_factura_ref))
    _sub(ref, 'FchRef', fecha_factura_ref)
    _sub(ref, 'RazonRef', 'ANULA FACTURA ELECTRONICA CERTIFICACION')

    mnt_neto = 100000
    iva = int(round(mnt_neto * 0.19))
    mnt_total = mnt_neto + iva

    tot = etree.SubElement(enc, _ns('Totales'))
    _sub(tot, 'MntNeto', str(mnt_neto))
    _sub(tot, 'TasaIVA', '19')
    _sub(tot, 'IVA', str(iva))
    _sub(tot, 'MntTotal', str(mnt_total))

    det = etree.SubElement(doc, _ns('Detalle'))
    it = etree.SubElement(det, _ns('Item'))
    it.set('NroLinDet', '1')
    _sub(it, 'NmbItem', 'Nota de credito anula factura certificacion')
    _sub(it, 'QtyItem', '1')
    _sub(it, 'PrcItem', str(mnt_neto))
    _sub(it, 'MontoItem', str(mnt_neto))

    com = etree.SubElement(doc, _ns('Comentario'))
    com.text = 'Caso3_SET_SII_NC61_ref_F33_MOCK'
    return _to_xml_bytes(root)


def mock_caf_xml(tipo_dte: int, desde: int, hasta: int, rut_emisor: str = '8054120-1') -> str:
    """XML AUTORIZACION con RSASK para Maullín / QA (ver facturacion_caf_certificacion)."""
    from services import facturacion_caf_certificacion as caf_cert

    return caf_cert.generar_autorizacion_caf_certificacion(
        int(tipo_dte), int(desde), int(hasta), rut_emisor=rut_emisor
    ).decode('utf-8', errors='replace')


def _timbrar_xml_caso(
    xml_bytes: bytes,
    ctx_ted: Dict[str, Any],
    caf_autorizacion: bytes,
) -> Tuple[bytes, str]:
    from services import facturacion_ted_service as ted_svc

    out, estado = ted_svc.timbrar_dte_xml(xml_bytes, ctx_ted, caf_autorizacion)
    return out, estado


def ejecutar_set_certificacion_sii(
    app_root: str,
    *,
    rut_emisor: str,
    razon_emisor: str,
    folio_39: int = 1,
    folio_33: int = 1,
    folio_61: int = 1,
    timbrar_con_caf_cert: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Genera los 3 casos, timbra TED (CAF cert), firma .pfx y guarda en storage/dtes/pruebas_sii/.

    Retorna (resumen_casos, rutas_archivos).
    """
    from services import facturacion_caf_certificacion as caf_cert

    fecha = date.today().isoformat()
    casos: List[Dict[str, Any]] = []
    paths: List[str] = []

    caf39_b = caf33_b = None
    if timbrar_con_caf_cert:
        caf_cert.guardar_cafs_certificacion(app_root, rut_emisor=rut_emisor, razon_social=razon_emisor)
        caf39_b = caf_cert.generar_autorizacion_caf_certificacion(
            DTE_39, caf_cert.RANGO_CERT_BOLETA_39[0], caf_cert.RANGO_CERT_BOLETA_39[1],
            rut_emisor=rut_emisor, razon_social=razon_emisor,
        )
        caf33_b = caf_cert.generar_autorizacion_caf_certificacion(
            DTE_33, caf_cert.RANGO_CERT_FACTURA_33[0], caf_cert.RANGO_CERT_FACTURA_33[1],
            rut_emisor=rut_emisor, razon_social=razon_emisor,
        )

    xml39 = generar_xml_caso1_boleta_39_exento_afecto(
        folio=folio_39, rut_emisor=rut_emisor, razon_emisor=razon_emisor, fecha=fecha
    )
    st_ted39 = 'omitido'
    if caf39_b:
        mnt39 = 25000 + 70000 + int(round(70000 * 0.19))
        ctx39 = {
            'dte_tipo': DTE_39,
            'folio': folio_39,
            'rut_emisor': rut_emisor,
            'razon_social_emisor': razon_emisor,
            'rut_receptor': '66666666-6',
            'razon_social_receptor': 'BOLETA ELECTRONICA CERT',
            'fecha_emision': fecha,
            'monto_neto': 70000,
            'monto_iva': int(round(70000 * 0.19)),
            'monto_total': mnt39,
            'items': [{'nombre': 'Producto exento certificacion'}],
        }
        xml39, st_ted39 = _timbrar_xml_caso(xml39, ctx39, caf39_b)
    b39, st39 = fe.firmar_xml_dte(xml39)
    p39 = guardar_xml_dte_certificacion(app_root, DTE_39, folio_39, b39)
    paths.append(p39)
    casos.append(
        {
            'caso': 1,
            'nombre': 'Boleta 39 exento + afecto IVA 19%',
            'dte_tipo': DTE_39,
            'folio': folio_39,
            'archivo': os.path.basename(p39),
            'estado_firma': st39,
            'estado_ted': st_ted39,
        }
    )

    xml33 = generar_xml_caso2_factura_33(
        folio=folio_33, rut_emisor=rut_emisor, razon_emisor=razon_emisor, fecha=fecha
    )
    st_ted33 = 'omitido'
    if caf33_b:
        mnt_neto = 100000
        iva = int(round(mnt_neto * 0.19))
        ctx33 = {
            'dte_tipo': DTE_33,
            'folio': folio_33,
            'rut_emisor': rut_emisor,
            'razon_social_emisor': razon_emisor,
            'rut_receptor': RUT_RECEPTOR_PRUEBA_SII,
            'razon_social_receptor': 'SERVICIO DE IMPUESTOS INTERNOS PRUEBA',
            'fecha_emision': fecha,
            'monto_neto': mnt_neto,
            'monto_iva': iva,
            'monto_total': mnt_neto + iva,
            'items': [{'nombre': 'Venta factura certificacion'}],
        }
        xml33, st_ted33 = _timbrar_xml_caso(xml33, ctx33, caf33_b)
    b33, st33 = fe.firmar_xml_dte(xml33)
    p33 = guardar_xml_dte_certificacion(app_root, DTE_33, folio_33, b33)
    paths.append(p33)
    casos.append(
        {
            'caso': 2,
            'nombre': 'Factura 33 RUT prueba SII',
            'dte_tipo': DTE_33,
            'folio': folio_33,
            'rut_receptor': RUT_RECEPTOR_PRUEBA_SII,
            'archivo': os.path.basename(p33),
            'estado_firma': st33,
            'estado_ted': st_ted33,
        }
    )

    xml61 = generar_xml_caso3_nota_credito_61(
        folio_nc=folio_61,
        folio_factura_ref=folio_33,
        fecha_nc=fecha,
        fecha_factura_ref=fecha,
        rut_emisor=rut_emisor,
        razon_emisor=razon_emisor,
    )
    b61, st61 = fe.firmar_xml_dte(xml61)
    p61 = guardar_xml_dte_certificacion(app_root, DTE_61, folio_61, b61)
    paths.append(p61)
    casos.append(
        {
            'caso': 3,
            'nombre': 'Nota credito 61 referencia factura caso 2',
            'dte_tipo': DTE_61,
            'folio': folio_61,
            'referencia_tpo': DTE_33,
            'referencia_folio': folio_33,
            'archivo': os.path.basename(p61),
            'estado_firma': st61,
        }
    )

    return casos, paths


def crear_zip_pruebas_sii(paths: List[str]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if os.path.isfile(p):
                zf.write(p, arcname=os.path.basename(p))
    buf.seek(0)
    return buf
