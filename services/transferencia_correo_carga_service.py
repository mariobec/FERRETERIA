# -*- coding: utf-8 -*-
"""Sincroniza avisos de transferencia bancaria desde IMAP (misma cuenta que DTE)."""
from __future__ import annotations

import email
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

from services.imap_correo_util import (
    conectar_imap,
    decodificar_header,
    extraer_texto_plano,
    imap_configurado,
    load_env_local,
    message_id_unico,
    parsear_fecha_correo,
    fecha_imap,
)
from services.transferencia_correo_parser import parsear_correo_transferencia, sugerir_venta_id

logger = logging.getLogger(__name__)


def _carpeta_imap() -> str:
    load_env_local()
    return (
        os.getenv('TRF_CORREO_FOLDER')
        or os.getenv('TRF_GMAIL_LABEL')
        or os.getenv('IMAP_FOLDER')
        or 'Transferencias-Banco'
    ).strip() or 'Transferencias-Banco'


def _dias_sync() -> int:
    load_env_local()
    try:
        return max(1, min(int(os.getenv('TRF_CORREO_DIAS') or '45'), 365))
    except (TypeError, ValueError):
        return 45


def query_correos_bandaja(*, limit: int = 100):
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo

    _asegurar_tabla_transferencia_correo()
    return (
        TransferenciaCorreoIngreso.query.filter(
            TransferenciaCorreoIngreso.estado.in_(('pendiente', 'vinculado'))
        )
        .order_by(TransferenciaCorreoIngreso.fecha_correo.desc(), TransferenciaCorreoIngreso.id.desc())
        .limit(max(1, min(int(limit or 100), 300)))
    )


def _monto_clp_entero(monto) -> int | None:
    if monto is None:
        return None
    try:
        return int(round(float(monto)))
    except (TypeError, ValueError):
        return None


def _nombre_ordenante_correo(c) -> str:
    de = (getattr(c, 'nombre_ordenante', None) or '').strip()
    if de:
        return de[:120]
    rem = (getattr(c, 'remitente', None) or '').strip()
    if rem:
        return rem[:120]
    return 'Ordenante no identificado'


def serializar_correo_transferencia_alerta(c) -> dict:
    return {
        'id': int(c.id),
        'tipo': 'correo',
        'monto': _monto_clp_entero(getattr(c, 'monto', None)),
        'de': _nombre_ordenante_correo(c),
        'referencia': ((getattr(c, 'referencia', None) or '')[:80] or None),
        'fecha': c.fecha_correo.isoformat() if getattr(c, 'fecha_correo', None) else None,
        'venta_id_sugerida': getattr(c, 'venta_id_sugerida', None),
        'tiene_match': bool(getattr(c, 'venta_id_sugerida', None)),
    }


def serializar_vale_transferencia_alerta(v) -> dict:
    cliente = 'Cliente final'
    cl = getattr(v, 'cliente', None)
    if cl and getattr(cl, 'nombre', None):
        cliente = (cl.nombre or '').strip() or cliente
    vid = int(v.id)
    return {
        'id': vid,
        'tipo': 'vale',
        'monto': _monto_clp_entero(getattr(v, 'monto_total', None)),
        'de': cliente[:120],
        'referencia': ((getattr(v, 'transferencia_referencia', None) or '')[:80] or None),
        'fecha': v.fecha.isoformat() if getattr(v, 'fecha', None) else None,
        'folio': f'VL{vid:06d}',
    }


def serializar_correo_transferencia_detalle(c) -> dict:
    return {
        'ok': True,
        'id': int(c.id),
        'monto': _monto_clp_entero(getattr(c, 'monto', None)),
        'nombre_ordenante': (getattr(c, 'nombre_ordenante', None) or '').strip() or None,
        'rut_ordenante': (getattr(c, 'rut_ordenante', None) or '').strip() or None,
        'remitente': (getattr(c, 'remitente', None) or '').strip() or None,
        'asunto': (getattr(c, 'asunto', None) or '').strip() or None,
        'referencia': (getattr(c, 'referencia', None) or '').strip() or None,
        'fecha_correo': c.fecha_correo.isoformat() if getattr(c, 'fecha_correo', None) else None,
        'extracto': (getattr(c, 'extracto', None) or '').strip()[:2500] or None,
        'venta_id_sugerida': getattr(c, 'venta_id_sugerida', None),
        'estado': (getattr(c, 'estado', None) or '').strip() or 'pendiente',
    }


def obtener_correo_transferencia_detalle(cid: int) -> dict:
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo

    _asegurar_tabla_transferencia_correo()
    c = TransferenciaCorreoIngreso.query.get(int(cid))
    if not c:
        return {'ok': False, 'error': 'Aviso bancario no encontrado.'}
    if (c.estado or '') not in ('pendiente', 'vinculado'):
        return {'ok': False, 'error': 'Este aviso ya fue procesado.'}
    return serializar_correo_transferencia_detalle(c)


def _ventas_pendientes_confirmacion():
    from services.transferencia_caja_service import query_transferencias_pendientes

    return query_transferencias_pendientes(caja_id=None, limit=500).all()


def _persistir_correo(
    *,
    message_id: str,
    imap_uid: str,
    fecha_correo: datetime | None,
    parsed,
    venta_id_sugerida: int | None,
    usuario: str,
) -> tuple[str, int | None]:
    """Retorna ('nuevo'|'duplicado'|'actualizado', id)."""
    from app import TransferenciaCorreoIngreso, db, _asegurar_tabla_transferencia_correo

    _asegurar_tabla_transferencia_correo()
    existente = TransferenciaCorreoIngreso.query.filter_by(message_id=message_id).first()
    if existente:
        cambio = False
        if venta_id_sugerida and not existente.venta_id_sugerida:
            existente.venta_id_sugerida = venta_id_sugerida
            if existente.estado == 'pendiente' and venta_id_sugerida:
                existente.estado = 'vinculado'
            cambio = True
        if parsed.monto and not existente.monto:
            existente.monto = parsed.monto
            cambio = True
        if parsed.referencia and not existente.referencia:
            existente.referencia = (parsed.referencia or '')[:120] or None
            cambio = True
        if parsed.nombre_ordenante and not existente.nombre_ordenante:
            existente.nombre_ordenante = (parsed.nombre_ordenante or '')[:200] or None
            cambio = True
        if parsed.rut_ordenante and not existente.rut_ordenante:
            existente.rut_ordenante = (parsed.rut_ordenante or '')[:20] or None
            cambio = True
        if parsed.extracto and (not existente.extracto or len(existente.extracto or '') < len(parsed.extracto or '')):
            existente.extracto = (parsed.extracto or '')[:2000] or None
            cambio = True
        if cambio:
            db.session.commit()
            return 'actualizado', existente.id
        return 'duplicado', existente.id

    row = TransferenciaCorreoIngreso(
        message_id=message_id[:255],
        imap_uid=(imap_uid or '')[:64],
        fecha_correo=fecha_correo,
        remitente=parsed.remitente,
        asunto=parsed.asunto,
        monto=parsed.monto,
        referencia=(parsed.referencia or '')[:120] or None,
        rut_ordenante=(parsed.rut_ordenante or '')[:20] or None,
        nombre_ordenante=(parsed.nombre_ordenante or '')[:200] or None,
        extracto=(parsed.extracto or '')[:2000] or None,
        venta_id_sugerida=venta_id_sugerida,
        estado='vinculado' if venta_id_sugerida else 'pendiente',
        sync_usuario=(usuario or '')[:80] or None,
        created_at=datetime.now(),
    )
    db.session.add(row)
    db.session.flush()

    if venta_id_sugerida:
        _aplicar_referencia_correo_a_venta(venta_id_sugerida, parsed.referencia)

    db.session.commit()
    return 'nuevo', row.id


def _aplicar_referencia_correo_a_venta(venta_id: int, referencia: str | None) -> None:
    if not referencia:
        return
    from app import Venta, _asegurar_columnas_transferencia_caja, db

    _asegurar_columnas_transferencia_caja()
    v = db.session.get(Venta, int(venta_id))
    if not v:
        return
    if not (v.transferencia_referencia or '').strip():
        v.transferencia_referencia = referencia[:80]


def contar_correos_transferencia_bandaja() -> int:
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo

    _asegurar_tabla_transferencia_correo()
    return (
        TransferenciaCorreoIngreso.query.filter(
            TransferenciaCorreoIngreso.estado.in_(('pendiente', 'vinculado'))
        ).count()
    )


def payload_alerta_transferencias_caja(*, caja_id: int | None = None) -> dict:
    """JSON para campanita caja: vales + avisos bancarios pendientes de revisión."""
    from app import TransferenciaCorreoIngreso, Venta, _asegurar_columnas_transferencia_caja, _asegurar_tabla_transferencia_correo
    from services.transferencia_caja_service import contar_transferencias_pendientes, query_transferencias_pendientes
    from sqlalchemy.orm import joinedload

    _asegurar_columnas_transferencia_caja()
    _asegurar_tabla_transferencia_correo()

    n_vales = int(contar_transferencias_pendientes(caja_id=caja_id) or 0)
    q_corr = TransferenciaCorreoIngreso.query.filter(
        TransferenciaCorreoIngreso.estado.in_(('pendiente', 'vinculado'))
    )
    n_correos = q_corr.count()
    n_correos_match = q_corr.filter(TransferenciaCorreoIngreso.venta_id_sugerida.isnot(None)).count()
    ultimo = (
        TransferenciaCorreoIngreso.query.filter(
            TransferenciaCorreoIngreso.estado.in_(('pendiente', 'vinculado'))
        )
        .order_by(TransferenciaCorreoIngreso.id.desc())
        .first()
    )
    ultimo_id = int(ultimo.id) if ultimo else 0
    ultimo_at = ultimo.fecha_correo.isoformat() if ultimo and ultimo.fecha_correo else None
    total = n_vales + n_correos

    correos_recientes = [
        serializar_correo_transferencia_alerta(c)
        for c in query_correos_bandaja(limit=5).all()
    ]
    vales_recientes = [
        serializar_vale_transferencia_alerta(v)
        for v in query_transferencias_pendientes(caja_id=caja_id, limit=5)
        .options(joinedload(Venta.cliente))
        .all()
    ]
    items = []
    for c in correos_recientes:
        items.append({**c, 'origen': 'banco'})
    for v in vales_recientes:
        items.append({**v, 'origen': 'vale'})
    items.sort(key=lambda x: x.get('fecha') or '', reverse=True)
    items = items[:6]

    return {
        'ok': True,
        'n_vales': n_vales,
        'n_correos': n_correos,
        'n_correos_con_match': n_correos_match,
        'total': total,
        'ultimo_correo_id': ultimo_id,
        'ultimo_correo_at': ultimo_at,
        'hay_pendientes': total > 0,
        'url_bandaja': None,
        'correos_recientes': correos_recientes,
        'vales_recientes': vales_recientes,
        'items': items,
    }


def sincronizar_correo_transferencias(
    *,
    limite: int = 80,
    offset: int = 0,
    solo_no_leidos: bool = False,
    usuario: str = 'Caja',
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Lee IMAP (misma config que DTE) y persiste avisos de transferencia en BD.
    """
    load_env_local()
    if not imap_configurado():
        return {'ok': False, 'error': 'Configure IMAP_USER e IMAP_PASSWORD en .env.local (buzón avisos bancarios).'}

    desde = date.today() - timedelta(days=_dias_sync())
    criterio = 'UNSEEN' if solo_no_leidos else 'ALL'
    criterio = f'({criterio} SINCE {fecha_imap(desde)})'
    mailbox = _carpeta_imap()
    ventas = _ventas_pendientes_confirmacion()

    dep = depurar_correos_bandaja_invalidos(usuario=usuario)
    stats = {
        'correos_escaneados': 0,
        'transferencias_detectadas': 0,
        'nuevos': 0,
        'duplicados': 0,
        'actualizados': 0,
        'omitidos': 0,
        'vinculados_sugeridos': 0,
        'depurados': int(dep.get('descartados') or 0),
    }
    nuevos_ids: list[int] = []

    client = None
    try:
        client = conectar_imap()
        typ, _ = client.select(f'"{mailbox}"' if ' ' in mailbox else mailbox)
        if typ != 'OK':
            return {'ok': False, 'error': f'No se pudo abrir carpeta IMAP: {mailbox}'}

        typ, data = client.search(None, criterio)
        if typ != 'OK' or not data or not data[0]:
            return {'ok': True, 'stats': stats, 'carpeta': mailbox, 'mensaje': 'Sin correos en el periodo.'}

        ids = data[0].split()
        ids = ids[offset: offset + max(1, min(int(limite or 80), 500))]

        for num in ids:
            stats['correos_escaneados'] += 1
            typ, msg_data = client.fetch(num, '(RFC822)')
            if typ != 'OK' or not msg_data or not msg_data[0]:
                stats['omitidos'] += 1
                continue
            raw = msg_data[0][1]
            if not raw:
                stats['omitidos'] += 1
                continue
            msg = email.message_from_bytes(raw)
            remitente = decodificar_header(msg.get('From'))
            asunto = decodificar_header(msg.get('Subject'))
            cuerpo = extraer_texto_plano(msg)
            parsed = parsear_correo_transferencia(remitente=remitente, asunto=asunto, cuerpo=cuerpo)
            if not parsed.es_transferencia:
                stats['omitidos'] += 1
                continue

            stats['transferencias_detectadas'] += 1
            if dry_run:
                vid = sugerir_venta_id(monto=parsed.monto, referencia=parsed.referencia, ventas=ventas)
                if vid:
                    stats['vinculados_sugeridos'] += 1
                continue

            mid = message_id_unico(msg, fallback_uid=num.decode(errors='replace'))
            vid = sugerir_venta_id(monto=parsed.monto, referencia=parsed.referencia, ventas=ventas)
            if vid:
                stats['vinculados_sugeridos'] += 1
            accion, row_id = _persistir_correo(
                message_id=mid,
                imap_uid=num.decode(errors='replace'),
                fecha_correo=parsear_fecha_correo(msg),
                parsed=parsed,
                venta_id_sugerida=vid,
                usuario=usuario,
            )
            if accion == 'nuevo':
                stats['nuevos'] += 1
                if row_id:
                    nuevos_ids.append(row_id)
            elif accion == 'duplicado':
                stats['duplicados'] += 1
            elif accion == 'actualizado':
                stats['actualizados'] += 1

        return {
            'ok': True,
            'stats': stats,
            'carpeta': mailbox,
            'desde': desde.isoformat(),
            'nuevos_ids': nuevos_ids,
            'mensaje': (
                f"Sync OK: {stats['nuevos']} nuevo(s), "
                f"{stats['transferencias_detectadas']} transferencia(s) detectada(s)."
            ),
        }
    except Exception as ex:
        logger.exception('sync transferencias correo')
        return {'ok': False, 'error': str(ex)[:300], 'stats': stats}
    finally:
        if client:
            try:
                client.logout()
            except Exception:
                pass


def confirmar_desde_correo(correo_id: int, venta_id: int | None, usuario: str) -> dict[str, Any]:
    """Confirma abono de vale usando evidencia del correo banco."""
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo, db
    from services.transferencia_caja_service import confirmar_transferencia_venta, es_transferencia_pendiente_confirmacion

    _asegurar_tabla_transferencia_correo()
    row = db.session.get(TransferenciaCorreoIngreso, int(correo_id))
    if not row:
        return {'ok': False, 'error': 'Correo no encontrado.'}
    if row.estado == 'confirmado':
        return {'ok': False, 'error': 'Este aviso de correo ya fue utilizado para confirmar.'}

    vid = int(venta_id or row.venta_id_sugerida or 0)
    if not vid:
        return {'ok': False, 'error': 'Indique el vale a confirmar o sincronice de nuevo para sugerir match.'}

    from app import Venta

    venta = db.session.get(Venta, vid)
    if not venta or not es_transferencia_pendiente_confirmacion(venta):
        return {'ok': False, 'error': 'El vale no está pendiente de confirmación por transferencia.'}

    if row.referencia and not (venta.transferencia_referencia or '').strip():
        venta.transferencia_referencia = row.referencia[:80]
        db.session.commit()

    res = confirmar_transferencia_venta(vid, usuario)
    if not res.get('ok'):
        return res

    row.venta_id_vinculada = vid
    row.venta_id_sugerida = vid
    row.estado = 'confirmado'
    row.confirmado_at = datetime.now()
    row.confirmado_por = (usuario or '')[:80]
    db.session.commit()
    return {
        'ok': True,
        'venta_id': vid,
        'correo_id': row.id,
        'mensaje': res.get('mensaje') or f'Transferencia confirmada con aviso de correo — vale #{vid}.',
    }


def depurar_correos_bandaja_invalidos(*, usuario: str = 'Sistema') -> dict[str, Any]:
    """
    Descarta avisos en bandeja que no son transferencias reales (marketing, etc.).
    Conserva siempre los registros que:
    - Ya tienen monto detectado (fueron correctamente parseados al ingresar)
    - Vienen de un dominio bancario reconocido
    El re-parse usa el extracto truncado (≤2000 chars) — insuficiente para
    decidir descarte definitivo cuando el email original era más largo.
    """
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo, db
    from services.transferencia_correo_parser import parsear_correo_transferencia, _dominios_banco

    _asegurar_tabla_transferencia_correo()
    rows = (
        TransferenciaCorreoIngreso.query.filter(
            TransferenciaCorreoIngreso.estado.in_(('pendiente', 'vinculado'))
        )
        .all()
    )
    descartados = 0
    usr = (usuario or '')[:80] or 'Sistema'
    dominios_banco = _dominios_banco()
    for row in rows:
        # Nunca descartar si ya tiene monto — fue correctamente parseado al ingresar
        if row.monto is not None and row.monto > 0:
            continue
        # Nunca descartar si viene de un dominio bancario conocido
        rem_l = (row.remitente or '').lower()
        if any(d in rem_l for d in dominios_banco):
            continue
        parsed = parsear_correo_transferencia(
            remitente=row.remitente or '',
            asunto=row.asunto or '',
            cuerpo=row.extracto or '',
        )
        if parsed.es_transferencia:
            continue
        row.estado = 'descartado'
        row.confirmado_por = usr
        descartados += 1
    if descartados:
        db.session.commit()
    return {'ok': True, 'descartados': descartados, 'revisados': len(rows)}


def descartar_correo(correo_id: int, usuario: str) -> dict[str, Any]:
    from app import TransferenciaCorreoIngreso, _asegurar_tabla_transferencia_correo, db

    _asegurar_tabla_transferencia_correo()
    row = db.session.get(TransferenciaCorreoIngreso, int(correo_id))
    if not row:
        return {'ok': False, 'error': 'Correo no encontrado.'}
    row.estado = 'descartado'
    row.confirmado_por = (usuario or '')[:80]
    db.session.commit()
    return {'ok': True, 'correo_id': row.id}
