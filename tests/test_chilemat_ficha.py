"""Smoke — ficha Chilemat (imagen/descripción) y helpers."""
import pytest

from services.chilemat_ficha_service import extraer_ficha_de_json_vtex, fichas_resumen_carrito_por_productos


def test_extraer_ficha_de_json_vtex_minimo():
    prod = {
        'productId': '999',
        'productName': 'Taladro demo',
        'description': '<p>Descripcion <b>fuerte</b></p>',
        'metaTagDescription': 'Corta',
        'link': '/taladro/p',
        'productReference': 'REF-1',
        'items': [
            {
                'images': [{'imageUrl': 'https://cdn.example/img.jpg'}],
                'sellers': [{'commertialOffer': {'Price': 12500}}],
            }
        ],
    }
    f = extraer_ficha_de_json_vtex(prod)
    assert f['vtex_product_id'] == '999'
    assert f['imagen_url'] == 'https://cdn.example/img.jpg'
    assert 'fuerte' in f['descripcion_texto']
    assert f['precio_lista'] == 12500


def test_fichas_resumen_carrito_vacio():
    assert fichas_resumen_carrito_por_productos([]) == {}


@pytest.mark.smoke
def test_api_pos_producto_ficha(app_client, productos_con_stock):
    pid = productos_con_stock[0].id
    r = app_client.get(f'/api/pos/producto-ficha/{pid}')
    assert r.status_code == 200
    assert r.get_json().get('ok') is True


@pytest.mark.smoke
def test_api_chilemat_ficha_vtex_404(app_client):
    r = app_client.get('/api/compras/chilemat/ficha/__no_existe__')
    assert r.status_code == 404


@pytest.mark.smoke
def test_api_chilemat_ficha_producto_invalido(app_client, productos_con_stock):
    pid = productos_con_stock[0].id
    r = app_client.get(f'/api/compras/chilemat/ficha/producto/{pid}')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('producto_id') == pid
