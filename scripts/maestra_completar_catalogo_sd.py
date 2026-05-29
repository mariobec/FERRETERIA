#!/usr/bin/env python3
"""
Completa catálogo SD: activos + precio lista (con o sin costo) + vínculo VTEX e-commerce.

- activo=True (venta catálogo / semáforo azul sin stock)
- precio_venta desde Chilemat VTEX si no hay costo
- vincula chilemat_vtex_producto.producto_id para vitrina

Uso:
  .\\venv\\Scripts\\python.exe scripts\\maestra_completar_catalogo_sd.py --dry-run
  .\\venv\\Scripts\\python.exe scripts\\maestra_completar_catalogo_sd.py --aplicar
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
OUT = ROOT / "respaldos" / "maestra_catalogo_sd"


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


def _es_ficha_maestro(p) -> bool:
    interno = (p.codigo_interno or "").upper()
    return interno.startswith("CM-") or interno.startswith("MAESTRA-")


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
    from services.chilemat_catalogo_ui_service import resolver_proveedor_chilemat
    from services.maestra_chilemat_sd_service import (
        buscar_vtex_producto,
        index_vtex_por_ean,
        index_vtex_por_referencia,
        resolver_precio_lista,
        vincular_vtex_a_producto,
    )

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir = OUT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    with m.app.app_context():
        prov = resolver_proveedor_chilemat()
        chilemat_id = int(prov.id) if prov else None

        puentes_por_pid: dict[int, str] = {}
        if chilemat_id:
            for r in ProductoCodigoProveedor.query.filter_by(proveedor_id=chilemat_id).all():
                puentes_por_pid[int(r.producto_id)] = str(r.codigo_factura_proveedor or "")

        vtex_ean = index_vtex_por_ean()
        vtex_ref = index_vtex_por_referencia()

        candidatos = Producto.query.filter(
            db.or_(
                Producto.codigo_interno.like("CM-%"),
                Producto.codigo_interno.like("MAESTRA-%"),
                Producto.id.in_(list(puentes_por_pid.keys()) if puentes_por_pid else [-1]),
            )
        ).all()

        print(f"Fichas maestro/catálogo: {len(candidatos)}")

        for p in candidatos:
            cod_factura = puentes_por_pid.get(int(p.id), "")
            vtex = buscar_vtex_producto(
                ean="",
                codigo_factura=cod_factura,
                codigo_chilemat=p.codigo_chilemat or "",
                codigo_barra=p.codigo_barra or "",
                vtex_ean=vtex_ean,
                vtex_ref=vtex_ref,
            )

            costo = float(p.precio_compra or 0)
            pv_antes = float(p.precio_venta or 0)
            pv_nuevo, fuente = resolver_precio_lista(
                precio_venta_actual=pv_antes,
                vtex=vtex,
                costo=costo,
                margen=args.margen,
            )

            activar = not p.activo
            cambio_pv = pv_nuevo > 0 and pv_antes <= 0
            vinc = vincular_vtex_a_producto(p, vtex, dry_run=dry_run) if vtex else False

            if not (activar or cambio_pv or vinc):
                continue

            reg = {
                "producto_id": p.id,
                "codigo_interno": p.codigo_interno,
                "codigo_barra": p.codigo_barra,
                "nombre": p.nombre,
                "activo_antes": bool(p.activo),
                "activo_nuevo": True,
                "precio_compra": costo,
                "precio_venta_antes": pv_antes,
                "precio_venta_nuevo": pv_nuevo,
                "precio_fuente": fuente,
                "codigo_factura_chilemat": cod_factura,
                "vtex_vinculado": vtex.get("vtex_product_id") if vinc and vtex else "",
            }

            if not dry_run:
                p.activo = True
                if cambio_pv:
                    p.precio_venta = pv_nuevo

            rows.append(reg)

        if not dry_run:
            db.session.commit()
            print("Commit OK")

    pd.DataFrame(rows).to_csv(run_dir / "actualizados.csv", index=False, encoding="utf-8-sig")
    meta = {
        "stamp": stamp,
        "dry_run": dry_run,
        "actualizados": len(rows),
        "activados": sum(1 for r in rows if not r["activo_antes"]),
        "precio_completado": sum(1 for r in rows if r["precio_venta_antes"] <= 0 and r["precio_venta_nuevo"] > 0),
        "vtex_vinculados": sum(1 for r in rows if r["vtex_vinculado"]),
        "sin_precio_lista": sum(1 for r in rows if r["precio_venta_nuevo"] <= 0),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
