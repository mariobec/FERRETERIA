"""Fase 2 — salida WhatsApp Cloud (siempre post-commit desde flujos de dominio)."""

import json
import os
import urllib.error
import urllib.request


def wa_cloud_config():
    """Credenciales WhatsApp Cloud API (Meta). None si faltan."""
    token = (os.getenv('WHATSAPP_CLOUD_ACCESS_TOKEN') or '').strip()
    phone_id = (os.getenv('WHATSAPP_CLOUD_PHONE_NUMBER_ID') or '').strip()
    if not token or not phone_id:
        return None
    ver = (os.getenv('WHATSAPP_CLOUD_API_VERSION') or 'v21.0').strip().lstrip('/') or 'v21.0'
    if not ver.startswith('v'):
        ver = 'v' + ver
    return {'token': token, 'phone_number_id': phone_id, 'version': ver}


def whatsapp_cloud_send_text(to_e164_digits, body):
    """
    Envía mensaje tipo texto por WhatsApp Cloud API.
    Retorna (ok: bool, detalle: str). Meta puede rechazar si hace falta plantilla aprobada (fuera de ventana 24h).
    """
    cfg = wa_cloud_config()
    if not cfg:
        return False, 'wa_cloud_not_configured'
    to = ''.join(c for c in (to_e164_digits or '') if c.isdigit())
    if len(to) < 8:
        return False, 'invalid_to'
    text = (body or '')[:4096]
    if not text.strip():
        return False, 'empty_body'
    url = f"https://graph.facebook.com/{cfg['version']}/{cfg['phone_number_id']}/messages"
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'preview_url': False, 'body': text},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {cfg["token"]}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return True, (resp.read().decode('utf-8', errors='replace') or 'ok')
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8', errors='replace')
        return False, f'http_{e.code}:{err}'
    except Exception as e:
        return False, str(e)


def enviar_texto_cloud(destino, texto):
    return whatsapp_cloud_send_text(destino, texto)
