"""
DEPRECADO — Arqueo fusionado en modelo Caja (tabla caja) y ruta /cerrar_caja.

Ver: app.Caja.monto_declarado_cajero, services/cuadratura_arqueo_service.py
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional, Type

ESTADO_ABIERTO = 'ABIERTO'
ESTADO_PENDIENTE_CONCILIACION = 'PENDIENTE_CONCILIACION'
ESTADO_CONCILIADO = 'CONCILIADO'

_ESTADOS_VALIDOS = frozenset(
    {ESTADO_ABIERTO, ESTADO_PENDIENTE_CONCILIACION, ESTADO_CONCILIADO}
)


class ArqueoCajaError(ValueError):
    """Violación de reglas de arqueo (cierre a ciegas, transición de estado)."""


def register_arqueo_caja_model(db: Any) -> Type[Any]:
    """
    Registra ArqueoCaja en el SQLAlchemy de Flask (evita import circular con app.py).
    """

    class ArqueoCaja(db.Model):
        __tablename__ = 'arqueo_caja'

        id = db.Column(db.Integer, primary_key=True)
        cajero_id = db.Column(db.String(50), nullable=False)
        fecha_apertura = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
        fecha_cierre = db.Column(db.DateTime, nullable=True)
        estado = db.Column(db.String(30), nullable=False, default=ESTADO_ABIERTO)

        monto_apertura = db.Column(db.Integer, nullable=False, default=0)
        monto_esperado_efectivo = db.Column(db.Integer, nullable=False, default=0)
        monto_esperado_tarjeta = db.Column(db.Integer, nullable=False, default=0)
        monto_declarado_cajero = db.Column(db.Integer, nullable=True)
        monto_descuadre = db.Column(db.Integer, nullable=False, default=0)

        boletas_emitidas_qty = db.Column(db.Integer, nullable=False, default=0)
        boletas_sincronizadas_qty = db.Column(db.Integer, nullable=False, default=0)
        monto_total_ventas = db.Column(db.Integer, nullable=False, default=0)
        monto_total_sii = db.Column(db.Integer, nullable=False, default=0)

        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault('estado', ESTADO_ABIERTO)
            kwargs.setdefault('monto_apertura', 0)
            kwargs.setdefault('monto_esperado_efectivo', 0)
            kwargs.setdefault('monto_esperado_tarjeta', 0)
            kwargs.setdefault('monto_descuadre', 0)
            kwargs.setdefault('boletas_emitidas_qty', 0)
            kwargs.setdefault('boletas_sincronizadas_qty', 0)
            kwargs.setdefault('monto_total_ventas', 0)
            kwargs.setdefault('monto_total_sii', 0)
            super().__init__(**kwargs)

        def _base_efectivo_esperado_clp(self) -> int:
            return int(self.monto_apertura or 0) + int(self.monto_esperado_efectivo or 0)

        def calcular_descuadre_cierre(self, monto_declarado: int) -> int:
            """
            Fórmula inmutable de cierre:
            monto_descuadre = monto_declarado_cajero - (monto_apertura + monto_esperado_efectivo)
            """
            return int(monto_declarado) - self._base_efectivo_esperado_clp()

        def cerrar_turno_pendiente_conciliacion(self, monto_declarado_cajero: int) -> int:
            """
            Gatilla el cierre del turno: exige declaración a ciegas y fija descuadre + estado.
            """
            if self.estado != ESTADO_ABIERTO:
                raise ArqueoCajaError(
                    f'Solo se puede cerrar un arqueo en estado {ESTADO_ABIERTO} (actual: {self.estado}).'
                )
            if monto_declarado_cajero is None:
                raise ArqueoCajaError(
                    'monto_declarado_cajero es obligatorio para pasar a PENDIENTE_CONCILIACION.'
                )
            declarado = int(monto_declarado_cajero)
            if declarado < 0:
                raise ArqueoCajaError('monto_declarado_cajero no puede ser negativo.')

            self.monto_declarado_cajero = declarado
            self.monto_descuadre = self.calcular_descuadre_cierre(declarado)
            self.fecha_cierre = datetime.now(UTC)
            self.estado = ESTADO_PENDIENTE_CONCILIACION
            return self.monto_descuadre

        def marcar_conciliado(self) -> None:
            if self.estado != ESTADO_PENDIENTE_CONCILIACION:
                raise ArqueoCajaError(
                    'Solo arqueos en PENDIENTE_CONCILIACION pueden pasar a CONCILIADO.'
                )
            if self.monto_declarado_cajero is None:
                raise ArqueoCajaError('No se puede conciliar sin monto_declarado_cajero.')
            self.estado = ESTADO_CONCILIADO

        def __repr__(self) -> str:
            return (
                f'<ArqueoCaja id={self.id} cajero={self.cajero_id!r} '
                f'estado={self.estado} descuadre={self.monto_descuadre}>'
            )

    ArqueoCaja.__name__ = 'ArqueoCaja'
    return ArqueoCaja


def validar_estado_arqueo(estado: str) -> None:
    if estado not in _ESTADOS_VALIDOS:
        raise ArqueoCajaError(f'Estado de arqueo inválido: {estado!r}')
