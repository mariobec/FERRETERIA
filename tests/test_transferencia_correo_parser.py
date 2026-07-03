"""Parser correo transferencias bancarias."""
from services.transferencia_correo_parser import (
    es_correo_transferencia_bancaria,
    parsear_correo_transferencia,
    sugerir_venta_id,
)


class _VentaFake:
    def __init__(self, vid, monto, ref=None):
        self.id = vid
        self.monto_total = monto
        self.transferencia_referencia = ref


def test_detecta_correo_bci():
    cuerpo = (
        'Estimado cliente, se ha recibido una transferencia por $ 24.990 '
        'en su cuenta. N° operación: 8834521. RUT ordenante 12.345.678-9.'
    )
    ok, _ = es_correo_transferencia_bancaria('avisos@bci.cl', 'Aviso transferencia', cuerpo)
    assert ok is True
    p = parsear_correo_transferencia(remitente='avisos@bci.cl', asunto='Aviso transferencia', cuerpo=cuerpo)
    assert p.es_transferencia
    assert p.monto == 24990
    assert p.referencia == '8834521'


def test_excluye_dte_sii():
    ok, motivo = es_correo_transferencia_bancaria(
        'siidte@sii.cl', 'Resultado de revision envio DTE', 'xml factura'
    )
    assert ok is False
    assert motivo in ('excluido_sii', 'excluido_dte_sii')


def test_sugerir_venta_por_monto():
    ventas = [_VentaFake(1, 2490), _VentaFake(2, 9990)]
    assert sugerir_venta_id(monto=2490, referencia=None, ventas=ventas) == 1


def test_sugerir_venta_por_referencia():
    ventas = [_VentaFake(1, 2490, 'OP-123'), _VentaFake(2, 2490)]
    assert sugerir_venta_id(monto=2490, referencia='OP-123', ventas=ventas) == 1


def test_bancoestado_html_plano_monto_y_transaccion():
    cuerpo = (
        'Mensaje para JUAN PEREZ GONZALEZ\n'
        'Fecha y hora 06/06/2026 12:44:43\n'
        'Monto $ 45.990\n'
        'N° transaccion7039771\n'
        'RUT 12.345.678-9'
    )
    p = parsear_correo_transferencia(
        remitente='"BancoEstado" <noreply@correo.bancoestado.cl>',
        asunto='Aviso de Transferencia de Fondos',
        cuerpo=cuerpo,
    )
    assert p.es_transferencia
    assert p.monto == 45990
    assert p.referencia == '7039771'


def test_excluye_bancoestado_marketing():
    cuerpo = (
        'Estimado(a): Luis Rivera\n\n'
        'javascript :;\n\n'
        'Opera desde tu\n\n'
        'App BancoEstado Empresas\n\n'
        'y Banca en Linea, con herramientas'
    )
    ok, motivo = es_correo_transferencia_bancaria(
        '"BancoEstado" <mensajeria@correobancoestado.cl>',
        'Tu negocio siempre en control con BancoEstado',
        cuerpo,
    )
    assert ok is False
    assert motivo in ('remitente_marketing', 'asunto_marketing', 'cuerpo_marketing', 'bancoestado_promocional', 'no_coincide')
    p = parsear_correo_transferencia(
        remitente='"BancoEstado" <mensajeria@correobancoestado.cl>',
        asunto='Tu negocio siempre en control con BancoEstado',
        cuerpo=cuerpo,
    )
    assert not p.es_transferencia
