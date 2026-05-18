"""
Factories de casos de uso (wiring Flask ↔ core).

Centraliza imports para no inflar app.py.
"""
from __future__ import annotations

from typing import Callable, Optional

from core.application.creditos.post_cobro_credito import PostCobroCreditoService
from core.application.inventario.stock_cobro import DescontarStockCobroService
from core.application.ventas import FinalizarVentaUseCase, ProcesarCobroUseCase
from core.application.ventas.post_cobro_saldo_favor import PostCobroSaldoFavorService
from core.infrastructure.adapters.cobro_stock_adapter import AppCobroStockAdapter
from core.infrastructure.adapters.post_cobro_credito_adapter import AppPostCobroCreditoAdapter
from core.infrastructure.adapters.post_cobro_saldo_favor_adapter import AppPostCobroSaldoFavorAdapter
from core.infrastructure.adapters.stock_tienda_validator import AppStockTiendaValidator
from core.infrastructure.persistence.venta_repository import sqlalchemy_venta_repository_from_app


def build_finalizar_venta_use_case(
    *,
    transaccion_critica: Optional[Callable] = None,
    validar_stock: bool = True,
) -> FinalizarVentaUseCase:
    return FinalizarVentaUseCase(
        sqlalchemy_venta_repository_from_app(),
        stock_validator=AppStockTiendaValidator() if validar_stock else None,
        transaccion_critica=transaccion_critica,
    )


def build_descontar_stock_cobro_service() -> DescontarStockCobroService:
    adapter = AppCobroStockAdapter()
    return DescontarStockCobroService(preparar=adapter, aplicar=adapter)


def build_post_cobro_credito_service() -> PostCobroCreditoService:
    return PostCobroCreditoService(AppPostCobroCreditoAdapter())


def build_post_cobro_saldo_favor_service() -> PostCobroSaldoFavorService:
    return PostCobroSaldoFavorService(AppPostCobroSaldoFavorAdapter())


def build_procesar_cobro_use_case(
    *,
    transaccion_critica: Optional[Callable] = None,
    validar_stock: bool = False,
    obtener_caja_id_abierta: Optional[Callable[[], Optional[int]]] = None,
) -> ProcesarCobroUseCase:
    """validar_stock=False por defecto: el handler de caja ya validó antes del savepoint."""
    return ProcesarCobroUseCase(
        sqlalchemy_venta_repository_from_app(),
        stock_validator=AppStockTiendaValidator() if validar_stock else None,
        transaccion_critica=transaccion_critica,
        obtener_caja_id_abierta=obtener_caja_id_abierta,
    )
