# -*- coding: utf-8 -*-
"""Persistencia local de XML DTE firmado (cola / auditoría hasta envío SII)."""
from __future__ import annotations

import os
import re
from typing import Optional


def _ambiente_carpeta(ambiente: str) -> str:
    a = (ambiente or 'certificacion').strip().lower()
    if a in ('prod', 'palena', 'produccion'):
        return 'produccion'
    return 'certificacion'


def directorio_emitidos(erp_root: str, ambiente: str) -> str:
    d = os.path.join(erp_root, 'storage', 'dtes', 'emitidos', _ambiente_carpeta(ambiente))
    os.makedirs(d, exist_ok=True)
    return d


def persistir_xml_dte_firmado(
    erp_root: str,
    ambiente: str,
    venta_id: int,
    folio: int,
    dte_tipo: int,
    xml_bytes: bytes,
) -> str:
    """
    Guarda el XML bajo storage/dtes/emitidos/{certificacion|produccion}/.
    Retorna ruta absoluta del archivo.
    """
    d = directorio_emitidos(erp_root, ambiente)
    fn = f'V{int(venta_id)}_T{int(dte_tipo)}_F{int(folio)}.xml'
    path = os.path.join(d, fn)
    with open(path, 'wb') as fh:
        fh.write(xml_bytes or b'')
    return path


def buscar_xml_dte_por_venta(erp_root: str, venta_id: int) -> Optional[str]:
    """Último XML guardado para la venta (por mtime), o None."""
    base = os.path.join(erp_root, 'storage', 'dtes', 'emitidos')
    if not os.path.isdir(base):
        return None
    best: Optional[str] = None
    best_m = 0.0
    prefix = f'V{int(venta_id)}_'
    for amb in os.listdir(base):
        pdir = os.path.join(base, amb)
        if not os.path.isdir(pdir):
            continue
        for f in os.listdir(pdir):
            if not f.startswith(prefix) or not f.endswith('.xml'):
                continue
            if not re.match(rf'^V{int(venta_id)}_T\d+_F\d+\.xml$', f):
                continue
            cand = os.path.join(pdir, f)
            try:
                m = os.path.getmtime(cand)
            except OSError:
                continue
            if best is None or m > best_m:
                best, best_m = cand, m
    return best
