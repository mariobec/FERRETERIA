"""LhexIA Operador — reglas SQL v0.1 + enriquecimiento Ollama v0.2 (worker local)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from services.agente_contexto_service import contexto_a_texto_prompt, empaquetar_contexto_alerta
from services.agente_ejecuciones_service import (
    EST_ALERTA_ABIERTA,
    TIPO_ALERTA,
    aplicar_enriquecimiento_semantico,
    crear_registro,
    existe_dedupe_abierta,
    listar_alertas_sin_enriquecer,
    obtener_por_id,
    parse_payload_json,
)
from services.ollama_client import generar_chat, ollama_disponible, ollama_model

_log = logging.getLogger(__name__)

_PROMPT_SISTEMA = (
    'Eres LhexIA Operador, supervisor digital de una ferretería en Chile. '
    'Analiza la alerta operativa con el contexto JSON. Responde en español, '
    'máximo 6 oraciones: hipótesis de causa, riesgo para caja/stock, y acción concreta '
    'para el gerente. No inventes montos ni IDs. Costo cloud cero.'
)


def _umbral_vale_horas() -> float:
    try:
        return float((os.getenv('AGENTE_VALE_HORAS_UMBRAL') or '3').strip() or '3')
    except ValueError:
        return 3.0


def _umbral_descuadre_clp() -> int:
    try:
        return int(round(float((os.getenv('AGENTE_CIERRE_DIF_UMBRAL_CLP') or '5000').strip() or '5000')))
    except ValueError:
        return 5000


def _batch_enrich_size() -> int:
    try:
        n = int((os.getenv('AGENTE_ENRICH_BATCH_SIZE') or '5').strip() or '5')
    except ValueError:
        n = 5
    return max(1, min(n, 10))


def _fmt_clp(n: int) -> str:
    sign = '+' if n > 0 else ''
    return f'{sign}${abs(int(n)):,}'.replace(',', '.')


def _payload_operador(base: dict | None) -> dict:
    p = dict(base or {})
    p.setdefault('enriquecido_semantico', False)
    return p


def escanear_y_registrar_alertas() -> dict:
    """
    Ejecuta reglas de solo lectura sobre ventas/cajas (v0.1).
    No llama a Ollama — el enriquecimiento es async vía worker local.
    """
    from app import Caja, Venta

    from services.agente_ejecuciones_service import asegurar_tabla

    if not asegurar_tabla():
        return {'ok': False, 'motivo': 'tabla_agente_ejecuciones_no_disponible'}

    ahora = datetime.now()
    umbral_h = _umbral_vale_horas()
    umbral_clp = _umbral_descuadre_clp()
    creadas = 0
    omitidas = 0
    detalle: list[str] = []

    corte = ahora - timedelta(hours=umbral_h)
    vales = (
        Venta.query.filter(
            Venta.estado == 'Pendiente',
            Venta.fecha.isnot(None),
            Venta.fecha < corte,
        )
        .order_by(Venta.fecha.asc())
        .limit(200)
        .all()
    )
    for v in vales:
        horas = (ahora - (v.fecha or ahora)).total_seconds() / 3600.0
        dedupe = f'operador:vale_pendiente:{v.id}'
        if existe_dedupe_abierta(dedupe):
            omitidas += 1
            continue
        monto = int(round(float(v.monto_total or 0)))
        sev = 'critical' if horas >= umbral_h * 2 else 'warning'
        titulo = f'Vale #{v.id} pendiente {horas:.1f} h'
        cuerpo = (
            f'Vale en estado Pendiente desde {v.fecha.strftime("%d-%m-%Y %H:%M") if v.fecha else "—"}. '
            f'Monto ${monto:,}. Operador: {v.usuario or "—"}.'.replace(',', '.')
        )
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=titulo[:255],
            cuerpo=cuerpo,
            severidad=sev,
            codigo='vale_pendiente_horas',
            dedupe_key=dedupe,
            payload=_payload_operador({
                'venta_id': v.id,
                'horas': round(horas, 2),
                'monto_clp': monto,
                'cuerpo_base_v01': cuerpo,
            }),
            venta_id=v.id,
        )
        if rid:
            creadas += 1
            detalle.append(titulo)
        else:
            omitidas += 1

    desde_caja = ahora - timedelta(days=14)
    cajas = (
        Caja.query.filter(
            Caja.estado == 'Cerrada',
            Caja.fecha_cierre.isnot(None),
            Caja.fecha_cierre >= desde_caja,
        )
        .order_by(Caja.fecha_cierre.desc())
        .limit(100)
        .all()
    )
    for c in cajas:
        diff = int(round(float(c.diferencia_cierre or 0)))
        if abs(diff) < max(1, umbral_clp):
            continue
        dedupe = f'operador:caja_descuadre:{c.id}'
        if existe_dedupe_abierta(dedupe):
            omitidas += 1
            continue
        modo_cierre = (getattr(c, 'modo_cierre_arqueo', None) or '').strip().lower()
        if modo_cierre not in ('ciego', 'visible'):
            from services.cierre_caja_config_service import obtener_modo_cierre_caja

            modo_cierre = obtener_modo_cierre_caja()
        if modo_cierre == 'visible':
            sev = 'critical'
        else:
            sev = 'critical' if diff < 0 else 'warning'
        titulo = f'Caja #{c.id} descuadre {_fmt_clp(diff)} CLP'
        etiqueta_modo = 'ciego' if modo_cierre == 'ciego' else 'visible'
        cuerpo = (
            f'Cierre {c.fecha_cierre.strftime("%d-%m-%Y %H:%M") if c.fecha_cierre else "—"}. '
            f'Apertura: {c.usuario_apertura or "—"}. '
            f'Modo arqueo: {etiqueta_modo}. Diferencia arqueo.'
        )
        rid = crear_registro(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
            titulo=titulo[:255],
            cuerpo=cuerpo,
            severidad=sev,
            codigo='caja_descuadre',
            dedupe_key=dedupe,
            payload=_payload_operador({
                'caja_id': c.id,
                'diferencia_clp': diff,
                'modo_cierre': modo_cierre,
                'cuerpo_base_v01': cuerpo,
            }),
            caja_id=c.id,
        )
        if rid:
            creadas += 1
            detalle.append(titulo)
        else:
            omitidas += 1

    return {
        'ok': True,
        'creadas': creadas,
        'omitidas': omitidas,
        'vales_revisados': len(vales),
        'cajas_revisadas': len(cajas),
        'detalle': detalle[:20],
    }


def construir_prompt_enriquecimiento(row, contexto: dict[str, Any]) -> tuple[str, str]:
    """system, user para Ollama."""
    hist = contexto.get('historial') or {}
    if contexto.get('codigo') == 'vale_pendiente_horas' and isinstance(hist.get('venta'), dict):
        horas = parse_payload_json(row.payload_json).get('horas')
        if horas is not None:
            hist['venta']['horas_pendiente'] = horas
    ctx_txt = contexto_a_texto_prompt(contexto)
    user = (
        f'Alerta: {row.titulo}\n'
        f'Resumen v0.1: {row.cuerpo}\n\n'
        f'Contexto JSON:\n{ctx_txt}\n\n'
        'Redacta el análisis predictivo para el gerente.'
    )
    return _PROMPT_SISTEMA, user


def enriquecer_alerta_operativa(registro_id: int) -> dict[str, Any]:
    """
    Enriquece una alerta con Ollama local. Nunca lanza excepción.
    Si falla, conserva cuerpo v0.1.
    """
    row = obtener_por_id(registro_id)
    if not row or row.tipo != TIPO_ALERTA or row.estado != EST_ALERTA_ABIERTA:
        return {'ok': False, 'id': registro_id, 'motivo': 'registro_no_valido'}

    if parse_payload_json(row.payload_json).get('enriquecido_semantico'):
        return {'ok': True, 'id': registro_id, 'omitida': True, 'motivo': 'ya_enriquecida'}

    if not ollama_disponible():
        return {'ok': False, 'id': registro_id, 'motivo': 'ollama_no_disponible', 'fallback': True}

    try:
        contexto = empaquetar_contexto_alerta(row)
        system, user = construir_prompt_enriquecimiento(row, contexto)
        chat = generar_chat(system=system, user=user)
        if not chat.get('ok'):
            return {
                'ok': False,
                'id': registro_id,
                'motivo': chat.get('error') or 'ollama_error',
                'fallback': True,
            }
        cuerpo_ia = (chat.get('texto') or '').strip()
        cuerpo_final = (
            f'{cuerpo_ia}\n\n---\n'
            f'[Base operativa] {parse_payload_json(row.payload_json).get("cuerpo_base_v01") or row.cuerpo}'
        )[:10000]
        ok = aplicar_enriquecimiento_semantico(
            registro_id,
            cuerpo_enriquecido=cuerpo_final,
            tokens_total=int(chat.get('tokens_total') or 0),
            modelo=chat.get('modelo') or ollama_model(),
        )
        return {
            'ok': ok,
            'id': registro_id,
            'tokens': int(chat.get('tokens_total') or 0),
            'modelo': chat.get('modelo'),
        }
    except Exception as ex:
        _log.debug('enriquecer_alerta_operativa id=%s: %s', registro_id, ex)
        return {'ok': False, 'id': registro_id, 'motivo': 'exception', 'fallback': True}


def ejecutar_lote_enriquecimiento(*, limite: int | None = None) -> dict[str, Any]:
    """Procesa hasta N alertas (worker cron en PC sucursal)."""
    limite = limite if limite is not None else _batch_enrich_size()
    limite = max(1, min(int(limite), 10))
    if not ollama_disponible():
        return {'ok': True, 'procesadas': 0, 'motivo': 'ollama_no_disponible', 'detalle': []}

    filas = listar_alertas_sin_enriquecer(limite=limite)
    detalle = []
    ok_n = 0
    fail_n = 0
    for row in filas:
        res = enriquecer_alerta_operativa(row.id)
        detalle.append(res)
        if res.get('ok') and not res.get('omitida'):
            ok_n += 1
        elif not res.get('omitida'):
            fail_n += 1
    return {
        'ok': True,
        'candidatas': len(filas),
        'enriquecidas': ok_n,
        'fallidas': fail_n,
        'detalle': detalle,
    }
