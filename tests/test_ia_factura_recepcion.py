"""IA factura en recepciones — smoke sin llamar a OpenAI."""
import io
import os

import pytest

from app import RecepcionCompra, _carpeta_docs_recepcion, _guardar_doc_recepcion


@pytest.mark.smoke
def test_ia_factura_analizar_sin_api_key(app_client, proveedor_test):
    prev = os.environ.pop('OPENAI_API_KEY', None)
    try:
        rec = RecepcionCompra(
            proveedor_id=proveedor_test.id,
            documento_tipo='Factura',
            documento_numero='TEST-IA-SIN-KEY',
            usuario_bodega='QA',
            estado='Pendiente',
        )
        from app import db

        db.session.add(rec)
        db.session.commit()
        r = app_client.post(f'/recepciones/{rec.id}/ia-factura/analizar')
        assert r.status_code == 503
        data = r.get_json()
        assert data.get('sin_api_key') is True
    finally:
        if prev is not None:
            os.environ['OPENAI_API_KEY'] = prev


@pytest.mark.smoke
def test_ia_factura_analizar_sin_documento(app_client, proveedor_test):
    os.environ['OPENAI_API_KEY'] = 'sk-test-no-llamar-openai'
    try:
        rec = RecepcionCompra(
            proveedor_id=proveedor_test.id,
            documento_tipo='Factura',
            documento_numero='TEST-IA-SIN-DOC',
            usuario_bodega='QA',
            estado='Pendiente',
        )
        from app import db

        db.session.add(rec)
        db.session.commit()
        r = app_client.post(f'/recepciones/{rec.id}/ia-factura/analizar')
        assert r.status_code == 400
        assert 'documento' in (r.get_json().get('message') or '').lower()
    finally:
        os.environ.pop('OPENAI_API_KEY', None)


@pytest.mark.smoke
def test_ia_factura_analizar_imagen_mock_openai(app_client, proveedor_test, monkeypatch):
    os.environ['OPENAI_API_KEY'] = 'sk-test-mock'
    rec = None
    try:
        rec = RecepcionCompra(
            proveedor_id=proveedor_test.id,
            documento_tipo='Factura',
            documento_numero='TEST-IA-MOCK',
            usuario_bodega='QA',
            estado='Pendiente',
        )
        from app import db

        db.session.add(rec)
        db.session.commit()

        class _FakeFile:
            filename = 'factura_test.png'

            def save(self, path):
                from PIL import Image

                im = Image.new('RGB', (80, 40), color=(255, 255, 255))
                im.save(path, format='PNG')

        _guardar_doc_recepcion(rec.id, _FakeFile())

        def _fake_extraer(data_urls, api_key):
            assert api_key == 'sk-test-mock'
            assert data_urls
            return [
                {
                    'codigo_proveedor': None,
                    'descripcion': 'Tornillo hexagonal 1/2',
                    'cantidad': 10,
                    'precio_unitario': 1990,
                },
                {
                    'codigo_proveedor': None,
                    'descripcion': 'Producto sin precio en doc',
                    'cantidad': 2,
                    'precio_unitario': None,
                },
            ]

        import app as app_mod

        monkeypatch.setattr(app_mod, '_openai_extraer_items_factura', _fake_extraer)

        r = app_client.post(f'/recepciones/{rec.id}/ia-factura/analizar')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert data.get('total', 0) >= 1
        assert data.get('modelo') == 'gpt-4o-mini'
        assert isinstance(data.get('items'), list)
    finally:
        os.environ.pop('OPENAI_API_KEY', None)
        if rec is not None:
            nom = None
            for fn in os.listdir(_carpeta_docs_recepcion()):
                if fn.startswith(f'recepcion_{rec.id}_'):
                    nom = fn
                    break
            if nom:
                try:
                    os.remove(os.path.join(_carpeta_docs_recepcion(), nom))
                except OSError:
                    pass
