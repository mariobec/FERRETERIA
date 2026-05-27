"""Cross-sell: reglas JSON + producto_relacion (sin romper CAS-V07)."""
import pytest


@pytest.mark.smoke
def test_cross_sell_merge_prioriza_reglas_json(app_ctx):
    from app import _pos_cross_sell_merge_sugerencias

    rule = {
        'rule_id': 'obra_arena',
        'titulo': '¿Completar obra?',
        'mensaje': 'Con cemento suele faltar arena.',
        'items': [{'id': 1, 'nombre': 'Arena', 'precio': 1000, 'codigo': 'A1'}],
    }
    rel = {
        'rule_id': 'relaciones_catalogo',
        'titulo': 'Complementos',
        'mensaje': 'Chilemat',
        'items': [{'id': 2, 'nombre': 'Pegamento', 'precio': 2000, 'codigo': 'P1'}],
    }
    merged = _pos_cross_sell_merge_sugerencias(rule, rel)
    assert merged is not None
    assert 'obra' in (merged.get('titulo') or '').lower() or 'completar' in (merged.get('titulo') or '').lower()
    ids = {it['id'] for it in merged.get('items') or []}
    assert 1 in ids and 2 in ids


@pytest.mark.smoke
def test_upsert_relacion_idempotente(app_ctx):
    from app import Producto, ProductoRelacion, db
    from services.producto_relacion_service import upsert_relacion

    pa = Producto(
        nombre='TEST-REL-A',
        codigo_barra='TEST-REL-A',
        precio_venta=100,
        stock=5,
        activo=True,
    )
    pb = Producto(
        nombre='TEST-REL-B',
        codigo_barra='TEST-REL-B',
        precio_venta=200,
        stock=3,
        activo=True,
    )
    db.session.add(pa)
    db.session.add(pb)
    db.session.commit()
    try:
        assert upsert_relacion(pa.id, pb.id, tipo='co_comprado', fuente='historico_sd', peso=0.8)
        assert upsert_relacion(pa.id, pb.id, tipo='co_comprado', fuente='historico_sd', peso=0.8)
        n = ProductoRelacion.query.filter_by(
            producto_id=pa.id, relacionado_id=pb.id, fuente='historico_sd'
        ).count()
        assert n == 1
    finally:
        ProductoRelacion.query.filter(
            ProductoRelacion.producto_id.in_([pa.id, pb.id])
        ).delete(synchronize_session=False)
        db.session.delete(pa)
        db.session.delete(pb)
        db.session.commit()


@pytest.mark.smoke
def test_sugerencias_carrito_excluye_items_en_carrito(app_ctx):
    from app import Producto, db
    from services.producto_relacion_service import sugerencias_para_carrito, upsert_relacion

    pa = Producto(nombre='TEST-SUG-A', codigo_barra='TEST-SUG-A', precio_venta=100, stock=2, activo=True)
    pb = Producto(nombre='TEST-SUG-B', codigo_barra='TEST-SUG-B', precio_venta=150, stock=4, activo=True)
    db.session.add(pa)
    db.session.add(pb)
    db.session.commit()
    try:
        upsert_relacion(pa.id, pb.id, fuente='historico_sd', peso=1.0)
        items = sugerencias_para_carrito([pa.id], limite=5)
        assert all(it['id'] != pa.id for it in items)
        if items:
            assert items[0]['id'] == pb.id
    finally:
        from app import ProductoRelacion

        ProductoRelacion.query.filter(
            ProductoRelacion.producto_id.in_([pa.id, pb.id])
        ).delete(synchronize_session=False)
        db.session.delete(pa)
        db.session.delete(pb)
        db.session.commit()
