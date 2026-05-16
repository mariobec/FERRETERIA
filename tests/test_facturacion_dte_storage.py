"""Persistencia local XML DTE firmado."""
import os

from services import facturacion_dte_storage as st


def test_persistir_y_buscar_xml(tmp_path):
    root = str(tmp_path)
    path = st.persistir_xml_dte_firmado(root, 'certificacion', 42, 7, 39, b'<DTE/>')
    assert os.path.isfile(path)
    assert 'V42_T39_F7.xml' in path
    found = st.buscar_xml_dte_por_venta(root, 42)
    assert found == path


def test_buscar_prefiere_mtime(tmp_path):
    root = str(tmp_path)
    p1 = st.persistir_xml_dte_firmado(root, 'certificacion', 1, 1, 39, b'<a/>')
    p2 = st.persistir_xml_dte_firmado(root, 'produccion', 1, 2, 39, b'<b/>')
    found = st.buscar_xml_dte_por_venta(root, 1)
    assert found in (p1, p2)
    m1 = os.path.getmtime(p1)
    m2 = os.path.getmtime(p2)
    assert found == (p2 if m2 >= m1 else p1)
