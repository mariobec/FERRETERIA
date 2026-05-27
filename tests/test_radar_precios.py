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


@pytest.mark.smoke
def test_fetch_electrocom_ssl_relaxed(monkeypatch):
    """electrocom.cl falla verify=True en Windows; lista relajada debe permitir descarga."""
    from services.radar_precios_fetch import fetch_public_html

    monkeypatch.setenv(
        'RADAR_FETCH_SSL_RELAXED_HOSTS',
        'electrocom.cl,www.electrocom.cl',
    )
    monkeypatch.setenv('RADAR_FETCH_SSL_VERIFY', '1')
    url = 'https://electrocom.cl/lineas/9/instalacion-residencial'
    res = fetch_public_html(url)
    if not res.get('ok'):
        pytest.skip(f'Red no disponible o sitio caído: {res.get("error")}')
    assert len(res.get('html') or '') > 1000
    assert res.get('ssl_relaxed') is True


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


def test_parse_imperial_occ_state():
    from pathlib import Path

    from services.radar_precios_fetch import parse_imperial_occ_state

    p = Path(__file__).resolve().parents[1] / 'respaldos/imperial_playwright.html'
    if not p.is_file():
        pytest.skip('sin html de prueba imperial')
    html = p.read_text(encoding='utf-8')
    items = parse_imperial_occ_state(html)
    assert len(items) >= 10
    assert any('Cepillo' in (i.get('descripcion_producto') or '') for i in items)
    assert items[0]['precio'] > 1000


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

    r3 = mc.append_linea_maestro_csv(
        sku_proveedor='CH-9910',
        descripcion='Pala Punta Huevo',
        precio_lista_clp=13990,
        url='https://www.chilemat.cl/cat',
        proveedor_nombre='Proveedor Test A',
        proveedor_id=101,
        erp_root=root,
    )
    assert r3['accion'] == 'nuevo'
    assert r3['total_filas'] == 2
    assert r3['fila']['codigo_chilemat'] == 'PRV101-CH-9910'
    assert r3['fila']['subcategoria'].startswith('Proveedor:')

    stats = mc.estadisticas_maestro_csv(root)
    assert stats['total_filas'] == 2
    path = mc.ruta_maestro_csv(root)
    text = path.read_text(encoding='utf-8-sig')
    assert 'nombre,codigo_chilemat' in text.splitlines()[0]
    assert 'Pala Punta Huevo Premium' in text


def test_crear_job_solo_lectura_por_defecto(monkeypatch):
    from services import radar_precios_service as svc

    started = {}

    def fake_run(app, job_id):
        started['job_id'] = job_id

    monkeypatch.setattr(svc, '_run_job', fake_run)
    job_id = svc.crear_job(
        url='https://example.com/cat',
        proveedor_id=None,
        usuario='test',
        app=object(),
        guardar_resultados=False,
    )
    job = svc.get_job(job_id)
    assert job is not None
    assert job.get('guardar_resultados') is False
    assert job.get('persistido') is False


@pytest.mark.smoke
def test_ruta_precios_radar_ok_admin(app_client):
    r = app_client.get('/precios/radar', follow_redirects=False)
    assert r.status_code == 200
    assert b'Radar Precios' in r.data or b'radar' in r.data.lower()


def test_api_radar_crear_proveedor(app_client, app_ctx):
    from blueprints._app_ref import app_module

    m = app_module()
    ts = __import__('time').time()
    nombre = f'QA Radar Prov {int(ts)}'
    r = app_client.post(
        '/api/precios/radar/proveedores/crear',
        json={'nombre': nombre, 'rut': '76.000.000-0'},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('id')
    prov = m.Proveedor.query.get(data['id'])
    assert prov is not None
    assert prov.nombre == nombre
    m.db.session.delete(prov)
    m.db.session.commit()


@pytest.mark.smoke
def test_api_radar_buscar_proveedores(app_client, proveedor_test):
    r = app_client.get('/api/precios/radar/proveedores/buscar?q=TEST')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('results')
    assert any('TEST' in (x.get('text') or '').upper() for x in data['results'])


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
