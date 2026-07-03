# -*- coding: utf-8 -*-
"""Utilidades IMAP compartidas (DTE compra + transferencias caja)."""
from __future__ import annotations

import email
import imaplib
import logging
import os
from datetime import date, datetime
from email.header import decode_header
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
_MESES_IMAP = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def load_env_local() -> None:
    p = ROOT / '.env.local'
    if not p.is_file():
        return
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def imap_configurado() -> bool:
    load_env_local()
    return bool((os.getenv('IMAP_USER') or '').strip() and (os.getenv('IMAP_PASSWORD') or '').strip())


def decodificar_header(valor: str | None) -> str:
    if not valor:
        return ''
    partes = decode_header(valor)
    out: list[str] = []
    for frag, enc in partes:
        if isinstance(frag, bytes):
            codec = (enc or 'utf-8').strip().lower()
            if codec in ('unknown-8bit', 'unknown', 'x-unknown', 'default'):
                codec = 'utf-8'
            try:
                out.append(frag.decode(codec, errors='replace'))
            except LookupError:
                out.append(frag.decode('utf-8', errors='replace'))
        else:
            out.append(str(frag))
    return ''.join(out).strip()


def fecha_imap(d: date) -> str:
    return f'{d.day:02d}-{_MESES_IMAP[d.month - 1]}-{d.year}'


def conectar_imap():
    load_env_local()
    host = (os.getenv('IMAP_HOST') or 'imap.gmail.com').strip()
    user = (os.getenv('IMAP_USER') or '').strip()
    password = (os.getenv('IMAP_PASSWORD') or '').strip()
    if not host or not user or not password:
        raise ValueError('Configure IMAP_HOST, IMAP_USER e IMAP_PASSWORD en .env.local')
    port = int(os.getenv('IMAP_PORT') or '993')
    use_ssl = (os.getenv('IMAP_USE_SSL') or '1').strip().lower() in ('1', 'true', 'yes')
    logger.info('Conectando IMAP %s:%s usuario=%s', host, port, user)
    if use_ssl:
        client = imaplib.IMAP4_SSL(host, port)
    else:
        client = imaplib.IMAP4(host, port)
    client.login(user, password)
    return client


def _html_a_texto(raw: str) -> str:
    import html as html_mod
    import re

    if not raw:
        return ''
    t = raw.replace('\r\n', '\n').replace('\r', '\n')
    t = re.sub(r'(?i)<br\s*/?>', '\n', t)
    t = re.sub(r'(?i)</p\s*>', '\n', t)
    t = re.sub(r'(?i)</tr\s*>', '\n', t)
    t = re.sub(r'(?i)</td\s*>', ' ', t)
    t = re.sub(r'(?i)</th\s*>', ' ', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html_mod.unescape(t)
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    # Palabras pegadas por HTML (ej. "Monto$12.345", "transaccion7039771")
    t = re.sub(r'(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ$])', ' ', t)
    t = re.sub(r'(?<=[a-záéíóúñ])(?=\d)', ' ', t)
    t = re.sub(r'(?<=\d)(?=[A-Za-zÁÉÍÓÚáéíóú])', ' ', t)
    return t.strip()


def extraer_texto_plano(msg: email.message.Message, *, max_chars: int = 12000) -> str:
    partes_plain: list[str] = []
    partes_html: list[str] = []

    def _decode(part: email.message.Message) -> str:
        payload = part.get_payload(decode=True)
        if not payload:
            return ''
        charset = part.get_content_charset() or 'utf-8'
        try:
            return payload.decode(charset, errors='replace')
        except LookupError:
            return payload.decode('utf-8', errors='replace')

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disp:
                continue
            if ctype == 'text/plain':
                partes_plain.append(_decode(part))
            elif ctype == 'text/html':
                partes_html.append(_html_a_texto(_decode(part)))
    else:
        ctype = (msg.get_content_type() or '').lower()
        raw = _decode(msg)
        if ctype == 'text/html':
            partes_html.append(_html_a_texto(raw))
        else:
            partes_plain.append(raw)

    bloques: list[str] = []
    if partes_plain:
        bloques.append('\n'.join(p for p in partes_plain if p).strip())
    if partes_html:
        bloques.append('\n'.join(p for p in partes_html if p).strip())
    texto = '\n\n'.join(b for b in bloques if b).strip()
    if len(texto) > max_chars:
        return texto[:max_chars]
    return texto


def parsear_fecha_correo(msg: email.message.Message) -> datetime | None:
    from email.utils import parsedate_to_datetime

    raw = msg.get('Date')
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt
    except (TypeError, ValueError, IndexError):
        return None


def message_id_unico(msg: email.message.Message, *, fallback_uid: str = '') -> str:
    mid = (msg.get('Message-ID') or msg.get('Message-Id') or '').strip()
    if mid:
        return mid[:255]
    rem = decodificar_header(msg.get('From'))[:80]
    sub = decodificar_header(msg.get('Subject'))[:120]
    when = decodificar_header(msg.get('Date'))[:40]
    fb = fallback_uid or '0'
    return f'hash:{fb}|{rem}|{sub}|{when}'[:255]
