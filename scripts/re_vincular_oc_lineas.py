#!/usr/bin/env python3
"""
Re-vincula líneas de OC históricas que quedaron como COMPRA-HIST-MAESTRA.

Lee la Maestra_Ferreteria_Santo_Domingo.xlsx e intenta hacer match de los
productos no resueltos usando EAN/código-de-barras (columna adicional no usada
en el import original) además del Código Producto.

Uso:
  python scripts/re_vincular_oc_lineas.py --dry-run          # muestra qué haría
  python scripts/re_vincular_oc_lineas.py                    # aplica cambios
  python scripts/re_vincular_oc_lineas.py --solo-reporte     # CSV sin tocar BD
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MAESTRA = ROOT / "docs" / "Maestro Materiales" / "Maestra_Ferreteria_Santo_Domingo.xlsx"
FALLBACK_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")
USUARIO_IMPORT = "maestra-import-oc"
CODIGO_GENERICO = "COMPRA-HIST-MAESTRA"

OUT_DIR = ROOT / "respaldos" / "re_vincular_oc"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# Normalización (igual que el script original)
# ──────────────────────────────────────────────

def norm_prov(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", s))


def norm_cod(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip().upper()


def norm_ean(x) -> str:
    """Normaliza EAN/código de barras: solo dígitos, mínimo 8."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = re.sub(r"\D", "", str(x))
    return s if len(s) >= 8 else ""


def col_match(cols, *parts):
    for c in cols:
        u = str(c).upper()
        if all(p.upper() in u for p in parts):
            return c
    return None


# ──────────────────────────────────────────────
# Carga del Excel
# ──────────────────────────────────────────────

def load_maestra(path: Path) -> pd.DataFrame:
    """Carga la Maestra SD completa con todas las columnas útiles."""
    df = pd.read_excel(path, sheet_name="Hoja1")
    cols = df.columns.tolist()
    print(f"  Columnas encontradas: {cols}")

    col_anio = cols[0]

    # OC: buscar coincidencia exacta o columna cuyo nombre sea solo "OC"
    col_oc = next(
        (c for c in cols if str(c).strip().upper() == "OC"),
        col_match(cols, "ORDEN", "COMPRA") or cols[2],
    )

    # Proveedor: columna que contiene "PROVEEDOR"
    col_prov = next(
        (c for c in cols if "PROVEEDOR" in str(c).upper()),
        cols[1],
    )

    # Código producto proveedor
    col_cod = next(
        (c for c in cols if "DIGO" in str(c).upper() and "PRODUCTO" in str(c).upper()),
        cols[3],
    )

    # Código de barra / EAN
    col_ean = next(
        (c for c in cols if "BARRA" in str(c).upper() or "EAN" in str(c).upper()),
        None,
    )

    # Descripción
    col_desc = next(
        (c for c in cols if "SCRIP" in str(c).upper()),
        cols[5] if len(cols) > 5 else None,
    )

    # Cantidad
    col_cant = next(
        (c for c in cols if "CANTIDAD" in str(c).upper()),
        cols[-2],
    )

    # Neto
    col_neto = next(
        (c for c in cols if "NETO" in str(c).upper()),
        cols[-1],
    )

    print(f"  Usando: anio={col_anio!r} oc={col_oc!r} prov={col_prov!r} "
          f"cod={col_cod!r} ean={col_ean!r} desc={col_desc!r} "
          f"cant={col_cant!r} neto={col_neto!r}")

    # Construir rename dict solo con columnas presentes (evita duplicados)
    rename_map: dict = {}
    seen: set = set()
    for src, dst in [
        (col_anio, "anio"),
        (col_oc,   "oc"),
        (col_prov, "proveedor"),
        (col_cod,  "codigo_proveedor"),
        (col_ean,  "ean"),
        (col_desc, "descripcion"),
        (col_cant, "cantidad"),
        (col_neto, "neto"),
    ]:
        if src and src not in seen:
            rename_map[src] = dst
            seen.add(src)

    df_r = df.rename(columns=rename_map)

    # Columnas de salida (solo las que existen tras el rename)
    out_cols = [c for c in ["anio","oc","proveedor","codigo_proveedor","ean","descripcion","cantidad","neto"]
                if c in df_r.columns]
    # Agregar columna ean vacía si no existía
    if "ean" not in df_r.columns:
        df_r["ean"] = ""
    if "descripcion" not in df_r.columns:
        df_r["descripcion"] = ""

    df2 = df_r[["anio","oc","proveedor","codigo_proveedor","ean","descripcion","cantidad","neto"]]

    df2["anio"]     = pd.to_numeric(df2["anio"], errors="coerce")
    df2["cantidad"] = pd.to_numeric(df2["cantidad"], errors="coerce").fillna(0)
    df2["neto"]     = pd.to_numeric(df2["neto"],     errors="coerce").fillna(0)
    df2 = df2[df2["oc"].notna() & (df2["cantidad"] > 0)].copy()
    # Sin underscore inicial para que funcione con itertuples()
    df2["prov_k"] = df2["proveedor"].map(norm_prov)
    df2["cod_k"]  = df2["codigo_proveedor"].map(norm_cod)
    df2["ean_k"]  = df2["ean"].map(norm_ean)
    df2["oc_k"]   = df2["oc"].apply(
        lambda x: str(int(float(x))) if not pd.isna(x) else str(x).strip()
    )
    return df2


# ──────────────────────────────────────────────
# Índices de productos en ERP
# ──────────────────────────────────────────────

def build_product_indexes(app):
    """Devuelve dicts: ean→prod_id, cod→prod_id (barra/interno/chilemat)."""
    from app import Producto

    ean_idx: dict[str, int] = {}
    cod_idx: dict[str, int] = {}

    with app.app_context():
        for p in Producto.query.filter(Producto.activo == True).all():
            pid = int(p.id)
            for raw in (
                getattr(p, "codigo_barra", None),
                getattr(p, "codigo_chilemat", None),
                getattr(p, "codigo_interno", None),
            ):
                ean = norm_ean(raw)
                if ean and ean not in ean_idx:
                    ean_idx[ean] = pid
                cod = norm_cod(raw)
                if cod and cod not in cod_idx:
                    cod_idx[cod] = pid

    return ean_idx, cod_idx


def resolve_product(row, ean_idx, cod_idx) -> int | None:
    """Intenta encontrar el producto por EAN primero, luego código.
    row puede ser un namedtuple de itertuples o un dict-like.
    """
    try:
        ean = row.ean_k
        cod = row.cod_k
    except AttributeError:
        ean = row.get("ean_k", "")
        cod = row.get("cod_k", "")
    if ean and ean in ean_idx:
        return ean_idx[ean]
    if cod and cod in cod_idx:
        return cod_idx[cod]
    return None


# ──────────────────────────────────────────────
# Construcción del OC key para buscar en Excel
# ──────────────────────────────────────────────

def oc_key_from_numero(numero: str, anio: int) -> str:
    """
    El import guardó numero como "123" o "123-2024".
    Devolvemos la parte base (sin sufijo -anio) para buscar en Excel.
    """
    suffix = f"-{anio}"
    if numero.endswith(suffix):
        return numero[: -len(suffix)]
    return numero


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Re-vincula OC históricas con COMPRA-HIST-MAESTRA")
    ap.add_argument("--maestra", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="No modifica la BD")
    ap.add_argument("--solo-reporte", action="store_true", help="Solo CSV, no modifica BD")
    args = ap.parse_args()

    # Resolver ruta maestra
    maestra_path = args.maestra
    if not maestra_path:
        for candidate in (DEFAULT_MAESTRA, FALLBACK_MAESTRA):
            if candidate.is_file():
                maestra_path = candidate
                break
    if not maestra_path or not maestra_path.is_file():
        print(f"[ERROR] No se encontró el Excel. Rutas buscadas:")
        print(f"  {DEFAULT_MAESTRA}")
        print(f"  {FALLBACK_MAESTRA}")
        print(f"  Usa --maestra RUTA para indicar la ubicación.")
        return 1

    dry = args.dry_run or args.solo_reporte
    modo = "DRY-RUN" if dry else "APLICADO"
    print(f"\n=== re_vincular_oc_lineas — {modo} ===")
    print(f"Maestra: {maestra_path}")

    # Cargar Excel
    print("\n[1] Cargando Excel...")
    df_mae = load_maestra(maestra_path)
    print(f"  {len(df_mae):,} filas con cantidad > 0")

    # Construir índice: (prov_k, oc_k, anio) → lista de filas
    mae_idx: dict[tuple, list] = defaultdict(list)
    for row in df_mae.itertuples(index=False):
        anio = int(row.anio) if not pd.isna(row.anio) else 0
        key  = (row.prov_k, row.oc_k, anio)
        mae_idx[key].append(row)

    print(f"  {len(mae_idx):,} grupos (prov+oc+año) en Excel")

    # Cargar app Flask
    import app as m
    from app import DetalleOrdenCompra, OrdenCompra, Producto, db

    with m.app.app_context():
        # Obtener ID del producto genérico
        generico = Producto.query.filter_by(codigo_interno=CODIGO_GENERICO).first()
        if not generico:
            generico = Producto.query.filter_by(codigo_barra=CODIGO_GENERICO).first()
        if not generico:
            print("[ERROR] No se encontró el producto COMPRA-HIST-MAESTRA en la BD.")
            return 1
        generico_id = int(generico.id)
        print(f"\n[2] Producto genérico → id={generico_id}")

        # Índices de productos
        print("[3] Construyendo índices de productos ERP...")
        ean_idx, cod_idx = build_product_indexes(m.app)
        print(f"  EAN/barras: {len(ean_idx):,}  |  Códigos: {len(cod_idx):,}")

        # Obtener OCs del import maestra que tienen líneas genéricas
        print("[4] Buscando OCs con líneas COMPRA-HIST-MAESTRA...")
        ocs_con_generico = (
            db.session.query(OrdenCompra)
            .join(DetalleOrdenCompra)
            .filter(
                OrdenCompra.usuario_creador == USUARIO_IMPORT,
                DetalleOrdenCompra.producto_id == generico_id,
            )
            .distinct()
            .all()
        )
        print(f"  {len(ocs_con_generico):,} OCs con líneas genéricas")

        stats = {
            "ocs_procesadas": 0,
            "ocs_sin_excel": 0,
            "ocs_mejoradas": 0,
            "lineas_nuevas_ok": 0,
            "lineas_generico_borradas": 0,
            "lineas_generico_retenidas": 0,
            "lineas_sin_match": 0,
        }

        reporte: list[dict] = []

        for oc in ocs_con_generico:
            stats["ocs_procesadas"] += 1
            anio = oc.fecha_emision.year if oc.fecha_emision else 0
            prov_nombre = oc.proveedor.nombre if oc.proveedor else ""
            prov_k = norm_prov(prov_nombre)
            oc_k   = oc_key_from_numero(oc.numero or "", anio)

            # Buscar filas en Excel
            excel_rows = mae_idx.get((prov_k, oc_k, anio), [])
            if not excel_rows:
                # Intentar sin el año como sufijo (OC simple)
                for ak in range(anio - 1, anio + 2):
                    excel_rows = mae_idx.get((prov_k, oc_k, ak), [])
                    if excel_rows:
                        break

            if not excel_rows:
                stats["ocs_sin_excel"] += 1
                reporte.append({
                    "oc_id": oc.id,
                    "oc_numero": oc.numero,
                    "proveedor": prov_nombre,
                    "anio": anio,
                    "resultado": "SIN_EXCEL",
                    "detalle": "No se encontraron filas en el Excel para esta OC",
                    "codigo_proveedor": "",
                    "ean": "",
                    "descripcion": "",
                    "producto_id_nuevo": "",
                })
                continue

            # Para cada fila del Excel, intentar match mejorado
            nuevas_lineas: list[dict] = []
            for row in excel_rows:
                prod_id = resolve_product(row, ean_idx, cod_idx)
                cant = float(row.cantidad or 0)
                neto = float(row.neto or 0)
                precio_u = round(neto / cant, 2) if cant > 0 and neto > 0 else 0.0

                reporte.append({
                    "oc_id": oc.id,
                    "oc_numero": oc.numero,
                    "proveedor": prov_nombre,
                    "anio": anio,
                    "resultado": "MATCH_OK" if prod_id else "SIN_MATCH",
                    "detalle": f"prod_id={prod_id}" if prod_id else "No encontrado",
                    "codigo_proveedor": row.codigo_proveedor,
                    "ean": row.ean,
                    "descripcion": row.descripcion,
                    "producto_id_nuevo": prod_id or "",
                })

                if prod_id:
                    nuevas_lineas.append({
                        "producto_id": prod_id,
                        "cantidad": cant,
                        "precio_unitario": precio_u,
                    })
                    stats["lineas_nuevas_ok"] += 1
                else:
                    stats["lineas_sin_match"] += 1

            if not nuevas_lineas:
                stats["lineas_generico_retenidas"] += (
                    DetalleOrdenCompra.query
                    .filter_by(orden_compra_id=oc.id, producto_id=generico_id)
                    .count()
                )
                continue

            # Hay al menos un match nuevo → borrar genéricos y agregar reales
            stats["ocs_mejoradas"] += 1
            n_gen = (
                DetalleOrdenCompra.query
                .filter_by(orden_compra_id=oc.id, producto_id=generico_id)
                .count()
            )
            stats["lineas_generico_borradas"] += n_gen

            if not dry:
                DetalleOrdenCompra.query.filter_by(
                    orden_compra_id=oc.id, producto_id=generico_id
                ).delete(synchronize_session=False)

                for ln in nuevas_lineas:
                    db.session.add(
                        DetalleOrdenCompra(
                            orden_compra_id=oc.id,
                            producto_id=ln["producto_id"],
                            cantidad=ln["cantidad"],
                            precio_unitario=ln["precio_unitario"],
                        )
                    )

                # Si hay filas sin match aún, re-crear las genéricas
                unmatched_count = sum(
                    1 for r in excel_rows
                    if resolve_product(r, ean_idx, cod_idx) is None
                    and float(r.cantidad or 0) > 0
                )
                if unmatched_count:
                    # Agregar de vuelta 1 línea genérica con el total de sin match
                    total_cant_unmatched = sum(
                        float(r.cantidad or 0)
                        for r in excel_rows
                        if resolve_product(r, ean_idx, cod_idx) is None
                    )
                    total_neto_unmatched = sum(
                        float(r.neto or 0)
                        for r in excel_rows
                        if resolve_product(r, ean_idx, cod_idx) is None
                    )
                    db.session.add(
                        DetalleOrdenCompra(
                            orden_compra_id=oc.id,
                            producto_id=generico_id,
                            cantidad=total_cant_unmatched,
                            precio_unitario=(
                                round(total_neto_unmatched / total_cant_unmatched, 2)
                                if total_cant_unmatched > 0 else 0
                            ),
                        )
                    )
                    stats["lineas_generico_retenidas"] += 1

            if stats["ocs_mejoradas"] % 50 == 0:
                print(f"  … procesando {stats['ocs_mejoradas']} OCs mejoradas")
                if not dry:
                    db.session.commit()

        if not dry:
            db.session.commit()

        # ── Reporte ──
        reporte_path = OUT_DIR / "reporte_vinculacion.csv"
        with open(reporte_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "oc_id", "oc_numero", "proveedor", "anio",
                "resultado", "detalle",
                "codigo_proveedor", "ean", "descripcion", "producto_id_nuevo",
            ])
            writer.writeheader()
            writer.writerows(reporte)

        print(f"\n=== RESULTADO {modo} ===")
        for k, v in stats.items():
            print(f"  {k}: {v:,}")

        match_total = stats["lineas_nuevas_ok"] + stats["lineas_sin_match"]
        pct = 100 * stats["lineas_nuevas_ok"] / max(1, match_total)
        print(f"\n  Match rate: {pct:.1f}%  ({stats['lineas_nuevas_ok']:,}/{match_total:,} líneas)")
        print(f"\nReporte CSV: {reporte_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
