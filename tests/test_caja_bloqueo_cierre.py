"""Cola caja vs bloqueo cierre de turno."""
import pytest

from app import (
    _build_bloqueo_cierre_filas,
    _documentos_bloquean_cierre_caja,
    _venta_es_borrador_pos_vacio,
    app as flask_app,
    db,
)
from app import Venta
from tests.conftest import QA_USER, crear_venta_pendiente


@pytest.mark.smoke
def test_pendiente_metodo_vacio_bloquea_y_cuenta_en_cola(app_ctx, productos_con_stock, caja_abierta, cliente_final):
    """Legacy metodo_pago='' debe bloquear cierre y verse en cola (mismo criterio)."""
    p = productos_con_stock[0]
    venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
    venta.metodo_pago = ''
    db.session.commit()

    vales, tickets = _documentos_bloquean_cierre_caja(caja_abierta)
    ids = {v.id for v in vales + tickets}
    assert venta.id in ids

    with flask_app.test_request_context():
        from app import _build_caja_pendientes_context

        ctx = _build_caja_pendientes_context()
    cola_ids = {v.id for v in ctx['cola_combined']}
    assert venta.id in cola_ids


@pytest.mark.smoke
def test_borrador_abierto_vacio_no_bloquea_cierre(app_ctx, caja_abierta, cliente_final):
    """Borrador POS sin líneas no debe impedir cerrar caja."""
    v = Venta(
        fecha=__import__('datetime').datetime.now(),
        monto_total=0,
        usuario=QA_USER,
        estado='Abierta',
        caja_id=caja_abierta.id,
        cliente_id=cliente_final.id,
        punto_retiro='Tienda',
    )
    db.session.add(v)
    db.session.commit()

    assert _venta_es_borrador_pos_vacio(v) is True
    _vales, tickets = _documentos_bloquean_cierre_caja(caja_abierta)
    assert v.id not in {t.id for t in tickets}


@pytest.mark.smoke
def test_bloqueo_fuera_cola_detectado(app_ctx, productos_con_stock, caja_abierta, cliente_final):
    """Si bloquea pero no está en cola_combined, queda marcado en fuera_cola."""
    p = productos_con_stock[0]
    venta, _ = crear_venta_pendiente([(p, 1)], caja_abierta, cliente_final)
    venta.metodo_pago = ''
    db.session.commit()

    filas, fuera = _build_bloqueo_cierre_filas(caja_abierta, cola_combined=[])
    assert any(f['id'] == venta.id for f in filas)
    assert any(f['id'] == venta.id for f in fuera)
