"""
Repositorio Venta: puerto + implementación SQLAlchemy (modelos legacy en app.py).

El mapper traduce ORM ↔ entidades de dominio sin exponer Flask a domain/.
"""
from __future__ import annotations

from typing import Optional, Protocol

from core.domain.venta import DetalleVenta, EstadoVenta, Venta
from core.domain.venta.value_objects import Money


class VentaRepository(Protocol):
    def get_by_id(self, venta_id: int, *, with_detalles: bool = True) -> Optional[Venta]:
        ...

    def save(self, venta: Venta) -> Venta:
        ...


def _estado_from_orm(raw: str | None) -> EstadoVenta:
    s = (raw or EstadoVenta.PENDIENTE.value).strip()
    try:
        return EstadoVenta(s)
    except ValueError:
        return EstadoVenta.PENDIENTE


def _detalle_from_orm(row) -> DetalleVenta:
    return DetalleVenta(
        id=row.id,
        producto_id=row.id_producto,
        cantidad=int(row.cantidad or 0),
        precio_unitario=float(row.precio_unitario or 0),
        descuento_pct=float(row.descuento or 0),
        punto_retiro_linea=getattr(row, "punto_retiro_linea", None),
        cantidad_entregada_retiro_bodega=int(getattr(row, "cantidad_entregada_retiro_bodega", 0) or 0),
    )


def venta_from_orm(model) -> Venta:
    detalles = [_detalle_from_orm(d) for d in (model.detalles or [])]
    v = Venta(
        id=model.id,
        estado=_estado_from_orm(model.estado),
        detalles=detalles,
        monto_total=Money.from_float(model.monto_total),
        neto=Money.from_float(model.neto),
        iva=Money.from_float(model.iva),
        cliente_id=model.cliente_id,
        caja_id=model.caja_id,
        usuario=model.usuario,
        prioridad=model.prioridad,
        punto_retiro=model.punto_retiro,
        metodo_pago=model.metodo_pago,
        tipo_documento=(model.tipo_documento or "Boleta"),
        monto_recibido=model.monto_recibido,
        vuelto=model.vuelto,
        saldo_favor_usado=float(model.saldo_favor_usado or 0),
        credito_plan_codigo=getattr(model, "credito_plan_codigo", None),
        motivo_anulacion=getattr(model, "motivo_anulacion", None),
    )
    return v


def apply_venta_to_orm(domain: Venta, model) -> None:
    model.estado = domain.estado.value
    model.monto_total = domain.monto_total.to_float()
    model.neto = domain.neto.to_float()
    model.iva = domain.iva.to_float()
    model.cliente_id = domain.cliente_id
    model.caja_id = domain.caja_id
    model.usuario = domain.usuario
    model.prioridad = domain.prioridad
    model.punto_retiro = domain.punto_retiro
    model.metodo_pago = domain.metodo_pago
    model.tipo_documento = domain.tipo_documento
    model.monto_recibido = domain.monto_recibido
    model.vuelto = domain.vuelto
    model.saldo_favor_usado = domain.saldo_favor_usado
    if hasattr(model, "credito_plan_codigo"):
        model.credito_plan_codigo = domain.credito_plan_codigo
    if domain.motivo_anulacion is not None and hasattr(model, "motivo_anulacion"):
        model.motivo_anulacion = domain.motivo_anulacion


class SqlAlchemyVentaRepository:
    """Implementación contra modelos `Venta` / `DetalleVenta` de app.py."""

    def __init__(self, session, venta_model, detalle_model) -> None:
        self._session = session
        self._Venta = venta_model
        self._DetalleVenta = detalle_model

    def get_by_id(self, venta_id: int, *, with_detalles: bool = True) -> Optional[Venta]:
        q = self._session.query(self._Venta)
        if with_detalles:
            from sqlalchemy.orm import joinedload

            q = q.options(joinedload(self._Venta.detalles))
        row = q.filter(self._Venta.id == venta_id).first()
        if row is None:
            return None
        return venta_from_orm(row)

    def save(self, venta: Venta) -> Venta:
        if venta.id is None:
            raise ValueError("SqlAlchemyVentaRepository.save requiere venta.id (persistencia nueva vía app.py).")
        model = self._session.query(self._Venta).filter(self._Venta.id == venta.id).first()
        if model is None:
            raise ValueError(f"Venta ORM id={venta.id} no encontrada.")
        apply_venta_to_orm(venta, model)
        for d_dom in venta.detalles:
            if d_dom.id is None:
                continue
            d_orm = next((x for x in (model.detalles or []) if x.id == d_dom.id), None)
            if d_orm is None:
                continue
            d_orm.cantidad = d_dom.cantidad
            d_orm.precio_unitario = d_dom.precio_unitario
            d_orm.descuento = d_dom.descuento_pct
            if hasattr(d_orm, "punto_retiro_linea"):
                d_orm.punto_retiro_linea = d_dom.punto_retiro_linea
        self._session.flush()
        return venta_from_orm(model)


def sqlalchemy_venta_repository_from_app() -> SqlAlchemyVentaRepository:
    """Factory para wiring desde Flask (app.py) cuando se redirijan rutas."""
    import app as app_module

    return SqlAlchemyVentaRepository(
        app_module.db.session,
        app_module.Venta,
        app_module.DetalleVenta,
    )
