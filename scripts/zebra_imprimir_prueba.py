#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba física Zebra GX420d — ejecutar en el PC con USB conectado."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ZPL_MIN = (
    "^XA\n"
    "^PW400\n"
    "^LL240\n"
    "^LH0,0\n"
    "^FO20,20^A0N,36,36^FDPRUEBA LHEXIA^FS\n"
    "^FO20,70^BY2^BCN,70,Y,N,N^FD123456789012^FS\n"
    "^XZ\n"
)


def main() -> int:
    from services.ticket_impresion_escpos import describir_cola_impresora, enviar_raw_zpl, listar_colas_zebra_detalle

    print("=== Colas Zebra ===")
    for c in listar_colas_zebra_detalle():
        print(f"  {c.get('nombre')} · {c.get('puerto')} · usable={c.get('usable')}")

    imp = "ZDesigner GX420d"
    desc = describir_cola_impresora(imp)
    print(f"\n=== Cola activa: {imp} ===")
    print(desc)

    print("\n=== Enviando ZPL mínimo (win32 RAW, sin ^CI28) ===")
    print(ZPL_MIN)
    res = enviar_raw_zpl(ZPL_MIN.encode("ascii"), imp)
    print(res)

    if res.get("ok"):
        print("\nOK — revise si salió etiqueta en la Zebra (nombre + barras).")
        print("Si no sale nada: apague/encienda, cargue rollo 50x30, mantenga FEED 2 s.")
    else:
        print("\nFALLO — copie este mensaje para soporte.")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
