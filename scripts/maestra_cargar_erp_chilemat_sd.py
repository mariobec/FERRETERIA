#!/usr/bin/env python3
"""
Carga maestro → ERP Santo Domingo (Chilemat = único proveedor factura).

Consolida:
  - productos.codigo_barra (EAN / escaneo estante)
  - productos.codigo_chilemat (portal VTEX)
  - producto_codigo_proveedor (código factura Chilemat → producto_id)
  - precio_compra (costo) + precio_venta (lista si falta)

Uso:
  .\\venv\\Scripts\\python.exe scripts\\maestra_cargar_erp_chilemat_sd.py --dry-run
  .\\venv\\Scripts\\python.exe scripts\\maestra_cargar_erp_chilemat_sd.py --aplicar
  .\\venv\\Scripts\\python.exe scripts\\maestra_cargar_erp_chilemat_sd.py --aplicar --confirm-neon
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
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "respaldos" / "maestra_chilemat_sd"
EXCEL_REL = ROOT / "docs" / "Maestro Materiales" / "Consolidado_Relaciones_ERP.xlsx"


def _load_env_local() -> None:
    p = ROOT / ".env.local"
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("DATABASE_URL", "NEON_DATABASE_URL") and v and k not in os.environ:
            os.environ[k] = v


def _apply_db_target(*, use_neon: bool) -> None:
    if use_neon and os.environ.get("NEON_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.environ["NEON_DATABASE_URL"]


def _warn_db():
    url = (os.environ.get("DATABASE_URL") or "").lower()
    if any(h in url for h in ("neon.tech", "render.com", "railway.app")):
        return "REMOTO"
    return "LOCAL"


def aggregate_por_codigo_sd(agg: pd.DataFrame) -> pd.DataFrame:
    """Una fila por código producto (todas las compras agregadas)."""
    from services.maestra_unificado_loaders import norm_cod, merge_maestra_consolidacion

    df = agg.copy()
    df["codigo_n"] = df["codigo_factura"].map(norm_cod)
    g = df.groupby("codigo_n", as_index=False).agg(
        codigo_factura=("codigo_factura", "first"),
        descripcion=("descripcion", "last"),
        neto_f=("neto_f", "sum"),
        cantidad_f=("cantidad_f", "sum"),
        ultimo_costo_unitario=("ultimo_costo_unitario", "last"),
        costo_promedio_ponderado=("costo_promedio_ponderado", "last"),
        grupo5=("grupo5", "last"),
        grupo4=("grupo4", "last"),
        proveedor_fabricante=("proveedor", "first"),
    )
    return g


def export_relaciones_excel(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty:
        return
    cols = [
        "producto_id",
        "codigo_factura_chilemat",
        "codigo_barra",
        "codigo_chilemat",
        "codigo_interno",
        "nombre",
        "precio_compra",
        "precio_venta",
        "activo",
        "accion",
        "match_metodo",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df[cols].to_excel(w, sheet_name="Relaciones_ERP", index=False)
        resumen = pd.DataFrame(
            [
                ("Filas", len(df)),
                ("Enriquecidos", int((df["accion"] == "enriquecer").sum())),
                ("Creados", int((df["accion"] == "crear").sum())),
                ("Con puente Chilemat", int(df.get("puente_chilemat", pd.Series()).eq("ok").sum())),
            ],
            columns=["Metrica", "Valor"],
        )
        resumen.to_excel(w, sheet_name="Resumen", index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm-neon", action="store_true", help="Requerido si DATABASE_URL es Neon/Render")
    ap.add_argument("--limit-enriquecer", type=int, default=6000)
    ap.add_argument("--limit-crear-activo", type=int, default=500)
    ap.add_argument("--limit-crear-pendiente", type=int, default=2000)
    ap.add_argument("--min-neto-activo", type=float, default=30_000)
    ap.add_argument("--margen", type=float, default=0.35)
    ap.add_argument("--solo-compras", action="store_true", default=True, help="Solo códigos con historial compra")
    args = ap.parse_args()

    if args.aplicar and not args.dry_run:
        dry_run = False
    else:
        dry_run = True
        if args.aplicar:
            print("Modo dry-run (use --aplicar sin --dry-run para escribir BD)")

    _load_env_local()
    if args.confirm_neon:
        _apply_db_target(use_neon=True)
    dest = _warn_db()
    if dest == "REMOTO" and args.aplicar and not args.dry_run and not args.confirm_neon:
        raise SystemExit("BD remota detectada. Agregue --confirm-neon para aplicar en producción.")

    import maestra_fase_a_enriquecer as fase_a
    from services.maestra_chilemat_sd_service import (
        buscar_vtex_producto,
        crear_producto_sd,
        enriquecer_producto,
        index_vtex_por_ean,
        index_vtex_por_referencia,
        norm_cod_factura,
        obtener_proveedor_chilemat_id,
    )
    from services.maestra_unificado_loaders import (
        load_consolidacion,
        merge_maestra_consolidacion,
        norm_ean,
        resolve_consolidacion_path,
        resolve_maestra_path,
    )

    import app as m
    from app import Producto, ProductoCodigoProveedor, _asegurar_tabla_producto_codigo_proveedor, db

    maestra_path = resolve_maestra_path(None)
    cons_path = resolve_consolidacion_path(None)
    raw = fase_a.load_maestra(maestra_path)
    agg = fase_a.aggregate_por_codigo(raw)
    sd = aggregate_por_codigo_sd(agg)
    cons = load_consolidacion(cons_path) if cons_path else None
    merged = merge_maestra_consolidacion(sd, cons)
    merged["codigo_factura_n"] = merged["codigo_factura"].map(fase_a.norm_text)
    merged["descripcion_n"] = merged["descripcion"].map(fase_a.norm_text)
    merged["proveedor_n"] = "CHILEMAT"

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir = OUT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    resultados: list[dict] = []
    omitidos: list[dict] = []

    with m.app.app_context():
        _asegurar_tabla_producto_codigo_proveedor()
        chilemat_id = obtener_proveedor_chilemat_id(crear=True, dry_run=dry_run)
        if not chilemat_id:
            raise SystemExit("No se encontró proveedor Chilemat en ERP.")

        print(f"Proveedor Chilemat id={chilemat_id} | BD={dest} | dry_run={dry_run}")

        pdf, prv, puente = fase_a.load_erp_catalog()
        indexes = fase_a.build_erp_indexes(pdf, prv, puente)
        vtex_ean = index_vtex_por_ean()
        vtex_ref = index_vtex_por_referencia()
        print(f"Productos ERP: {len(pdf)} | Puentes: {len(puente)} | VTEX EAN: {len(vtex_ean)}")

        ocupados_barra = {
            norm_cod_factura(p.codigo_barra)
            for p in Producto.query.filter(Producto.codigo_barra.isnot(None)).all()
            if p.codigo_barra
        }
        puentes = {
            (int(r.proveedor_id), norm_cod_factura(r.codigo_factura_proveedor))
            for r in ProductoCodigoProveedor.query.all()
        }
        puente_chilemat_map = {
            norm_cod_factura(r.codigo_factura_proveedor): int(r.producto_id)
            for r in ProductoCodigoProveedor.query.filter_by(proveedor_id=int(chilemat_id)).all()
        }

        # Priorizar por neto compras
        merged = merged.sort_values("neto_f", ascending=False)

        enriquecidos = 0
        creados_activo = 0
        creados_pendiente = 0

        for _, row in merged.iterrows():
            if args.solo_compras and float(row.get("neto_f") or 0) <= 0:
                continue

            cod = row.get("codigo_factura")
            ean = str(row.get("ean_consolidacion") or "")
            ean_n = norm_ean(ean)
            vtex = vtex_ean.get(ean_n) if ean_n else None
            if not vtex:
                vtex = buscar_vtex_producto(
                    codigo_factura=str(cod or ""),
                    codigo_barra=str(row.get("ean_consolidacion") or ""),
                    vtex_ean=vtex_ean,
                    vtex_ref=vtex_ref,
                )
            costo = pd.to_numeric(row.get("ultimo_costo_unitario"), errors="coerce")
            costo_f = float(costo) if pd.notna(costo) and float(costo) > 0 else 0.0
            neto = float(row.get("neto_f") or 0)

            # Match ERP
            pid, prod, metodo, conf = fase_a.match_row(row, indexes, pdf)

            cod_n = norm_cod_factura(cod)
            if pid is None and cod_n in puente_chilemat_map:
                pid = puente_chilemat_map[cod_n]
                metodo = "puente_chilemat"
                conf = 100

            nombre = str(row.get("descripcion") or row.get("descripcion_consolidacion") or cod)[:100]
            cat = str(row.get("grupo5") or row.get("familia_consolidacion") or "")[:50]
            sub = str(row.get("grupo4") or "")[:50]

            if pid is not None:
                if enriquecidos >= args.limit_enriquecer:
                    continue
                producto = Producto.query.get(int(pid))
                if not producto:
                    omitidos.append({"codigo": cod, "motivo": "producto_id_invalido"})
                    continue
                reg = enriquecer_producto(
                    producto,
                    codigo_factura=str(cod),
                    costo=costo_f if costo_f > 0 else None,
                    ean=ean,
                    categoria=cat,
                    subcategoria=sub,
                    vtex=vtex,
                    chilemat_id=int(chilemat_id),
                    ocupados_barra=ocupados_barra,
                    puentes=puentes,
                    dry_run=dry_run,
                    margen_venta=args.margen,
                )
                reg["match_metodo"] = metodo
                reg["match_confianza"] = conf
                reg["nombre"] = producto.nombre
                reg["codigo_barra"] = reg.get("codigo_barra") or producto.codigo_barra
                reg["codigo_chilemat"] = reg.get("codigo_chilemat") or producto.codigo_chilemat
                reg["codigo_interno"] = producto.codigo_interno
                reg["precio_compra"] = reg.get("precio_compra", producto.precio_compra)
                reg["precio_venta"] = reg.get("precio_venta", producto.precio_venta)
                reg["activo"] = producto.activo
                resultados.append(reg)
                enriquecidos += 1
                continue

            # Crear faltante — catálogo SD: activo siempre; precio lista desde VTEX aunque costo=0
            activo = True
            if activo and creados_activo >= args.limit_crear_activo:
                continue
            if not activo and creados_pendiente >= args.limit_crear_pendiente:
                continue

            reg, err = crear_producto_sd(
                codigo_factura=str(cod),
                nombre=nombre,
                costo=costo_f,
                ean=ean,
                categoria=cat,
                subcategoria=sub,
                vtex=vtex,
                chilemat_id=int(chilemat_id),
                ocupados_barra=ocupados_barra,
                activo=activo,
                margen_venta=args.margen,
                dry_run=dry_run,
            )
            if err:
                omitidos.append({"codigo": cod, "motivo": err})
                continue
            if reg:
                reg["match_metodo"] = "nuevo"
                reg["activo"] = activo
                resultados.append(reg)
                if activo:
                    creados_activo += 1
                else:
                    creados_pendiente += 1

        if not dry_run:
            db.session.commit()
            print("Commit OK")

    pd.DataFrame(resultados).to_csv(run_dir / "relaciones_aplicadas.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(omitidos).to_csv(run_dir / "omitidos.csv", index=False, encoding="utf-8-sig")
    meta = {
        "stamp": stamp,
        "dry_run": dry_run,
        "chilemat_id": chilemat_id,
        "enriquecidos": sum(1 for r in resultados if r.get("accion") == "enriquecer"),
        "creados": sum(1 for r in resultados if r.get("accion") == "crear"),
        "omitidos": len(omitidos),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    export_relaciones_excel(resultados, EXCEL_REL)
    export_relaciones_excel(resultados, run_dir / "Consolidado_Relaciones_ERP.xlsx")

    print(json.dumps(meta, indent=2))
    print("Excel relaciones:", EXCEL_REL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
