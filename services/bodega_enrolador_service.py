"""URLs LAN y helpers para Enrolador Bodega (tablet + pistola BCST-560B)."""
from __future__ import annotations

import os
import socket


def _puerto_desde_request(request) -> str:
    host = (getattr(request, 'host', None) or '').strip()
    if ':' in host:
        return host.split(':', 1)[1]
    return (os.getenv('FLASK_RUN_PORT') or '5000').strip() or '5000'


def detectar_ipv4_lan() -> str | None:
    """IP IPv4 de la interfaz usada hacia internet (típico Wi‑Fi LAN)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.6)
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def resolver_base_lan(request) -> str:
    """
    Base http://IP:puerto para QR tablet.
    Prioridad: BODEGA_ENROLADOR_LAN_URL → ERP_LAN_BASE_URL → IP detectada → host del request.
    """
    explicit = (
        (os.getenv('BODEGA_ENROLADOR_LAN_URL') or '').strip()
        or (os.getenv('ERP_LAN_BASE_URL') or '').strip()
    ).rstrip('/')
    if explicit:
        return explicit

    port = _puerto_desde_request(request)
    host = (request.host or '').split(':')[0].lower()
    if host in ('127.0.0.1', 'localhost', '::1'):
        ip = detectar_ipv4_lan()
        if ip:
            return f'http://{ip}:{port}'
    return request.url_root.rstrip('/')


def urls_enrolador_bodega(request) -> dict:
    """URLs absolutas para instalador / QR (misma red WiFi)."""
    base = resolver_base_lan(request)
    return {
        'base_lan': base,
        'login': f'{base}/login',
        'tablet': f'{base}/inventario/enrolamiento/tablet',
        'setup': f'{base}/bodega/enrolador',
        'enrolamiento': f'{base}/inventario/enrolamiento',
    }
