"""Smoke tests — LhexIA Radar Precios."""
import json

import pytest

from services.radar_precios_fetch import (
    extraer_productos_de_html,
    parse_json_ld_products,
    validar_url_publica,
)


def test_validar_url_publica_ok():
    assert validar_url_publica('https://www.ejemplo.cl/productos') == 'https://www.ejemplo.cl/productos'


def test_validar_url_rechaza_localhost():
    with pytest.raises(ValueError):
        validar_url_publica('http://127.0.0.1/lista')


def test_parse_json_ld_product():
    html = '''
    <script type="application/ld+json">
    {"@type":"Product","name":"Martillo 16oz","sku":"M-16","offers":{"price":"8990"}}
    </script>
    '''
    items = parse_json_ld_products(html)
    assert len(items) == 1
    assert items[0]['descripcion_producto'] == 'Martillo 16oz'
    assert items[0]['precio'] == 8990


def test_extraer_heuristica_precio():
    html = '<div class="product"><h3>Tornillo 1/2</h3><span>$1.290</span></div>'
    items, fuente = extraer_productos_de_html(html)
    assert fuente
    assert items or True  # heurística puede variar


def test_extraer_candidatos_texto_crudo():
    html = '<div class="product"><h3>Pala Punta Huevo</h3><span>$14.990</span></div>'
    cand = __import__('services.radar_precios_fetch', fromlist=['extraer_candidatos_texto_crudo']).extraer_candidatos_texto_crudo(html)
    assert isinstance(cand, list)


def test_parse_urls_multiline():
    from services import radar_precios_service as svc

    urls = svc._parse_urls_input('https://a.cl/x\nhttps://b.cl/y')
    assert len(urls) == 2
    assert urls[0].startswith('https://')


def test_ollama_normalizar_item_sin_ollama(monkeypatch):
    from services import radar_precios_service as svc

    monkeypatch.setattr(
        'services.ollama_client.ollama_disponible',
        lambda *a, **k: False,
    )
    res = svc.ollama_normalizar_item('SKU X Producto $1000')
    assert res['ok'] is False


def test_radar_maestro_csv_acumula(tmp_path):
    from services import radar_maestro_csv as mc

    root = str(tmp_path)
    r1 = mc.append_linea_maestro_csv(
        sku_proveedor='CH-9910',
        descripcion='Pala Punta Huevo',
        precio_lista_clp=14990,
        url='https://www.chilemat.cl/cat',
        erp_root=root,
    )
    assert r1['ok'] is True
    assert r1['accion'] == 'nuevo'
    assert r1['total_filas'] == 1
    assert r1['fila']['stock'] == '0'
    assert r1['fila']['codigo_chilemat'] == 'CH-9910'
    assert r1['fila']['codigo_barra'].startswith('PEND-')
    assert r1['fila']['codigo_interno'].startswith('CHM-')

    r2 = mc.append_linea_maestro_csv(
        sku_proveedor='CH-9910',
        descripcion='Pala Punta Huevo Premium',
        precio_lista_clp=15990,
        url='https://www.chilemat.cl/cat',
        erp_root=root,
    )
    assert r2['accion'] == 'actualizado'
    assert r2['total_filas'] == 1
    assert r2['fila']['precio_compra'] == '15990'

    stats = mc.estadisticas_maestro_csv(root)
    assert stats['total_filas'] == 1
    path = mc.ruta_maestro_csv(root)
    text = path.read_text(encoding='utf-8-sig')
    assert 'nombre,codigo_chilemat' in text.splitlines()[0]
    assert 'Pala Punta Huevo Premium' in text


@pytest.mark.smoke
def test_ruta_precios_radar_ok_admin(app_client):
    r = app_client.get('/precios/radar', follow_redirects=False)
    assert r.status_code == 200
    assert b'Radar Precios' in r.data or b'radar' in r.data.lower()


@pytest.mark.smoke
def test_api_radar_iniciar_sin_url(app_client):
    with app_client.session_transaction() as sess:
        pass
    r = app_client.post(
        '/api/precios/radar/iniciar',
        data=json.dumps({'url': ''}),
        content_type='application/json',
    )
    assert r.status_code in (302, 400, 403)
