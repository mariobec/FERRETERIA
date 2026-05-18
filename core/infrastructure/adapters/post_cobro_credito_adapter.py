"""
Adaptador post-cobro crédito (cuotas + saldo_deudor).
"""
from __future__ import annotations


class AppPostCobroCreditoAdapter:
    def normalizar_plan_cuotas(self, raw: str | None) -> str:
        import app as app_module

        return app_module._plan_cuotas_credito_valido(raw)

    def aplicar_cobro_credito(self, venta_id: int, plan_codigo: str | None) -> None:
        import app as app_module
        from sqlalchemy.orm import joinedload

        venta = (
            app_module.Venta.query.options(joinedload(app_module.Venta.cliente))
            .filter_by(id=venta_id)
            .first()
        )
        if venta is None:
            raise ValueError(f"Venta {venta_id} no encontrada.")

        app_module.VentaCuotaCredito.query.filter_by(venta_id=venta.id).delete(
            synchronize_session=False
        )
        plan = (plan_codigo or "").strip()
        if plan:
            app_module._registrar_cuotas_credito_venta(venta, plan, venta.fecha)
        if venta.cliente:
            venta.cliente.saldo_deudor = (venta.cliente.saldo_deudor or 0) + float(
                venta.monto_total or 0
            )
