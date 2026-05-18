"""
Adaptador débito de saldo a favor al cobrar.
"""
from __future__ import annotations


class AppPostCobroSaldoFavorAdapter:
    def aplicar_debito_cobro(self, venta_id: int, monto: float) -> None:
        import app as app_module

        venta = app_module.Venta.query.filter_by(id=venta_id).first()
        if venta is None:
            raise ValueError(f"Venta {venta_id} no encontrada.")
        if not venta.cliente_id:
            raise ValueError("Para usar saldo a favor el vale debe tener cliente identificado.")
        app_module._aplicar_mov_saldo_favor(
            venta.cliente_id,
            None,
            "DEBITO",
            monto,
            f"Uso en venta #{venta.id}",
        )
