#!/usr/bin/env python3
"""Informes de historia de compras — Maestra Santo Domingo (solo lectura + CSV)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")
OUT = ROOT / "respaldos" / "maestra_informes"


def load(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)
    col_prov = [c for c in df.columns if "proveedor" in str(c).lower()][0]
    col_cod = [c for c in df.columns if "digo" in str(c) and "Producto" in str(c)][0]
    col_desc = [c for c in df.columns if "scrip" in str(c) and "Producto" in str(c)][0]
    col_neto = [c for c in df.columns if "Neto" in str(c)][0]
    col_cant = [c for c in df.columns if "Cantidad" in str(c)][0]
    col_anio = df.columns[0]
    df = df.rename(
        columns={
            col_prov: "proveedor",
            col_cod: "codigo_factura",
            col_desc: "descripcion",
            col_neto: "neto",
            col_cant: "cantidad",
            col_anio: "anio",
        }
    )
    g5 = [c for c in df.columns if "Grupo5" in str(c)]
    if g5:
        df = df.rename(columns={g5[0]: "categoria"})
    df["neto"] = pd.to_numeric(df["neto"], errors="coerce").fillna(0)
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["costo_u"] = df["neto"] / df["cantidad"].replace(0, pd.NA)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maestra", type=Path, default=DEFAULT_MAESTRA)
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = OUT / stamp
    out.mkdir(parents=True, exist_ok=True)

    df = load(args.maestra)

    por_anio = (
        df.groupby("anio", dropna=False)
        .agg(neto_total=("neto", "sum"), lineas=("neto", "count"))
        .reset_index()
        .sort_values("anio")
    )
    por_anio.to_csv(out / "compras_por_anio.csv", index=False, encoding="utf-8-sig")

    por_prov = (
        df.groupby("proveedor")
        .agg(neto_total=("neto", "sum"), lineas=("neto", "count"))
        .reset_index()
        .sort_values("neto_total", ascending=False)
    )
    por_prov.to_csv(out / "top_proveedores.csv", index=False, encoding="utf-8-sig")

    if "categoria" in df.columns:
        por_cat = (
            df.groupby("categoria")
            .agg(neto_total=("neto", "sum"))
            .reset_index()
            .sort_values("neto_total", ascending=False)
        )
        por_cat.to_csv(out / "compras_por_categoria.csv", index=False, encoding="utf-8-sig")

    cod = (
        df.groupby(["codigo_factura", "proveedor", "descripcion"])
        .agg(
            neto_total=("neto", "sum"),
            ultimo_costo=("costo_u", "last"),
            anio_ultimo=("anio", "last"),
        )
        .reset_index()
        .sort_values("neto_total", ascending=False)
    )
    cod.head(200).to_csv(out / "top200_codigos_factura.csv", index=False, encoding="utf-8-sig")

    inflacion = []
    for (cf, prov), g in df.groupby(["codigo_factura", "proveedor"]):
        por_a = g.groupby("anio")["costo_u"].mean().dropna()
        if len(por_a) < 2:
            continue
        años = sorted(por_a.index)
        c0, c1 = float(por_a[años[0]]), float(por_a[años[-1]])
        if c0 <= 0:
            continue
        inflacion.append(
            {
                "codigo_factura": cf,
                "proveedor": prov,
                "descripcion": g["descripcion"].iloc[-1],
                "costo_primer_anio": round(c0, 2),
                "costo_ultimo_anio": round(c1, 2),
                "variacion_pct": round((c1 - c0) / c0 * 100, 1),
                "anio_desde": int(años[0]),
                "anio_hasta": int(años[-1]),
            }
        )
    pd.DataFrame(inflacion).sort_values("variacion_pct", ascending=False).head(150).to_csv(
        out / "inflacion_codigos_top150.csv", index=False, encoding="utf-8-sig"
    )

    resumen = f"""# Informes maestra SD
Archivo: {args.maestra}
Salida: {out}
Neto total periodo: ${df['neto'].sum():,.0f}
Proveedores distintos: {df['proveedor'].nunique()}
"""
    (out / "RESUMEN.md").write_text(resumen, encoding="utf-8")
    print(resumen)


if __name__ == "__main__":
    main()
