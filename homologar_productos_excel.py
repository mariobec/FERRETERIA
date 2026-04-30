import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


TARGET_COLUMNS = [
    "nombre",
    "codigo_barra",
    "precio_compra",
    "precio_venta",
    "precio_mayoreo",
    "unidad_compra",
    "unidad_venta",
    "factor_conversion",
    "stock",
    "categoria",
    "subcategoria",
    "ubicacion_pasillo",
    "ubicacion_estante",
    "ubicacion_nivel",
]

ALIASES = {
    "nombre": ["nombre", "producto", "descripcion", "descripcion producto", "item"],
    "codigo_barra": ["codigo", "codigo barra", "cod barra", "barcode", "sku", "codigo producto"],
    "precio_compra": ["precio compra", "costo", "costo neto", "costo compra", "costo final"],
    "precio_venta": ["precio venta", "precio publico", "pvp", "precio unitario", "precio venta final", "precio lista"],
    "precio_mayoreo": ["precio mayorista", "precio mayoreo", "precio por mayor"],
    "unidad_compra": ["unidad compra", "um compra"],
    "unidad_venta": ["unidad venta", "um venta", "unidad"],
    "factor_conversion": ["factor", "factor conversion", "conversion", "medida"],
    "stock": ["stock", "existencia", "saldo", "cantidad"],
    "categoria": ["categoria", "rubro", "familia"],
    "subcategoria": ["subcategoria", "sub categoria", "subfamilia", "linea"],
    "ubicacion_pasillo": ["pasillo", "ubicacion pasillo"],
    "ubicacion_estante": ["estante", "ubicacion estante"],
    "ubicacion_nivel": ["nivel", "ubicacion nivel"],
}


def norm(value: str) -> str:
    value = str(value or "").strip().lower()
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )
    value = re.sub(r"[\s_\-]+", " ", value)
    return value


def parse_float(value, default=0.0):
    if value is None:
        return default
    raw = str(value).strip()
    if not raw:
        return default
    raw = raw.replace(" ", "")
    # soporta 1.234,56 o 1,234.56
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return default


def parse_int(value, default=0):
    return int(round(parse_float(value, default)))


def resolver_mapeo(df_columns):
    normalized = {norm(c): c for c in df_columns}
    mapping = {}
    for target in TARGET_COLUMNS:
        found = None
        for alias in ALIASES.get(target, []):
            if norm(alias) in normalized:
                found = normalized[norm(alias)]
                break
        mapping[target] = found
    return mapping


def homologar(df: pd.DataFrame):
    mapping = resolver_mapeo(df.columns)
    out = pd.DataFrame(columns=TARGET_COLUMNS)

    for col in TARGET_COLUMNS:
        src = mapping.get(col)
        out[col] = df[src] if src else ""

    out["nombre"] = out["nombre"].fillna("").astype(str).str.strip()
    out["codigo_barra"] = out["codigo_barra"].fillna("").astype(str).str.strip()
    out["categoria"] = out["categoria"].fillna("").astype(str).str.strip()
    out["subcategoria"] = out["subcategoria"].fillna("").astype(str).str.strip()
    out["unidad_compra"] = out["unidad_compra"].fillna("").astype(str).str.strip()
    out["unidad_venta"] = out["unidad_venta"].fillna("").astype(str).str.strip()
    out["ubicacion_pasillo"] = out["ubicacion_pasillo"].fillna("").astype(str).str.strip().str.upper()
    out["ubicacion_estante"] = out["ubicacion_estante"].fillna("").astype(str).str.strip().str.upper()
    out["ubicacion_nivel"] = out["ubicacion_nivel"].fillna("").astype(str).str.strip().str.upper()

    out["precio_compra"] = out["precio_compra"].apply(parse_float)
    out["precio_venta"] = out["precio_venta"].apply(parse_float)
    out["precio_mayoreo"] = out["precio_mayoreo"].apply(parse_float)
    out["factor_conversion"] = out["factor_conversion"].apply(lambda v: parse_float(v, 1.0) or 1.0)
    out["stock"] = out["stock"].apply(parse_int)

    # Fallbacks para archivos de maestro comercial sin todas las columnas ERP.
    out.loc[out["precio_compra"] <= 0, "precio_compra"] = out["precio_venta"]
    out.loc[out["precio_venta"] <= 0, "precio_venta"] = out["precio_compra"]
    out.loc[out["precio_mayoreo"] <= 0, "precio_mayoreo"] = out["precio_venta"]
    out.loc[out["factor_conversion"] <= 0, "factor_conversion"] = 1.0
    out.loc[out["unidad_compra"] == "", "unidad_compra"] = out["unidad_venta"]
    out.loc[out["unidad_venta"] == "", "unidad_venta"] = "Unidad"
    out.loc[out["unidad_compra"] == "", "unidad_compra"] = "Unidad"

    return out, mapping


def main():
    parser = argparse.ArgumentParser(description="Homologa un Excel de productos al formato CSV del ERP.")
    parser.add_argument("--input", required=True, help="Ruta del archivo de entrada (.xlsx, .xls, .csv)")
    parser.add_argument("--output", default="productos_homologados.csv", help="Ruta CSV salida")
    parser.add_argument("--errores", default="productos_homologacion_errores.csv", help="Ruta CSV errores")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"No existe archivo de entrada: {in_path}")

    if in_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(in_path)
    else:
        try:
            df = pd.read_csv(in_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(in_path, encoding="latin-1")

    df_out, mapping = homologar(df)

    mask_error = (df_out["nombre"] == "") | (df_out["codigo_barra"] == "")
    df_ok = df_out[~mask_error].copy()
    df_err = df_out[mask_error].copy()

    df_ok.to_csv(args.output, index=False, encoding="utf-8")
    if not df_err.empty:
        df_err.to_csv(args.errores, index=False, encoding="utf-8")

    print("=== HOMOLOGACION COMPLETADA ===")
    print(f"Entrada: {in_path}")
    print(f"Salida OK: {Path(args.output)} ({len(df_ok)} filas)")
    print(f"Filas con error (nombre/codigo_barra vacio): {len(df_err)}")
    if not df_err.empty:
        print(f"Archivo errores: {Path(args.errores)}")
    print("Mapeo detectado:")
    for k, v in mapping.items():
        print(f"  - {k}: {v or '[NO ENCONTRADA]'}")


if __name__ == "__main__":
    main()
