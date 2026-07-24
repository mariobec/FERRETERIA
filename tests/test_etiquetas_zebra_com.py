"""Smoke — etiquetas COM/Bluetooth (TSPL) y ZPL."""
from services.ticket_impresion_escpos import _parse_com_port, enviar_raw_zpl


def test_parse_com_port():
    assert _parse_com_port('COM4') == 'COM4'
    assert _parse_com_port('com4') == 'COM4'
    assert _parse_com_port(r'\\.\COM4') == 'COM4'
    assert _parse_com_port('Zebra GX420d') is None
    assert _parse_com_port('') is None


def test_enviar_raw_zpl_prioriza_com(monkeypatch):
    called = {}

    def _fake_com(data, port, *, baud=9600):
        called['port'] = port
        called['baud'] = baud
        called['bytes'] = len(data)
        return {'ok': True, 'metodo': 'com_serial', 'puerto': port, 'bytes': len(data)}

    monkeypatch.setattr('services.ticket_impresion_escpos._enviar_zpl_com', _fake_com)
    zpl = b'^XA^FO50,50^FDTEST^FS^XZ'
    res = enviar_raw_zpl(zpl, 'Zebra GX420d - ZPL', com_port='COM4', baud=9600)
    assert res['ok'] is True
    assert called['port'] == 'COM4'
    assert called['baud'] == 9600


def test_config_com4_en_json():
    from services.etiquetas_zebra_zpl_service import cargar_config_etiqueta_zebra, puerto_com_impresora_zebra

    cfg = cargar_config_etiqueta_zebra()
    assert float(cfg.get('ancho_mm') or 0) == 50.0
    assert float(cfg.get('alto_mm') or 0) == 30.0
    # Si el JSON local tiene COM4, el resolver lo expone
    com = puerto_com_impresora_zebra(cfg)
    assert com in ('', 'COM4') or com.startswith('COM')


def test_lenguaje_auto_tspl_con_com():
    from services.etiquetas_zebra_zpl_service import lenguaje_etiqueta

    assert lenguaje_etiqueta({'lenguaje': 'auto', 'impresora_com': 'COM4'}) == 'tspl'
    assert lenguaje_etiqueta({'lenguaje': 'zpl', 'impresora_com': 'COM4'}) == 'zpl'
    assert lenguaje_etiqueta({'lenguaje': 'auto', 'impresora_com': ''}) == 'zpl'


def test_generar_tspl_50x30():
    from services.etiquetas_zebra_zpl_service import generar_lote_etiquetas, generar_tspl_etiqueta

    cfg = {
        'ancho_mm': 50,
        'alto_mm': 30,
        'gap_mm': 2,
        'nombre_max_lineas': 2,
        'mostrar_codigo_texto': True,
        'mostrar_precio_lista': True,
        'mostrar_precio_mayoreo': False,
        'lenguaje': 'tspl',
        'impresora_com': 'COM4',
    }
    fila = {
        'nombre': 'Tornillo 1/4 prueba',
        'codigo': '7805201592032',
        'precio_clp': 1990,
        'precio_pos': 1990,
        'cantidad': 1,
    }
    one = generar_tspl_etiqueta(fila, cfg)
    assert 'SIZE 50 mm,30 mm' in one
    assert 'PRINT 1,1' in one
    assert '7805201592032' in one
    assert '^XA' not in one
    payload, lang = generar_lote_etiquetas([fila], cfg)
    assert lang == 'tspl'
    assert 'SIZE' in payload


def test_imprimir_filas_usa_raw_com_tspl(monkeypatch):
    from services import etiquetas_zebra_zpl_service as ez

    sent = {}

    def _fake_raw(data, port, *, baud=9600):
        sent['data'] = data.decode('ascii', errors='replace')
        sent['port'] = port
        sent['baud'] = baud
        return {'ok': True, 'metodo': 'com_serial', 'puerto': port, 'bytes': len(data)}

    monkeypatch.setattr('services.ticket_impresion_escpos._enviar_raw_com', _fake_raw)
    cfg = {
        'ancho_mm': 50,
        'alto_mm': 30,
        'gap_mm': 2,
        'lenguaje': 'tspl',
        'impresora_com': 'COM4',
        'impresora_baud': 9600,
        'mostrar_codigo_texto': True,
    }
    res = ez.imprimir_filas_etiqueta(
        [{'nombre': 'Test', 'codigo': '123', 'precio_clp': 1000, 'cantidad': 1}],
        cfg=cfg,
        impresora='COM4',
    )
    assert res['ok'] is True
    assert sent['port'] == 'COM4'
    assert 'SIZE' in sent['data']
    assert '^XA' not in sent['data']
