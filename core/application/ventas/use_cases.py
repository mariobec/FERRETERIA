"""
Casos de uso Venta + Cobro.

Fase 1.2: orquestación con dominio + repositorio. La persistencia de efectos
secundarios (stock, kardex, cuotas crédito, FE, auditoría) sigue en app.py hasta
redirigir llamadas de forma explícita.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from core.application.ventas.commands import FinalizarVentaCommand, ProcesarCobroCommand
from core.domain.venta import Venta
from core.domain.venta.exceptions import VentaDomainError
from core.infrastructure.persistence.venta_repository import VentaRepository


class StockTiendaValidator(Protocol):
    """Puerto: validar disponibilidad en tienda antes de finalizar/cobrar."""

    def faltantes_para_venta(self, venta_id: int) -> list[str]:
        """Mensajes humanos de productos sin stock (vacío = OK)."""
        ...


@dataclass
class FinalizarVentaResult:
    venta_id: int
    estado: str
    prioridad: int


@dataclass
class ProcesarCobroResult:
    venta_id: int
    estado: str
    metodo_pago: str
    requiere_post_cobro_stock: bool = True
    requiere_post_cobro_fe: bool = False


class FinalizarVentaUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        stock_validator: Optional[StockTiendaValidator] = None,
        *,
        transaccion_critica: Optional[Callable] = None,
    ) -> None:
        self._repo = venta_repo
        self._stock = stock_validator
        self._tx = transaccion_critica

    def execute(self, cmd: FinalizarVentaCommand) -> FinalizarVentaResult:
        venta = self._repo.get_by_id(cmd.venta_id)
        if venta is None:
            raise VentaDomainError(f"Venta {cmd.venta_id} no encontrada.")

        if self._stock is not None:
            faltantes = self._stock.faltantes_para_venta(cmd.venta_id)
            if faltantes:
                raise VentaDomainError(
                    "No se puede emitir el vale: falta stock en tienda para "
                    + "; ".join(faltantes[:3])
                )

        def _cuerpo() -> FinalizarVentaResult:
            venta.finalizar(
                cliente_id=cmd.cliente_id,
                punto_retiro=cmd.punto_retiro,
                prioridad_cola=cmd.prioridad_cola,
                usuario_vendedor=cmd.usuario_vendedor,
                retiro_por_linea=cmd.retiro_por_linea,
            )
            self._repo.save(venta)
            return FinalizarVentaResult(
                venta_id=venta.id or cmd.venta_id,
                estado=venta.estado.value,
                prioridad=venta.prioridad or cmd.prioridad_cola,
            )

        if self._tx is not None:
            with self._tx():
                return _cuerpo()
        return _cuerpo()


class ProcesarCobroUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        stock_validator: Optional[StockTiendaValidator] = None,
        *,
        transaccion_critica: Optional[Callable] = None,
        obtener_caja_id_abierta: Optional[Callable[[], Optional[int]]] = None,
    ) -> None:
        self._repo = venta_repo
        self._stock = stock_validator
        self._tx = transaccion_critica
        self._caja_abierta = obtener_caja_id_abierta

    def execute(self, cmd: ProcesarCobroCommand) -> ProcesarCobroResult:
        venta = self._repo.get_by_id(cmd.venta_id)
        if venta is None:
            raise VentaDomainError(f"Venta {cmd.venta_id} no encontrada.")

        caja_abierta_id = cmd.caja_id
        if self._caja_abierta is not None:
            cid = self._caja_abierta()
            if cid is not None:
                caja_abierta_id = cid

        venta.puede_registrar_cobro(caja_id_abierta=caja_abierta_id)

        if self._stock is not None:
            faltantes = self._stock.faltantes_para_venta(cmd.venta_id)
            if faltantes:
                raise VentaDomainError(
                    "No se puede cobrar el vale por stock insuficiente en tienda: "
                    + "; ".join(faltantes[:3])
                )

        def _cuerpo() -> ProcesarCobroResult:
            venta.registrar_cobro(
                metodo=cmd.metodo_pago,
                tipo_documento=cmd.tipo_documento,
                monto_recibido=cmd.monto_recibido,
                saldo_favor_usado=cmd.saldo_favor_usado,
                credito_plan_codigo=cmd.credito_plan_codigo,
                caja_id=cmd.caja_id,
            )
            self._repo.save(venta)
            es_pagado = venta.estado.value == "Pagado"
            es_credito = (cmd.metodo_pago or "").strip() == "Credito"
            return ProcesarCobroResult(
                venta_id=venta.id or cmd.venta_id,
                estado=venta.estado.value,
                metodo_pago=cmd.metodo_pago,
                requiere_post_cobro_stock=True,
                requiere_post_cobro_fe=es_pagado and not es_credito,
            )

        if self._tx is not None:
            with self._tx():
                return _cuerpo()
        return _cuerpo()
