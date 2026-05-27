#!/usr/bin/env python3
"""
Arranque del ERP usando siempre el Python del proyecto.

Uso (cualquiera de estos):
  python run.py
  .venv\\Scripts\\python.exe run.py
  iniciar_servidor.bat
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PY = ROOT / '.venv' / 'Scripts' / 'python.exe'


def _reexec_en_venv_si_hace_falta() -> None:
    """Si se invocó con Python del sistema, relanzar con .venv (seguro en rutas con espacios)."""
    if not VENV_PY.is_file():
        return
    actual = Path(sys.executable).resolve()
    esperado = VENV_PY.resolve()
    if actual == esperado:
        return
    import subprocess

    cmd = [str(esperado), str(ROOT / 'app.py'), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


def main() -> int:
    _reexec_en_venv_si_hace_falta()
    if not VENV_PY.is_file():
        print(
            '[ERROR] No existe .venv. Ejecute instalar_pruebas_windows.bat\n'
            '        o:  .venv\\Scripts\\python.exe app.py',
            file=sys.stderr,
        )
        return 1
    os.chdir(ROOT)
    os.environ.setdefault('PGCLIENTENCODING', 'UTF8')
    import app as app_mod

    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    host = (os.getenv('FLASK_RUN_HOST') or '0.0.0.0').strip() or '0.0.0.0'
    port = int((os.getenv('FLASK_RUN_PORT') or '5000').strip() or '5000')
    app_mod.app.run(host=host, port=port, debug=debug_mode)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
