"""Observabilidad mínima — métricas para GET /api/sistema/salud (lazy `import app`)."""
import os
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_


def collect_sistema_salud_metrics():
    """Dict serializable a JSON (sin `ok`; lo agrega la ruta)."""
    import app as m

    m._asegurar_columnas_ventas_bodega_despacho()
    Venta = m.Venta
    horas = m._vale_despacho_sin_cobro_alert_horas()
    limite = datetime.now() - timedelta(hours=horas)
    json_no_vacio = and_(
        Venta.bodega_despacho_json.isnot(None),
        func.length(func.trim(Venta.bodega_despacho_json)) > 2,
    )
    est_dsp = and_(Venta.bodega_despacho_estado.isnot(None), func.trim(Venta.bodega_despacho_estado) != '')
    ref_ts = func.coalesce(Venta.bodega_despacho_ultimo_at, Venta.fecha)
    ids = [
        r[0]
        for r in (
            m.db.session.query(m.Venta.id)
            .filter(
                m.Venta.estado == 'Pendiente',
                m.Venta.metodo_pago.is_(None),
                m.or_(est_dsp, json_no_vacio),
                ref_ts < limite,
            )
            .limit(400)
            .all()
        )
    ]
    n_riesgo = 0
    if ids:
        for v in Venta.query.filter(Venta.id.in_(ids)).all():
            if m._venta_tiene_despacho_bodega(v):
                n_riesgo += 1

    audit_ok = bool(m._asegurar_tabla_erp_audit_log())
    audit_eventos_24h = None
    bodega_voice_despachos_auditoria_24h = None
    if audit_ok:
        try:
            since = datetime.now() - timedelta(hours=24)
            audit_eventos_24h = int(
                m.db.session.query(func.count(m.ErpAuditLog.id))
                .filter(m.ErpAuditLog.created_at >= since)
                .scalar()
                or 0
            )
            bodega_voice_despachos_auditoria_24h = int(
                m.db.session.query(func.count(m.ErpAuditLog.id))
                .filter(
                    m.ErpAuditLog.created_at >= since,
                    m.ErpAuditLog.evento == 'bodega_despacho_voz',
                )
                .scalar()
                or 0
            )
        except Exception:
            audit_eventos_24h = None
            bodega_voice_despachos_auditoria_24h = None

    openai_key_configured = bool(m._openai_api_key())
    return {
        'server_time': datetime.now().isoformat(timespec='seconds'),
        'vales_despacho_bodega_sin_cobro_sobre_umbral': n_riesgo,
        'horas_umbral': horas,
        'vista_riesgo_despacho_instalada': m._vista_vales_riesgo_despacho_existe(),
        'erp_audit_log_tabla_ok': audit_ok,
        'erp_audit_eventos_24h': audit_eventos_24h,
        'bodega_voice_despachos_auditoria_24h': bodega_voice_despachos_auditoria_24h,
        'openai_key_configured': openai_key_configured,
        'slack_webhook_configured': bool((os.getenv('SLACK_WEBHOOK_URL') or os.getenv('ERP_SLACK_WEBHOOK_URL') or '').strip()),
    }


def slack_post_text(webhook_url: str, text: str, timeout_sec: float = 12.0) -> tuple[bool, str | None]:
    """POST Incoming Webhook de Slack. Retorna (ok, error_corta)."""
    import requests

    if not (webhook_url or '').strip():
        return False, 'sin_webhook'
    try:
        r = requests.post(webhook_url.strip(), json={'text': text}, timeout=timeout_sec)
        if r.ok:
            return True, None
        return False, f'http_{r.status_code}'
    except Exception as ex:
        return False, str(ex)[:200]


def texto_resumen_vales_riesgo_slack(horas_umbral: int, items: list) -> str:
    lineas = [
        f"#{it.get('venta_id')} — {it.get('vendedor') or 'sin vendedor'} — {it.get('horas_sin_cobro') or '?'} h — {it.get('bodega_despacho_estado') or ''}"
        for it in items[:35]
    ]
    body = (
        f'*Lhexa ERP* Vales con despacho bodega sin cobro (≥{horas_umbral} h): *{len(items)}* caso(s)\n'
        + '\n'.join(lineas)
    )
    if len(body) > 3900:
        body = body[:3890] + '\n…(truncado)'
    return body
