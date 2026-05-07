"""
Establece una nueva contraseña para un usuario del ERP (por correo).

No recupera la clave anterior (solo hay hash en BD).

PowerShell:
  cd "ruta\\a\\sistema_ventas"
  $env:NUEVA_CLAVE = "LaClaveQueTuEliges"
  python reset_password_usuario.py andremunozs91@gmail.com

CMD:
  set NUEVA_CLAVE=LaClaveQueTuEliges
  python reset_password_usuario.py andremunozs91@gmail.com

Luego borra NUEVA_CLAVE del entorno si quieres.
"""
from __future__ import annotations

import os
import sys

from app import Usuario, app, db


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python reset_password_usuario.py <correo>", file=sys.stderr)
        sys.exit(1)

    correo = sys.argv[1].strip()
    pwd = (os.getenv("NUEVA_CLAVE") or "").strip()
    if not pwd:
        print("Defina NUEVA_CLAVE en el entorno (contraseña nueva).", file=sys.stderr)
        sys.exit(1)

    with app.app_context():
        u = Usuario.query.filter_by(correo=correo).first()
        if not u:
            print(f"No existe usuario con correo: {correo}", file=sys.stderr)
            sys.exit(2)
        u.set_password(pwd)
        db.session.commit()
        print(f"OK: contraseña actualizada para {correo} ({u.nombre}).")


if __name__ == "__main__":
    main()
