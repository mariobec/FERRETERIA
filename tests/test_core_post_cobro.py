"""Tests unitarios post-cobro (Fase 1.4) con puertos mock."""
from core.application.creditos.post_cobro_credito import PostCobroCreditoService
from core.application.ventas.post_cobro_saldo_favor import PostCobroSaldoFavorService


class _CreditoPortFake:
    def __init__(self):
        self.aplicados = []

    def normalizar_plan_cuotas(self, raw):
        return (raw or "").strip() if raw == "30_60_90" else ""

    def aplicar_cobro_credito(self, venta_id, plan_codigo):
        self.aplicados.append((venta_id, plan_codigo))


class _SaldoFavorPortFake:
    def __init__(self):
        self.debitos = []

    def aplicar_debito_cobro(self, venta_id, monto):
        self.debitos.append((venta_id, monto))


def test_post_cobro_credito_normaliza_y_aplica():
    port = _CreditoPortFake()
    svc = PostCobroCreditoService(port)
    assert svc.normalizar_plan_cuotas("30_60_90") == "30_60_90"
    assert svc.normalizar_plan_cuotas("invalido") == ""
    svc.aplicar_cobro_credito(42, "30_60_90")
    assert port.aplicados == [(42, "30_60_90")]


def test_post_cobro_saldo_favor_ignora_cero():
    port = _SaldoFavorPortFake()
    svc = PostCobroSaldoFavorService(port)
    svc.aplicar_uso_saldo_favor(1, 0)
    assert port.debitos == []
    svc.aplicar_uso_saldo_favor(1, 1500.0)
    assert port.debitos == [(1, 1500.0)]
