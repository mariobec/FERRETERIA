"""Perfiles de empresa emisor para cotizaciones (multi-membrete)."""
from __future__ import annotations

import json
import os
import re
from typing import Any

_CACHE: dict[str, Any] | None = None
_CACHE_MTIME: float | None = None
_EMPRESA_COT_MARKER_RE = re.compile(r"\[\[empresa_cot:([a-z0-9-]+)\]\]", re.IGNORECASE)

# Respaldo embebido si falta data/empresas_cotizacion.json (p. ej. exe sin recompilar).
_EMBEDDED: dict[str, Any] = {
    "default": "santo-domingo",
    "empresas": [
        {
            "id": "santo-domingo",
            "label": "Ferretería Santo Domingo (Chilemat)",
            "plantilla": "chilemat",
            "nombre_comercial": "Ferretería Santo Domingo",
            "razon_social": "Luis Gastón Rivera Pérez",
            "eslogan": "Materiales para Construcción · Ferretería Industrial · Herramientas · Seguridad · Pinturas",
            "marca_linea1": "FERRETERÍA",
            "marca_linea2": "SANTO DOMINGO",
            "rut_emisor": "8.054.120-1",
            "telefono": "(41) 264 5574",
            "correo": "ferreteria426@gmail.com",
            "direccion": "C. Matriz Arturo Prat n°426 - Florida\nBodega Arturo Prat n°439",
        },
        {
            "id": "transportes-st-julliet",
            "label": "Transportes Sta JULLIET",
            "plantilla": "transportes",
            "nombre_comercial": "Transportes Sta JULLIET",
            "razon_social": "JULIO IVAN RIVERA PEREZ EIRL",
            "eslogan": "venta de aridos y fletes",
            "marca_linea1": "TRANSPORTES",
            "marca_linea2": "Sta JULLIET",
            "rut_emisor": "76.873.527-1",
            "telefono": "989145920",
            "correo": "aridosjr1963@gmail.com",
            "cuenta_banco": "CHEQUERA ELECTRONICA: 51270010532",
            "banco": "Banco Estado",
            "logo_img": "img/cot_transportes_julliet_v5.png",
            "color_primario": "#c41e3a",
            "color_acento": "#1a1a1a",
        },
    ],
}


def _ruta_config() -> str:
    from flask import current_app

    return os.path.join(current_app.root_path, "data", "empresas_cotizacion.json")


def _cargar_raw() -> dict[str, Any]:
    global _CACHE, _CACHE_MTIME
    ruta = _ruta_config()
    mtime: float | None = None
    try:
        if os.path.isfile(ruta):
            mtime = os.path.getmtime(ruta)
    except Exception:
        mtime = None
    if _CACHE is not None and _CACHE_MTIME == mtime:
        return _CACHE
    data: dict[str, Any] = {"default": "santo-domingo", "empresas": []}
    if os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                parsed = json.load(f) or {}
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            pass
    if not (data.get("empresas") or []):
        data = dict(_EMBEDDED)
    _CACHE = data
    _CACHE_MTIME = mtime
    return data


def invalidar_cache_empresas_cotizacion() -> None:
    global _CACHE, _CACHE_MTIME
    _CACHE = None
    _CACHE_MTIME = None


def empresa_cotizacion_default_id() -> str:
    raw = _cargar_raw()
    default = (raw.get("default") or "santo-domingo").strip()
    ids = {str(e.get("id") or "").strip() for e in (raw.get("empresas") or []) if isinstance(e, dict)}
    if default in ids:
        return default
    if ids:
        return next(iter(ids))
    return "santo-domingo"


def listar_empresas_cotizacion() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for e in _cargar_raw().get("empresas") or []:
        if not isinstance(e, dict):
            continue
        eid = (e.get("id") or "").strip()
        if not eid:
            continue
        out.append(
            {
                "id": eid,
                "label": (e.get("label") or e.get("nombre_comercial") or eid).strip(),
                "plantilla": (e.get("plantilla") or "chilemat").strip(),
            }
        )
    return out


def listar_perfiles_empresas_cotizacion() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in _cargar_raw().get("empresas") or []:
        if isinstance(e, dict) and (e.get("id") or "").strip():
            out.append(dict(e))
    return out


def slug_desde_notas_cotizacion(notas: str | None) -> str | None:
    if not notas:
        return None
    m = _EMPRESA_COT_MARKER_RE.search(str(notas))
    if not m:
        return None
    return (m.group(1) or "").strip() or None


def notas_cotizacion_visibles(notas: str | None) -> str:
    if not notas:
        return ""
    return _EMPRESA_COT_MARKER_RE.sub("", str(notas)).strip()


def aplicar_marker_empresa_notas(notas: str | None, slug: str | None) -> str:
    limpio = notas_cotizacion_visibles(notas)
    s = (slug or "").strip()
    if not s or s == empresa_cotizacion_default_id():
        return limpio
    prefix = f"[[empresa_cot:{s}]]"
    return f"{prefix}\n{limpio}" if limpio else prefix


def extraer_empresa_slug_cot(cot) -> str | None:
    if cot is None:
        return None
    slug = (getattr(cot, "empresa_cotizacion", None) or "").strip()
    notas_slug = slug_desde_notas_cotizacion(getattr(cot, "notas", None))
    # Marker en notas gana si apunta a Transportes (exe viejo sin columna o columna vacía/errónea)
    if notas_slug == "transportes-st-julliet":
        return notas_slug
    if slug:
        return slug
    return notas_slug


def resolver_empresa_cotizacion(slug: str | None = None) -> dict[str, Any]:
    """Perfil emisor para PDF/formulario. Fallback: empresa_config global (Chilemat)."""
    from app import obtener_config_empresa

    raw = _cargar_raw()
    wanted = (slug or "").strip() or empresa_cotizacion_default_id()
    perfil: dict[str, Any] | None = None
    for e in raw.get("empresas") or []:
        if isinstance(e, dict) and (e.get("id") or "").strip() == wanted:
            perfil = dict(e)
            break
    if perfil is None:
        for e in raw.get("empresas") or []:
            if isinstance(e, dict) and (e.get("id") or "").strip() == empresa_cotizacion_default_id():
                perfil = dict(e)
                break
    if perfil is None:
        cfg = obtener_config_empresa()
        perfil = {
            "id": "santo-domingo",
            "label": cfg.get("nombre_comercial") or "Ferretería Santo Domingo",
            "plantilla": "chilemat",
            "nombre_comercial": cfg.get("nombre_comercial") or "",
            "razon_social": cfg.get("razon_social") or "",
            "eslogan": cfg.get("eslogan") or "",
            "marca_linea1": "FERRETERÍA",
            "marca_linea2": "SANTO DOMINGO",
            "rut_emisor": cfg.get("rut_emisor") or "",
            "telefono": cfg.get("telefono") or "",
            "correo": cfg.get("correo") or "",
            "direccion": cfg.get("direccion") or "",
        }
    perfil.setdefault("plantilla", "chilemat")
    perfil.setdefault("id", wanted or empresa_cotizacion_default_id())
    if "label" not in perfil:
        perfil["label"] = (perfil.get("nombre_comercial") or perfil.get("id") or "").strip()
    return perfil


def resolver_empresa_cotizacion_cot(cot) -> dict[str, Any]:
    slug = extraer_empresa_slug_cot(cot)
    return resolver_empresa_cotizacion(slug)


def normalizar_empresa_cotizacion_id(slug: str | None) -> str:
    s = (slug or "").strip()
    ids = {x["id"] for x in listar_empresas_cotizacion()}
    if s in ids:
        return s
    return empresa_cotizacion_default_id()
