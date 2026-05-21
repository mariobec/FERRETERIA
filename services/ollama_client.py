"""Cliente HTTP Ollama — inferencia local (LhexIA v0.2). Falla en silencio."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

_log = logging.getLogger(__name__)

OLLAMA_TIMEOUT_SEC = 30
DEFAULT_BASE_URL = 'http://127.0.0.1:11434'
DEFAULT_MODEL = 'qwen2.5:7b'


def ollama_habilitado() -> bool:
    v = (os.getenv('AGENTE_OLLAMA_ENABLED') or '0').strip().lower()
    return v in ('1', 'true', 'yes', 'on')


def ollama_base_url() -> str:
    return (os.getenv('OLLAMA_BASE_URL') or DEFAULT_BASE_URL).strip().rstrip('/')


def ollama_model() -> str:
    return (os.getenv('OLLAMA_MODEL') or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def ollama_disponible() -> bool:
    """Ping liviano; no lanza excepciones."""
    if not ollama_habilitado():
        return False
    try:
        r = requests.get(f'{ollama_base_url()}/api/tags', timeout=5)
        return r.status_code == 200
    except Exception as ex:
        _log.debug('Ollama no disponible: %s', ex)
        return False


def generar_chat(
    *,
    system: str,
    user: str,
    model: str | None = None,
    timeout: int = OLLAMA_TIMEOUT_SEC,
) -> dict[str, Any]:
    """
    POST /api/chat. Retorna siempre dict:
    {ok, texto, tokens_total, error, modelo}.
    """
    if not ollama_habilitado():
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'ollama_disabled', 'modelo': ''}

    modelo = (model or ollama_model()).strip()
    url = f'{ollama_base_url()}/api/chat'
    payload = {
        'model': modelo,
        'messages': [
            {'role': 'system', 'content': (system or '')[:8000]},
            {'role': 'user', 'content': (user or '')[:12000]},
        ],
        'stream': False,
        'options': {'temperature': 0.25, 'num_predict': 480},
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            return {
                'ok': False,
                'texto': '',
                'tokens_total': 0,
                'error': f'http_{r.status_code}',
                'modelo': modelo,
            }
        data = r.json()
        msg = data.get('message') or {}
        texto = (msg.get('content') or '').strip()
        if not texto:
            return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'empty_response', 'modelo': modelo}
        tokens = int(data.get('eval_count') or 0) + int(data.get('prompt_eval_count') or 0)
        return {'ok': True, 'texto': texto, 'tokens_total': tokens, 'error': None, 'modelo': modelo}
    except requests.Timeout:
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'timeout', 'modelo': modelo}
    except requests.RequestException as ex:
        _log.debug('Ollama chat error: %s', ex)
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'connection', 'modelo': modelo}
    except Exception as ex:
        _log.debug('Ollama chat unexpected: %s', ex)
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'unexpected', 'modelo': modelo}
