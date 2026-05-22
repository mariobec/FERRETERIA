import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


TARGET_COLUMNS = [
    "nombre",
    "codigo_chilemat",
    "codigo_interno",
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
    "codigo_chilemat": [
        "codigo chilemat",
        "codigo_chilemat",
        "chilemat",
        "sku chilemat",
        "cod chilemat",
        "codigo cadena",
        "codigo proveedor cadena",
        "ref chilemat",
        "referencia chilemat",
    ],
    "codigo_interno": [
        "codigo interno",
        "codigo_interno",
        "interno",
        "cod interno",
        "sku interno",
        "codigo ferreteria",
    ],
    "codigo_barra": [
        "codigo barra",
        "codigo_barra",
        "cod barra",
        "barcode",
        "ean",
        "ean13",
        "gtin",
        "codigo de barras",
    ],
    "precio_compra": ["precio compra", "costo", "costo neto", "costo compra", "costo final"],
    "precio_venta": [
        "precio venta",
        "precio publico",
        "pvp",
        "precio unitario",
        "precio venta final",
        "precio lista",
    ],
    "precio_mayoreo": ["precio mayorista", "precio mayoreo", "precio por mayor"],
    "unidad_compra": ["unidad compra", "um compra"],
    "unidad_venta": ["unidad venta", "um venta", "unidad"],
    "factor_conversion": ["factor", "factor conversion", "conversion", "medida"],
    "stock": ["stock", "existencia", "saldo", "cantidad", "cantidad stock"],
    "categoria": ["categoria", "rubro", "familia"],
    "subcategoria": ["subcategoria", "sub categoria", "subfamilia", "linea"],
    "ubicacion_pasillo": ["pasillo", "ubicacion pasillo"],
    "ubicacion_estante": ["estante", "ubicacion estante"],
    "ubicacion_nivel": ["nivel", "ubicacion nivel"],
}

# Alias que antes mapeaban a codigo_barra; en modo maestro Chilemat van a codigo_chilemat.
_ALIASES_LEGACY_SKU = ["codigo", "sku", "codigo producto"]


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


def _sanitizar_token(s: str, max_len: int) -> str:
    s = str(s or "").strip().upper()
    s = re.sub(r"[^\w\-]", "", s.replace(" ", "-"))
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s or "SINREF")[:max_len]


def _codigo_barra_pendiente(chilemat: str) -> str:
    """Barras provisional para alta en ERP; se reemplaza en enrolamiento (Caso B)."""
    token = _sanitizar_token(chilemat, 42)
    return f"PEND-{token}"[:50]


def _codigo_interno_sugerido(chilemat: str) -> str:
    token = _sanitizar_token(chilemat, 32)
    if token.upper().startswith("CHM-"):
        return token[:32]
    return f"CHM-{token}"[:32]


def resolver_mapeo(df_columns, maestro_chilemat: bool):
    normalized = {norm(c): c for c in df_columns}
    mapping = {}
    for target in TARGET_COLUMNS:
        found = None
        for alias in ALIASES.get(target, []):
            if norm(alias) in normalized:
                found = normalized[norm(alias)]
                break
        mapping[target] = found

    if maestro_chilemat and not mapping.get("codigo_chilemat"):
        for alias in _ALIASES_LEGACY_SKU:
            if norm(alias) in normalized:
                mapping["codigo_chilemat"] = normalized[norm(alias)]
                break
    elif not mapping.get("codigo_barra"):
        for alias in _ALIASES_LEGACY_SKU:
            if norm(alias) in normalized:
                mapping["codigo_barra"] = normalized[norm(alias)]
                break

    return mapping


def homologar(df: pd.DataFrame, maestro_chilemat: bool = False):
    mapping = resolver_mapeo(df.columns, maestro_chilemat)
    out = pd.DataFrame(columns=TARGET_COLUMNS)

    for col in TARGET_COLUMNS:
        src = mapping.get(col)
        out[col] = df[src] if src else ""

    out["nombre"] = out["nombre"].fillna("").astype(str).str.strip()
    out["codigo_chilemat"] = out["codigo_chilemat"].fillna("").astype(str).str.strip()
    out["codigo_interno"] = out["codigo_interno"].fillna("").astype(str).str.strip()
    out["codigo_barra"] = out["codigo_barra"].fillna("").astype(str).str.strip()
    out["categoria"] = out["categoria"].fillna("").astype(str).str.strip()
    out["subcategoria"] = out["subcategoria"].fillna("").astype(str).str.strip()
    out["unidad_compra"] = out["unidad_compra"].fillna("").astype(str).str.strip()
    out["unidad_venta"] = out["unidad_venta"].fillna("").astype(str).str.strip()
    out["ubicacion_pasillo"] = (
        out["ubicacion_pasillo"].fillna("").astype(str).str.strip().str.upper()
    )
    out["ubicacion_estante"] = (
        out["ubicacion_estante"].fillna("").astype(str).str.strip().str.upper()
    )
    out["ubicacion_nivel"] = (
        out["ubicacion_nivel"].fillna("").astype(str).str.strip().str.upper()
    )

    out["precio_compra"] = out["precio_compra"].apply(parse_float)
    out["precio_venta"] = out["precio_venta"].apply(parse_float)
    out["precio_mayoreo"] = out["precio_mayoreo"].apply(parse_float)
    out["factor_conversion"] = out["factor_conversion"].apply(lambda v: parse_float(v, 1.0) or 1.0)
    out["stock"] = out["stock"].apply(parse_int)

    if maestro_chilemat:
        out["stock"] = 0

    for idx, row in out.iterrows():
        chm = str(row["codigo_chilemat"] or "").strip()
        barra = str(row["codigo_barra"] or "").strip()
        interno = str(row["codigo_interno"] or "").strip()

        if maestro_chilemat and chm:
            if not interno:
                out.at[idx, "codigo_interno"] = _codigo_interno_sugerido(chm)
            if not barra:
                out.at[idx, "codigo_barra"] = _codigo_barra_pendiente(chm)

    out.loc[out["precio_compra"] <= 0, "precio_compra"] = out["precio_venta"]
    out.loc[out["precio_venta"] <= 0, "precio_venta"] = out["precio_compra"]
    out.loc[out["precio_mayoreo"] <= 0, "precio_mayoreo"] = out["precio_venta"]
    out.loc[out["factor_conversion"] <= 0, "factor_conversion"] = 1.0
    out.loc[out["unidad_compra"] == "", "unidad_compra"] = out["unidad_venta"]
    out.loc[out["unidad_venta"] == "", "unidad_venta"] = "Unidad"
    out.loc[out["unidad_compra"] == "", "unidad_compra"] = "Unidad"

    return out, mapping


def _fila_valida(row) -> bool:
    nombre = str(row["nombre"] or "").strip()
    if not nombre:
        return False
    return bool(
        str(row["codigo_barra"] or "").strip()
        or str(row["codigo_chilemat"] or "").strip()
        or str(row["codigo_interno"] or "").strip()
    )


def main():
    parser = argparse.ArgumentParser(
        description="Homologa un Excel de productos al formato CSV del ERP LhexIA."
    )
    parser.add_argument("--input", required=True, help="Ruta del archivo de entrada (.xlsx, .xls, .csv)")
    parser.add_argument("--output", default="productos_homologados.csv", help="Ruta CSV salida")
    parser.add_argument("--errores", default="productos_homologacion_errores.csv", help="Ruta CSV errores")
    parser.add_argument(
        "--maestro",
        action="store_true",
        help=(
            "Carga maestro Chilemat: stock=0, codigo_chilemat obligatorio en filas OK, "
            "genera codigo_barra PEND-* y codigo_interno CHM-* si faltan."
        ),
    )
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

    df_out, mapping = homologar(df, maestro_chilemat=args.maestro)

    mask_ok = df_out.apply(_fila_valida, axis=1)
    df_ok = df_out[mask_ok].copy()
    df_err = df_out[~mask_ok].copy()

    df_ok.to_csv(args.output, index=False, encoding="utf-8")
    if not df_err.empty:
        df_err.to_csv(args.errores, index=False, encoding="utf-8")

    pend = int(df_ok["codigo_barra"].astype(str).str.startswith("PEND-").sum()) if len(df_ok) else 0

    print("=== HOMOLOGACION COMPLETADA ===")
    print(f"Entrada: {in_path}")
    print(f"Modo maestro Chilemat: {'SI' if args.maestro else 'NO'}")
    print(f"Salida OK: {Path(args.output)} ({len(df_ok)} filas)")
    print(f"Filas con error (sin nombre o sin ningun codigo): {len(df_err)}")
    if args.maestro and pend:
        print(f"Barras provisionales PEND-* (reemplazar en enrolamiento): {pend}")
    if not df_err.empty:
        print(f"Archivo errores: {Path(args.errores)}")
    print("Mapeo detectado:")
    for k, v in mapping.items():
        print(f"  - {k}: {v or '[NO ENCONTRADA]'}")


if __name__ == "__main__":
    main()
