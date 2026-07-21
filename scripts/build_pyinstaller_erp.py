#!/usr/bin/env python3
"""Compila LhexIA_ERP (PyInstaller onedir) desde el repo DEV."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "LhexIA_ERP"
BUILD = ROOT / "build" / "pyinstaller_erp"
SPEC = BUILD / "LhexIA_ERP.spec"
LAUNCHER = ROOT / "scripts" / "erp_launcher.py"


def _collect_hidden() -> list[str]:
    try:
        from PyInstaller.utils.hooks import collect_submodules
    except ImportError:
        return []
    mods = []
    for pkg in ("blueprints", "services", "core", "domain", "application", "infrastructure", "adapters"):
        try:
            mods.extend(collect_submodules(pkg))
        except Exception:
            pass
    extras = [
        "app",
        "schema_sync",
        "init_db",
        "flask",
        "flask_login",
        "flask_sqlalchemy",
        "sqlalchemy",
        "sqlalchemy.dialects.postgresql",
        "psycopg2",
        "pg8000",
        "pandas",
        "openpyxl",
        "qrcode",
        "PIL",
        "fitz",
        "lxml",
        "lxml.etree",
        "cryptography",
        "signxml",
        "zeep",
        "jinja2.ext",
        "email.mime.multipart",
        "email.mime.text",
        "pkg_resources.extern",
    ]
    return sorted(set(mods + extras))


def _datas() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for folder in ("templates", "static", "config"):
        src = ROOT / folder
        if src.is_dir():
            out.append((str(src), folder))
    data_src = ROOT / "data"
    if data_src.is_dir():
        for name in (
            "empresa_config.json",
            "empresas_cotizacion.json",
            "proveedores_config.json",
            "cross_sell_associations.json",
            "pintura_cartilla_sd.json",
            "zebra_etiqueta_config.json",
        ):
            p = data_src / name
            if p.is_file():
                out.append((str(p), "data"))
    ops = ROOT / "INSTALACION" / "paquete" / "04_SCRIPTS_OPERACION" / "crear_usuario_test_piso.py"
    if ops.is_file():
        out.append((str(ops), "scripts"))
    init_py = ROOT / "scripts" / "__init__.py"
    if init_py.is_file():
        out.append((str(init_py), "scripts"))
    return out


def write_spec() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    hidden = _collect_hidden()
    datas = _datas()
    hidden_repr = ",\n        ".join(repr(x) for x in hidden)
    datas_repr = ",\n        ".join(repr(x) for x in datas)
    launcher_s = str(LAUNCHER).replace("\\", "/")
    root_s = str(ROOT).replace("\\", "/")
    spec = f'''# -*- mode: python ; coding: utf-8 -*-
# Generado por scripts/build_pyinstaller_erp.py — no editar a mano

block_cipher = None

a = Analysis(
    [{launcher_s!r}],
    pathex=[{root_s!r}],
    binaries=[],
    datas=[
        {datas_repr}
    ],
    hiddenimports=[
        {hidden_repr}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tests', 'pytest', 'matplotlib', 'tkinter', 'IPython', 'notebook'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LhexIA_ERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LhexIA_ERP',
)
'''
    SPEC.write_text(spec, encoding="utf-8")


def run_pyinstaller(clean: bool) -> None:
    write_spec()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={BUILD / 'work'}",
    ]
    if clean:
        cmd.append("--clean")
    cmd.append(str(SPEC))
    print("Ejecutando:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def stage_instalacion() -> Path:
    dest = ROOT / "INSTALACION" / "erp"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if not DIST.is_dir():
        raise SystemExit(f"[ERROR] No existe build: {DIST}")
    for item in DIST.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    for sub in ("data", "storage", "logs", "storage/dtes", "storage/dtes/emitidos"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    for name in (
        "empresa_config.json",
        "empresas_cotizacion.json",
        "proveedores_config.json",
        "cross_sell_associations.json",
        "pintura_cartilla_sd.json",
        "zebra_etiqueta_config.json",
    ):
        src = ROOT / "data" / name
        if src.is_file():
            shutil.copy2(src, dest / "data" / name)
    ps1 = ROOT / "INSTALACION" / "paquete" / "04_SCRIPTS_OPERACION" / "servidor_erp_autostart.ps1"
    if ps1.is_file():
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ps1, dest / "scripts" / "servidor_erp_autostart.ps1")
        shutil.copy2(ps1, dest / "servidor_erp_autostart.ps1")
    # Quitar .py sueltos del runtime cliente (solo debe quedar el exe + _internal)
    for py in dest.rglob("*.py"):
        if "_internal" in py.parts:
            continue
        py.unlink()
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Limpiar cache PyInstaller")
    parser.add_argument("--no-stage", action="store_true", help="No copiar a INSTALACION/erp")
    args = parser.parse_args()

    if not LAUNCHER.is_file():
        print("[ERROR] Falta scripts/erp_launcher.py", file=sys.stderr)
        return 1
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[ERROR] Instale PyInstaller: pip install pyinstaller", file=sys.stderr)
        return 1

    run_pyinstaller(clean=args.clean)
    if not (DIST / "LhexIA_ERP.exe").is_file():
        print("[ERROR] Build sin LhexIA_ERP.exe", file=sys.stderr)
        return 1
    print(f"[OK] Build: {DIST}")
    if not args.no_stage:
        staged = stage_instalacion()
        print(f"[OK] Staged en {staged} (sin .py sueltos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
