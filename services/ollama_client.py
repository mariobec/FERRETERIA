"""Cliente HTTP Ollama — inferencia local o remota (LhexIA v0.2 + Liz vitrina)."""
from __future__ import annotations

import logging
import os
from typing import Any, Literal

import requests

_log = logging.getLogger(__name__)

OllamaScope = Literal['default', 'vitrina']

OLLAMA_TIMEOUT_SEC = 120
DEFAULT_BASE_URL = 'http://127.0.0.1:11434'
DEFAULT_MODEL = 'qwen2.5:7b-instruct-q4_K_M'


def _truthy_env(val: str | None) -> bool:
    return (val or '').strip().lower() in ('1', 'true', 'yes', 'on', 'si')


def _is_remote_url(url: str) -> bool:
    u = (url or '').strip().lower()
    return not any(x in u for x in ('127.0.0.1', 'localhost', '[::1]', '0.0.0.0'))


def _ollama_timeout_sec(*, scope: OllamaScope = 'default') -> int:
    keys = (
        ('VITRINA_OLLAMA_TIMEOUT_SEC', 'OLLAMA_TIMEOUT_SEC')
        if scope == 'vitrina'
        else ('OLLAMA_TIMEOUT_SEC',)
    )
    for key in keys:
        raw = (os.getenv(key) or '').strip()
        if raw:
            try:
                return max(30, min(int(raw), 300))
            except ValueError:
                pass
    if scope == 'vitrina' and _is_remote_url(ollama_base_url(scope='vitrina')):
        return 120
    return OLLAMA_TIMEOUT_SEC


def _ping_timeout_sec(*, scope: OllamaScope = 'default') -> int:
    if scope == 'vitrina':
        raw = (os.getenv('VITRINA_OLLAMA_PING_SEC') or '').strip()
        if raw:
            try:
                return max(3, min(int(raw), 30))
            except ValueError:
                pass
        if _is_remote_url(ollama_base_url(scope='vitrina')):
            return 12
    return 5


def ollama_habilitado(*, scope: OllamaScope = 'default') -> bool:
    """
    default: Operador / radar (AGENTE_OLLAMA_ENABLED).
    vitrina: Liz en lhexia.cl — VITRINA_OLLAMA_* sin forzar Operador en Render.
    """
    if scope == 'vitrina':
        ve = os.getenv('VITRINA_OLLAMA_ENABLED')
        if ve is not None:
            return _truthy_env(ve)
        if (os.getenv('VITRINA_OLLAMA_BASE_URL') or '').strip():
            return True
        return _truthy_env(os.getenv('AGENTE_OLLAMA_ENABLED'))
    return _truthy_env(os.getenv('AGENTE_OLLAMA_ENABLED'))


def ollama_base_url(*, scope: OllamaScope = 'default') -> str:
    if scope == 'vitrina':
        custom = (os.getenv('VITRINA_OLLAMA_BASE_URL') or '').strip().rstrip('/')
        if custom:
            return custom
    return (os.getenv('OLLAMA_BASE_URL') or DEFAULT_BASE_URL).strip().rstrip('/')


def ollama_model(*, scope: OllamaScope = 'default') -> str:
    if scope == 'vitrina':
        m = (os.getenv('VITRINA_OLLAMA_MODEL') or '').strip()
        if m:
            return m
    return (os.getenv('OLLAMA_MODEL') or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _request_headers(*, scope: OllamaScope = 'default') -> dict[str, str]:
    if scope == 'vitrina':
        key = (os.getenv('VITRINA_OLLAMA_API_KEY') or os.getenv('OLLAMA_API_KEY') or '').strip()
    else:
        key = (os.getenv('OLLAMA_API_KEY') or '').strip()
    if not key:
        return {}
    return {'Authorization': f'Bearer {key}'}


def ollama_disponible(*, scope: OllamaScope = 'default', requiere_modelo: bool = True) -> bool:
    """Ping liviano; opcionalmente exige que el modelo configurado esté descargado."""
    if not ollama_habilitado(scope=scope):
        return False
    base = ollama_base_url(scope=scope)
    try:
        r = requests.get(
            f'{base}/api/tags',
            timeout=_ping_timeout_sec(scope=scope),
            headers=_request_headers(scope=scope),
        )
        if r.status_code != 200:
            return False
        if not requiere_modelo:
            return True
        data = r.json()
        want = ollama_model(scope=scope).lower()
        names = []
        for m in data.get('models') or []:
            n = (m.get('name') or '').strip().lower()
            if n:
                names.append(n)
        if not names:
            return False
        return any(
            n == want or n.startswith(want + ':') or want.startswith(n + ':')
            for n in names
        )
    except Exception as ex:
        _log.debug('Ollama no disponible (%s): %s', scope, ex)
        return False


def generar_chat(
    *,
    scope: OllamaScope = 'default',
    system: str,
    user: str,
    model: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    POST /api/chat. Retorna siempre dict:
    {ok, texto, tokens_total, error, modelo}.
    """
    if not ollama_habilitado(scope=scope):
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'ollama_disabled', 'modelo': ''}

    modelo = (model or ollama_model(scope=scope)).strip()
    if timeout is None:
        timeout = _ollama_timeout_sec(scope=scope)
    url = f'{ollama_base_url(scope=scope)}/api/chat'
    payload = {
        'model': modelo,
        'messages': [
            {'role': 'system', 'content': (system or '')[:8000]},
            {'role': 'user', 'content': (user or '')[:12000]},
        ],
        'stream': False,
        'options': {'temperature': 0.25, 'num_predict': 480},
    }
    headers = _request_headers(scope=scope)
    try:
        r = requests.post(url, json=payload, timeout=timeout, headers=headers)
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
        _log.debug('Ollama chat error (%s): %s', scope, ex)
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'connection', 'modelo': modelo}
    except Exception as ex:
        _log.debug('Ollama chat unexpected (%s): %s', scope, ex)
        return {'ok': False, 'texto': '', 'tokens_total': 0, 'error': 'unexpected', 'modelo': modelo}


def ollama_habilitado_vitrina() -> bool:
    return ollama_habilitado(scope='vitrina')


def ollama_disponible_vitrina(*, requiere_modelo: bool = True) -> bool:
    return ollama_disponible(scope='vitrina', requiere_modelo=requiere_modelo)


def generar_chat_vitrina(*, system: str, user: str, model: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    return generar_chat(scope='vitrina', system=system, user=user, model=model, timeout=timeout)


def vitrina_ollama_status() -> dict[str, Any]:
    """Diagnóstico Liz / Render (sin lanzar excepciones)."""
    hab = ollama_habilitado_vitrina()
    base = ollama_base_url(scope='vitrina')
    return {
        'habilitado': hab,
        'base_url': base,
        'remoto': _is_remote_url(base),
        'modelo': ollama_model(scope='vitrina'),
        'disponible': ollama_disponible_vitrina() if hab else False,
    }
