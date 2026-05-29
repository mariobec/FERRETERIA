"""
Carga y unión Maestra compras + Consolidación materiales (solo datos, sin BD).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAESTRA = ROOT / "docs" / "Maestro Materiales" / "Maestra_Ferreteria_Santo_Domingo.xlsx"
DEFAULT_CONSOLIDACION = ROOT / "docs" / "Maestro Materiales" / "Consolidacion_Maestro_Materiales.xlsx"
FALLBACK_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")


def resolve_maestra_path(path: Path | None) -> Path:
    if path and path.is_file():
        return path
    if DEFAULT_MAESTRA.is_file():
        return DEFAULT_MAESTRA
    if FALLBACK_MAESTRA.is_file():
        return FALLBACK_MAESTRA
    raise FileNotFoundError(
        f"No se encontró maestra de compras. Coloque el Excel en {DEFAULT_MAESTRA} "
        f"o pase --maestra."
    )


def resolve_consolidacion_path(path: Path | None) -> Path | None:
    if path and path.is_file():
        return path
    if DEFAULT_CONSOLIDACION.is_file():
        return DEFAULT_CONSOLIDACION
    return None


def norm_cod(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    s = re.sub(r"\s+", "", s)
    if s.startswith("INT-"):
        s = s[4:]
    return s


def norm_ean(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = re.sub(r"\D", "", str(x).strip())
    if len(s) >= 8:
        return s[:50]
    return ""


def norm_text(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    return re.sub(r"\s+", " ", s)


def _col_match(columns, *parts: str):
    for c in columns:
        u = str(c).upper()
        if all(p.upper() in u for p in parts):
            return c
    return None


def load_consolidacion(path: Path, *, sample: int | None = None) -> pd.DataFrame:
    """Una fila por código producto; prioriza fila con EAN válido."""
    df = pd.read_excel(path, sheet_name=0)
    if sample and sample > 0:
        df = df.head(sample)

    ccol = _col_match(df.columns, "CODIGO", "PRODUCTO") or df.columns[min(3, len(df.columns) - 1)]
    bcol = (
        _col_match(df.columns, "BARRA")
        or _col_match(df.columns, "EAN")
        or _col_match(df.columns, "CODIGO", "BARRA")
    )
    dcol = _col_match(df.columns, "DESCRIPCION") or df.columns[min(4, len(df.columns) - 1)]
    pcol = _col_match(df.columns, "PROVEEDOR") or df.columns[min(1, len(df.columns) - 1)]
    fcol = _col_match(df.columns, "FAMILIA") or _col_match(df.columns, "GRUPO")
    mcol = _col_match(df.columns, "MARCA")

    out = pd.DataFrame(
        {
            "codigo_producto": df[ccol],
            "ean_consolidacion": df[bcol] if bcol else "",
            "descripcion_consolidacion": df[dcol],
            "proveedor_consolidacion": df[pcol] if pcol else "",
            "familia_consolidacion": df[fcol] if fcol else "",
            "marca_consolidacion": df[mcol] if mcol else "",
        }
    )
    out["codigo_n"] = out["codigo_producto"].map(norm_cod)
    out["ean_n"] = out["ean_consolidacion"].map(norm_ean)
    out = out[out["codigo_n"] != ""].copy()
    out["_ean_len"] = out["ean_n"].str.len()
    out.sort_values(["codigo_n", "_ean_len"], ascending=[True, False], inplace=True)
    out = out.drop_duplicates(subset=["codigo_n"], keep="first")
    out.drop(columns=["_ean_len"], inplace=True)
    return out


def merge_maestra_consolidacion(maestra_agg: pd.DataFrame, cons: pd.DataFrame | None) -> pd.DataFrame:
    """Enriquece filas agregadas de compras con catálogo consolidación (por código)."""
    base = maestra_agg.copy()
    base["codigo_n"] = base["codigo_factura"].map(norm_cod)
    if cons is None or cons.empty:
        base["ean_consolidacion"] = ""
        base["descripcion_consolidacion"] = ""
        base["familia_consolidacion"] = ""
        base["marca_consolidacion"] = ""
        base["proveedor_consolidacion"] = ""
        base["en_consolidacion"] = False
        return base

    c = cons[
        [
            "codigo_n",
            "ean_consolidacion",
            "descripcion_consolidacion",
            "familia_consolidacion",
            "marca_consolidacion",
            "proveedor_consolidacion",
        ]
    ].copy()
    c["en_consolidacion"] = True
    merged = base.merge(c, on="codigo_n", how="left")
    merged["en_consolidacion"] = merged["en_consolidacion"].fillna(False)
    for col in ("ean_consolidacion", "descripcion_consolidacion", "familia_consolidacion", "marca_consolidacion", "proveedor_consolidacion"):
        if col in merged.columns:
            merged[col] = merged[col].fillna("")
    return merged


def consolidacion_sin_maestra(cons: pd.DataFrame, maestra_codigos: set[str]) -> pd.DataFrame:
    """Códigos solo en catálogo consolidación (sin historial de compra en maestra)."""
    if cons is None or cons.empty:
        return pd.DataFrame()
    solo = cons[~cons["codigo_n"].isin(maestra_codigos)].copy()
    solo["neto_acumulado"] = 0
    solo["ultimo_costo_unitario"] = ""
    solo["codigo_factura"] = solo["codigo_producto"]
    solo["proveedor"] = solo["proveedor_consolidacion"]
    solo["descripcion"] = solo["descripcion_consolidacion"]
    solo["origen"] = "solo_consolidacion"
    return solo
