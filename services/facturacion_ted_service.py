# -*- coding: utf-8 -*-
"""
TED (Timbre Electrónico DTE) — firma FRMT con clave RSASK del XML AUTORIZACION SII.

Algoritmo SII (SHA1withRSA sobre elemento <DD> aplanado, encoding ISO-8859-1).
Ver: https://www.cryptosys.net/pki/xmldsig-ChileSII.html (sección FRMT).
"""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

_logger = logging.getLogger(__name__)


def _localname(el: Any) -> str:
    from lxml import etree

    return etree.QName(el).localname


def extraer_rsask_pem(autorizacion_xml: bytes) -> str:
    """Obtiene la clave privada PEM del bloque RSASK en AUTORIZACION."""
    from lxml import etree

    if not autorizacion_xml or not autorizacion_xml.strip():
        raise ValueError('caf_xml_vacio')
    root = etree.fromstring(autorizacion_xml)
    for el in root.iter():
        if _localname(el) == 'RSASK' and el.text and 'BEGIN RSA PRIVATE KEY' in el.text:
            return str(el.text).strip()
    raise ValueError('caf_sin_rsask')


def extraer_elemento_caf(autorizacion_xml: bytes) -> Any:
    """Copia el nodo <CAF version=\"1.0\"> completo (DA + FRMA) para insertar en DD."""
    from lxml import etree

    root = etree.fromstring(autorizacion_xml)
    for el in root.iter():
        if _localname(el) == 'CAF':
            return etree.fromstring(etree.tostring(el))
    raise ValueError('caf_sin_nodo_caf')


def _primer_item_nombre(contexto: Dict[str, Any], max_len: int = 40) -> str:
    items = contexto.get('items') or []
    if items:
        nombre = str(items[0].get('nombre') or 'Item')
    else:
        nombre = 'Venta'
    nombre = nombre.replace('\n', ' ').strip()
    if len(nombre) > max_len:
        return nombre[:max_len]
    return nombre


def construir_elemento_dd(contexto: Dict[str, Any], caf_el: Any) -> Any:
    """
    Arma <DD> sin namespace (formato esperado por SII para FRMT).
    """
    from lxml import etree

    dd = etree.Element('DD')
    etree.SubElement(dd, 'RE').text = str(contexto['rut_emisor']).strip()
    etree.SubElement(dd, 'TD').text = str(int(contexto['dte_tipo']))
    etree.SubElement(dd, 'F').text = str(int(contexto['folio']))
    etree.SubElement(dd, 'FE').text = str(contexto['fecha_emision'])[:10]
    etree.SubElement(dd, 'RR').text = str(contexto['rut_receptor']).strip()
    etree.SubElement(dd, 'RSR').text = str(contexto.get('razon_social_receptor') or 'CLIENTE')[:100]
    etree.SubElement(dd, 'MNT').text = str(int(contexto['monto_total']))
    etree.SubElement(dd, 'IT1').text = _primer_item_nombre(contexto)
    dd.append(caf_el)
    tsted = etree.SubElement(dd, 'TSTED')
    tsted.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return dd


def aplanar_dd_para_firma(dd_el: Any) -> bytes:
    """Serializa <DD> en una línea y codifica ISO-8859-1 (reglas FRMT SII)."""
    from lxml import etree

    raw = etree.tostring(dd_el, encoding='unicode', method='xml', with_tail=False)
    if raw.startswith('<?xml'):
        raw = raw.split('?>', 1)[-1].strip()
    flat = re.sub(r'>\s+<', '><', raw.strip())
    return flat.encode('iso-8859-1', errors='replace')


def firmar_frmt_dd(dd_bytes: bytes, rsask_pem: str) -> str:
    """Firma SHA1withRSA del DD aplanado; retorna base64 para <FRMT>."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(rsask_pem.encode('ascii'), password=None)
    sig = key.sign(dd_bytes, padding.PKCS1v15(), hashes.SHA1())
    return base64.b64encode(sig).decode('ascii')


def construir_ted(contexto: Dict[str, Any], autorizacion_xml: bytes) -> Any:
    """
    Construye nodo TED (DD + FRMT) listo para insertar en Documento.
    """
    from lxml import etree

    rsask = extraer_rsask_pem(autorizacion_xml)
    caf_el = extraer_elemento_caf(autorizacion_xml)
    dd = construir_elemento_dd(contexto, caf_el)
    dd_bytes = aplanar_dd_para_firma(dd)
    frmt_b64 = firmar_frmt_dd(dd_bytes, rsask)

    ted = etree.Element('TED')
    ted.set('version', '1.0')
    ted.append(dd)
    frmt = etree.SubElement(ted, 'FRMT')
    frmt.set('algoritmo', 'SHA1withRSA')
    frmt.text = frmt_b64
    return ted


def documento_id_sii(dte_tipo: int, folio: int) -> str:
    return 'F%sT%s' % (int(dte_tipo), int(folio))


def insertar_ted_en_documento(
    doc_el: Any,
    contexto: Dict[str, Any],
    autorizacion_xml: bytes,
    *,
    ns: str = 'http://www.sii.cl/SiiDte',
) -> None:
    """
    Inserta TED (DD sin namespace + FRMT) y TmstFirma en Documento SiiDte.
    El FRMT se calcula sobre el mismo <DD> que se inserta (reglas SII).
    """
    from lxml import etree

    for el in list(doc_el):
        if _localname(el) == 'StubFase1':
            doc_el.remove(el)

    ted = construir_ted(contexto, autorizacion_xml)
    tmst = etree.Element('{%s}TmstFirma' % ns)
    tmst.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    detalle_idx = None
    for i, el in enumerate(doc_el):
        if _localname(el) == 'Detalle':
            detalle_idx = i
    if detalle_idx is not None:
        doc_el.insert(detalle_idx + 1, ted)
        doc_el.insert(detalle_idx + 2, tmst)
    else:
        doc_el.append(ted)
        doc_el.append(tmst)


def timbrar_dte_xml(
    xml_dte: bytes,
    contexto: Dict[str, Any],
    autorizacion_xml: bytes,
) -> Tuple[bytes, str]:
    """
    Toma XML DTE (sin TED), inserta TED+TmstFirma y asigna ID al Documento.
    Retorna (xml_con_ted, estado).
    """
    from lxml import etree

    NS = 'http://www.sii.cl/SiiDte'
    try:
        root = etree.fromstring(xml_dte)
        doc = None
        for el in root.iter():
            if _localname(el) == 'Documento':
                doc = el
                break
        if doc is None:
            raise ValueError('dte_sin_documento')
        doc_id = documento_id_sii(int(contexto['dte_tipo']), int(contexto['folio']))
        doc.set('ID', doc_id)
        insertar_ted_en_documento(doc, contexto, autorizacion_xml, ns=NS)
        out = etree.tostring(
            root,
            xml_declaration=True,
            encoding='ISO-8859-1',
            pretty_print=True,
        )
        return out, 'TIMBRADO'
    except ValueError as ex:
        _logger.warning('timbrar_dte_xml: %s', ex)
        return xml_dte, f'ERROR_TED:{ex}'
    except Exception as ex:
        _logger.exception('timbrar_dte_xml falló')
        return xml_dte, f'ERROR_TED:{type(ex).__name__}'
