#!/usr/bin/env python3
"""Guarda URL fija del ERP en data/empresa_config.json (red local WiFi)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def _ruta_config():
    return os.path.join(ROOT, "data", "empresa_config.json")


def _normalizar_url(raw: str) -> str:
    u = (raw or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = f"http://{u}"
    u = u.rstrip("/")
    if not re.match(r"^https?://[^\s/]+(:\d+)?$", u, re.I):
        raise ValueError(f"URL no válida: {raw!r} (ej: http://192.168.1.100:5000)")
    return u


def _ips_lan():
    try:
        import subprocess

        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 | "
                "Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' "
                "-and $_.IPAddress -notlike '169.254.*' } | "
                "Select-Object -ExpandProperty IPAddress -Unique",
            ],
            text=True,
            timeout=15,
        )
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="Configurar URL fija LAN del ERP")
    parser.add_argument("url", nargs="?", help="Ej: http://192.168.1.100:5000")
    parser.add_argument("--mostrar", action="store_true", help="Solo mostrar URL guardada")
    parser.add_argument("--borrar", action="store_true", help="Quitar URL fija")
    args = parser.parse_args()

    ruta = _ruta_config()
    cfg = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            cfg = json.load(f) or {}

    if args.mostrar:
        print(cfg.get("url_red_erp") or "(sin URL fija configurada)")
        return

    if args.borrar:
        cfg["url_red_erp"] = ""
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("[OK] URL fija eliminada.")
        return

    url = args.url
    if not url:
        ips = _ips_lan()
        host = os.environ.get("COMPUTERNAME", "erp-sd").strip().lower()
        sugerida = f"http://{ips[0]}:5000" if ips else f"http://{host}:5000"
        print("")
        print("=== Configurar URL fija del ERP (red WiFi) ===")
        print("")
        print("Recomendado: IP reservada en el router (siempre la misma).")
        if ips:
            print("IP detectada ahora:", ", ".join(ips))
        print("Nombre de este PC:", host, f"→ http://{host}:5000")
        print("")
        url = input(f"URL fija [{sugerida}]: ").strip() or sugerida

    url = _normalizar_url(url)
    cfg["url_red_erp"] = url
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    try:
        import app as m

        m._CONFIG_EMPRESA_CACHE = None
        m._CONFIG_EMPRESA_CACHE_AT = 0.0
    except Exception:
        pass

    print("")
    print("[OK] URL fija guardada:")
    print(f"  {url}")
    print("")
    print("Usar en tablets/PC de la tienda (misma WiFi).")
    print("Reinicie Flask si ya estaba corriendo.")
    print("")


if __name__ == "__main__":
    main()
