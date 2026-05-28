"""Vitrina pública piloto — /tienda/ferreteria-santo-domingo."""
import pytest

from services import vitrina_tienda_service as vt


@pytest.mark.smoke
def test_tienda_redirect(app_client):
    r = app_client.get('/tienda', follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308)
    assert 'ferreteria-santo-domingo' in (r.location or r.headers.get('Location', ''))


@pytest.mark.smoke
def test_tienda_vitrina_html(app_client):
    r = app_client.get('/tienda/ferreteria-santo-domingo')
    assert r.status_code == 200
    assert b'Ferreter' in r.data or b'tienda' in r.data.lower()
    assert b'tienda-mega' in r.data or b'Categor' in r.data


@pytest.mark.smoke
def test_menu_mega_construye(app_ctx):
    menu = vt.construir_menu_mega(slug=vt.TIENDA_SLUG_SD)
    assert menu.get('raices')
    if menu['raices']:
        assert menu['paneles']
        assert len(menu['paneles']) == len(menu['raices'])


@pytest.mark.smoke
def test_tienda_vitrina_incluye_liz(app_client):
    r = app_client.get('/tienda/ferreteria-santo-domingo')
    assert r.status_code == 200
    assert b'Liz' in r.data
    assert b'tienda-assistant' in r.data
    assert b'liz_avatar' in r.data


@pytest.mark.smoke
def test_tienda_asistente_api(app_client):
    r = app_client.post(
        '/api/tienda/ferreteria-santo-domingo/asistente',
        json={'mensaje': 'hola'},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'reply' in data
    assert 'motor' in data
    assert 'liz' in (data.get('reply') or '').lower() or data.get('motor')


def test_normalizar_consulta_asistente_remueve_ruido():
    q, tokens = vt._normalizar_consulta_asistente('Busco pintura impermeabilizante para techo')
    assert 'busco' not in q
    assert 'pintura' in tokens
    assert 'impermeabilizante' in tokens


def test_hola_quiero_producto_no_es_solo_saludo():
    assert vt._es_solo_saludo('hola') is True
    assert vt._es_solo_saludo('hola quiero pintura') is False


def test_busqueda_asistente_fallback_tokens(monkeypatch):
    calls = []

    def _fake_listar_productos(*, page=1, per_page=12, q_text='', solo_disponibles=False, **_kwargs):
        calls.append(q_text)
        if q_text in ('busco pintura', 'pintura impermeabilizante'):
            return {'productos': [], 'total': 0}
        if q_text == 'pintura':
            return {
                'productos': [{'producto_id': 101, 'nombre': 'Pintura test', 'precio_fmt': '$9.990', 'disponible': True}],
                'total': 1,
            }
        return {'productos': [], 'total': 0}

    monkeypatch.setattr(vt, 'listar_productos', _fake_listar_productos)
    items, total = vt._buscar_items_asistente('busco pintura')
    assert total >= 1
    assert items and items[0]['producto_id'] == 101
    assert 'pintura' in calls


def test_tienda_api_catalogo_q(app_client):
    r = app_client.get('/api/tienda/ferreteria-santo-domingo/catalogo?q=test')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'productos' in data


def test_rankear_prefiere_pintura_sobre_bandeja():
    items = [
        {'nombre': 'Bandeja Pintura 7 x 27 cm Rojo', 'categoria': 'Herramientas', 'categoria_path': ''},
        {'nombre': 'Pintura Latex Blanco 1 Galon', 'categoria': 'Pinturas', 'categoria_path': '/Pinturas/'},
        {'nombre': 'Bandeja Pintura 7 x 27 cm Rojo', 'categoria': 'Herramientas', 'categoria_path': ''},
    ]
    out = vt._rankear_y_filtrar_items(items, ['pintura'], min_score=8, limite=10)
    assert out
    assert 'Latex' in out[0]['nombre']
    assert len(out) == 1


def test_reply_destacado_menciona_producto():
    items = [{'nombre': 'Pintura Esmalte Rojo 1/4 Galon', 'precio_fmt': '$9.990', 'disponible': True}]
    msg = vt._reply_destacado_sodimac(items, 'pintura')
    assert 'Pintura Esmalte' in msg
    assert '$9.990' in msg


def test_reply_combo_reglas_menciona_carrito():
    combo = {
        'activo': True,
        'ancla': {
            'nombre': 'Cinta Masking 48mm',
            'precio_fmt': '$2.500',
            'disponible': True,
        },
        'relacionados': [
            {'nombre': 'Brocha Hormigon 4"', 'precio_fmt': '$4.990', 'disponible': True},
        ],
    }
    msg = vt._reply_combo_reglas(combo, 'cinta masking')
    assert 'Cinta Masking' in msg
    assert 'Brocha' in msg
    assert 'carrito' in msg.lower()


def test_contexto_combo_vacio_sin_relaciones(monkeypatch):
    monkeypatch.setattr(vt, 'sugeridos_para_detalle', lambda *_a, **_k: [])
    ctx = vt._contexto_combo_liz(
        [{'producto_id': 1, 'nombre': 'Test', 'precio_fmt': '$1', 'disponible': True}],
        vt.TIENDA_SLUG_SD,
    )
    assert ctx.get('activo') is False


def test_respuesta_asistente_modo_combo(monkeypatch):
    items = [
        {
            'producto_id': 10,
            'nombre': 'Cinta Masking',
            'precio_fmt': '$2.500',
            'precio': 2500,
            'disponible': True,
            'stock_tienda': 5,
            'referencia': 'CM1',
        }
    ]

    def _fake_buscar(txt):
        return items, 1

    monkeypatch.setattr(vt, '_buscar_items_asistente', _fake_buscar)
    monkeypatch.setattr(
        vt,
        '_contexto_combo_liz',
        lambda _items, _slug, **_: {
            'activo': True,
            'ancla': items[0],
            'relacionados': [
                {
                    'producto_id': 11,
                    'nombre': 'Brocha Hormigon',
                    'precio_fmt': '$4.990',
                    'disponible': True,
                }
            ],
            'cards_combo': [],
            'lineas_carrito': [
                vt._linea_carrito_desde_item(items[0]),
                {
                    'producto_id': 11,
                    'nombre': 'Brocha Hormigon',
                    'precio_fmt': '$4.990',
                    'precio': 4990,
                    'disponible': True,
                    'stock_tienda': 2,
                    'referencia': '',
                },
            ],
            'resumen_ollama': 'Brocha Hormigon ($4.990)',
        },
    )
    monkeypatch.setattr(vt, '_respuesta_ollama', lambda **_k: None)

    out = vt.respuesta_asistente(slug=vt.TIENDA_SLUG_SD, mensaje='tienes cinta masking?')
    assert out.get('modo_combo') is True
    assert 'Brocha' in (out.get('reply') or '')
    assert len(out.get('combo_lineas') or []) >= 2
    assert out.get('motor') in ('combo', 'ollama')


def test_respuesta_hola_quiero_pintura_devuelve_cards(monkeypatch):
    def _fake_buscar(txt):
        if 'pintura' in (txt or ''):
            return (
                [{'producto_id': 55, 'nombre': 'Pintura latex', 'precio_fmt': '$12.990', 'disponible': True}],
                1,
            )
        return [], 0

    monkeypatch.setattr(vt, '_buscar_items_asistente', _fake_buscar)
    monkeypatch.setattr(vt, '_respuesta_ollama', lambda **_k: None)
    out = vt.respuesta_asistente(slug=vt.TIENDA_SLUG_SD, mensaje='hola quiero pintura')
    assert out.get('catalogo_url')
    assert out.get('consulta') == 'pintura'
    assert 'opcion' in (out.get('reply') or '').lower() or 'destacada' in (out.get('reply') or '').lower()


def test_respuesta_recomendacion_generica_fallback(monkeypatch):
    monkeypatch.setattr(vt, '_buscar_items_asistente', lambda _txt: ([], 0))
    monkeypatch.setattr(vt, '_respuesta_ollama', lambda **_k: None)
    monkeypatch.setattr(
        vt,
        'listar_productos',
        lambda **_k: {
            'productos': [
                {'producto_id': 201, 'nombre': 'Serrucho Profesional 20"', 'precio_fmt': '$8.990', 'disponible': True},
                {'producto_id': 202, 'nombre': 'Martillo Carpintero 16oz', 'precio_fmt': '$6.990', 'disponible': True},
                {'producto_id': 203, 'nombre': 'Broca Muro 8mm', 'precio_fmt': '$1.990', 'disponible': True},
            ],
            'total': 3,
        },
    )
    out = vt.respuesta_asistente(slug=vt.TIENDA_SLUG_SD, mensaje='me puedes recomendar una')
    assert out.get('cards')
    assert len(out['cards']) >= 1
    assert 'recom' in (out.get('reply') or '').lower()


def test_respuesta_tienes_producto_sin_match_entrega_alternativas(monkeypatch):
    monkeypatch.setattr(vt, '_buscar_items_asistente', lambda _txt: ([], 0))
    monkeypatch.setattr(vt, '_respuesta_ollama', lambda **_k: None)
    monkeypatch.setattr(
        vt,
        'listar_productos',
        lambda **kwargs: {
            'productos': [
                {'producto_id': 301, 'nombre': 'Alambre galvanizado 1.6 mm', 'precio_fmt': '$3.990', 'disponible': True},
                {'producto_id': 302, 'nombre': 'Alambre recocido 1 kg', 'precio_fmt': '$4.490', 'disponible': True},
                {'producto_id': 303, 'nombre': 'Alambre de amarre 0.8 mm', 'precio_fmt': '$2.990', 'disponible': True},
            ],
            'total': 3,
            'q': kwargs.get('q_text', ''),
        },
    )
    out = vt.respuesta_asistente(slug=vt.TIENDA_SLUG_SD, mensaje='hola linda, tienes alambre?')
    assert out.get('cards')
    assert len(out['cards']) >= 1
    assert 'carrito' in (out.get('reply') or '').lower()
    assert 'alternativas' in (out.get('reply') or '').lower() or 'opciones' in (out.get('reply') or '').lower()


@pytest.mark.smoke
def test_tienda_vitrina_incluye_carrito(app_client):
    r = app_client.get('/tienda/ferreteria-santo-domingo')
    assert r.status_code == 200
    assert b'tiendaCartToggle' in r.data
    assert b'data-add-carrito' in r.data
    assert b'tiendaCarritoConfig' in r.data


def test_mensaje_whatsapp_carrito():
    lineas = [
        {
            'producto_id': 1,
            'nombre': 'Cemento 25 kg',
            'referencia': 'CEM25',
            'precio': 5990,
            'precio_fmt': '$5.990',
            'cantidad': 2,
            'disponible': True,
        }
    ]
    msg = vt.mensaje_whatsapp_carrito('Ferretería Santo Domingo', lineas, cliente_nombre='Mario')
    assert 'Cemento 25 kg' in msg
    assert 'x2' in msg
    assert 'Mario' in msg
    assert 'confirman en caja' in msg.lower()
    tot = vt.calcular_totales_carrito(lineas)
    assert tot['subtotal'] == 5990 * 2


def test_api_carrito_whatsapp_vacio(app_client):
    r = app_client.post(
        '/api/tienda/ferreteria-santo-domingo/carrito/whatsapp',
        json={'lineas': []},
    )
    assert r.status_code == 400


def test_api_carrito_whatsapp_ok(monkeypatch, app_client):
    monkeypatch.setenv('WHATSAPP_VENTAS', '+56912345678')
    r = app_client.post(
        '/api/tienda/ferreteria-santo-domingo/carrito/whatsapp',
        json={
            'lineas': [
                {
                    'producto_id': 99,
                    'nombre': 'Broca 8 mm',
                    'referencia': 'BR8',
                    'precio': 1990,
                    'precio_fmt': '$1.990',
                    'cantidad': 1,
                    'disponible': True,
                }
            ],
            'cliente_nombre': 'Cliente web',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'wa.me' in (data.get('url') or '')
    assert 'Broca' in (data.get('mensaje') or '')
