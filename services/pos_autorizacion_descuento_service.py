"""Autorización de descuentos POS: tarjeta supervisor + PIN opcional."""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

# Sin caracteres ambiguos en pistola (0/O, 1/I/L)
_TOKEN_ALFABETO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
_TOKEN_PREFIJO = 'LHX-SUP-'


def normalizar_codigo_tarjeta(raw: str) -> str:
    """Acepta lectura con o sin prefijo; devuelve token en mayúsculas."""
    s = (raw or '').strip().upper().replace(' ', '')
    if not s:
        return ''
    if s.startswith(_TOKEN_PREFIJO):
        return s
    # Solo payload alfanumérico
    payload = re.sub(r'[^A-Z0-9]', '', s)
    if len(payload) >= 8:
        return _TOKEN_PREFIJO + payload[-12:] if len(payload) > 12 else _TOKEN_PREFIJO + payload
    return s


def generar_token_tarjeta() -> str:
    cuerpo = ''.join(secrets.choice(_TOKEN_ALFABETO) for _ in range(12))
    return _TOKEN_PREFIJO + cuerpo


def hash_token_tarjeta(token_plano: str) -> str:
    return generate_password_hash((token_plano or '').strip().upper())


def verificar_token_tarjeta(token_plano: str, token_hash: str) -> bool:
    if not token_plano or not token_hash:
        return False
    return check_password_hash(token_hash, (token_plano or '').strip().upper())


def pin_valido_formato(pin: str) -> bool:
    p = (pin or '').strip()
    return len(p) == 4 and p.isdigit()


def hash_pin(pin: str) -> str:
    return generate_password_hash((pin or '').strip())


def verificar_pin(pin: str, pin_hash: str) -> bool:
    if not pin_valido_formato(pin) or not pin_hash:
        return False
    return check_password_hash(pin_hash, (pin or '').strip())


def umbral_pin_desde_config(cfg: dict) -> float:
    try:
        v = float(str((cfg or {}).get('pos_descuento_umbral_pin_pct', '20')).replace(',', '.'))
        return max(0.0, min(100.0, v))
    except (TypeError, ValueError):
        return 20.0


def requiere_pin_para_descuento(descuento_pct: float, umbral: float) -> bool:
    return float(descuento_pct or 0) > float(umbral) + 1e-6


def producto_descuento_preautorizado_cubre(producto, descuento_pct: float) -> bool:
    """
    Productos marcados en catálogo con descuento preaprobado (sin tarjeta supervisor).
    pos_descuento_preautorizado=1 y tope pos_descuento_preautorizado_pct (si es 0, no cubre).
    """
    if not producto:
        return False
    flag = getattr(producto, 'pos_descuento_preautorizado', False)
    if not flag:
        return False
    dto = float(descuento_pct or 0)
    if dto <= 1e-6:
        return True
    max_pct = float(getattr(producto, 'pos_descuento_preautorizado_pct', None) or 0)
    if max_pct <= 1e-6:
        return False
    return dto <= max_pct + 1e-6


def requiere_autorizacion_supervisor_pos(
    descuento_pct: float,
    producto,
    usuario_tiene_permiso_autorizar: bool = False,
) -> bool:
    """
    Todo descuento > 0 exige tarjeta/PIN de supervisor en el momento de aplicarlo.
    El permiso autorizar_descuento_pos identifica quién puede autorizar (tarjeta),
    no exime al vendedor de pedir autorización (incl. usuario admin en caja).
    """
    _ = usuario_tiene_permiso_autorizar  # compat. firmas antiguas; sin bypass por rol
    if float(descuento_pct or 0) <= 1e-6:
        return False
    if producto_descuento_preautorizado_cubre(producto, descuento_pct):
        return False
    return True


def detalle_descuento_autorizacion_valida(detalle) -> bool:
    """True si la línea con descuento tiene traza de autorización o producto preautorizado."""
    dto = float(getattr(detalle, 'descuento', None) or 0)
    if dto <= 1e-6:
        return True
    producto = getattr(detalle, 'producto', None)
    if producto_descuento_preautorizado_cubre(producto, dto):
        return (getattr(detalle, 'descuento_autorizado_metodo', None) or '') == 'producto_preautorizado'
    metodo = (getattr(detalle, 'descuento_autorizado_metodo', None) or '').strip()
    if metodo in ('tarjeta', 'tarjeta_pin', 'password'):
        return bool(getattr(detalle, 'descuento_autorizado_por_id', None))
    return False


def metodo_autorizacion_label(descuento_pct: float, umbral: float, uso_password: bool = False) -> str:
    if uso_password:
        return 'password'
    if requiere_pin_para_descuento(descuento_pct, umbral):
        return 'tarjeta_pin'
    return 'tarjeta'


def resolver_supervisor_por_tarjeta(db, models, token_raw: str) -> Tuple[Optional[object], str]:
    """
    Devuelve (Usuario, error_code).
    error_code: '' | 'not_found' | 'inactive' | 'no_permiso'
    """
    Usuario = models['Usuario']
    UsuarioTarjetaAutorizacion = models['UsuarioTarjetaAutorizacion']
    usuario_obj_tiene_permiso = models['usuario_obj_tiene_permiso']
    usuario_esta_activo = models['usuario_esta_activo']

    codigo = normalizar_codigo_tarjeta(token_raw)
    if not codigo or not codigo.startswith(_TOKEN_PREFIJO):
        return None, 'not_found'

    filas = (
        UsuarioTarjetaAutorizacion.query.filter_by(activo=True)
        .order_by(UsuarioTarjetaAutorizacion.id.desc())
        .all()
    )
    for fila in filas:
        if not verificar_token_tarjeta(codigo, fila.token_hash):
            continue
        sup = Usuario.query.get(fila.usuario_id)
        if not sup:
            return None, 'not_found'
        if not usuario_esta_activo(sup):
            return None, 'inactive'
        if not usuario_obj_tiene_permiso(sup, 'autorizar_descuento_pos'):
            return None, 'no_permiso'
        fila.ultimo_uso_en = datetime.utcnow()
        return sup, ''

    return None, 'not_found'


def registrar_uso_tarjeta(db, fila_id: int) -> None:
    """Marca último uso (si la fila sigue activa)."""
    pass  # ultimo_uso ya se actualiza en resolver_supervisor_por_tarjeta
