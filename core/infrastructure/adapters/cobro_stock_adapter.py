"""
Adaptador: preparación y aplicación de stock al cobro (delega en app.py / stock_service).
"""
from __future__ import annotations

from core.application.inventario.stock_cobro import LineaStockCobro


class AppCobroStockAdapter:
    """Implementación usando helpers del monolito (misma lógica que procesar_cobro_caja)."""

    def preparar_lineas(self, venta_id: int) -> list[LineaStockCobro]:
        import app as app_module
        from sqlalchemy.orm import joinedload

        venta = (
            app_module.Venta.query.options(joinedload(app_module.Venta.detalles))
            .filter_by(id=venta_id)
            .first()
        )
        if venta is None:
            raise ValueError(f"Venta {venta_id} no encontrada.")

        lineas_stock: list[LineaStockCobro] = []
        agrupado_tienda = app_module._stock_service.consumo_tienda_agrupado_por_producto(venta)
        for pid, info in agrupado_tienda.items():
            if info.get("invalido"):
                raise ValueError(f"Conversión inválida para {info.get('nombre') or pid}.")
            need = int(info.get("consumo") or 0)
            if need <= 0:
                continue
            producto = app_module.Producto.query.get(pid)
            if not producto:
                raise ValueError("Producto no encontrado en línea de venta.")
            disp = app_module.stock_disponible_venta_tienda(producto)
            if disp < need:
                raise ValueError(
                    f"Stock insuficiente para {producto.nombre} "
                    f"(disponible tienda: {disp}, requerido: {need})."
                )

        for d in list(venta.detalles or []):
            if getattr(d, 'a_pedido', False):
                continue
            producto = app_module.Producto.query.get(d.id_producto)
            if not producto:
                raise ValueError(f"Producto no encontrado en línea #{d.id}.")
            factor_venta_stock = app_module._factor_venta_a_stock(producto)
            consumo_stock = int(round((d.cantidad or 0) * factor_venta_stock))
            if consumo_stock <= 0:
                raise ValueError(f"Conversión inválida para {producto.nombre}.")
            ya_bod = app_module._venta_consumo_ya_despachado_bodega(venta, d.id)
            pr_line = (app_module._detalle_punto_retiro_efectivo(d, venta) or "").strip()
            if pr_line == "Bodega":
                consumo_tienda = 0
                necesita_bod = max(0, consumo_stock - ya_bod)
                if necesita_bod > 0:
                    disp_b = app_module.stock_disponible_bodega(producto)
                    if disp_b < necesita_bod:
                        raise ValueError(
                            f"Stock insuficiente en bodega para {producto.nombre} "
                            f"(hay {disp_b}, requiere {necesita_bod})."
                        )
            else:
                consumo_tienda = max(0, consumo_stock - ya_bod)
            lineas_stock.append(
                LineaStockCobro(
                    detalle_id=d.id,
                    producto_id=producto.id,
                    cantidad_venta=int(d.cantidad or 0),
                    consumo_stock=consumo_stock,
                    consumo_tienda=consumo_tienda,
                )
            )
        return lineas_stock

    def aplicar_descontos(
        self,
        venta_id: int,
        lineas: list[LineaStockCobro],
        metodo_pago: str,
        usuario: str | None,
    ) -> None:
        import app as app_module

        for linea in lineas:
            producto = app_module.Producto.query.get(linea.producto_id)
            if not producto:
                raise ValueError(f"Producto no encontrado en línea #{linea.detalle_id}.")
            consumo_tienda = int(linea.consumo_tienda or 0)
            if consumo_tienda <= 0:
                continue
            err_st = app_module.descontar_stock_venta_tienda(producto, consumo_tienda)
            if err_st:
                raise ValueError(f"{producto.nombre}: {err_st}")
            app_module.registrar_movimiento_kardex(
                producto.id,
                "SALIDA",
                consumo_tienda,
                f"Cobro vale/venta #{venta_id} ({metodo_pago})"
                f" ({linea.cantidad_venta} {producto.unidad_venta_final} -> {consumo_tienda} stock tienda)",
                usuario=usuario,
                id_almacen=app_module.id_almacen_tienda() or 1,
                referencia_tipo="venta",
                referencia_id=venta_id,
                stock_saldo=None,
            )
