"""Inicio de sesión OAuth con PKCE. La contraseña queda solo en FamilySearch."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from intelligence.registros_chile.cliente import ErrorFamilySearch

AUTORIZACION = "https://ident.familysearch.org/cis-web/oauth2/v3/authorization"
TOKEN_URL = "https://ident.familysearch.org/cis-web/oauth2/v3/token"
RUTA_CALLBACK = "/callback"


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def nuevo_verifier() -> str:
    return secrets.token_urlsafe(48)


def url_autorizacion(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTORIZACION}?{query}"


def redirect_uri(puerto: int) -> str:
    return f"http://127.0.0.1:{puerto}{RUTA_CALLBACK}"


def ruta_token() -> Path:
    base = os.environ.get("INTELLIGENCE_TOKEN_DIR", "").strip()
    directorio = Path(base) if base else Path.home() / ".config" / "intelligence-registros-chile"
    directorio.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directorio, 0o700)
    except OSError:
        pass
    return directorio / "token.json"


def guardar_token(data: dict) -> Path:
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise ErrorFamilySearch("FamilySearch no entregó un token de acceso.")
    payload = {
        "access_token": token,
        "token_type": data.get("token_type") or "Bearer",
        "obtenido_en": int(time.time()),
    }
    if data.get("expires_in") is not None:
        payload["expires_in"] = data["expires_in"]
    destino = ruta_token()
    destino.write_text(json.dumps(payload), encoding="utf-8")
    try:
        os.chmod(destino, 0o600)
    except OSError:
        pass
    return destino


def leer_token() -> str:
    entorno = os.environ.get("FAMILYSEARCH_ACCESS_TOKEN", "").strip()
    if entorno:
        return entorno
    destino = ruta_token()
    if not destino.exists():
        return ""
    try:
        data = json.loads(destino.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("access_token") or "").strip()


def esperar_codigo(puerto: int, state_esperado: str, timeout: int = 180) -> str:
    resultado: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != RUTA_CALLBACK:
                self._html(404, "Esta dirección no es el retorno de FamilySearch.")
                return
            qs = parse_qs(parsed.query)
            if qs.get("state", [""])[0] != state_esperado:
                resultado["error"] = "state"
                self._html(400, "La sesión no coincide. Cierra esta ventana y vuelve a intentar.")
                return
            if qs.get("error"):
                resultado["error"] = qs["error"][0]
                self._html(400, "FamilySearch no autorizó el acceso.")
                return
            code = qs.get("code", [""])[0]
            if not code:
                resultado["error"] = "sin-codigo"
                self._html(400, "No llegó el código de autorización.")
                return
            resultado["code"] = code
            self._html(200, "Listo. Puedes volver a la terminal.")

        def log_message(self, fmt: str, *args) -> None:
            return

        def _html(self, status: int, mensaje: str) -> None:
            cuerpo = (
                "<!doctype html><meta charset=utf-8><title>FamilySearch</title><p>"
                + html.escape(mensaje)
                + "</p>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", puerto), Callback)
    except OSError as exc:
        raise ErrorFamilySearch(f"No pude abrir el puerto local {puerto}: {exc}") from exc
    server.timeout = 1
    limite = time.time() + timeout
    try:
        while "code" not in resultado and "error" not in resultado:
            if time.time() > limite:
                raise ErrorFamilySearch("Se agotó el tiempo de espera del inicio de sesión.")
            server.handle_request()
    finally:
        server.server_close()
    if "code" not in resultado:
        raise ErrorFamilySearch("No se pudo completar el inicio de sesión en FamilySearch.")
    return resultado["code"]


def pedir_token(client_id: str, redirect_uri: str, code: str, verifier: str, transport=None) -> dict:
    cuerpo = urlencode(
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": verifier,
        }
    )
    enviar = transport or _post_urllib
    estado, data = enviar(TOKEN_URL, cuerpo)
    if estado != 200 or not isinstance(data, dict) or not data.get("access_token"):
        raise ErrorFamilySearch(
            "FamilySearch no entregó la sesión. Revisa la app key y que la redirect URI esté registrada.",
            estado,
        )
    return data


def _post_urllib(url: str, cuerpo: str) -> tuple[int, dict | None]:
    solicitud = urllib.request.Request(
        url,
        data=cuerpo.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "intelligence-registros-chile/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=60) as respuesta:
            return respuesta.status, _leer_json(respuesta.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _leer_json(exc.read())
    except urllib.error.URLError as exc:
        raise ErrorFamilySearch(f"No hubo conexión con FamilySearch: {exc.reason}") from exc


def _leer_json(raw: bytes) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
