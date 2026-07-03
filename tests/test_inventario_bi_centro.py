"""Smoke tests — Centro de Inteligencia de Inventario."""
import pytest


@pytest.mark.smoke
def test_inventario_bi_acciones_blocks():
    from services.inventario_bi_decision_service import build_acciones

    lineas = [{
        'id': 1, 'codigo': 'X', 'nombre': 'Test', 'estado': 'critico',
        'stock_tienda': 1, 'stock_bodega': 0, 'compra_unidades': 2,
        'precio_compra': 500, 'precio_venta': 800, 'mercaderia_total': 500,
        'mercaderia_bodega': 0, 'capital_inmovilizado': 0,
        'ventas_30': 3, 'ventas_90': 5, 'categoria': 'T', 'sobrestock_unidades': 0,
    }]
    blocks = build_acciones(
        lineas, umbral=5,
        urls={'dashboard': '/d', 'orden_compra_nueva': '/oc', 'bodega': '/b', 'productos': '/p', 'pinturas_remates': '/r'},
        filtros={'periodo': '30d', 'umbral': 5},
    )
    assert len(blocks) == 5
    assert blocks[0]['ejecutar_url'].find('sugerencias_payload') >= 0


@pytest.mark.smoke
def test_inventario_bi_decision_layer():
    from services.inventario_bi_decision_service import build_decision_layer

    kpis = {
        'sku_activos': 10,
        'sin_stock': 2,
        'critico': 3,
        'sobrestock': 1,
        'con_stock': 8,
        'mercaderia_clp': 1000000,
        'capital_clp': 1200000,
        'capital_inmovilizado_clp': 200000,
        'cobertura_promedio_dias': 120.0,
        'rotacion_mes': 0.02,
        'nivel_servicio_pct': 98.0,
        'compra_sugerida_unidades': 5,
        'umbral_critico': 5,
        'fmt_mercaderia': '$1.000.000',
        'fmt_capital': '$1.200.000',
        'fmt_inmovilizado': '$200.000',
    }
    lineas = [
        {
            'id': 1, 'categoria': 'Pinturas', 'subcategoria': 'Barnices',
            'estado': 'sin_stock', 'stock_tienda': 0, 'stock_bodega': 5,
            'stock_total': 5, 'ventas_30': 10, 'ventas_90': 20,
            'precio_venta': 5000, 'precio_compra': 3000,
            'mercaderia_total': 50000, 'capital_inmovilizado': 80000,
            'compra_unidades': 3, 'cobertura_dias': 200,
        },
    ]
    out = build_decision_layer(kpis, lineas, [], {'pct': 5.0}, umbral=5)
    assert 'kpi_cards' in out
    assert out['salud_inventario']['nivel'] in ('excelente', 'buena', 'riesgo')
    assert out['recomendaciones']
    assert out['kpi_cards']['nivel_servicio']['meta_objetivo']['cumple'] is True
    assert out['kpi_cards']['cobertura']['estado'] == 'warn'


@pytest.mark.smoke
def test_inventario_bi_service_collect(app_ctx):
    from services.inventario_bi_service import collect_inventario_bi_centro

    payload = collect_inventario_bi_centro({'umbral': 5})
    assert 'kpis' in payload
    assert 'charts' in payload
    assert 'insights' in payload
    assert payload['kpis']['sku_activos'] >= 0
    assert 'valor_categoria_bar' in payload['charts']
    assert 'kpi_cards' in payload
    assert 'salud_inventario' in payload
    assert 'recomendaciones' in payload
    assert 'acciones' in payload
    assert isinstance(payload['acciones'], list)
    assert 'inmovilizado_top' in payload['charts']
    assert 'riesgo_quiebre' in payload['charts']
    assert 'categorias_catalogo' in payload['opts']
    assert isinstance(payload['opts']['catalogo_tree'], dict)


@pytest.mark.smoke
def test_inventario_bi_valor_bar_drill_subcategoria(app_ctx):
    from services.inventario_bi_service import collect_inventario_bi_centro

    payload = collect_inventario_bi_centro({
        'umbral': 5,
        'categoria': 'Construcción',
        'categoria_modo': 'catalog',
        'solo_con_stock': True,
    })
    bar = payload['charts']['valor_categoria_bar']
    assert bar.get('drill') == 'subcategoria'
    assert bar.get('parent') == 'Construcción'
    assert len(bar['labels']) <= 6  # top 5 + posible «Otros»


@pytest.mark.smoke
def test_inventario_catalogo_filtro_parse():
    from services.inventario_catalogo_filtro_service import parse_categoria_request

    assert parse_categoria_request('Construcción') == ('catalog', 'Construcción')
    assert parse_categoria_request('legacy:Electricidad') == ('legacy', 'Electricidad')
    assert parse_categoria_request('') == ('', None)


@pytest.mark.smoke
def test_inventario_dashboard_premium_bi_template(app_client):
    r = app_client.get('/inventario/dashboard-premium')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Centro de stock' in html
    assert 'Estado general del inventario' in html
    assert 'Recomendaciones' in html
    assert 'Acciones' in html
    assert 'page-inventario-bi-centro' in html or 'bi-shell' in html
