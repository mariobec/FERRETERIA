"""Parser XML DTE compra — smoke."""
from pathlib import Path

import pytest

from services.parser_xml_compra import (
    ParserXmlCompraError,
    lineas_a_payload_detalle_recepcion,
    parsear_archivo_dte_compra,
    parsear_xml_dte_compra,
    _ejemplo_xml_compra_minimo,
)


FIXTURE = Path(__file__).resolve().parents[0] / 'fixtures' / 'dte_compra_ejemplo.xml'


@pytest.mark.smoke
def test_parsear_fixture_dte_compra():
    dte = parsear_archivo_dte_compra(FIXTURE)
    assert dte.cabecera.folio == 5005433
    assert dte.cabecera.tipo_dte == 33
    assert dte.cabecera.rut_emisor == '96516560-5'
    assert dte.cabecera.rut_receptor == '76123456-7'
    assert len(dte.lineas) == 2
    assert dte.lineas[0].codigo_item == 'INT-110109'
    assert dte.lineas[0].nombre == 'ALAMBRE GALV N18 1KG'
    assert dte.lineas[0].cantidad == 10.0
    assert dte.lineas[0].precio_unitario == 1498.0
    assert dte.lineas[0].monto_linea == 14980.0


@pytest.mark.smoke
def test_payload_detalle_recepcion():
    dte = parsear_xml_dte_compra(_ejemplo_xml_compra_minimo())
    filas = lineas_a_payload_detalle_recepcion(dte)
    assert len(filas) == 2
    assert filas[0]['cantidad_documento'] == 10
    assert filas[0]['costo_unitario'] == 1498.0
    assert filas[0]['codigo_factura'] == 'INT-110109'


@pytest.mark.smoke
def test_procesar_xml_dte():
    from services.parser_xml_compra import procesar_xml_dte

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / 'factura.xml'
        xml_path.write_text(FIXTURE.read_text(encoding='utf-8'), encoding='utf-8')
        res = procesar_xml_dte(xml_path, guardar_json=True, carpeta_json=tmp)
        assert res['ok'] is True
        assert res['total_lineas'] == 2
        assert res['cabecera']['folio'] == 5005433
        assert len(res['detalle_recepcion']) == 2
        assert Path(res['archivo_json']).is_file()


@pytest.mark.smoke
def test_xml_invalido():
    with pytest.raises(ParserXmlCompraError):
        parsear_xml_dte_compra('<root><sin-dte/></root>')
