"""Imprime ticket térmico de un vale existente (CLI diagnóstico piso)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def _load_env_local(force: bool = True) -> None:
    path = ROOT / ".env.local"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k:
            if force:
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="Listar vales Pendiente/Abierta")
    ap.add_argument("--venta-id", type=int, default=0, help="ID vale a imprimir")
    ap.add_argument("--impresora", default="", help="Override nombre impresora")
    ap.add_argument("--diag", action="store_true", help="Solo diagnóstico impresora")
    args = ap.parse_args()

    _load_env_local(force=True)

    from sqlalchemy.orm import joinedload

    from app import DetalleVenta, Venta, app
    from services.ticket_impresion_service import (
        diagnostico_impresora,
        imprimir_vale_termica_por_id,
    )

    if args.diag:
        print(json.dumps(diagnostico_impresora(), indent=2, ensure_ascii=False))
        return 0

    with app.app_context():
        if args.list or not args.venta_id:
            rows = (
                Venta.query.options(joinedload(Venta.cliente))
                .filter(Venta.estado.in_(("Pendiente", "Abierta")))
                .order_by(Venta.id.desc())
                .limit(15)
                .all()
            )
            if not rows:
                print("No hay vales Pendiente/Abierta.")
                return 1
            print("Vales disponibles:")
            for v in rows:
                cli = (v.cliente.nombre if v.cliente else "—") or "—"
                print(
                    f"  #{v.id}  {v.estado}  turno={v.prioridad}  "
                    f"total={int(v.monto_total or 0)}  cliente={cli[:40]}"
                )
            if not args.venta_id:
                print("\nUse: python scripts/_imprimir_vale_cli.py --venta-id ID")
                return 0

        vid = int(args.venta_id)
        printer = (args.impresora or "").strip() or None
        res = imprimir_vale_termica_por_id(vid, printer_name=printer)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
