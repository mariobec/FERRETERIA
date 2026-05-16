"""
Agregado Venta (vale POS) y entidad DetalleVenta.

Réplica las reglas de negocio documentadas en app.py (finalizar_venta, procesar_cobro_caja)
sin dependencias de framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.domain.venta.exceptions import (
    CobroNoPermitidoError,
    EstadoVentaInvalidoError,
    PuntoRetiroInvalidoError,
    VentaSinLineasError,
    VentaTotalInvalidoError,
)
from core.domain.venta.value_objects import (
    EstadoVenta,
    MetodoPago,
    Money,
    PuntoRetiro,
    TipoDocumento,
)


def _linea_subtotal_bruto_clp(
    cantidad: int,
    precio_unitario: float,
    descuento_pct: float,
) -> int:
    """Misma fórmula que `_ticket_linea_subtotal_clp` en app.py."""
    cant = float(cantidad or 0)
    pu = float(precio_unitario or 0)
    desc = float(descuento_pct or 0)
    return int(round(max(0.0, cant * pu * (1.0 - desc / 100.0))))


@dataclass
class DetalleVenta:
    """Línea de venta (unidad de catálogo en el carrito / vale)."""

    producto_id: int
    cantidad: int
    precio_unitario: float
    descuento_pct: float = 0.0
    id: Optional[int] = None
    punto_retiro_linea: Optional[str] = None
    cantidad_entregada_retiro_bodega: int = 0

    def __post_init__(self) -> None:
        if self.cantidad < 1:
            raise ValueError("La cantidad de la línea debe ser al menos 1.")
        if self.precio_unitario < 0:
            raise ValueError("El precio unitario no puede ser negativo.")

    def subtotal_bruto(self) -> Money:
        return Money.from_float(_linea_subtotal_bruto_clp(self.cantidad, self.precio_unitario, self.descuento_pct))

    def actualizar_cantidad(self, cantidad: int) -> None:
        if cantidad < 1:
            raise ValueError("La cantidad debe ser al menos 1.")
        self.cantidad = cantidad

    def actualizar_precio(self, precio_unitario: float, descuento_pct: float | None = None) -> None:
        if precio_unitario < 0:
            raise ValueError("El precio unitario no puede ser negativo.")
        self.precio_unitario = precio_unitario
        if descuento_pct is not None:
            self.descuento_pct = descuento_pct


@dataclass
class Venta:
    """
    Agregado raíz: vale POS desde armado (Abierta) hasta cobro (Pagado) o anulación.

    Stock en tienda se descuenta al cobrar (no al finalizar), salvo flujo legacy formulario.
    """

    detalles: list[DetalleVenta] = field(default_factory=list)
    estado: EstadoVenta = EstadoVenta.ABIERTA
    monto_total: Money = field(default_factory=Money.zero)
    neto: Money = field(default_factory=Money.zero)
    iva: Money = field(default_factory=Money.zero)
    id: Optional[int] = None
    cliente_id: Optional[int] = None
    caja_id: Optional[int] = None
    usuario: Optional[str] = None
    prioridad: Optional[int] = None
    punto_retiro: Optional[str] = None
    metodo_pago: Optional[str] = None
    tipo_documento: str = TipoDocumento.BOLETA.value
    monto_recibido: Optional[float] = None
    vuelto: Optional[float] = None
    saldo_favor_usado: float = 0.0
    credito_plan_codigo: Optional[str] = None
    motivo_anulacion: Optional[str] = None

    # --- Líneas ---

    def agregar_linea(
        self,
        producto_id: int,
        cantidad: int,
        precio_unitario: float,
        descuento_pct: float = 0.0,
        *,
        punto_retiro_linea: str | None = None,
    ) -> DetalleVenta:
        if self.estado != EstadoVenta.ABIERTA:
            raise EstadoVentaInvalidoError(
                f"Solo se pueden agregar líneas con el vale en estado {EstadoVenta.ABIERTA.value}."
            )
        linea = DetalleVenta(
            producto_id=producto_id,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            descuento_pct=descuento_pct,
            punto_retiro_linea=punto_retiro_linea,
        )
        self.detalles.append(linea)
        self.recalcular_total()
        return linea

    def quitar_linea_por_indice(self, indice: int) -> None:
        if self.estado != EstadoVenta.ABIERTA:
            raise EstadoVentaInvalidoError("Solo se pueden quitar líneas en vale Abierta.")
        if indice < 0 or indice >= len(self.detalles):
            raise IndexError("Índice de línea fuera de rango.")
        del self.detalles[indice]
        self.recalcular_total()

    def quitar_linea_por_id(self, detalle_id: int) -> None:
        if self.estado != EstadoVenta.ABIERTA:
            raise EstadoVentaInvalidoError("Solo se pueden quitar líneas en vale Abierta.")
        for i, d in enumerate(self.detalles):
            if d.id == detalle_id:
                del self.detalles[i]
                self.recalcular_total()
                return
        raise ValueError(f"Línea id={detalle_id} no encontrada en el vale.")

    # --- Totales e impuestos ---

    def recalcular_total(self) -> Money:
        bruto = sum((d.subtotal_bruto().amount_clp for d in self.detalles), 0)
        self.monto_total = Money(bruto)
        self.desglosar_iva()
        return self.monto_total

    def desglosar_iva(self) -> None:
        self.neto, self.iva = Money.desglosar_iva_desde_total_bruto(self.monto_total)

    # --- Consultas de estado (réplica helpers app.py) ---

    def metodo_pago_vacio(self) -> bool:
        if self.metodo_pago is None:
            return True
        return str(self.metodo_pago).strip() == ""

    def stock_ya_descontado_en_reglas_legacy(self) -> bool:
        """
        Indica si, según estado/método, la mercadería ya debió salir de inventario tienda.

        Alineado con `_venta_stock_ya_descontado` en app.py.
        """
        if self.estado in (EstadoVenta.ABIERTA, EstadoVenta.ANULADA):
            return False
        if self.estado == EstadoVenta.PAGADO:
            return True
        if self.estado == EstadoVenta.PENDIENTE:
            return not self.metodo_pago_vacio()
        return False

    def esta_anulada(self) -> bool:
        return self.estado == EstadoVenta.ANULADA

    def esta_en_cola_cobro(self) -> bool:
        return self.estado in (EstadoVenta.PENDIENTE, EstadoVenta.ABIERTA)

    # --- Validaciones previas a casos de uso ---

    def asegurar_tiene_lineas(self) -> None:
        if not self.detalles:
            raise VentaSinLineasError("El vale debe tener al menos una línea de producto.")

    def asegurar_total_positivo(self) -> None:
        self.recalcular_total()
        if self.monto_total.amount_clp <= 0:
            raise VentaTotalInvalidoError("El vale no tiene un total válido para operar.")

    def validar_punto_retiro_final(self, punto_retiro: str, *, retiro_por_linea: bool) -> str:
        """
        Devuelve punto_retiro normalizado para persistir (incluye Mixto).

        :param retiro_por_linea: empresa con POS retiro por línea activo.
        """
        validos_linea = PuntoRetiro.valores_linea()
        if retiro_por_linea:
            marcas: list[str] = []
            for d in self.detalles:
                pv = (d.punto_retiro_linea or PuntoRetiro.TIENDA.value).strip()
                if pv not in validos_linea:
                    raise PuntoRetiroInvalidoError(
                        "Cada línea debe indicar retiro Tienda, Bodega o Despacho."
                    )
                marcas.append(pv)
            unicos = set(marcas)
            return list(unicos)[0] if len(unicos) == 1 else PuntoRetiro.MIXTO.value
        pr = (punto_retiro or "").strip()
        if not pr or pr == "__PENDIENTE__" or pr not in validos_linea:
            raise PuntoRetiroInvalidoError("Debe seleccionar punto de retiro: Bodega, Tienda o Despacho.")
        return pr

    # --- Transiciones de negocio ---

    def finalizar(
        self,
        *,
        cliente_id: int,
        punto_retiro: str,
        prioridad_cola: int,
        usuario_vendedor: str,
        retiro_por_linea: bool = False,
    ) -> None:
        """
        Emite el vale: Abierta → Pendiente (sin descontar stock).

        La validación de stock en tienda es responsabilidad de la capa de aplicación
        (consulta inventario) antes de llamar a este método.
        """
        if self.estado != EstadoVenta.ABIERTA:
            raise EstadoVentaInvalidoError(
                f"Solo se puede finalizar un vale en estado {EstadoVenta.ABIERTA.value}."
            )
        self.asegurar_tiene_lineas()
        self.asegurar_total_positivo()
        pr = self.validar_punto_retiro_final(punto_retiro, retiro_por_linea=retiro_por_linea)
        if retiro_por_linea:
            for d in self.detalles:
                d.punto_retiro_linea = (d.punto_retiro_linea or PuntoRetiro.TIENDA.value).strip()
        self.cliente_id = cliente_id
        self.punto_retiro = pr
        self.prioridad = prioridad_cola
        self.usuario = (usuario_vendedor or "").strip() or self.usuario
        self.estado = EstadoVenta.PENDIENTE

    def puede_registrar_cobro(self, *, caja_id_abierta: int | None) -> None:
        """Precondiciones de cobro (sin validar stock; eso va en aplicación)."""
        if self.esta_anulada():
            raise CobroNoPermitidoError("El vale está anulado y no puede cobrarse.")
        if self.estado == EstadoVenta.ABIERTA:
            if self.caja_id and caja_id_abierta and self.caja_id != caja_id_abierta:
                raise CobroNoPermitidoError("El borrador no pertenece a la caja abierta.")
        elif self.estado != EstadoVenta.PENDIENTE:
            raise CobroNoPermitidoError("El documento no está en cola de cobro.")
        if not self.metodo_pago_vacio():
            raise CobroNoPermitidoError("El vale ya fue procesado (tiene método de pago).")

    def registrar_cobro(
        self,
        *,
        metodo: MetodoPago | str,
        tipo_documento: TipoDocumento | str = TipoDocumento.BOLETA,
        monto_recibido: float,
        saldo_favor_usado: float = 0.0,
        credito_plan_codigo: str | None = None,
        caja_id: int,
    ) -> None:
        """
        Registra cobro en caja: actualiza estado y montos.

        No descuenta stock ni escribe kardex (infraestructura / aplicación).
        Crédito tienda: queda Pendiente con método Credito y plan de cuotas opcional.
        """
        metodo_str = metodo.value if isinstance(metodo, MetodoPago) else str(metodo).strip()
        if not metodo_str:
            raise CobroNoPermitidoError("Método de pago requerido.")

        tipo_doc = (
            tipo_documento.value if isinstance(tipo_documento, TipoDocumento) else str(tipo_documento).strip()
        ) or TipoDocumento.BOLETA.value

        self.asegurar_total_positivo()
        self.metodo_pago = metodo_str
        self.tipo_documento = tipo_doc
        self.caja_id = caja_id
        self.desglosar_iva()

        total = self.monto_total
        sf = min(float(saldo_favor_usado or 0), total.to_float())
        total_a_pagar = max(0.0, total.to_float() - sf)

        if metodo_str == MetodoPago.CREDITO.value:
            self.estado = EstadoVenta.PENDIENTE
            self.monto_recibido = 0.0
            self.vuelto = 0.0
            self.saldo_favor_usado = 0.0
            self.credito_plan_codigo = (credito_plan_codigo or "").strip() or None
            return

        if monto_recibido < total_a_pagar:
            raise CobroNoPermitidoError(
                "El monto recibido no puede ser menor al total pendiente después de saldo a favor."
            )

        self.estado = EstadoVenta.PAGADO
        self.monto_recibido = float(monto_recibido)
        self.vuelto = float(monto_recibido) - total_a_pagar
        self.saldo_favor_usado = sf
        self.credito_plan_codigo = None

    def anular(self, *, motivo: str, usuario: str) -> None:
        if self.estado == EstadoVenta.PAGADO:
            raise EstadoVentaInvalidoError(
                "Un vale Pagado no se anula con este método; usar flujo de anulación en caja."
            )
        self.estado = EstadoVenta.ANULADA
        self.motivo_anulacion = (motivo or "").strip()[:500] or None
        self.usuario = usuario or self.usuario
