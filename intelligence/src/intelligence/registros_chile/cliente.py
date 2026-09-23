"""Cliente mínimo de la API oficial de registros históricos de FamilySearch."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

API_REGISTROS = "https://api.familysearch.org"
ACCEPT = "application/x-gedcomx-atom+json"
USER_AGENT = "intelligence-registros-chile/0.1"


class ErrorFamilySearch(Exception):
    def __init__(self, mensaje: str, estado: int | None = None):
        super().__init__(mensaje)
        self.estado = estado


class Cliente:
    def __init__(self, token: str, transport=None, base: str = API_REGISTROS, reintentos: int = 3, dormir=None):
        limpio = (token or "").strip()
        if not limpio:
            raise ErrorFamilySearch("Falta el token de FamilySearch. Ejecuta el comando login.")
        self.token = limpio
        self.transport = transport or transport_urllib
        self.base = base.rstrip("/")
        self.reintentos = reintentos
        self.dormir = dormir or _dormir

    def buscar_pagina(self, params: list[tuple[str, str]]) -> dict:
        url = f"{self.base}/platform/records/personas?{urlencode(params)}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": ACCEPT,
            "User-Agent": USER_AGENT,
        }
        espera = 1.0
        estado = None
        for intento in range(self.reintentos):
            estado, cuerpo, respuesta = self.transport(url, headers)
            if estado == 204:
                return {"entries": [], "results": 0}
            if estado == 200 and isinstance(cuerpo, dict):
                return cuerpo
            if estado in (429, 503) and intento + 1 < self.reintentos:
                self.dormir(_espera(respuesta, espera))
                espera = min(espera * 2, 30)
                continue
            break
        if estado == 401:
            raise ErrorFamilySearch(
                "FamilySearch rechazó la sesión. Vuelve a entrar con el comando login.",
                401,
            )
        raise ErrorFamilySearch(
            f"FamilySearch respondió {estado}. Revisa la sesión y los filtros de la consulta.",
            estado,
        )


def transport_urllib(url: str, headers: dict[str, str]) -> tuple[int, dict | None, dict]:
    solicitud = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(solicitud, timeout=60) as respuesta:
            return respuesta.status, _json(respuesta.read()), dict(respuesta.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, _json(exc.read()), dict(exc.headers.items()) if exc.headers else {}
    except urllib.error.URLError as exc:
        raise ErrorFamilySearch(f"No hubo conexión con FamilySearch: {exc.reason}") from exc


def _json(raw: bytes) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _espera(headers: dict, respaldo: float) -> float:
    valor = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return min(float(valor), 30.0)
    except (TypeError, ValueError):
        return respaldo


def _dormir(segundos: float) -> None:
    import time

    time.sleep(segundos)
