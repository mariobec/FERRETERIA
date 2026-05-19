"""Tests autorización descuento POS (tarjeta + PIN)."""
import pytest

from services.pos_autorizacion_descuento_service import (
    detalle_descuento_autorizacion_valida,
    generar_token_tarjeta,
    hash_token_tarjeta,
    normalizar_codigo_tarjeta,
    pin_valido_formato,
    producto_descuento_preautorizado_cubre,
    requiere_autorizacion_supervisor_pos,
    requiere_pin_para_descuento,
)


class _ProdStub:
    def __init__(self, preauth=False, max_pct=0.0):
        self.pos_descuento_preautorizado = preauth
        self.pos_descuento_preautorizado_pct = max_pct


@pytest.mark.smoke
def test_normalizar_codigo_tarjeta():
    t = generar_token_tarjeta()
    assert t.startswith('LHX-SUP-')
    assert normalizar_codigo_tarjeta(t) == t
    payload = t.replace('LHX-SUP-', '')
    assert normalizar_codigo_tarjeta(payload) == t


@pytest.mark.smoke
def test_todo_descuento_requiere_supervisor_salvo_preauth():
    assert requiere_autorizacion_supervisor_pos(5.0, None, False) is True
    assert requiere_autorizacion_supervisor_pos(5.0, None, True) is True
    assert requiere_autorizacion_supervisor_pos(0.0, None, False) is False
    prod = _ProdStub(preauth=True, max_pct=10.0)
    assert producto_descuento_preautorizado_cubre(prod, 8.0) is True
    assert producto_descuento_preautorizado_cubre(prod, 15.0) is False
    assert requiere_autorizacion_supervisor_pos(8.0, prod, False) is False
    assert requiere_autorizacion_supervisor_pos(15.0, prod, False) is True


@pytest.mark.smoke
def test_umbral_pin():
    assert requiere_pin_para_descuento(21, 20) is True
    assert requiere_pin_para_descuento(20, 20) is False
    assert pin_valido_formato('1234') is True
    assert pin_valido_formato('123') is False


@pytest.mark.smoke
def test_actualizar_item_con_tarjeta_y_pin(app_ctx, caja_abierta, productos_con_stock, cliente_final):
    import app as m
    from tests.conftest import crear_venta_pendiente  # noqa: PLC0415

    m._asegurar_columnas_usuario_pin_autorizacion()
    m._asegurar_tabla_usuario_tarjeta_autorizacion()
    m._asegurar_columnas_detalle_ventas_legacy()

    sup = None
    for u in m.Usuario.query.all():
        if m.usuario_esta_activo(u) and m.usuario_obj_tiene_permiso(u, 'autorizar_descuento_pos'):
            sup = u
            break
    if not sup:
        pytest.skip('Sin supervisor con permiso autorizar_descuento_pos en BD QA')
    sup.set_pin_autorizacion('4321')
    token = generar_token_tarjeta()
    m.db.session.add(
        m.UsuarioTarjetaAutorizacion(
            usuario_id=sup.id,
            token_hash=hash_token_tarjeta(token),
            etiqueta='QA',
            activo=True,
        )
    )
    m.db.session.commit()

    prod = productos_con_stock[0]
    venta, dets = crear_venta_pendiente([(prod, 1)], caja_abierta, cliente_final)
    venta.estado = 'Abierta'
    m.db.session.commit()
    det = dets[0]
    assert det is not None

    class _Form:
        def get(self, k, default=None):
            data = {
                'supervisor_tarjeta': token,
                'supervisor_pin': '4321',
            }
            return data.get(k, default)

    sup_ok, metodo, err = m._validar_autorizacion_descuento_pos(25.0, _Form())
    assert err is None
    assert sup_ok.id == sup.id
    assert metodo == 'tarjeta_pin'

    det.descuento = 25.0
    m._registrar_autorizacion_descuento_en_linea(det, sup_ok, metodo, 0.0, 25.0)
    m.db.session.commit()

    m.db.session.expire_all()
    det2 = m.db.session.get(m.DetalleVenta, det.id)
    assert float(det2.descuento or 0) == 25.0
    assert det2.descuento_autorizado_por_id == sup.id
    assert det2.descuento_autorizado_metodo == 'tarjeta_pin'
