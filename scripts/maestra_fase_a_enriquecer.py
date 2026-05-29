#!/usr/bin/env python3
"""
Fase A — Maestra de compras (2024-2026) vs catálogo ERP.

Solo lectura sobre BD y Excel; escribe CSV en respaldos/.
No modifica productos ni proveedores.

Uso (raíz del proyecto):
  .\\venv\\Scripts\\python.exe scripts\\maestra_fase_a_enriquecer.py
  .\\venv\\Scripts\\python.exe scripts\\maestra_fase_a_enriquecer.py --maestra "C:\\ERP FERRETERIA\\Maestra_Ferreteria_Santo_Domingo.xlsx"
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MAESTRA = ROOT / "docs" / "Maestro Materiales" / "Maestra_Ferreteria_Santo_Domingo.xlsx"
FALLBACK_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")
OUT_BASE = ROOT / "respaldos" / "maestra_fase_a"


def norm_text(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_proveedor(x) -> str:
    s = norm_text(x)
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    return s


def strip_int_chilemat(cod: str) -> str:
    c = norm_text(cod)
    if c.startswith("INT-"):
        return c[4:].strip()
    return c


_STOP_TOKENS = frozenset(
    {
        "DE",
        "LA",
        "EL",
        "Y",
        "EN",
        "PARA",
        "CON",
        "DEL",
        "LOS",
        "LAS",
        "UN",
        "UNA",
        "X",
        "MM",
        "CM",
        "MTS",
        "LT",
        "LTS",
        "KG",
        "GR",
        "GRS",
    }
)


def token_set(text: str) -> set[str]:
    words = [
        w
        for w in norm_text(text).split()
        if len(w) >= 3 and w not in _STOP_TOKENS and not w.isdigit()
    ]
    return set(words[:14])


def build_token_index(pdf: pd.DataFrame) -> list[tuple[int, set[str], object]]:
    out = []
    for _, r in pdf.iterrows():
        toks = token_set(r.get("nombre") or "")
        if len(toks) >= 2:
            out.append((int(r["id"]), toks, r))
    return out


def match_por_tokens(desc: str, token_index: list) -> tuple[object | None, float]:
    dt = token_set(desc or "")
    if len(dt) < 2:
        return None, 0.0
    best_row = None
    best_score = 0.0
    for _pid, ptoks, row in token_index:
        inter = len(dt & ptoks)
        if inter < 2:
            continue
        score = inter / max(len(dt), len(ptoks))
        if score > best_score:
            best_score = score
            best_row = row
    return best_row, best_score


def col_by_hint(columns, *hints):
    for c in columns:
        cl = str(c).lower()
        if all(h.lower() in cl for h in hints):
            return c
    return None


def load_maestra(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = "Hoja1" if "Hoja1" in xl.sheet_names else 0
    df = pd.read_excel(path, sheet_name=sheet)
    rename = {}
    for c in df.columns:
        cl = str(c).lower()
        cl_ascii = (
            cl.replace("ó", "o")
            .replace("í", "i")
            .replace("é", "e")
            .replace("á", "a")
            .replace("ú", "u")
            .replace("ñ", "n")
        )
        if cl in ("año", "ano", "anio") or "año" in cl or cl_ascii == "ano":
            rename[c] = "anio"
        elif "razon" in cl and "proveedor" in cl:
            rename[c] = "proveedor"
        elif str(c).strip().upper() == "OC":
            rename[c] = "oc"
        elif ("codigo" in cl_ascii or "cod" in cl_ascii) and "producto" in cl_ascii:
            rename[c] = "codigo_factura"
        elif "descrip" in cl_ascii and "producto" in cl_ascii:
            rename[c] = "descripcion"
        elif "grupo5" in cl.lower():
            rename[c] = "grupo5"
        elif "grupo4" in cl.lower():
            rename[c] = "grupo4"
        elif "grupo1" in cl.lower():
            rename[c] = "grupo1"
        elif "maestra.aa" in cl.lower() or c == "Maestra.AA":
            rename[c] = "familia_aa"
        elif "cantidad" in cl:
            rename[c] = "cantidad"
        elif "neto" in cl:
            rename[c] = "neto"
    df = df.rename(columns=rename)
    if "codigo_factura" not in df.columns:
        cand = col_by_hint(df.columns, "producto")
        if cand and cand != "descripcion":
            df = df.rename(columns={cand: "codigo_factura"})
        elif len(df.columns) >= 5:
            df = df.rename(columns={df.columns[4]: "codigo_factura"})
    required = {"codigo_factura", "proveedor", "descripcion", "neto", "cantidad"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Columnas faltantes en maestra: {missing}. Tiene: {list(df.columns)}")
    df["codigo_factura_n"] = df["codigo_factura"].map(norm_text)
    df["proveedor_n"] = df["proveedor"].map(norm_proveedor)
    df["descripcion_n"] = df["descripcion"].map(norm_text)
    df["neto_f"] = pd.to_numeric(df["neto"], errors="coerce")
    df["cantidad_f"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["costo_unitario"] = df["neto_f"] / df["cantidad_f"].replace(0, pd.NA)
    if "anio" in df.columns:
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    return df


def aggregate_por_codigo(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por código factura + proveedor normalizado."""
    gcols = ["codigo_factura", "codigo_factura_n", "proveedor", "proveedor_n"]
    agg = {
        "descripcion": "last",
        "descripcion_n": "last",
        "neto_f": "sum",
        "cantidad_f": "sum",
        "costo_unitario": "last",
        "oc": "last" if "oc" in df.columns else "first",
    }
    for c in ("grupo5", "grupo4", "grupo1", "familia_aa", "anio"):
        if c in df.columns:
            agg[c] = "last"
    base = df.groupby(gcols, as_index=False).agg(agg)
    base["num_lineas_historicas"] = df.groupby(
        ["codigo_factura_n", "proveedor_n"]
    ).size().values
    base["costo_promedio_ponderado"] = base["neto_f"] / base["cantidad_f"].replace(0, pd.NA)
    # última compra por orden de aparición en archivo (proxy si no hay fecha fina)
    last_rows = []
    for (cf, pv), grp in df.groupby(["codigo_factura_n", "proveedor_n"]):
        last = grp.iloc[-1]
        last_rows.append(
            {
                "codigo_factura_n": cf,
                "proveedor_n": pv,
                "ultimo_costo_unitario": last.get("costo_unitario"),
                "ultimo_anio": last.get("anio") if "anio" in last else None,
                "ultimo_neto": last.get("neto_f"),
                "ultimo_cantidad": last.get("cantidad_f"),
            }
        )
    last_df = pd.DataFrame(last_rows)
    return base.merge(last_df, on=["codigo_factura_n", "proveedor_n"], how="left")


def load_erp_catalog():
    import app as m
    from app import db

    with m.app.app_context():
        productos = db.session.execute(
            db.text(
                """
                SELECT id, nombre, codigo_barra, codigo_interno, codigo_chilemat,
                       precio_compra, precio_venta, categoria, subcategoria, activo
                FROM productos
                """
            )
        ).mappings().all()
        proveedores = db.session.execute(
            db.text("SELECT id, nombre FROM proveedores")
        ).mappings().all()
        try:
            puentes = db.session.execute(
                db.text(
                    """
                    SELECT pcp.proveedor_id, pcp.codigo_factura_proveedor, pcp.producto_id,
                           pr.nombre AS proveedor_nombre
                    FROM producto_codigo_proveedor pcp
                    JOIN proveedores pr ON pr.id = pcp.proveedor_id
                    """
                )
            ).mappings().all()
        except Exception:
            puentes = []
    pdf = pd.DataFrame([dict(r) for r in productos])
    prv = pd.DataFrame([dict(r) for r in proveedores])
    puente = pd.DataFrame([dict(r) for r in puentes]) if puentes else pd.DataFrame()
    return pdf, prv, puente


def build_erp_indexes(pdf: pd.DataFrame, prv: pd.DataFrame, puente: pd.DataFrame):
    by_barra, by_interno, by_chilemat, by_nombre = {}, {}, {}, {}
    for _, r in pdf.iterrows():
        pid = int(r["id"])
        for key, bucket in (
            (norm_text(r.get("codigo_barra")), by_barra),
            (norm_text(r.get("codigo_interno")), by_interno),
            (norm_text(r.get("codigo_chilemat")), by_chilemat),
            (norm_text(r.get("nombre")), by_nombre),
        ):
            if key and key not in bucket:
                bucket[key] = r
    prov_by_norm = {}
    for _, r in prv.iterrows():
        k = norm_proveedor(r.get("nombre"))
        if k and k not in prov_by_norm:
            prov_by_norm[k] = r
    puente_map = {}
    if not puente.empty:
        for _, r in puente.iterrows():
            k = (int(r["proveedor_id"]), norm_text(r["codigo_factura_proveedor"]))
            puente_map[k] = int(r["producto_id"])
    token_index = build_token_index(pdf)
    return by_barra, by_interno, by_chilemat, by_nombre, prov_by_norm, puente_map, pdf, token_index


def match_row(row, indexes, pdf):
    by_barra, by_interno, by_chilemat, by_nombre, prov_by_norm, puente_map, _, token_index = indexes
    cod = row["codigo_factura_n"]
    prov_n = row["proveedor_n"]
    prov_row = prov_by_norm.get(prov_n)
    prov_id = int(prov_row["id"]) if prov_row is not None else None

    if prov_id and (prov_id, cod) in puente_map:
        pid = puente_map[(prov_id, cod)]
        p = pdf[pdf["id"] == pid].iloc[0]
        return pid, p, "puente_factura", 100

    for etiqueta, bucket in (
        ("codigo_barra", by_barra),
        ("codigo_interno", by_interno),
        ("codigo_chilemat", by_chilemat),
    ):
        if cod in bucket:
            p = bucket[cod]
            return int(p["id"]), p, etiqueta, 95

    cod_sin = strip_int_chilemat(cod)
    if cod_sin and cod_sin in by_chilemat:
        p = by_chilemat[cod_sin]
        return int(p["id"]), p, "chilemat_sin_INT", 90

    if cod.startswith("INT-") and cod[4:] in by_chilemat:
        p = by_chilemat[cod[4:]]
        return int(p["id"]), p, "chilemat_sin_INT", 90

    desc = row.get("descripcion_n") or ""
    if desc and desc in by_nombre:
        p = by_nombre[desc]
        return int(p["id"]), p, "nombre_exacto", 75

    p_tok, score = match_por_tokens(desc, token_index)
    if p_tok is not None and score >= 0.72:
        return int(p_tok["id"]), p_tok, "descripcion_tokens", int(round(score * 100))
    if p_tok is not None and score >= 0.55:
        return int(p_tok["id"]), p_tok, "descripcion_tokens", int(round(score * 100))

    return None, None, "", 0


def main():
    ap = argparse.ArgumentParser(description="Fase A maestra compras → CSV enriquecidos")
    ap.add_argument("--maestra", type=Path, default=DEFAULT_MAESTRA)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.maestra.is_file() and FALLBACK_MAESTRA.is_file():
        args.maestra = FALLBACK_MAESTRA
    if not args.maestra.is_file():
        raise SystemExit(
            f"No existe maestra: {args.maestra}\n"
            f"Coloque el archivo en {DEFAULT_MAESTRA} o use --maestra."
        )

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = args.out or (OUT_BASE / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Leyendo maestra:", args.maestra)
    raw = load_maestra(args.maestra)
    agg = aggregate_por_codigo(raw)
    print("Filas maestra:", len(raw), "| Claves factura+proveedor:", len(agg))

    pdf, prv, puente = load_erp_catalog()
    print("ERP productos:", len(pdf), "| proveedores:", len(prv), "| puentes factura:", len(puente))

    indexes = build_erp_indexes(pdf, prv, puente)

    rows = []
    for _, row in agg.iterrows():
        pid, prod, metodo, conf = match_row(row, indexes, pdf)
        precio_erp = float(prod["precio_compra"] or 0) if prod is not None else None
        ultimo_raw = row.get("ultimo_costo_unitario")
        ultimo = None
        if ultimo_raw is not None and pd.notna(ultimo_raw):
            ultimo = float(ultimo_raw)
        delta_pct = None
        if precio_erp and ultimo is not None and precio_erp > 0:
            delta_pct = round((ultimo - precio_erp) / precio_erp * 100, 1)

        if pid is None:
            estado = "sin_producto_erp"
        elif conf >= 90:
            estado = "match_alto"
        elif conf >= 72:
            estado = "match_medio"
        elif conf >= 55:
            estado = "revisar"
        else:
            estado = "sin_producto_erp"

        rows.append(
            {
                "codigo_factura": row["codigo_factura"],
                "proveedor": row["proveedor"],
                "descripcion_maestra": row["descripcion"],
                "familia_aa": row.get("familia_aa", ""),
                "categoria_sugerida": row.get("grupo5", ""),
                "subcategoria_sugerida": row.get("grupo4", ""),
                "grupo1": row.get("grupo1", ""),
                "num_lineas_historicas": int(row.get("num_lineas_historicas", 0)),
                "neto_acumulado": round(float(row.get("neto_f") or 0), 0),
                "cantidad_acumulada": round(float(row.get("cantidad_f") or 0), 2),
                "ultimo_costo_unitario": round(ultimo, 2) if ultimo is not None else "",
                "costo_promedio_ponderado": round(float(row["costo_promedio_ponderado"]), 2)
                if pd.notna(row.get("costo_promedio_ponderado"))
                else "",
                "ultimo_anio": row.get("ultimo_anio", ""),
                "producto_id": pid or "",
                "producto_nombre_erp": (prod["nombre"] if prod is not None else ""),
                "codigo_barra_erp": (prod.get("codigo_barra") or "") if prod is not None else "",
                "codigo_chilemat_erp": (prod.get("codigo_chilemat") or "") if prod is not None else "",
                "precio_compra_erp": precio_erp if precio_erp is not None else "",
                "delta_costo_pct": delta_pct if delta_pct is not None else "",
                "match_metodo": metodo,
                "match_confianza": conf,
                "match_estado": estado,
            }
        )

    full = pd.DataFrame(rows)
    full.sort_values(["neto_acumulado"], ascending=False, inplace=True)

    path_full = out_dir / "01_maestra_enriquecida.csv"
    full.to_csv(path_full, index=False, encoding="utf-8-sig")

    match_ok = full[full["match_estado"] == "match_alto"].copy()
    match_ok.to_csv(out_dir / "02_match_alto.csv", index=False, encoding="utf-8-sig")

    match_medio = full[full["match_estado"] == "match_medio"].copy()
    match_medio.to_csv(out_dir / "07_match_medio.csv", index=False, encoding="utf-8-sig")

    revisar = full[full["match_estado"] == "revisar"].copy()
    revisar.to_csv(out_dir / "03_match_revisar.csv", index=False, encoding="utf-8-sig")

    sin_prod = full[full["match_estado"] == "sin_producto_erp"].copy()
    sin_prod.to_csv(out_dir / "04_sin_producto_erp.csv", index=False, encoding="utf-8-sig")

    propuestas = sin_prod.sort_values("neto_acumulado", ascending=False).head(500)
    propuestas_out = propuestas[
        [
            "codigo_factura",
            "proveedor",
            "descripcion_maestra",
            "familia_aa",
            "categoria_sugerida",
            "subcategoria_sugerida",
            "ultimo_costo_unitario",
            "neto_acumulado",
            "num_lineas_historicas",
        ]
    ].copy()
    propuestas_out.rename(
        columns={
            "descripcion_maestra": "nombre_sugerido",
            "ultimo_costo_unitario": "precio_compra_sugerido",
        },
        inplace=True,
    )
    propuestas_out.to_csv(out_dir / "08_propuestas_alta_producto.csv", index=False, encoding="utf-8-sig")

    full["_delta_num"] = pd.to_numeric(full["delta_costo_pct"], errors="coerce")
    desact = full[
        (full["producto_id"] != "") & full["_delta_num"].notna() & (full["_delta_num"].abs() >= 5)
    ].copy()
    desact["delta_abs"] = desact["_delta_num"].abs()
    desact.sort_values("delta_abs", ascending=False, inplace=True)
    top_desact = desact.head(100)
    top_desact.drop(columns=["_delta_num"], errors="ignore").to_csv(
        out_dir / "05_top_costos_desactualizados.csv", index=False, encoding="utf-8-sig"
    )
    full.drop(columns=["_delta_num"], errors="ignore", inplace=True)

    sin_prod.sort_values("neto_acumulado", ascending=False, inplace=True)
    top_sin = sin_prod.head(100)
    top_sin.to_csv(out_dir / "06_top_sin_producto_por_compra.csv", index=False, encoding="utf-8-sig")

    resumen = f"""# Fase A — Maestra de compras

Generado: {datetime.now().isoformat(timespec="seconds")}
Maestra: {args.maestra}
Salida: {out_dir}

## Conteos
| Métrica | Valor |
|---------|------:|
| Filas históricas (maestra) | {len(raw):,} |
| Códigos factura + proveedor únicos | {len(agg):,} |
| Productos ERP | {len(pdf):,} |
| Match alto (confianza >=90) | {(full["match_estado"] == "match_alto").sum():,} |
| Match medio (tokens/nombre, >=72) | {(full["match_estado"] == "match_medio").sum():,} |
| Revisar manualmente | {(full["match_estado"] == "revisar").sum():,} |
| Propuestas alta producto (top 500 sin match) | {len(propuestas_out):,} |
| Sin producto ERP | {(full["match_estado"] == "sin_producto_erp").sum():,} |
| Top costos desactualizados (>=5%) | {len(top_desact):,} |

## Archivos
- `01_maestra_enriquecida.csv` — dataset completo
- `02_match_alto.csv` — listo para Fase B (vínculo + costo)
- `07_match_medio.csv` — Fase B con revisión ligera
- `03_match_revisar.csv` — confirmar en ERP
- `08_propuestas_alta_producto.csv` — crear ficha en ERP (sin match)
- `04_sin_producto_erp.csv` — crear ficha o ignorar
- `05_top_costos_desactualizados.csv`
- `06_top_sin_producto_por_compra.csv`

## Rollback
Ver `REVERT_MAESTRA_FASE_A.md` en la raíz del proyecto.
Tag git: `checkpoint/maestra-fase-a-pre-2026-05-27`
"""
    (out_dir / "RESUMEN.md").write_text(resumen, encoding="utf-8")
    print(resumen)
    print("Listo:", out_dir)


if __name__ == "__main__":
    main()
