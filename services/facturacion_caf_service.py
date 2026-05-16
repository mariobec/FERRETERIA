# -*- coding: utf-8 -*-
"""
CAF (Código de autorización de folios) — parseo XML del SII e inserción en `cafs`.

El XML oficial viene del portal SII (AUTORIZACION > CAF > DA con TD, RNG, FA).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

_logger = logging.getLogger(__name__)


def _localname(el: Any) -> str:
    from lxml import etree

    return etree.QName(el).localname


def parse_caf_autorizacion_xml(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Extrae tipo DTE, rango de folios y fecha de autorización del XML CAF.
    Retorna dict con: tipo_dte, rango_desde, rango_hasta, fecha_autorizacion (date|None), caf_xml (str).
    """
    from lxml import etree

    if not xml_bytes or not xml_bytes.strip():
        raise ValueError('xml_vacio')
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as ex:
        raise ValueError(f'xml_invalido:{ex}') from ex

    da = None
    for el in root.iter():
        if _localname(el) == 'DA':
            da = el
            break
    if da is None:
        raise ValueError('caf_sin_bloque_da')

    tipo_dte: Optional[int] = None
    rango_desde: Optional[int] = None
    rango_hasta: Optional[int] = None
    fecha_txt: Optional[str] = None

    for el in da.iter():
        tag = _localname(el)
        if tag == 'TD' and el.text and str(el.text).strip():
            tipo_dte = int(str(el.text).strip())
        elif tag == 'FA' and el.text and str(el.text).strip():
            fecha_txt = str(el.text).strip()[:10]
        elif tag == 'RNG':
            for child in el:
                ct = _localname(child)
                if ct == 'D' and child.text and str(child.text).strip():
                    rango_desde = int(str(child.text).strip())
                elif ct == 'H' and child.text and str(child.text).strip():
                    rango_hasta = int(str(child.text).strip())

    if tipo_dte is None:
        raise ValueError('caf_sin_td')
    if rango_desde is None or rango_hasta is None:
        raise ValueError('caf_sin_rng')
    if rango_hasta < rango_desde:
        raise ValueError('caf_rng_invalido')

    fecha_autorizacion: Optional[date] = None
    if fecha_txt:
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
            try:
                fecha_autorizacion = datetime.strptime(fecha_txt, fmt).date()
                break
            except ValueError:
                continue

    xml_str = xml_bytes.decode('utf-8', errors='replace').strip()
    return {
        'tipo_dte': int(tipo_dte),
        'rango_desde': int(rango_desde),
        'rango_hasta': int(rango_hasta),
        'fecha_autorizacion': fecha_autorizacion,
        'caf_xml': xml_str,
    }


def caf_duplicado_rango(db_session: Any, caf_model: Any, tipo_dte: int, r0: int, r1: int) -> bool:
    q = (
        db_session.query(caf_model)
        .filter(
            caf_model.tipo_dte == int(tipo_dte),
            caf_model.rango_desde == int(r0),
            caf_model.rango_hasta == int(r1),
        )
        .first()
    )
    return q is not None


def insertar_caf_desde_xml(db_session: Any, caf_model: Any, xml_bytes: bytes) -> Tuple[Any, Dict[str, Any]]:
    """
    Parsea e inserta un CAF. Devuelve (instancia Caf, info dict).
    Lanza ValueError en validación o duplicado.
    """
    parsed = parse_caf_autorizacion_xml(xml_bytes)
    if caf_duplicado_rango(db_session, caf_model, parsed['tipo_dte'], parsed['rango_desde'], parsed['rango_hasta']):
        raise ValueError('caf_duplicado_mismo_rango')

    row = caf_model(
        tipo_dte=parsed['tipo_dte'],
        rango_desde=parsed['rango_desde'],
        rango_hasta=parsed['rango_hasta'],
        caf_xml=parsed['caf_xml'],
        fecha_autorizacion=parsed['fecha_autorizacion'],
        usado_hasta=0,
    )
    db_session.add(row)
    db_session.flush()
    _logger.info(
        'CAF insertado id=%s tipo=%s rango=%s-%s',
        row.id,
        parsed['tipo_dte'],
        parsed['rango_desde'],
        parsed['rango_hasta'],
    )
    return row, {'id': row.id, **{k: v for k, v in parsed.items() if k != 'caf_xml'}}
