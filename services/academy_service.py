"""LhexIA Academy — consultas DB, contexto Mentor y telemetría."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from services.vertex_pildora_contract import parse_payload_json

from services.academy_format import INVARIANTE_FINANCIERA, formatear_contenido_academy_html, formatear_texto_plano
from services.agente_ejecuciones_service import EST_LOG_EJECUTADO, TIPO_LOG, registrar_ejecucion_mentor
from services.vertex_mentor_service import (
    ACADEMY_GUIDES,
    _caja_dia_anterior_abierta,
    _normalizar_path,
    detectar_contexto_pantalla,
    listar_guias_biblioteca,
    resolver_pildora_prioritaria,
)
from services.vertex_pildora_contract import (
    TENANT_SANTO_DOMINGO,
    _MODULO_MENTOR,
    build_pildora,
)

CATEGORIA_POR_CONTEXTO: dict[str, str] = {
    'pos': 'pos',
    'caja': 'caja',
    'cerrar_caja': 'caja',
    'cambios_devoluciones': 'caja',
    'caja_dia_anterior': 'caja',
    'abrir_caja': 'caja',
    'movimiento_caja': 'caja',
    'general': 'pos',
}

PRACTICAR_HREF_POR_DEDUPE: dict[str, str] = {
    'academy:manual_v2:seccion_a_pos_semaforos': '/punto_venta',
    'academy:manual_v2:seccion_b_arqueo_ciego_plat11': '/cerrar_caja',
    'academy:manual_v2:seccion_c_telemetria_v3': '/inventario/enrolamiento',
    'academy:manual_v2:seccion_d_apertura_caja': '/abrir_caja',
    'academy:manual_v2:seccion_e_movimiento_caja': '/movimiento_caja',
    'academy:manual_v2:seccion_f_cobro_vales': '/caja/vales_pendientes',
    'academy:manual_v2:seccion_g_tablet_bodega': '/bodega/enrolador',
    'academy:manual_v2:seccion_h_salud_inventario': '/inventario/salud',
    'academy:pos:emitir_vale': '/punto_venta',
    'academy:caja:cobrar_vale': '/caja/vales_pendientes',
    'academy:caja:cambios_devoluciones': '/caja/cambios',
    'academy:caja:caja_dia_anterior': '/cerrar_caja',
    'academy:caja:abrir_cerrar': '/abrir_caja',
    'academy:caja:apertura_turno': '/abrir_caja',
    'academy:caja:movimiento_extra': '/movimiento_caja',
}

ANCLA_POR_CATEGORIA: dict[str, str] = {
    'pos': '/academy#academy-pos',
    'caja': '/academy#academy-caja',
    'bodega': '/academy#academy-bodega',
}

ANCLA_POR_DEDUPE: dict[str, str] = {
    'academy:manual_v2:seccion_a_pos_semaforos': '/academy#academy-pos',
    'academy:manual_v2:seccion_b_arqueo_ciego_plat11': '/academy#academy-caja',
    'academy:manual_v2:seccion_c_telemetria_v3': '/academy#academy-bodega',
    'academy:manual_v2:seccion_d_apertura_caja': '/academy#academy-caja',
    'academy:manual_v2:seccion_e_movimiento_caja': '/academy#academy-caja',
    'academy:manual_v2:seccion_f_cobro_vales': '/academy#academy-caja',
    'academy:manual_v2:seccion_g_tablet_bodega': '/academy#academy-bodega',
    'academy:manual_v2:seccion_h_salud_inventario': '/academy#academy-bodega',
}


def resolver_practicar_href(*, dedupe_key: str, category: str) -> str:
    key = (dedupe_key or '').strip()
    if key in PRACTICAR_HREF_POR_DEDUPE:
        return PRACTICAR_HREF_POR_DEDUPE[key]
    if category == 'caja':
        return '/caja/vales_pendientes'
    if category == 'bodega':
        return '/inventario/enrolamiento'
    return '/punto_venta'

PERMISO_POR_ROL_ACADEMY: dict[str, str] = {
    'vendedor': 'pos_emitir_vale',
    'cajera': 'caja_cobrar_vale',
    'cajero': 'caja_cobrar_vale',
    'bodega': 'bodega_operador',
    'bodeguero': 'bodega_operador',
    'admin': 'gestionar_usuarios',
    'administrador': 'gestionar_usuarios',
    'supervisor': 'gestionar_usuarios',
}

CAMINO_ACADEMY_META: dict[str, dict[str, str]] = {
    'pos': {
        'titulo': 'Ruta del Vendedor',
        'icon': 'fa-cash-register',
        'ancla_id': 'academy-pos',
        'descripcion': 'POS, semáforos, filtros de búsqueda y emisión de vales.',
    },
    'caja': {
        'titulo': 'Ruta del Cajero',
        'icon': 'fa-hand-holding-usd',
        'ancla_id': 'academy-caja',
        'descripcion': 'Apertura, cobro de vales, movimientos, arqueo y cierre.',
    },
    'bodega': {
        'titulo': 'Ruta del Bodeguero',
        'icon': 'fa-warehouse',
        'ancla_id': 'academy-bodega',
        'descripcion': 'Enrolamiento, tablet + pistola y salud del inventario.',
    },
}

ATAJOS_POR_CATEGORIA: dict[str, list[dict[str, str]]] = {
    'pos': [
        {'tecla': 'F2', 'accion': 'Foco búsqueda de producto / Invocación de Escáner universal'},
        {'tecla': 'F8', 'accion': 'Emitir vale de venta pendiente (Bloqueo de caja diferido)'},
        {'tecla': 'Esc', 'accion': 'Cerrar modal o cancelar línea actual'},
    ],
    'caja': [
        {'tecla': 'Ctrl+Enter', 'accion': 'Confirmar arqueo / cobro'},
        {'tecla': 'Esc', 'accion': 'Cerrar modal o cancelar línea actual'},
        {'tecla': 'F5', 'accion': 'Refrescar cola de vales pendientes'},
    ],
    'bodega': [
        {'tecla': 'Enter', 'accion': 'Confirmar código escaneado'},
        {'tecla': 'Esc', 'accion': 'Cerrar panel u overlay'},
        {'tecla': 'F2', 'accion': 'Foco búsqueda maestro (Caso B)'},
    ],
}


def resolver_categoria_academy(*, url: str | None, contexto: str) -> str:
    path = _normalizar_path(url)
    if any(x in path for x in ('/bodega', '/enrolamiento', '/recepcion', '/inventario')):
        return 'bodega'
    return CATEGORIA_POR_CONTEXTO.get(contexto, 'pos')


def _usuario_tiene_permiso_academy(rol_requerido: str) -> bool:
    from app import usuario_tiene_permiso

    rol = (rol_requerido or 'vendedor').strip().lower()
    perm = PERMISO_POR_ROL_ACADEMY.get(rol, rol)
    if usuario_tiene_permiso('gestionar_usuarios'):
        return True
    return usuario_tiene_permiso(perm)


def _parse_completed_steps(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data] if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _dump_completed_steps(steps: list[str]) -> str:
    return json.dumps(steps)


def _pasos_detalle(pasos: list[str], completed: set[str]) -> list[dict[str, Any]]:
    return [
        {'id': f'step-{i}', 'texto': p, 'completed': f'step-{i}' in completed}
        for i, p in enumerate(pasos)
    ]


def obtener_mapa_progreso_usuario(user_id: int) -> dict[str, dict[str, Any]]:
    from app import UserAcademyProgress, _asegurar_tabla_user_academy_progress

    _asegurar_tabla_user_academy_progress()
    rows = UserAcademyProgress.query.filter_by(user_id=int(user_id)).all()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        steps = _parse_completed_steps(row.completed_steps_json)
        out[row.dedupe_key] = {
            'completed_steps': steps,
            'completed_at': row.completed_at.isoformat() if row.completed_at else None,
            'all_complete': row.completed_at is not None,
        }
    return out


def enriquecer_item_progreso(item: dict[str, Any], progress_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = (item.get('dedupe_key') or '').strip()
    prog = progress_map.get(key) or {}
    completed = set(prog.get('completed_steps') or [])
    pasos = [str(p) for p in (item.get('pasos') or [])]
    if pasos:
        item['pasos_detalle'] = _pasos_detalle(pasos, completed)
    item['progress_complete'] = bool(prog.get('all_complete'))
    cat = item.get('category') or (
        'pos' if ':pos:' in key or 'seccion_a_' in key else 'bodega' if ':bodega' in key or 'seccion_c_' in key else 'caja'
    )
    item['practicar_href'] = resolver_practicar_href(dedupe_key=key, category=cat)
    return item


def _resolver_pasos_guia(dedupe_key: str) -> list[str]:
    art = buscar_articulo_por_dedupe(dedupe_key)
    if art:
        return _extraer_pasos(art.content_markdown or art.summary)
    guia = next((g for g in ACADEMY_GUIDES if g.get('dedupe_key') == dedupe_key), None)
    if guia:
        return [str(p) for p in (guia.get('pasos') or [])]
    return []


def guardar_paso_academy(
    *,
    user_id: int,
    dedupe_key: str,
    step_id: str,
    checked: bool,
) -> dict[str, Any]:
    from app import UserAcademyProgress, _asegurar_tabla_academy_articles, db
    from app import _asegurar_tabla_user_academy_progress

    _asegurar_tabla_academy_articles()
    _asegurar_tabla_user_academy_progress()

    dedupe_key = (dedupe_key or '').strip()[:128]
    step_id = (step_id or '').strip()[:32]
    if not dedupe_key or not step_id:
        return {'ok': False, 'error': 'dedupe_key_o_step_id_requerido'}

    pasos_validos = _resolver_pasos_guia(dedupe_key)
    if not pasos_validos:
        return {'ok': False, 'error': 'guia_sin_pasos'}

    valid_ids = {f'step-{i}' for i in range(len(pasos_validos))}
    if step_id not in valid_ids:
        return {'ok': False, 'error': 'step_id_invalido'}

    art = buscar_articulo_por_dedupe(dedupe_key)
    row = UserAcademyProgress.query.filter_by(user_id=int(user_id), dedupe_key=dedupe_key).first()
    if row is None:
        row = UserAcademyProgress(
            user_id=int(user_id),
            article_id=art.id if art else None,
            dedupe_key=dedupe_key,
            completed_steps_json=_dump_completed_steps([]),
        )
        db.session.add(row)

    steps = _parse_completed_steps(row.completed_steps_json)
    if checked:
        if step_id not in steps:
            steps.append(step_id)
    else:
        steps = [s for s in steps if s != step_id]

    row.completed_steps_json = _dump_completed_steps(steps)
    row.updated_at = datetime.now()
    all_complete = valid_ids.issubset(set(steps))
    if all_complete:
        row.completed_at = row.completed_at or datetime.now()
    else:
        row.completed_at = None

    db.session.commit()
    return {
        'ok': True,
        'dedupe_key': dedupe_key,
        'step_id': step_id,
        'checked': checked,
        'completed_steps': steps,
        'all_complete': all_complete,
        'completed_at': row.completed_at.isoformat() if row.completed_at else None,
    }


def _extraer_pasos(texto: str | None) -> list[str]:
    if not texto:
        return []
    pasos: list[str] = []
    for line in texto.splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#'):
            continue
        m = re.match(r'^(\d+[\.\)]\s*|-\s*|\*\s*)(.+)$', raw)
        if m:
            pasos.append(m.group(2).strip())
        elif raw.startswith('|') or raw.startswith('---'):
            continue
    return pasos[:12]


def articulo_a_dict(art, *, progress_map: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    md = art.content_markdown or ''
    summary = art.summary or ''
    pasos = _extraer_pasos(md or summary)
    item = {
        'id': art.id,
        'dedupe_key': art.dedupe_key,
        'category': art.category,
        'title': art.title,
        'titulo': art.title,
        'summary': formatear_texto_plano(summary),
        'summary_html': str(formatear_contenido_academy_html(summary)),
        'content_markdown': formatear_texto_plano(md),
        'content_html': str(formatear_contenido_academy_html(md)),
        'video_url': art.video_url,
        'permissions_required': art.permissions_required,
        'pasos': pasos,
        'ancla_ayuda': ANCLA_POR_DEDUPE.get(art.dedupe_key, ANCLA_POR_CATEGORIA.get(art.category, '/academy#lhexia-academy')),
        'practicar_href': resolver_practicar_href(dedupe_key=art.dedupe_key, category=art.category),
    }
    if progress_map is not None:
        enriquecer_item_progreso(item, progress_map)
    return item


def _extraer_dedupe_desde_payload_mentor(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ('dedupe_key', 'dedupe_key_componente'):
        raw = (payload.get(key) or '').strip()
        if raw:
            return raw[:128]
    snap = payload.get('kpi_snapshot') if isinstance(payload.get('kpi_snapshot'), dict) else {}
    for key in ('dedupe_key', 'pildora_dedupe_key'):
        raw = (snap.get(key) or '').strip()
        if raw:
            return raw[:128]
    return None


def obtener_dedupes_completados_usuario(user_id: int, *, dias: int = 90) -> set[str]:
    """Artículos/guías «vistos» vía telemetría mentor o checklist completado (LX-ACAD-2)."""
    from app import AgenteEjecucion, UserAcademyProgress, _asegurar_tabla_agente_ejecuciones
    from app import _asegurar_tabla_user_academy_progress
    from services.agente_ejecuciones_service import EST_LOG_EJECUTADO, TIPO_LOG

    _asegurar_tabla_agente_ejecuciones()
    _asegurar_tabla_user_academy_progress()

    out: set[str] = set()
    cutoff = datetime.now() - timedelta(days=max(1, int(dias)))

    prog_rows = UserAcademyProgress.query.filter_by(user_id=int(user_id)).all()
    for row in prog_rows:
        if row.completed_at is not None:
            out.add(row.dedupe_key)

    rows = (
        AgenteEjecucion.query.filter(
            AgenteEjecucion.agente_nombre == 'mentor',
            AgenteEjecucion.tipo == TIPO_LOG,
            AgenteEjecucion.estado == EST_LOG_EJECUTADO,
            AgenteEjecucion.created_at >= cutoff,
        )
        .all()
    )
    for row in rows:
        payload = parse_payload_json(row.payload_json)
        if int(payload.get('usuario_id') or 0) not in (0, int(user_id)):
            if payload.get('usuario_id') is not None:
                continue
        dedupe = _extraer_dedupe_desde_payload_mentor(payload)
        if dedupe:
            out.add(dedupe)
    return out


def obtener_progreso_academy_usuario(user_id: int, *, dias: int = 90) -> dict[str, dict[str, Any]]:
    """Progreso por categoría (pos/caja/bodega) para hub /academy."""
    articulos = listar_manual_v2_para_ayuda()
    completados = obtener_dedupes_completados_usuario(user_id, dias=dias)
    por_cat: dict[str, dict[str, Any]] = {
        cat: {'total': 0, 'completados': 0, 'pct': 0, 'dedupe_keys': []}
        for cat in CAMINO_ACADEMY_META
    }
    for art in articulos:
        cat = art.get('category') or 'pos'
        if cat not in por_cat:
            por_cat[cat] = {'total': 0, 'completados': 0, 'pct': 0, 'dedupe_keys': []}
        por_cat[cat]['total'] += 1
        dk = art.get('dedupe_key') or ''
        por_cat[cat]['dedupe_keys'].append(dk)
        if dk in completados or art.get('progress_complete'):
            por_cat[cat]['completados'] += 1
    for cat, data in por_cat.items():
        total = int(data['total'])
        done = int(data['completados'])
        data['pct'] = int(round(100 * done / total)) if total else 0
    return por_cat


def construir_caminos_academy_hub(user_id: int | None = None) -> list[dict[str, Any]]:
    """Tres caminos (vendedor / cajero / bodeguero) con artículos y progreso."""
    articulos = listar_manual_v2_para_ayuda()
    completados: set[str] = set()
    if user_id:
        completados = obtener_dedupes_completados_usuario(int(user_id))
        progress_map = obtener_mapa_progreso_usuario(int(user_id))
    else:
        progress_map = {}

    por_cat: dict[str, list[dict[str, Any]]] = {k: [] for k in CAMINO_ACADEMY_META}
    for art in articulos:
        item = dict(art)
        dk = item.get('dedupe_key') or ''
        if user_id and dk in progress_map:
            enriquecer_item_progreso(item, progress_map)
        item['completado'] = dk in completados or bool(item.get('progress_complete'))
        cat = item.get('category') or 'pos'
        por_cat.setdefault(cat, []).append(item)

    caminos: list[dict[str, Any]] = []
    for cat in ('pos', 'caja', 'bodega'):
        arts = por_cat.get(cat) or []
        if not arts:
            continue
        meta = CAMINO_ACADEMY_META[cat]
        total = len(arts)
        done = sum(1 for a in arts if a.get('completado'))
        caminos.append(
            {
                'category': cat,
                'titulo': meta['titulo'],
                'icon': meta['icon'],
                'ancla_id': meta['ancla_id'],
                'descripcion': meta['descripcion'],
                'articulos': arts,
                'completados': done,
                'total': total,
                'pct': int(round(100 * done / total)) if total else 0,
            }
        )
    return caminos


def enriquecer_pildora_mentor(pildora: dict[str, Any] | None, *, categoria: str) -> dict[str, Any] | None:
    """LX-ACAD-1: practicar_href en píldora prioritaria del sidebar."""
    if not pildora:
        return pildora
    pill = dict(pildora)
    snap = pill.get('kpi_snapshot') if isinstance(pill.get('kpi_snapshot'), dict) else {}
    dk = (
        (snap.get('dedupe_key') or '').strip()
        or (snap.get('pildora_dedupe_key') or '').strip()
        or (pill.get('dedupe_key') or '').strip()
    )
    href = pill.get('nav_href') or pill.get('practicar_href')
    if dk:
        href = resolver_practicar_href(dedupe_key=dk, category=categoria)
    elif not href:
        href = resolver_practicar_href(dedupe_key='', category=categoria)
    pill['practicar_href'] = href
    if not pill.get('nav_href'):
        pill['nav_href'] = href
    return pill


def listar_manual_v2_para_ayuda() -> list[dict[str, Any]]:
    """Artículos Manual V2 para la página /ayuda (LhexIA Academy)."""
    from app import AcademyArticle, _asegurar_tabla_academy_articles

    _asegurar_tabla_academy_articles()
    rows = AcademyArticle.query.order_by(AcademyArticle.id.asc()).all()
    out: list[dict[str, Any]] = []
    for art in rows:
        if not _usuario_tiene_permiso_academy(art.permissions_required or 'vendedor'):
            continue
        item = articulo_a_dict(art)
        item['ancla'] = ANCLA_POR_DEDUPE.get(art.dedupe_key, f'/academy#academy-{art.category}')
        out.append(item)
    return out


def listar_articulos_por_categoria(category: str) -> list:
    from app import AcademyArticle

    rows = (
        AcademyArticle.query.filter_by(category=category)
        .order_by(AcademyArticle.id.asc())
        .all()
    )
    return [r for r in rows if _usuario_tiene_permiso_academy(r.permissions_required or 'vendedor')]


def buscar_articulo_por_dedupe(dedupe_key: str):
    from app import AcademyArticle

    key = (dedupe_key or '').strip()
    if not key:
        return None
    return AcademyArticle.query.filter_by(dedupe_key=key).first()


def _merge_biblioteca(
    articulos_db: list[dict[str, Any]],
    contexto: str,
    *,
    caja_dia_anterior: bool,
    progress_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    seen = {a['dedupe_key'] for a in articulos_db}
    out = list(articulos_db)
    for g in listar_guias_biblioteca(contexto, caja_dia_anterior=caja_dia_anterior):
        if g.get('dedupe_key') not in seen:
            item = dict(g)
            if progress_map is not None:
                enriquecer_item_progreso(item, progress_map)
            out.append(item)
            seen.add(g.get('dedupe_key'))
    return out


def construir_contexto_mentor_db(*, url: str | None) -> dict[str, Any]:
    from app import _asegurar_tabla_academy_articles

    _asegurar_tabla_academy_articles()

    progress_map: dict[str, dict[str, Any]] = {}
    try:
        from flask_login import current_user

        if current_user is not None and getattr(current_user, 'is_authenticated', False):
            progress_map = obtener_mapa_progreso_usuario(int(current_user.id))
    except RuntimeError:
        pass

    contexto = detectar_contexto_pantalla(url)
    categoria = resolver_categoria_academy(url=url, contexto=contexto)
    caja_ant, _ = _caja_dia_anterior_abierta()
    pildora = enriquecer_pildora_mentor(
        resolver_pildora_prioritaria(contexto, caja_dia_anterior=caja_ant),
        categoria=categoria,
    )

    articulos = [articulo_a_dict(a, progress_map=progress_map) for a in listar_articulos_por_categoria(categoria)]
    articulo_principal = articulos[0] if articulos else None
    biblioteca = _merge_biblioteca(
        articulos, contexto, caja_dia_anterior=caja_ant, progress_map=progress_map
    )
    atajos = ATAJOS_POR_CATEGORIA.get(categoria, ATAJOS_POR_CATEGORIA['pos'])

    return {
        'ok': True,
        'contexto': contexto,
        'categoria_academy': categoria,
        'url': _normalizar_path(url) or (url or ''),
        'caja_dia_anterior': caja_ant,
        'articulo_principal': articulo_principal,
        'pildora_prioritaria': pildora,
        'biblioteca': biblioteca,
        'atajos_teclado': atajos,
        'invariante_financiera': INVARIANTE_FINANCIERA,
        'agente_producto': _MODULO_MENTOR,
        'progreso_usuario': progress_map,
    }


def registrar_lectura_academy(
    *,
    usuario_id: int,
    usuario_nombre: str,
    dedupe_key: str,
    accion: str = 'cargar',
    url: str | None = None,
) -> dict[str, Any]:
    """Inserta telemetría en agente_ejecuciones (estado ejecutado)."""
    from app import _asegurar_tabla_academy_articles, _asegurar_tabla_agente_ejecuciones

    _asegurar_tabla_agente_ejecuciones()
    _asegurar_tabla_academy_articles()

    dedupe_key = (dedupe_key or '').strip()[:128]
    if not dedupe_key:
        return {'ok': False, 'error': 'dedupe_key_requerido'}

    art = buscar_articulo_por_dedupe(dedupe_key)
    if art:
        titulo = art.title
        pasos_txt = '\n'.join(f'• {p}' for p in _extraer_pasos(art.content_markdown or art.summary))
    else:
        guia = next((g for g in ACADEMY_GUIDES if g['dedupe_key'] == dedupe_key), None)
        titulo = guia['titulo'] if guia else f'Consulta Academy · {dedupe_key}'
        pasos_txt = '\n'.join(f'• {p}' for p in (guia.get('pasos') if guia else []) or [])

    _, caja_id = _caja_dia_anterior_abierta()
    contexto = detectar_contexto_pantalla(url)
    categoria = resolver_categoria_academy(url=url, contexto=contexto)

    pill = build_pildora(
        tenant_id=TENANT_SANTO_DOMINGO,
        tenant_slug='santo-domingo',
        cliente_nombre='Ferretería Santo Domingo',
        agente_producto=_MODULO_MENTOR,
        agente_nombre='mentor',
        codigo='mentor_consulta_academy',
        severidad='info',
        titulo=titulo,
        mensaje_corto=f'Academy · {accion} · {dedupe_key}',
        modo='live',
        origen='academy_sidebar',
        semaforo_dominio=categoria if categoria in ('pos', 'caja', 'bodega') else 'caja',
        kpi_snapshot={
            'dedupe_key': dedupe_key,
            'accion': accion,
            'contexto_pantalla': contexto,
            'categoria_academy': categoria,
            'usuario_id': usuario_id,
            'articulo_id': art.id if art else None,
        },
    )
    pill['dedupe_key'] = dedupe_key
    pill['accion'] = accion
    pill['url_origen'] = _normalizar_path(url)

    reg_id = registrar_ejecucion_mentor(
        usuario_id=usuario_id,
        usuario_nombre=usuario_nombre,
        dedupe_key=dedupe_key,
        titulo=titulo,
        cuerpo=pasos_txt or None,
        codigo='mentor_consulta_academy',
        payload=pill,
        caja_id=caja_id,
    )
    return {
        'ok': reg_id is not None,
        'registro_id': reg_id,
        'estado': EST_LOG_EJECUTADO,
        'tipo': TIPO_LOG,
        'dedupe_key': dedupe_key,
    }
