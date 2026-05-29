#!/usr/bin/env python3
"""
Activa productos CM- del maestro Chilemat que tienen compras/costo.

Uso:
  .\\venv\\Scripts\\python.exe scripts\\maestra_activar_cm_compras.py --dry-run
  .\\venv\\Scripts\\python.exe scripts\\maestra_activar_cm_compras.py --aplicar
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "respaldos" / "maestra_activar_cm"


def _load_env() -> None:
    p = ROOT / ".env.local"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL=") or line.strip().startswith("NEON_DATABASE_URL="):
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


def _apply_db_target(*, use_neon: bool) -> None:
    if use_neon and os.environ.get("NEON_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.environ["NEON_DATABASE_URL"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--margen", type=float, default=0.35)
    ap.add_argument("--confirm-neon", action="store_true")
    args = ap.parse_args()

    dry_run = not args.aplicar or args.dry_run
    _load_env()
    if args.confirm_neon:
        _apply_db_target(use_neon=True)
    url = (os.environ.get("DATABASE_URL") or "").lower()
    if args.aplicar and not dry_run and any(h in url for h in ("neon.tech", "render.com")) and not args.confirm_neon:
        raise SystemExit("BD remota: use --confirm-neon")

    import app as m
    from app import Producto, ProductoCodigoProveedor, db

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir = OUT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    aplicados = []
    omitidos = []

    with m.app.app_context():
        chilemat_id = None
        from services.chilemat_catalogo_ui_service import resolver_proveedor_chilemat

        prov = resolver_proveedor_chilemat()
        if prov:
            chilemat_id = int(prov.id)

        q = Producto.query.filter(
            Producto.codigo_interno.like("CM-%"),
            Producto.activo.is_(False),
        )
        candidatos = q.all()
        print(f"Candidatos CM- inactivos: {len(candidatos)}")

        for p in candidatos:
            costo = float(p.precio_compra or 0)
            tiene_puente = False
            if chilemat_id:
                tiene_puente = (
                    ProductoCodigoProveedor.query.filter_by(
                        proveedor_id=chilemat_id, producto_id=p.id
                    ).first()
                    is not None
                )

            if costo <= 0 and not tiene_puente:
                omitidos.append(
                    {
                        "producto_id": p.id,
                        "codigo_interno": p.codigo_interno,
                        "nombre": p.nombre,
                        "motivo": "sin_costo_ni_puente",
                    }
                )
                continue

            pv_antes = float(p.precio_venta or 0)
            pv_nuevo = pv_antes
            if pv_antes <= 0 and costo > 0:
                pv_nuevo = round(costo * (1 + args.margen), 0)

            reg = {
                "producto_id": p.id,
                "codigo_interno": p.codigo_interno,
                "codigo_barra": p.codigo_barra,
                "codigo_chilemat": p.codigo_chilemat or "",
                "nombre": p.nombre,
                "precio_compra": costo,
                "precio_venta_antes": pv_antes,
                "precio_venta_nuevo": pv_nuevo,
                "tiene_puente_chilemat": "S" if tiene_puente else "N",
            }

            if not dry_run:
                p.activo = True
                if pv_nuevo > 0:
                    p.precio_venta = pv_nuevo

            aplicados.append(reg)

        if not dry_run:
            db.session.commit()
            print("Commit OK")

    pd.DataFrame(aplicados).to_csv(run_dir / "activados.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(omitidos).to_csv(run_dir / "omitidos.csv", index=False, encoding="utf-8-sig")
    meta = {
        "stamp": stamp,
        "dry_run": dry_run,
        "activados": len(aplicados),
        "omitidos": len(omitidos),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
