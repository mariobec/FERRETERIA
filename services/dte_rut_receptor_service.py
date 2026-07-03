# -*- coding: utf-8 -*-
"""RUT receptor DTE compra — validación Santo Domingo / multi-RUT permitido."""
from __future__ import annotations

import os
import re


def normalizar_rut(rut: str | None) -> str:
    s = re.sub(r'\s+', '', (rut or '').strip().upper())
    if not s:
        return s
    if '-' not in s and len(s) > 1:
        s = f'{s[:-1]}-{s[-1]}'
    return s


def ruts_receptor_permitidos() -> frozenset[str]:
    """
    RUT(s) empresa receptora válidos para importar DTE al ERP.
    DTE_RUT_RECEPTOR puede ser uno o varios separados por coma.
    Si vacío, cae en EMPRESA_RUT. Si ambos vacíos → no filtra (compat).
    """
    raw = (os.getenv('DTE_RUT_RECEPTOR') or os.getenv('EMPRESA_RUT') or '').strip()
    if not raw:
        return frozenset()
    parts = [normalizar_rut(x) for x in raw.replace(';', ',').split(',')]
    return frozenset(x for x in parts if x)


def rut_receptor_permitido(rut_receptor: str | None) -> bool:
    permitidos = ruts_receptor_permitidos()
    if not permitidos:
        return True
    return normalizar_rut(rut_receptor) in permitidos


def etiqueta_gmail_para_rut(rut_receptor: str | None) -> str:
    """Nombre de etiqueta Gmail según si el RUT receptor es de SD o no."""
    if rut_receptor_permitido(rut_receptor):
        return (
            os.getenv('DTE_GMAIL_LABEL_SD') or 'DTE-8054120-1'
        ).strip()
    return (
        os.getenv('DTE_GMAIL_LABEL_OTRO') or 'DTE-Otra-Sociedad'
    ).strip()


def etiqueta_gmail_entrada() -> str:
    return (os.getenv('DTE_GMAIL_LABEL_ENTRADA') or 'DTE-XML-Entrada').strip()
