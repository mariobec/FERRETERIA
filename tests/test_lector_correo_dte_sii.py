"""Filtro correos ruido SII — smoke."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_lector():
    path = ROOT / 'scripts' / 'lector_correo_dte.py'
    spec = importlib.util.spec_from_file_location('lector_correo_dte', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.smoke
def test_omitir_siidte_resultado_envio():
    lector = _load_lector()
    assert lector._es_correo_ruido_sii(
        'siidte@sii.cl',
        'Produccion - Resultado de Revision Envio 12110128202 - 8054120-1',
    )


@pytest.mark.smoke
def test_no_omitir_proveedor_chilemat():
    lector = _load_lector()
    assert not lector._es_correo_ruido_sii(
        'facturacion@chilemat.cl',
        'Factura Electronica 5005433',
    )


@pytest.mark.smoke
def test_omitir_asunto_resultado_envio_cualquier_remitente():
    lector = _load_lector()
    assert lector._es_correo_ruido_sii(
        'notificaciones@empresa.cl',
        'Produccion - Resultado de Revision Envio 12110128202 - 8054120-1',
    )


@pytest.mark.smoke
def test_filtrar_xml_factura_compra_ejemplo():
    lector = _load_lector()
    fx = ROOT / 'tests' / 'fixtures' / 'dte_compra_ejemplo.xml'
    data = fx.read_bytes()
    utiles, omitidos = lector._filtrar_xml_factura_compra([('f.xml', data)])
    assert omitidos == 0
    assert len(utiles) == 1


@pytest.mark.smoke
def test_filtrar_xml_ruido_respuesta():
    lector = _load_lector()
    basura = b'<?xml version="1.0"?><RespuestaDTE version="1.0"><Resultado>OK</Resultado></RespuestaDTE>'
    utiles, omitidos = lector._filtrar_xml_factura_compra([('r.xml', basura)])
    assert len(utiles) == 0
    assert omitidos == 1
