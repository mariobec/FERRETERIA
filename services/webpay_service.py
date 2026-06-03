"""Transbank Webpay Plus — checkout vitrina e-commerce."""
from __future__ import annotations

import os
from typing import Any

import requests


def webpay_habilitado() -> bool:
    v = (os.getenv('WEBPAY_ENABLED') or '0').strip().lower()
    return v in ('1', 'true', 'si', 'yes', 'on')


def _webpay_base_url() -> str:
    env = (os.getenv('WEBPAY_ENV') or 'integration').strip().lower()
    if env in ('prod', 'production', 'live'):
        return 'https://webpay3g.transbank.cl'
    return 'https://webpay3gint.transbank.cl'


def _webpay_credentials() -> tuple[str, str]:
    """Commerce code (API Key Id) y API Secret."""
    cc = (os.getenv('WEBPAY_COMMERCE_CODE') or '597055555532').strip()
    secret = (
        os.getenv('WEBPAY_API_SECRET')
        or '579B532A7440BB0C9079DEDCF7031791518E971285711964709F93767E94B376'
    ).strip()
    return cc, secret


def crear_transaccion(
    *,
    buy_order: str,
    session_id: str,
    amount: int,
    return_url: str,
) -> dict[str, Any]:
    """Inicia pago Webpay Plus. Retorna token + url redirect."""
    if not webpay_habilitado():
        return {'ok': False, 'error': 'webpay_disabled'}
    if amount < 50:
        return {'ok': False, 'error': 'monto_invalido', 'mensaje': 'Monto mínimo Webpay: $50.'}

    cc, secret = _webpay_credentials()
    url = f'{_webpay_base_url()}/rswebpaytransaction/api/webpay/v1.2/transactions'
    payload = {
        'buy_order': str(buy_order)[:26],
        'session_id': str(session_id)[:61],
        'amount': int(amount),
        'return_url': return_url,
    }
    try:
        res = requests.post(
            url,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'Tbk-Api-Key-Id': cc,
                'Tbk-Api-Key-Secret': secret,
            },
            timeout=30,
        )
        data = res.json() if res.content else {}
        if res.status_code >= 400:
            return {
                'ok': False,
                'error': 'webpay_create_failed',
                'mensaje': (data.get('error_message') or res.text or 'Error Webpay')[:200],
                'status': res.status_code,
            }
        token = (data.get('token') or '').strip()
        redirect = (data.get('url') or '').strip()
        if not token or not redirect:
            return {'ok': False, 'error': 'webpay_sin_token', 'mensaje': 'Respuesta Webpay incompleta.'}
        return {'ok': True, 'token': token, 'url': redirect, 'buy_order': payload['buy_order']}
    except requests.RequestException as ex:
        return {'ok': False, 'error': 'webpay_red', 'mensaje': str(ex)[:200]}


def confirmar_transaccion(token: str) -> dict[str, Any]:
    """Commit token_ws tras retorno del tarjetahabiente."""
    if not webpay_habilitado():
        return {'ok': False, 'error': 'webpay_disabled'}
    tok = (token or '').strip()
    if not tok:
        return {'ok': False, 'error': 'token_vacio'}

    cc, secret = _webpay_credentials()
    url = f'{_webpay_base_url()}/rswebpaytransaction/api/webpay/v1.2/transactions/{tok}'
    try:
        res = requests.put(
            url,
            headers={
                'Content-Type': 'application/json',
                'Tbk-Api-Key-Id': cc,
                'Tbk-Api-Key-Secret': secret,
            },
            timeout=30,
        )
        data = res.json() if res.content else {}
        if res.status_code >= 400:
            return {
                'ok': False,
                'error': 'webpay_commit_failed',
                'mensaje': (data.get('error_message') or res.text or 'Error commit Webpay')[:200],
            }
        status = (data.get('status') or '').strip().upper()
        approved = status == 'AUTHORIZED'
        return {
            'ok': True,
            'approved': approved,
            'status': status,
            'buy_order': data.get('buy_order'),
            'amount': data.get('amount'),
            'authorization_code': data.get('authorization_code'),
            'payment_type_code': data.get('payment_type_code'),
            'response_code': data.get('response_code'),
            'raw': data,
        }
    except requests.RequestException as ex:
        return {'ok': False, 'error': 'webpay_red', 'mensaje': str(ex)[:200]}
