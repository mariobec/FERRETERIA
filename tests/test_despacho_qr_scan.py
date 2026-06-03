"""QR despacho: URL corta y normalización lector corrupto."""
import pytest

from services.despacho_qr_service import (
    resolver_url_despacho_desde_escaneo,
    token_desde_qr_path,
    token_para_qr_path,
    url_despacho_qr_corta,
)


def test_url_despacho_qr_corta_sin_query():
    url = url_despacho_qr_corta(3136, 'eyJ2.a.b')
    assert '/r/despacho/3136/' in url
    assert '?' not in url
    assert 'eyJ2_a_b' in url or 'eyJ2' in url


def test_token_roundtrip_path():
    tok = 'eyJ2IjozMTM2fQ.ah4hfA.HKUPZmtLLBjZpejNrMjiebuQjJ0'
    seg = token_para_qr_path(tok)
    assert token_desde_qr_path(seg) == tok


def test_normalizar_escaneo_corrupto_usuario():
    raw = (
        'qr1httpÑ--127.0.0.1Ñ5000-pos-despacho-vale-3136_t¿'
        'eyJ2IjozMTM2fQ.ah4hfA.HKUPZmtLLBjZpejNrMjiebuQjJ0'
    )
    path = resolver_url_despacho_desde_escaneo(raw)
    assert path is not None
    assert path.startswith('/r/despacho/3136/')
    assert 'eyJ2IjozMTM2fQ' in token_desde_qr_path(path.split('/')[-1])


def test_pos_despacho_vale_qr_short_redirect(app_client):
    import app as m

    tok = m.pos_despacho_vale_token_create(999001)
    seg = token_para_qr_path(tok)
    r = app_client.get(f'/r/despacho/999001/{seg}', follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get('Location') or ''
    assert 'despacho/vale/999001' in loc
    assert 't=' in loc


def test_qr_scan_redirect_corrupto(app_client):
    raw = 'qr1httpÑ--127.0.0.1Ñ5000-pos-despacho-vale-3136_t¿eyJ2IjozMTM2fQ.ah4hfA.x'
    r = app_client.get('/r/scan', query_string={'q': raw}, follow_redirects=False)
    assert r.status_code == 200
    assert b'/r/despacho/3136/' in r.data
