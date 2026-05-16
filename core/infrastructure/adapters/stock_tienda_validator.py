"""
Validador de stock en tienda (puerto StockTiendaValidator).

Delega en la lógica existente de app.py / stock_service.
"""
from __future__ import annotations


class AppStockTiendaValidator:
    """Implementación que usa `_venta_validar_stock_tienda` del monolito."""

    def faltantes_para_venta(self, venta_id: int) -> list[str]:
        import app as app_module

        venta = app_module.Venta.query.get(venta_id)
        if venta is None:
            return [f"Venta {venta_id} no encontrada."]
        return list(app_module._venta_validar_stock_tienda(venta) or [])
