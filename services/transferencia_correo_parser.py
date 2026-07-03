# -*- coding: utf-8 -*-
"""Parser heurístico de avisos bancarios por transferencia (correo IMAP)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Dominios banco Chile (ampliar vía TRF_CORREO_REMITENTES en .env.local)
# Incluye variantes de subdominio usadas para notificaciones (correo., noreply., mensajeria., etc.)
_DOMINIOS_BANCO_DEFAULT = (
    'bci.cl', 'santander.cl', 'bancoestado.cl', 'bancochile.cl', 'itau.cl',
    'scotiabank.cl', 'security.cl', 'bice.cl', 'coopeuch.cl', 'tenpo.cl',
    'mercadopago.cl', 'mach.cl',
    # Variantes BancoEstado — usan correobancoestado.cl para notificaciones de transferencia
    'correobancoestado.cl',
    # Khipu / pasarelas de pago
    'khipu.com', 'flow.cl', 'webpay.cl', 'transbank.cl',
)

_PALABRAS_TRANSFERENCIA = (
    'transferencia', 'transferencia electr', 'abono en cuenta', 'abono a cuenta',
    'depósito', 'deposito', 'pago recibido', 'recibió una transferencia',
    'recibio una transferencia', 'ingreso de fondos', 'aviso de transferencia',
    'notificación de transferencia', 'notificacion de transferencia',
    'pago realizado', 'se ha acreditado', 'acreditado en su cuenta',
)

_EXCLUIR_ASUNTO = (
    'dte', 'factura electr', 'siidte', 'resultado de revision', 'acuse de recibo',
    'xml', 'envio dte', 'boleta electr',
    # Marketing / comunicaciones banco — solo aplica cuando el asunto NO es aviso de abono
    'tu negocio siempre', 'siempre en control', 'banca en linea',
    'banca en línea', 'conoce nuest', 'promoci', 'newsletter',
    'novedades', 'javascript',
)

# Solo bloquear remitentes claramente de marketing que NO son canales de notificación bancaria.
# IMPORTANTE: mensajeria@correobancoestado.cl y mensajeria@santander.cl son canales LEGÍTIMOS
# de aviso de transferencia — NO deben estar en esta lista.
_EXCLUIR_REMITENTE = (
    'marketing@',
    'novedades@',
    'comunicaciones@',
    'info@banco',
    'noreply@mercadolibre',
    'noreply@paypal',
)

# Solo excluir por cuerpo patrones que son inequívocamente de marketing (nunca en correo de abono).
# Eliminados: 'app bancoestado empresas', 'garantia estatal', 'cmfchile.cl', 'opera desde tu'
# — aparecen en el PIE DE PÁGINA de correos legítimos de transferencia de BancoEstado.
_EXCLUIR_CUERPO = (
    'javascript :;',
    'herramientas para tu negocio',
    'beneficios exclusivos para ti',
    'descarga nuestra app',
)

_ASUNTO_AVISO_TRANSFERENCIA = (
    'aviso de transferencia', 'transferencia de fondos', 'transferencia recibida',
    'transferencia electr', 'abono en cuenta', 'abono a su cuenta', 'abono a cuenta',
    'te han transferido', 'ha recibido una transferencia', 'recibio una transferencia',
    'ingreso de fondos', 'pago recibido',
)


@dataclass
class CorreoTransferenciaParseado:
    remitente: str
    asunto: str
    monto: float | None
    referencia: str | None
    rut_ordenante: str | None
    nombre_ordenante: str | None
    extracto: str
    es_transferencia: bool
    motivo_filtro: str = ''


def _normalizar_monto_clp(raw: str) -> float | None:
    s = (raw or '').strip().replace('\xa0', ' ').replace(' ', '')
    if not s:
        return None
    s = s.replace('$', '')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        tail = s.split(',')[-1]
        if len(tail) == 2:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    else:
        s = s.replace('.', '')
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None


def _extraer_monto(texto: str) -> float | None:
    """
    Extrae el monto de esta transferencia puntual.
    Usa búsqueda por prioridad (primer match del patrón más específico) en vez
    de max(), lo que evita capturar montos de secciones de historial o pie de
    correo bancario que listan transacciones anteriores.
    """
    t = texto or ''
    # Patrones de mayor a menor especificidad — se devuelve el PRIMER match válido.
    patrones_prioridad = [
        # Etiquetas explícitas de monto de esta operación
        r'(?:monto|importe)[:\s]*\$?\s*([\d.\s,]+)',
        r'total\s+abonado[:\s]*\$?\s*([\d.\s,]+)',
        r'(?:ha\s+recibido|recibió)[^\n]{0,40}\$\s*([\d.\s,]+)',
        r'transferencia\s+(?:de|por)[:\s]*\$?\s*([\d.\s,]+)',
        r'abono\s+(?:en|a|de)[^\n]{0,20}\$?\s*([\d.\s,]+)',
        r'ingreso\s+de\s+fondos[:\s]*\$?\s*([\d.\s,]+)',
        r'(?:monto|importe)\s+\$?\s*([\d]{1,3}(?:\.\d{3})+)',
        r'(?:monto|importe)\s+\$?\s*([\d]{4,9})\b',
        # Cualquier monto con $ (primera aparición en el texto)
        r'\$\s*([\d]{1,3}(?:\.\d{3})+(?:,\d{1,2})?)',
        r'(?:CLP|clp)[:\s]*([\d.\s,]+)',
        r'\$\s*([\d]+(?:,\d{1,2})?)',
    ]
    for pat in patrones_prioridad:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            val = _normalizar_monto_clp(m.group(1))
            if val and 100 <= val <= 50_000_000:
                return val
    return None


def _extraer_referencia(texto: str) -> str | None:
    t = texto or ''
    patrones = [
        r'(?:n[°ºo\.]*\s*(?:de\s*)?operaci[oó]n|n[°ºo]\s*transacci[oó]n|referencia|folio|comprobante)[:\s#\-]*([A-Za-z0-9\-]{4,40})',
        r'transacci[oó]n\s*n?[°ºo]?\s*:?\s*([0-9]{4,20})',
        r'(?:operation|transaction)\s*(?:id|number|no\.?)[:\s#\-]*([A-Za-z0-9\-]{4,40})',
    ]
    for pat in patrones:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            ref = m.group(1).strip()
            if ref.lower() not in ('transferencia', 'banco', 'cuenta'):
                return ref[:120]
    return None


def _extraer_rut(texto: str) -> str | None:
    m = re.search(r'(\d{1,2}\.?\d{3}\.?\d{3}[\-\.]?[\dkK])', texto or '')
    if not m:
        return None
    return m.group(1).replace('.', '').upper()[:20]


def _dominios_banco() -> tuple[str, ...]:
    import os
    raw = (os.getenv('TRF_CORREO_REMITENTES') or '').strip()
    if raw:
        return tuple(x.strip().lower().lstrip('@') for x in raw.split(',') if x.strip())
    return _DOMINIOS_BANCO_DEFAULT


def _asunto_es_aviso_transferencia(asunto: str) -> bool:
    asu = (asunto or '').lower()
    return any(x in asu for x in _ASUNTO_AVISO_TRANSFERENCIA)


def _es_correo_promocional_o_spam(remitente: str, asunto: str, cuerpo: str) -> tuple[bool, str]:
    rem = (remitente or '').lower()
    asu = (asunto or '').lower()
    cuerpo_l = (cuerpo or '').lower()
    blob = f'{asu} {cuerpo_l[:2000]}'

    # Si el asunto es explícitamente un aviso de transferencia, no bloqueamos por remitente
    # (cubre mensajeria@correobancoestado.cl, mensajeria@santander.cl, etc.)
    asunto_es_trf = _asunto_es_aviso_transferencia(asunto)
    dominio_es_banco = any(d in rem for d in _dominios_banco())

    if not asunto_es_trf:
        # Solo verificar remitente sospechoso si el asunto no es claramente un aviso de transferencia
        if any(x in rem for x in _EXCLUIR_REMITENTE):
            return True, 'remitente_marketing'

    if any(x in asu for x in _EXCLUIR_ASUNTO):
        return True, 'asunto_marketing'

    # El cuerpo solo aplica como filtro si NO viene de un dominio bancario conocido
    if not dominio_es_banco:
        if any(x in blob for x in _EXCLUIR_CUERPO):
            return True, 'cuerpo_marketing'

    return False, ''


def _tiene_indicio_abono_real(blob: str) -> bool:
    """Evita falsos positivos por 'depósitos' legal CMF en pie de correo."""
    b = blob or ''
    if re.search(r'\babono\b', b, flags=re.IGNORECASE):
        return True
    if re.search(r'\bdep[oó]sito\s+(en|a)\s+(su\s+)?cuenta\b', b, flags=re.IGNORECASE):
        return True
    if re.search(r'\btransferencia\b', b, flags=re.IGNORECASE):
        return True
    if re.search(r'\bingreso\s+de\s+fondos\b', b, flags=re.IGNORECASE):
        return True
    return False


def es_correo_transferencia_bancaria(remitente: str, asunto: str, cuerpo: str) -> tuple[bool, str]:
    rem = (remitente or '').lower()
    asu = (asunto or '').lower()
    cuerpo_l = (cuerpo or '').lower()
    blob = f'{asu} {cuerpo_l[:2000]}'

    _EXCLUIR_DTE = (
        'dte', 'factura electr', 'siidte', 'resultado de revision', 'acuse de recibo',
        'xml', 'envio dte', 'boleta electr',
    )
    if any(x in asu for x in _EXCLUIR_DTE):
        return False, 'excluido_dte_sii'
    promo, motivo_promo = _es_correo_promocional_o_spam(remitente, asunto, cuerpo)
    if promo:
        return False, motivo_promo
    if 'siidte@' in rem or '@sii.cl' in rem:
        return False, 'excluido_sii'

    dominio_ok = any(d in rem for d in _dominios_banco())
    asunto_trf = _asunto_es_aviso_transferencia(asunto)
    palabra_ok = any(p in blob for p in _PALABRAS_TRANSFERENCIA)
    indicio_real = _tiene_indicio_abono_real(blob)

    if asunto_trf and dominio_ok:
        return True, 'asunto_aviso+banco'
    if dominio_ok and palabra_ok and indicio_real:
        return True, 'banco+palabra'
    if dominio_ok and indicio_real:
        return True, 'banco+abono_real'
    return False, 'no_coincide'


def parsear_correo_transferencia(
    *,
    remitente: str,
    asunto: str,
    cuerpo: str,
) -> CorreoTransferenciaParseado:
    texto = f'{asunto or ""}\n{cuerpo or ""}'
    ok, motivo = es_correo_transferencia_bancaria(remitente, asunto, cuerpo)
    monto = _extraer_monto(texto) if ok else None
    referencia = _extraer_referencia(texto) if ok else None
    if ok and not monto and not referencia and not _asunto_es_aviso_transferencia(asunto):
        ok, motivo = False, 'sin_evidencia_operacion'
    rut = _extraer_rut(cuerpo or '') if ok else None
    if ok and not rut:
        rut = _extraer_rut(texto)
    nombre = None
    if ok and rut:
        m_nom = re.search(
            rf'(?:de|from|ordenante|cliente|nombre)[:\s]+([^\n\r]{{3,80}})\s*{re.escape(rut[:4])}',
            cuerpo or '',
            flags=re.IGNORECASE,
        )
        if m_nom:
            nombre = m_nom.group(1).strip()[:200]
        if not nombre:
            m_nom2 = re.search(
                r'(?:mensaje\s*para|nombre\s*(?:del\s*)?ordenante|de)[:\s]+([A-Za-zÁÉÍÓÚáéíóúñÑ\s\.\-]{3,80})',
                texto,
                flags=re.IGNORECASE,
            )
            if m_nom2:
                cand = m_nom2.group(1).strip()
                if cand.lower() not in ('crear cuenta', 'bancoestado', 'cliente'):
                    nombre = cand[:200]
    extracto = (cuerpo or '')[:2000]
    return CorreoTransferenciaParseado(
        remitente=(remitente or '')[:200],
        asunto=(asunto or '')[:500],
        monto=monto,
        referencia=referencia,
        rut_ordenante=rut,
        nombre_ordenante=nombre,
        extracto=extracto,
        es_transferencia=ok,
        motivo_filtro=motivo,
    )


def sugerir_venta_id(
    *,
    monto: float | None,
    referencia: str | None,
    ventas: list[Any],
) -> int | None:
    """Sugiere vale Pagado+Transferencia sin confirmar por monto/referencia."""
    if not ventas:
        return None
    ref_norm = (referencia or '').strip().lower()
    if ref_norm:
        for v in ventas:
            vr = (getattr(v, 'transferencia_referencia', None) or '').strip().lower()
            if vr and vr == ref_norm:
                return int(v.id)
    if monto is None:
        return None
    tol = 1.0
    candidatos = [
        v for v in ventas
        if abs(float(getattr(v, 'monto_total', 0) or 0) - float(monto)) <= tol
    ]
    if len(candidatos) == 1:
        return int(candidatos[0].id)
    return None
