#!/usr/bin/env python3
"""
Genera Consolidado_Maestro_Materiales.xlsx en docs/Maestro Materiales/

Une Maestra compras (Hoja1) + Consolidación catálogo por código producto.

Uso:
  .\\venv\\Scripts\\python.exe scripts\\export_maestro_materiales_consolidado_xlsx.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = ROOT / "docs" / "Maestro Materiales"
OUTPUT = BASE / "Consolidado_Maestro_Materiales.xlsx"


def _col_match(columns, *parts: str):
    for c in columns:
        u = str(c).upper()
        if all(p.upper() in u for p in parts):
            return c
    return None


def load_maestra_detalle(path: Path) -> pd.DataFrame:
    import maestra_fase_a_enriquecer as fase_a

    raw = fase_a.load_maestra(path)
    agg = fase_a.aggregate_por_codigo(raw)
    return raw, agg


def aggregate_maestra_por_codigo(agg: pd.DataFrame) -> pd.DataFrame:
    """Una fila por código producto (suma compras de todos los proveedores)."""
    from services.maestra_unificado_loaders import norm_cod, norm_ean

    df = agg.copy()
    df["codigo_n"] = df["codigo_factura"].map(norm_cod)

    g = df.groupby("codigo_n", as_index=False).agg(
        codigo_producto=("codigo_factura", "first"),
        proveedor_principal=("proveedor", "first"),
        num_proveedores=("proveedor", "nunique"),
        proveedores=("proveedor", lambda s: " | ".join(sorted(set(str(x) for x in s if str(x).strip()))[:5])),
        descripcion_compras=("descripcion", "last"),
        neto_acumulado=("neto_f", "sum"),
        cantidad_acumulada=("cantidad_f", "sum"),
        ultimo_costo_unitario=("ultimo_costo_unitario", "last"),
        costo_promedio_ponderado=("costo_promedio_ponderado", "last"),
        categoria_grupo5=("grupo5", "last"),
        subcategoria_grupo4=("grupo4", "last"),
        grupo1=("grupo1", "last"),
        familia_aa=("familia_aa", "last"),
        num_lineas_historicas=("num_lineas_historicas", "sum"),
        ultimo_anio=("ultimo_anio", "last"),
    )
    g["neto_acumulado"] = g["neto_acumulado"].round(0)
    g["cantidad_acumulada"] = g["cantidad_acumulada"].round(2)
    g["en_maestra_compras"] = "S"
    return g


def build_consolidado_codigo(mae_cod: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    from services.maestra_unificado_loaders import norm_ean, merge_maestra_consolidacion

    # merge_maestra espera columnas de agg detalle; usamos mae_cod renombrado
    mae_for_merge = mae_cod.rename(
        columns={
            "codigo_producto": "codigo_factura",
            "descripcion_compras": "descripcion",
            "categoria_grupo5": "grupo5",
            "subcategoria_grupo4": "grupo4",
            "neto_acumulado": "neto_f",
            "cantidad_acumulada": "cantidad_f",
        }
    )
    merged = merge_maestra_consolidacion(mae_for_merge, cons)

    out = pd.DataFrame(
        {
            "Codigo_Producto": merged["codigo_factura"],
            "EAN_Consolidacion": merged.get("ean_consolidacion", ""),
            "Descripcion_Consolidacion": merged.get("descripcion_consolidacion", ""),
            "Descripcion_Compras": merged.get("descripcion_compras", merged.get("descripcion", "")),
            "Descripcion_Unificada": merged.apply(
                lambda r: str(
                    r.get("descripcion_consolidacion")
                    or r.get("descripcion_compras")
                    or r.get("descripcion")
                    or ""
                )[:200],
                axis=1,
            ),
            "Proveedor_Principal_Compras": merged.get("proveedor_principal", ""),
            "Proveedores_Compras": merged.get("proveedores", ""),
            "Num_Proveedores": merged.get("num_proveedores", ""),
            "Proveedor_Consolidacion": merged.get("proveedor_consolidacion", ""),
            "Familia_Consolidacion": merged.get("familia_consolidacion", ""),
            "Marca_Consolidacion": merged.get("marca_consolidacion", ""),
            "Categoria_Grupo5": merged.get("grupo5", ""),
            "Subcategoria_Grupo4": merged.get("grupo4", ""),
            "Grupo1": merged.get("grupo1", ""),
            "Familia_AA": merged.get("familia_aa", ""),
            "Neto_Acumulado_CLP": merged.get("neto_f", 0),
            "Cantidad_Acumulada": merged.get("cantidad_f", 0),
            "Ultimo_Costo_Unitario": merged.get("ultimo_costo_unitario", ""),
            "Costo_Promedio_Ponderado": merged.get("costo_promedio_ponderado", ""),
            "Lineas_Historicas": merged.get("num_lineas_historicas", ""),
            "Ultimo_Anio_Compra": merged.get("ultimo_anio", ""),
            "En_Maestra_Compras": "S",
            "En_Consolidacion": merged["en_consolidacion"].map({True: "S", False: "N"}),
            "Codigo_Barra_Sugerido": merged.apply(
                lambda r: norm_ean(r.get("ean_consolidacion", ""))
                or str(r.get("codigo_factura", "")).strip()[:50],
                axis=1,
            ),
        }
    )

    # Full outer: filas solo consolidación
    if cons is not None and not cons.empty:
        codigos_mae = set(mae_cod["codigo_n"].astype(str))
        solo = cons[~cons["codigo_n"].isin(codigos_mae)].copy()
        if not solo.empty:
            extra = pd.DataFrame(
                {
                    "Codigo_Producto": solo["codigo_producto"],
                    "EAN_Consolidacion": solo["ean_consolidacion"],
                    "Descripcion_Consolidacion": solo["descripcion_consolidacion"],
                    "Descripcion_Compras": "",
                    "Descripcion_Unificada": solo["descripcion_consolidacion"],
                    "Proveedor_Principal_Compras": "",
                    "Proveedores_Compras": "",
                    "Num_Proveedores": "",
                    "Proveedor_Consolidacion": solo["proveedor_consolidacion"],
                    "Familia_Consolidacion": solo["familia_consolidacion"],
                    "Marca_Consolidacion": solo["marca_consolidacion"],
                    "Categoria_Grupo5": "",
                    "Subcategoria_Grupo4": "",
                    "Grupo1": "",
                    "Familia_AA": "",
                    "Neto_Acumulado_CLP": 0,
                    "Cantidad_Acumulada": 0,
                    "Ultimo_Costo_Unitario": "",
                    "Costo_Promedio_Ponderado": "",
                    "Lineas_Historicas": 0,
                    "Ultimo_Anio_Compra": "",
                    "En_Maestra_Compras": "N",
                    "En_Consolidacion": "S",
                    "Codigo_Barra_Sugerido": solo["ean_n"].where(
                        solo["ean_n"].astype(str).str.len() >= 8, solo["codigo_n"]
                    ),
                }
            )
            out = pd.concat([out, extra], ignore_index=True)

    out.sort_values(
        ["En_Maestra_Compras", "Neto_Acumulado_CLP"],
        ascending=[False, False],
        inplace=True,
    )
    return out


def build_detalle_compras(agg: pd.DataFrame, cons: pd.DataFrame | None) -> pd.DataFrame:
    from services.maestra_unificado_loaders import merge_maestra_consolidacion, norm_ean

    merged = merge_maestra_consolidacion(agg, cons)
    return pd.DataFrame(
        {
            "Codigo_Producto": merged["codigo_factura"],
            "Proveedor": merged["proveedor"],
            "Descripcion_Compras": merged["descripcion"],
            "EAN_Consolidacion": merged.get("ean_consolidacion", ""),
            "Descripcion_Consolidacion": merged.get("descripcion_consolidacion", ""),
            "Familia_Consolidacion": merged.get("familia_consolidacion", ""),
            "Marca_Consolidacion": merged.get("marca_consolidacion", ""),
            "Neto_Acumulado_CLP": merged["neto_f"].round(0),
            "Cantidad_Acumulada": merged["cantidad_f"].round(2),
            "Ultimo_Costo_Unitario": merged["ultimo_costo_unitario"],
            "Costo_Promedio_Ponderado": merged["costo_promedio_ponderado"],
            "Categoria_Grupo5": merged.get("grupo5", ""),
            "Subcategoria_Grupo4": merged.get("grupo4", ""),
            "Lineas_Historicas": merged["num_lineas_historicas"],
            "En_Consolidacion": merged["en_consolidacion"].map({True: "S", False: "N"}),
            "Codigo_Barra_Sugerido": merged.apply(
                lambda r: norm_ean(r.get("ean_consolidacion", ""))
                or str(r.get("codigo_factura", "")).strip()[:50],
                axis=1,
            ),
        }
    ).sort_values("Neto_Acumulado_CLP", ascending=False)


def build_resumen(raw, agg, mae_cod, cons, consolidado) -> pd.DataFrame:
    from services.maestra_unificado_loaders import norm_cod

    n_mae = len(mae_cod)
    n_cons = len(cons) if cons is not None else 0
    cod_mae = set(mae_cod["codigo_n"])
    cod_cons = set(cons["codigo_n"]) if cons is not None else set()
    rows = [
        ("Generado", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Filas historico compras (Hoja1)", len(raw)),
        ("Claves codigo+proveedor (detalle)", len(agg)),
        ("Codigos unicos maestra compras", n_mae),
        ("Codigos unicos consolidacion", n_cons),
        ("Codigos en ambos", len(cod_mae & cod_cons)),
        ("Solo maestra compras", len(cod_mae - cod_cons)),
        ("Solo consolidacion", len(cod_cons - cod_mae)),
        ("Filas hoja Consolidado_Codigo", len(consolidado)),
        (
            "Con EAN consolidacion valido",
            int((consolidado["EAN_Consolidacion"].astype(str).str.replace(r"\D", "", regex=True).str.len() >= 8).sum())
            if "EAN_Consolidacion" in consolidado.columns
            else 0,
        ),
        (
            "Con compras (neto>0)",
            int((pd.to_numeric(consolidado["Neto_Acumulado_CLP"], errors="coerce").fillna(0) > 0).sum()),
        ),
    ]
    return pd.DataFrame(rows, columns=["Metrica", "Valor"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maestra", type=Path, default=None)
    ap.add_argument("--consolidacion", type=Path, default=None)
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--consolidacion-sample", type=int, default=0, help="Solo N filas cons (prueba)")
    args = ap.parse_args()

    from services.maestra_unificado_loaders import (
        load_consolidacion,
        resolve_consolidacion_path,
        resolve_maestra_path,
    )

    maestra_path = resolve_maestra_path(args.maestra)
    cons_path = resolve_consolidacion_path(args.consolidacion)

    print("Maestra:", maestra_path)
    raw, agg = load_maestra_detalle(maestra_path)
    mae_cod = aggregate_maestra_por_codigo(agg)
    print("Codigos unicos compras:", len(mae_cod))

    cons = None
    if cons_path:
        print("Consolidacion:", cons_path)
        sample = args.consolidacion_sample if args.consolidacion_sample > 0 else None
        cons = load_consolidacion(cons_path, sample=sample)
        print("Codigos unicos catalogo:", len(cons))

    consolidado = build_consolidado_codigo(mae_cod, cons)
    detalle = build_detalle_compras(agg, cons)
    resumen = build_resumen(raw, agg, mae_cod, cons, consolidado)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print("Escribiendo:", args.output)
    with pd.ExcelWriter(args.output, engine="openpyxl") as w:
        resumen.to_excel(w, sheet_name="Resumen", index=False)
        consolidado.to_excel(w, sheet_name="Consolidado_Codigo", index=False)
        detalle.to_excel(w, sheet_name="Detalle_Compras", index=False)
        mae_cod.to_excel(w, sheet_name="Maestra_Por_Codigo", index=False)

    print("Listo:", args.output.resolve())
    print(resumen.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
