#!/usr/bin/env python3
"""
Importa órdenes de compra históricas desde Maestra_Ferreteria_Santo_Domingo.xlsx.

Agrupa por proveedor + OC (+ año si la misma OC cruza años).
Estado: Cerrada (no aparece en pendientes operativos).
Detalle: solo líneas con producto_id resoluble (producto_codigo_proveedor o código ERP).

Uso:
  python scripts/maestra_import_ordenes_compra.py --dry-run
  python scripts/maestra_import_ordenes_compra.py --anio-desde 2024 --anio-hasta 2026
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")
USUARIO = "maestra-import-oc"
CODIGO_PRODUCTO_GENERICO = "COMPRA-HIST-MAESTRA"


def norm_proveedor(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", s))


def norm_codigo(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip().upper()


def oc_numero_str(raw, anio: int, multi_anio: bool) -> str:
    if pd.isna(raw):
        return ""
    try:
        n = int(float(raw))
        base = str(n)
    except (TypeError, ValueError):
        base = str(raw).strip()[:50]
    if multi_anio:
        return f"{base}-{anio}"[:50]
    return base[:50]


def load_maestra(path: Path, anio_desde: int, anio_hasta: int) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)
    col_prov = [c for c in df.columns if "proveedor" in str(c).lower()][0]
    col_cod = [c for c in df.columns if "digo" in str(c) and "Producto" in str(c)][0]
    col_desc = [c for c in df.columns if "scrip" in str(c) and "Producto" in str(c)][0]
    col_neto = [c for c in df.columns if "Neto" in str(c)][0]
    col_cant = [c for c in df.columns if "Cantidad" in str(c)][0]
    col_anio = df.columns[0]
    col_oc = "OC" if "OC" in df.columns else [c for c in df.columns if str(c).strip().upper() == "OC"][0]

    out = df.rename(
        columns={
            col_prov: "proveedor",
            col_cod: "codigo_factura",
            col_desc: "descripcion",
            col_neto: "neto",
            col_cant: "cantidad",
            col_anio: "anio",
            col_oc: "oc",
        }
    )
    out["anio"] = pd.to_numeric(out["anio"], errors="coerce")
    out = out[out["anio"].between(anio_desde, anio_hasta)]
    out["neto"] = pd.to_numeric(out["neto"], errors="coerce").fillna(0)
    out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce").fillna(0)
    out = out[out["oc"].notna()]
    return out


def build_link_index(app) -> dict[tuple[int, str], int]:
    from app import ProductoCodigoProveedor

    idx: dict[tuple[int, str], int] = {}
    for row in ProductoCodigoProveedor.query.all():
        k = (int(row.proveedor_id), norm_codigo(row.codigo_factura_proveedor))
        if k[1]:
            idx[k] = int(row.producto_id)
    return idx


def build_codigo_erp_index(app) -> dict[str, int]:
    from app import Producto

    idx: dict[str, int] = {}
    for p in Producto.query.filter(Producto.activo == True).all():
        for raw in (p.codigo_barra, p.codigo_interno, getattr(p, "codigo_chilemat", None)):
            c = norm_codigo(raw)
            if c and c not in idx:
                idx[c] = int(p.id)
    return idx


def get_or_create_producto_generico(app, *, dry_run: bool) -> int | None:
    from app import Producto, db

    p = Producto.query.filter_by(codigo_interno=CODIGO_PRODUCTO_GENERICO).first()
    if p:
        return int(p.id)
    if dry_run:
        return -2
    p = Producto(
        codigo_interno=CODIGO_PRODUCTO_GENERICO,
        codigo_barra=CODIGO_PRODUCTO_GENERICO,
        nombre="[Histórico] Compras maestra sin ficha SKU",
        activo=False,
        precio_compra=0,
        precio_venta=0,
        stock=0,
    )
    db.session.add(p)
    db.session.flush()
    return int(p.id)


def build_prov_map(app) -> dict[str, int]:
    from app import Proveedor

    m: dict[str, int] = {}
    for p in Proveedor.query.all():
        k = norm_proveedor(p.nombre)
        if k and k not in m:
            m[k] = int(p.id)
    return m


def resolve_proveedor_id(nombre: str, prov_map: dict[str, int]) -> int | None:
    k = norm_proveedor(nombre)
    if k in prov_map:
        return prov_map[k]
    for pk, pid in prov_map.items():
        if pk and (pk in k or k in pk):
            return pid
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Maestra → ordenes_compra (histórico)")
    ap.add_argument("--maestra", type=Path, default=DEFAULT_MAESTRA)
    ap.add_argument("--anio-desde", type=int, default=2024)
    ap.add_argument("--anio-hasta", type=int, default=2026)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--crear-proveedores", action="store_true", default=True)
    ap.add_argument("--no-crear-proveedores", action="store_false", dest="crear_proveedores")
    ap.add_argument(
        "--incluir-sin-producto",
        action="store_true",
        help="Líneas sin vínculo → producto genérico COMPRA-HIST-MAESTRA (totales financieros)",
    )
    args = ap.parse_args()

    if not args.maestra.is_file():
        print(f"No existe maestra: {args.maestra}", file=sys.stderr)
        return 1

    df = load_maestra(args.maestra, args.anio_desde, args.anio_hasta)
    if df.empty:
        print("Sin filas en rango de años.")
        return 1

    df["_prov_k"] = df["proveedor"].map(norm_proveedor)
    df["_oc_raw"] = df["oc"]
    cross = (
        df.groupby(["_prov_k", "_oc_raw"])["anio"]
        .nunique()
        .reset_index(name="n_anios")
    )
    multi_keys = {
        (row["_prov_k"], row["_oc_raw"])
        for _, row in cross[cross["n_anios"] > 1].iterrows()
    }

    grupos: dict[tuple, list] = defaultdict(list)
    for row in df.itertuples(index=False):
        pk = norm_proveedor(row.proveedor)
        oc_raw = row.oc
        anio = int(row.anio)
        key = (pk, oc_raw, anio)
        grupos[key].append(row)

    print(f"Maestra: {len(df)} líneas | {len(grupos)} OC (proveedor+oc+año)")
    print(f"Años: {args.anio_desde}–{args.anio_hasta}")

    import app as m
    from app import DetalleOrdenCompra, OrdenCompra, Proveedor, db

    stats = {
        "oc_creadas": 0,
        "oc_omitidas_existentes": 0,
        "lineas_ok": 0,
        "lineas_sin_producto": 0,
        "lineas_generico": 0,
        "proveedores_creados": 0,
        "sin_proveedor": 0,
    }

    with m.app.app_context():
        prov_map = build_prov_map(m.app)
        link_idx = build_link_index(m.app)
        erp_cod_idx = build_codigo_erp_index(m.app)
        prod_generico_id = None
        if args.incluir_sin_producto:
            prod_generico_id = get_or_create_producto_generico(m.app, dry_run=args.dry_run)
        existentes = {
            (int(o.proveedor_id), (o.numero or "").strip())
            for o in OrdenCompra.query.with_entities(
                OrdenCompra.proveedor_id, OrdenCompra.numero
            ).all()
        }

        for (pk, oc_raw, anio), filas in sorted(grupos.items(), key=lambda x: (x[0][2], x[0][0])):
            nom_prov = str(filas[0].proveedor).strip()
            pid = resolve_proveedor_id(nom_prov, prov_map)
            if not pid and args.crear_proveedores and not args.dry_run:
                p = Proveedor(nombre=nom_prov[:100] or "PROVEEDOR MAESTRA")
                db.session.add(p)
                db.session.flush()
                pid = int(p.id)
                prov_map[norm_proveedor(p.nombre)] = pid
                stats["proveedores_creados"] += 1
            elif not pid and args.dry_run and args.crear_proveedores:
                pid = -1
            if not pid:
                stats["sin_proveedor"] += len(filas)
                continue

            multi = (pk, oc_raw) in multi_keys
            numero = oc_numero_str(oc_raw, anio, multi)
            if not numero:
                continue

            clave = (pid, numero) if pid > 0 else None
            if clave and clave in existentes:
                stats["oc_omitidas_existentes"] += 1
                continue

            lineas_det: list[dict] = []
            for row in filas:
                cod = norm_codigo(row.codigo_factura)
                cant = float(row.cantidad or 0)
                neto = float(row.neto or 0)
                if cant <= 0:
                    continue
                precio_u = round(neto / cant, 2) if neto > 0 else 0.0
                prod_id = None
                if pid > 0 and cod:
                    prod_id = link_idx.get((pid, cod))
                if not prod_id and cod:
                    prod_id = erp_cod_idx.get(cod)
                if not prod_id and args.incluir_sin_producto and prod_generico_id:
                    prod_id = prod_generico_id
                    stats["lineas_generico"] += 1
                if not prod_id:
                    stats["lineas_sin_producto"] += 1
                    continue
                lineas_det.append(
                    {
                        "producto_id": prod_id,
                        "cantidad": cant,
                        "precio_unitario": precio_u,
                    }
                )

            if not lineas_det:
                continue

            if args.dry_run:
                stats["oc_creadas"] += 1
                stats["lineas_ok"] += len(lineas_det)
                continue

            oc = OrdenCompra(
                proveedor_id=pid,
                numero=numero,
                fecha_emision=date(anio, 12, 31),
                estado="Cerrada",
                observacion=f"Histórico maestra SD · año {anio}",
                usuario_creador=USUARIO,
            )
            db.session.add(oc)
            db.session.flush()
            for ln in lineas_det:
                db.session.add(
                    DetalleOrdenCompra(
                        orden_compra_id=oc.id,
                        producto_id=ln["producto_id"],
                        cantidad=ln["cantidad"],
                        precio_unitario=ln["precio_unitario"],
                    )
                )
            existentes.add((pid, numero))
            stats["oc_creadas"] += 1
            stats["lineas_ok"] += len(lineas_det)

            if stats["oc_creadas"] % 200 == 0:
                db.session.commit()
                print(f"  … {stats['oc_creadas']} OC")

        if not args.dry_run:
            db.session.commit()

    modo = "DRY-RUN" if args.dry_run else "APLICADO"
    print(f"\n=== {modo} ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    with m.app.app_context():
        n_oc = OrdenCompra.query.count()
        n_det = DetalleOrdenCompra.query.count()
        hist = OrdenCompra.query.filter(OrdenCompra.usuario_creador == USUARIO).count()
        print(f"\nBD: OC total={n_oc} | detalles={n_det} | OC import maestra={hist}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
