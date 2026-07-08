"""Prueba impresion Zebra en red \\192.168.1.10 sin instalar cola local."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHARE = r"\\192.168.1.10\ZDesigner GX420d"
ZPL = b"^XA^FO20,20^A0N,40,40^FDPRUEBA RED LHEXIA^FS^XZ\n"


def try_copy_b() -> dict:
    tmp = Path(__file__).with_name("_zebra_red_test.zpl")
    tmp.write_bytes(ZPL)
    r = subprocess.run(
        ["cmd", "/c", "copy", "/b", str(tmp), SHARE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {"metodo": "copy_b", "ok": r.returncode == 0, "code": r.returncode, "out": (r.stdout or "") + (r.stderr or "")}


def try_win32_unc() -> dict:
    try:
        import win32print
    except ImportError:
        return {"metodo": "win32_unc", "ok": False, "error": "sin pywin32"}
    h = None
    try:
        h = win32print.OpenPrinter(SHARE)
        win32print.StartDocPrinter(h, 1, ("LhexIA RED", None, "RAW"))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, ZPL)
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
        return {"metodo": "win32_unc", "ok": True, "impresora": SHARE}
    except Exception as ex:
        return {"metodo": "win32_unc", "ok": False, "error": str(ex)[:300]}
    finally:
        if h:
            try:
                win32print.ClosePrinter(h)
            except Exception:
                pass


def try_rundll_in() -> dict:
    r = subprocess.run(
        [
            r"C:\Windows\System32\rundll32.exe",
            "printui.dll,PrintUIEntry",
            "/in",
            f'/n"{SHARE}"',
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    return {"metodo": "rundll32_in", "ok": r.returncode == 0, "code": r.returncode}


def list_printers() -> list[str]:
    from services.ticket_impresion_escpos import listar_colas_zebra_detalle

    return [f"{c['nombre']} ({c['puerto']}) usable={c['usable']}" for c in listar_colas_zebra_detalle()]


def main() -> int:
    print("=== Colas Zebra ===")
    for line in list_printers():
        print(" ", line)
    print("\n=== Pruebas red ===")
    for fn in (try_rundll_in, try_copy_b, try_win32_unc):
        res = fn()
        print(res)
    print("\n=== Colas despues ===")
    for line in list_printers():
        print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
