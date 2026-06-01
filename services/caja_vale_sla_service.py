"""SLA vales pendientes de cobro en caja (piloto SD-1)."""
import os
from datetime import datetime

_MOTIVO_AUTO_DEFAULT = 'Auto — vale sin cobro 20 min (SLA caja)'


def _parse_minutos_env(name, default):
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return list(default)
    out = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
            if n > 0:
                out.append(n)
        except ValueError:
            continue
    return sorted(set(out)) if out else list(default)


def obtener_config_sla_caja():
    alertas = _parse_minutos_env('CAJA_VALE_SLA_ALERTAS', (10, 15))
    try:
        anular = int((os.getenv('CAJA_VALE_SLA_ANULAR') or '20').strip() or '20')
    except ValueError:
        anular = 20
    anular = max(1, anular)
    motivo = (os.getenv('CAJA_VALE_SLA_MOTIVO_AUTO') or _MOTIVO_AUTO_DEFAULT).strip()[:500]
    return {
        'alertas': alertas,
        'anular_minutos': anular,
        'motivo_auto': motivo or _MOTIVO_AUTO_DEFAULT,
    }


def minutos_pendiente_caja(venta_fecha, ahora=None):
    if not venta_fecha:
        return 0
    ahora = ahora or datetime.now()
    delta = ahora - venta_fecha
    return max(0, int(delta.total_seconds() / 60))


def evaluar_sla_vale(minutos, config=None):
    config = config or obtener_config_sla_caja()
    alertas = config['alertas']
    anular = config['anular_minutos']
    umbral_atencion = alertas[0] if alertas else 10
    umbral_modal = alertas[1] if len(alertas) > 1 else umbral_atencion

    if minutos >= anular:
        tier = 3
        accion = 'auto_anular'
        label = 'Vencido'
        css = 'sla-critical'
    elif minutos >= umbral_modal:
        tier = 2
        accion = 'modal_cobrar_anular'
        label = f'{minutos} min'
        css = 'sla-delayed'
    elif minutos >= umbral_atencion:
        tier = 1
        accion = 'atencion'
        label = f'{minutos} min'
        css = 'sla-attention'
    else:
        tier = 0
        accion = 'ok'
        label = 'En tiempo'
        css = 'sla-ok'

    return {
        'minutos': minutos,
        'tier': tier,
        'accion': accion,
        'label': label,
        'css': css,
        'umbral_atencion': umbral_atencion,
        'umbral_modal': umbral_modal,
        'umbral_anular': anular,
    }


def venta_elegible_sla_caja(venta, caja_id, *, tiene_despacho_bodega=False):
    st = (getattr(venta, 'estado', None) or '').strip()
    mp = getattr(venta, 'metodo_pago', None)
    mp_vacio = mp is None or (isinstance(mp, str) and not mp.strip())
    if st != 'Pendiente' or not mp_vacio:
        return False
    if caja_id is None or getattr(venta, 'caja_id', None) != caja_id:
        return False
    if tiene_despacho_bodega:
        return False
    return True


def serializar_vale_sla(venta, config, ahora, *, tiene_despacho_bodega=False):
    mins = minutos_pendiente_caja(getattr(venta, 'fecha', None), ahora)
    sla = evaluar_sla_vale(mins, config)
    elegible_auto = (
        sla['accion'] == 'auto_anular'
        and venta_elegible_sla_caja(venta, getattr(venta, 'caja_id', None), tiene_despacho_bodega=tiene_despacho_bodega)
    )
    bloqueado_auto = sla['accion'] == 'auto_anular' and bool(tiene_despacho_bodega)
    return {
        'id': int(venta.id),
        'minutos': mins,
        'tier': sla['tier'],
        'accion': sla['accion'],
        'label': sla['label'],
        'css': sla['css'],
        'monto': float(getattr(venta, 'monto_total', 0) or 0),
        'usuario': (getattr(venta, 'usuario', None) or '')[:50],
        'fecha_iso': venta.fecha.isoformat() if getattr(venta, 'fecha', None) else None,
        'elegible_auto_anular': elegible_auto,
        'bloqueado_auto_anular': bloqueado_auto,
        'tiene_despacho_bodega': bool(tiene_despacho_bodega),
    }
