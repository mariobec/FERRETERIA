"""Auditoría ERP (erp_audit_log)."""
import json


def json_audit_chunk(data):
    if data is None:
        return None
    try:
        s = json.dumps(data, ensure_ascii=False, default=str)
        return s[:16000]
    except Exception:
        return (str(data) or '')[:8000]


def audit_log(evento, entidad_tipo, entidad_id=None, usuario=None, datos_antes=None, datos_despues=None, ip=None):
    """Registro de auditoría; no debe interrumpir el flujo principal."""
    from flask import request
    from flask_login import current_user

    import app as app_module

    try:
        if not app_module.app.config.get('_ERP_AUDIT_LOG_TABLE_OK'):
            return
        nom = (
            usuario
            or (current_user.nombre if getattr(current_user, 'is_authenticated', False) else '')
            or ''
        )[:120]
        addr = ip
        if addr is None and request:
            try:
                addr = (request.remote_addr or '')[:45] or None
            except Exception:
                addr = None
        row = app_module.ErpAuditLog(
            evento=(evento or '')[:80],
            entidad_tipo=(entidad_tipo or '')[:40],
            entidad_id=int(entidad_id) if entidad_id is not None else None,
            usuario=nom or None,
            ip=addr,
            datos_antes=json_audit_chunk(datos_antes),
            datos_despues=json_audit_chunk(datos_despues),
        )
        app_module.db.session.add(row)
    except Exception:
        app_module.app.logger.exception('erp_audit_log: evento=%s', evento)
