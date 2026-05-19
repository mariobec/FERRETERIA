#!/usr/bin/env python3
"""
Genera tarjeta LHX-SUP-* para un supervisor en la BD apuntada por DATABASE_URL.

Uso (local o Neon — revisar .env antes):
  python scripts/pos_generar_tarjeta_supervisor.py --correo ferreteria426@gmail.com
  python scripts/pos_generar_tarjeta_supervisor.py --id 4 --nombre "LUIS GASTÓN RIVERA PEREZ"
  python scripts/pos_generar_tarjeta_supervisor.py --correo x@y.cl --pin 4321 --dar-permiso-rol

El código de barras se imprime UNA vez en consola. No commitear ese valor.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generar tarjeta supervisor POS")
    parser.add_argument("--id", type=int, help="ID usuario en tabla usuarios")
    parser.add_argument("--correo", help="Correo exacto del usuario")
    parser.add_argument("--nombre", help="Actualizar nombre mostrado (opcional)")
    parser.add_argument("--pin", help="PIN 4 dígitos (opcional, solo si no tiene)")
    parser.add_argument(
        "--dar-permiso-rol",
        action="store_true",
        help="Agrega autorizar_descuento_pos al rol del usuario si falta",
    )
    parser.add_argument("--dry-run", action="store_true", help="No escribe en BD")
    args = parser.parse_args()

    if not args.id and not args.correo:
        parser.error("Indique --id o --correo")

    from app import (  # noqa: PLC0415
        Permiso,
        RolPermiso,
        Usuario,
        UsuarioTarjetaAutorizacion,
        _asegurar_columnas_usuario_pin_autorizacion,
        _asegurar_tabla_usuario_tarjeta_autorizacion,
        app,
        db,
        usuario_esta_activo,
        usuario_obj_tiene_permiso,
    )
    from services.pos_autorizacion_descuento_service import (  # noqa: PLC0415
        generar_token_tarjeta,
        hash_token_tarjeta,
        pin_valido_formato,
    )

    with app.app_context():
        _asegurar_columnas_usuario_pin_autorizacion()
        _asegurar_tabla_usuario_tarjeta_autorizacion()

        sup = None
        if args.id:
            sup = db.session.get(Usuario, args.id)
        elif args.correo:
            sup = Usuario.query.filter_by(correo=args.correo.strip()).first()

        if not sup:
            print("ERROR: usuario no encontrado.", file=sys.stderr)
            return 1
        if not usuario_esta_activo(sup):
            print("ERROR: usuario inactivo.", file=sys.stderr)
            return 1

        if args.nombre:
            sup.nombre = args.nombre.strip()[:120]

        perm = Permiso.query.filter_by(nombre="autorizar_descuento_pos").first()
        if not perm:
            print("ERROR: permiso autorizar_descuento_pos no existe. Ejecute seed de permisos.", file=sys.stderr)
            return 1

        if args.dar_permiso_rol and sup.rol and not usuario_obj_tiene_permiso(sup, "autorizar_descuento_pos"):
            if not RolPermiso.query.filter_by(rol_id=sup.rol.id, permiso_id=perm.id).first():
                if not args.dry_run:
                    db.session.add(RolPermiso(rol_id=sup.rol.id, permiso_id=perm.id))
                print(f"Permiso autorizar_descuento_pos → rol {sup.rol.nombre}")

        if not usuario_obj_tiene_permiso(sup, "autorizar_descuento_pos") and not args.dar_permiso_rol:
            print(
                "ERROR: usuario sin permiso autorizar_descuento_pos. "
                "Use --dar-permiso-rol o asígnelo en Roles.",
                file=sys.stderr,
            )
            return 1

        if args.pin:
            if not pin_valido_formato(args.pin):
                print("ERROR: PIN debe ser 4 dígitos.", file=sys.stderr)
                return 1
            if not args.dry_run:
                sup.set_pin_autorizacion(args.pin)
                print("PIN actualizado.")

        token = generar_token_tarjeta()
        if args.dry_run:
            print("DRY-RUN — no se guardó en BD")
            print("Usuario:", sup.nombre, sup.correo, f"id={sup.id}")
            print("Token ejemplo:", token)
            return 0

        UsuarioTarjetaAutorizacion.query.filter_by(usuario_id=sup.id, activo=True).update(
            {"activo": False, "revocado_en": datetime.utcnow()}
        )
        db.session.add(
            UsuarioTarjetaAutorizacion(
                usuario_id=sup.id,
                token_hash=hash_token_tarjeta(token),
                etiqueta=(sup.nombre or "")[:80],
                activo=True,
            )
        )
        db.session.commit()

        print("=== TARJETA SUPERVISOR (copiar / imprimir ahora) ===")
        print("Nombre:", sup.nombre)
        print("Correo:", sup.correo)
        print("Código:", token)
        print("PIN:", "configurado" if sup.pin_autorizacion_hash else "SIN PIN — definir en admin o --pin")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
