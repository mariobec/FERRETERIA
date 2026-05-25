"""Persistencia y estados — tabla agente_ejecuciones (PLAT-2.1)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

# Tipos
TIPO_ALERTA = 'alerta_operativa'
TIPO_BORRADOR = 'borrador_hitl'
TIPO_LOG = 'log_ejecucion'

# Estados alerta operativa
EST_ALERTA_ABIERTA = 'abierta'
EST_ALERTA_RECONOCIDA = 'reconocida'
EST_ALERTA_CERRADA = 'cerrada'

# Estados HITL
EST_HITL_NUEVA = 'nueva'
EST_HITL_PENDIENTE = 'pendiente_aprobacion'
EST_HITL_APROBADA = 'aprobada'
EST_HITL_RECHAZADA = 'rechazada'

# Logs
EST_LOG_OK = 'completada'
EST_LOG_ERROR = 'error'
EST_LOG_EJECUTADO = 'ejecutado'


def _model():
    from app import AgenteEjecucion

    return AgenteEjecucion


def _db():
    from app import db

    return db


def asegurar_tabla() -> bool:
    from app import _asegurar_tabla_agente_ejecuciones

    return _asegurar_tabla_agente_ejecuciones()


def parse_payload_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def cuerpo_alerta_para_ui(cuerpo: str | None, payload: dict[str, Any] | None = None) -> str:
    """Texto visible en Guardián / feed — sin bloque [Base operativa] si hubo enrich Ollama."""
    raw = (cuerpo or '').strip()
    if not raw:
        return ''
    payload = payload or {}
    if payload.get('enriquecido_semantico') and '\n---\n' in raw:
        lead = raw.split('\n---\n', 1)[0].strip()
        if lead:
            return lead[:500]
    return raw[:500]


def listar_alertas_sin_enriquecer(*, limite: int = 5) -> list:
    """Alertas operador abiertas pendientes de enriquecimiento semántico (v0.2)."""
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return []
    limite = max(1, min(int(limite or 5), 10))
    candidatas = (
        AgenteEjecucion.query.filter_by(
            agente_nombre='operador',
            tipo=TIPO_ALERTA,
            estado=EST_ALERTA_ABIERTA,
        )
        .order_by(AgenteEjecucion.created_at.asc())
        .limit(limite * 4)
        .all()
    )
    out = []
    for row in candidatas:
        p = parse_payload_json(row.payload_json)
        if p.get('enriquecido_semantico'):
            continue
        out.append(row)
        if len(out) >= limite:
            break
    return out


def aplicar_enriquecimiento_semantico(
    registro_id: int,
    *,
    cuerpo_enriquecido: str,
    tokens_total: int = 0,
    titulo_opcional: str | None = None,
    modelo: str | None = None,
) -> bool:
    """Actualiza cuerpo/tokens y marca payload enriquecido (worker local)."""
    row = obtener_por_id(registro_id)
    if not row or row.tipo != TIPO_ALERTA:
        return False
    ahora = datetime.now()
    payload_prev = parse_payload_json(row.payload_json)
    if not payload_prev.get('cuerpo_base_v01'):
        payload_prev['cuerpo_base_v01'] = row.cuerpo
    payload_prev['enriquecido_semantico'] = True
    payload_prev['enriquecido_at'] = ahora.isoformat()
    if modelo:
        payload_prev['ollama_model'] = modelo[:64]
    row.cuerpo = (cuerpo_enriquecido or row.cuerpo or '')[:10000]
    if titulo_opcional:
        row.titulo = (titulo_opcional or row.titulo)[:255]
    row.tokens_total = int(tokens_total or 0)
    row.costo_api_usd = 0
    row.payload_json = json.dumps(payload_prev, ensure_ascii=False)
    row.updated_at = ahora
    try:
        _db().session.commit()
        return True
    except Exception:
        _db().session.rollback()
        return False


def crear_registro(
    *,
    agente_nombre: str,
    tipo: str,
    estado: str,
    titulo: str,
    cuerpo: str | None = None,
    severidad: str | None = None,
    codigo: str | None = None,
    dedupe_key: str | None = None,
    payload: dict | Any | None = None,
    venta_id: int | None = None,
    caja_id: int | None = None,
    tokens_total: int = 0,
    costo_api_usd: float = 0,
) -> int | None:
    """Inserta fila; si dedupe_key choca (índice parcial), retorna None."""
    AgenteEjecucion = _model()
    db = _db()
    if not asegurar_tabla():
        return None
    if dedupe_key and existe_dedupe_abierta(dedupe_key):
        return None
    row = AgenteEjecucion(
        agente_nombre=(agente_nombre or 'sistema')[:40],
        tipo=tipo[:32],
        estado=estado[:32],
        titulo=(titulo or 'Sin título')[:255],
        cuerpo=cuerpo,
        severidad=(severidad or '')[:16] or None,
        codigo=(codigo or '')[:64] or None,
        dedupe_key=(dedupe_key or '')[:128] or None,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        venta_id=venta_id,
        caja_id=caja_id,
        tokens_total=int(tokens_total or 0),
        costo_api_usd=float(costo_api_usd or 0),
    )
    try:
        db.session.add(row)
        db.session.commit()
        return row.id
    except Exception:
        db.session.rollback()
        return None


def existe_dedupe_abierta(dedupe_key: str) -> bool:
    AgenteEjecucion = _model()
    db = _db()
    if not dedupe_key or not asegurar_tabla():
        return False
    q = AgenteEjecucion.query.filter(
        AgenteEjecucion.dedupe_key == dedupe_key,
        AgenteEjecucion.estado.in_((EST_ALERTA_ABIERTA, EST_HITL_PENDIENTE)),
    )
    return db.session.query(q.exists()).scalar()


def existe_dedupe_registrada(dedupe_key: str) -> bool:
    """True si ya hubo insert con esa clave (cualquier estado)."""
    AgenteEjecucion = _model()
    db = _db()
    if not dedupe_key or not asegurar_tabla():
        return False
    q = AgenteEjecucion.query.filter(AgenteEjecucion.dedupe_key == dedupe_key)
    return db.session.query(q.exists()).scalar()


def listar_alertas_operativas(*, limite: int = 15, solo_abiertas: bool = False) -> list:
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return []
    q = AgenteEjecucion.query.filter_by(tipo=TIPO_ALERTA)
    if solo_abiertas:
        q = q.filter(AgenteEjecucion.estado.in_((EST_ALERTA_ABIERTA, EST_ALERTA_RECONOCIDA)))
    return q.order_by(AgenteEjecucion.created_at.desc()).limit(limite).all()


def contar_alertas_abiertas() -> int:
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return 0
    return (
        AgenteEjecucion.query.filter_by(tipo=TIPO_ALERTA, estado=EST_ALERTA_ABIERTA).count()
    )


def contar_hitl_pendientes() -> int:
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return 0
    return (
        AgenteEjecucion.query.filter_by(tipo=TIPO_BORRADOR, estado=EST_HITL_PENDIENTE).count()
    )


def obtener_por_id(registro_id: int):
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return None
    return AgenteEjecucion.query.get(registro_id)


def limpiar_alertas_operativas(
    *,
    modo: str = 'cerrar',
    solo_agente: str | None = None,
    usuario: str = 'admin_limpieza',
) -> dict[str, int]:
    """
    Vacía el feed Guardián: cierra o borra filas tipo alerta_operativa (abierta/reconocida).
    modo: 'cerrar' | 'borrar'
    """
    AgenteEjecucion = _model()
    db = _db()
    if not asegurar_tabla():
        return {'ok': False, 'cerradas': 0, 'borradas': 0, 'antes_abiertas': 0}

    q = AgenteEjecucion.query.filter(
        AgenteEjecucion.tipo == TIPO_ALERTA,
        AgenteEjecucion.estado.in_((EST_ALERTA_ABIERTA, EST_ALERTA_RECONOCIDA)),
    )
    if solo_agente:
        q = q.filter(AgenteEjecucion.agente_nombre == solo_agente[:40])

    filas = q.all()
    antes_abiertas = contar_alertas_abiertas()
    cerradas = 0
    borradas = 0
    modo = (modo or 'cerrar').strip().lower()

    if modo == 'borrar':
        for row in filas:
            db.session.delete(row)
            borradas += 1
    else:
        ahora = datetime.now()
        for row in filas:
            row.estado = EST_ALERTA_CERRADA
            row.updated_at = ahora
            row.reconocido_por = (usuario or '')[:120]
            row.fecha_reconocido = ahora
            cerradas += 1

    try:
        db.session.commit()
        return {
            'ok': True,
            'modo': modo,
            'cerradas': cerradas,
            'borradas': borradas,
            'antes_abiertas': antes_abiertas,
            'restantes_abiertas': contar_alertas_abiertas(),
        }
    except Exception:
        db.session.rollback()
        return {'ok': False, 'cerradas': 0, 'borradas': 0, 'antes_abiertas': antes_abiertas}


def transicion_alerta(registro_id: int, nuevo_estado: str, usuario: str) -> bool:
    row = obtener_por_id(registro_id)
    if not row or row.tipo != TIPO_ALERTA:
        return False
    ahora = datetime.now()
    row.estado = nuevo_estado[:32]
    row.updated_at = ahora
    if nuevo_estado == EST_ALERTA_RECONOCIDA:
        row.reconocido_por = (usuario or '')[:120]
        row.fecha_reconocido = ahora
    if nuevo_estado == EST_ALERTA_CERRADA:
        if not row.reconocido_por:
            row.reconocido_por = (usuario or '')[:120]
            row.fecha_reconocido = ahora
    try:
        _db().session.commit()
        return True
    except Exception:
        _db().session.rollback()
        return False


def metricas_telemetria_30d() -> list[dict]:
    """Consumo por agente (solo filas con tokens > 0)."""
    from sqlalchemy import func

    AgenteEjecucion = _model()
    db = _db()
    if not asegurar_tabla():
        return []
    desde = datetime.now() - timedelta(days=30)
    rows = (
        db.session.query(
            AgenteEjecucion.agente_nombre.label('agente'),
            func.coalesce(func.sum(AgenteEjecucion.tokens_total), 0).label('tokens'),
            func.coalesce(func.sum(AgenteEjecucion.costo_api_usd), 0).label('costo_usd'),
        )
        .filter(AgenteEjecucion.created_at >= desde)
        .group_by(AgenteEjecucion.agente_nombre)
        .order_by(func.sum(AgenteEjecucion.tokens_total).desc())
        .limit(6)
        .all()
    )
    return [{'agente': r.agente, 'tokens': int(r.tokens or 0), 'costo_usd': float(r.costo_usd or 0)} for r in rows]


def ultimo_borrador_hitl():
    AgenteEjecucion = _model()
    if not asegurar_tabla():
        return None
    return (
        AgenteEjecucion.query.filter_by(tipo=TIPO_BORRADOR)
        .order_by(AgenteEjecucion.id.desc())
        .first()
    )


def registrar_ejecucion_mentor(
    *,
    usuario_id: int,
    usuario_nombre: str,
    dedupe_key: str,
    titulo: str,
    cuerpo: str | None = None,
    codigo: str = 'mentor_consulta_academy',
    payload: dict | None = None,
    caja_id: int | None = None,
) -> int | None:
    """
    Telemetría LhexIA Academy — cada consulta/expansión de guía (sin bloqueo dedupe).
    Alimenta feed VERTEX con tipo log_ejecucion / estado ejecutado.
    """
    pill = dict(payload or {})
    pill.setdefault('usuario_id', usuario_id)
    pill.setdefault('usuario_nombre', (usuario_nombre or '')[:120])
    pill.setdefault('dedupe_key_componente', dedupe_key)
    pill.setdefault('origen', 'academy_sidebar')
    return crear_registro(
        agente_nombre='mentor',
        tipo=TIPO_LOG,
        estado=EST_LOG_EJECUTADO,
        titulo=(titulo or 'Consulta Academy')[:255],
        cuerpo=cuerpo,
        severidad='info',
        codigo=codigo,
        dedupe_key=None,
        payload=pill,
        caja_id=caja_id,
    )
