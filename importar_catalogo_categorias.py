"""
Carga el maestro categoría → subcategoría (2 niveles) o el Excel maestro de 3 niveles
(COD-CT1 / CATEGORIA 1 / SUBCATEGORIA NIVEL 2 / SUBCATEGORIA NIVEL 3), p. ej. Categorias.xlsx.

Migraciones MySQL (en orden):
  1) sql/2026_05_02_catalogo_categorias.sql
  2) sql/2026_05_02_catalogo_subcategoria_nivel2.sql   (columna nivel2 + unique ternario)

Uso:
  python importar_catalogo_categorias.py
  python importar_catalogo_categorias.py "..\\Categorias.xlsx"
  python importar_catalogo_categorias.py "..\\Categorias.xlsx" --backfill

Sin argumento, busca en orden: ../Categorias.xlsx, ../categorias.xlsx, ./Categorias.xlsx, ./categorias.csv

CSV plano (2 niveles): categoria, subcategoria; opcional orden_categoria, orden_subcategoria.
En catálogo 3 niveles, `nombre` = nivel 3 y `nivel2` = nivel 2 (misma categoría 1 que en el Excel).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, OrderedDict

import pandas as pd

from app import app, db, CatalogoCategoria, CatalogoSubcategoria, Producto


def _norm_map(df: pd.DataFrame) -> dict[str, str]:
    return {str(c).lower().strip(): c for c in df.columns}


def _pick(cols: dict[str, str], *candidates: str) -> str | None:
    for name in candidates:
        key = name.lower().strip()
        if key in cols:
            return cols[key]
    return None


def _default_archivo() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(base)
    for p in (
        os.path.join(parent, "Categorias.xlsx"),
        os.path.join(parent, "categorias.xlsx"),
        os.path.join(base, "Categorias.xlsx"),
        os.path.join(base, "categorias.csv"),
    ):
        if os.path.isfile(p):
            return p
    return os.path.join(base, "categorias.csv")


def _excel_header_row(path: str) -> int | None:
    raw = pd.read_excel(path, dtype=object, header=None).fillna("")
    for hi in range(min(12, len(raw))):
        cells = [str(x).strip().upper().replace(" ", "") for x in raw.iloc[hi].tolist() if str(x).strip()]
        if any("COD-CT1" in c or c == "COD-CT1" for c in cells):
            return hi
        if any("CATEGORIA1" == c or "CATEGORÍA1" == c for c in cells) and any(
            "SUBCATEGORIANIVEL2" in c for c in cells
        ):
            return hi
    return None


def _load_dataframe(path: str) -> pd.DataFrame:
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        hi = _excel_header_row(path)
        if hi is not None:
            return pd.read_excel(path, dtype=object, header=hi).fillna("")
        for hi in (0, 1, 2, 3):
            df = pd.read_excel(path, dtype=object, header=hi).fillna("")
            cols = _norm_map(df)
            if _pick(
                cols,
                "categoria",
                "categoría",
                "category",
                "cat",
                "cod-ct1",
                "cod_ct1",
                "categoria 1",
                "categoría 1",
            ):
                return df
        return pd.read_excel(path, dtype=object, header=0).fillna("")
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def _int_or(val, default: int) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        if not s:
            return default
        return int(float(s))
    except (TypeError, ValueError):
        return default


def _es_formato_cod_ct(cols: dict[str, str]) -> bool:
    return bool(
        _pick(cols, "cod-ct1", "cod_ct1")
        and (
            _pick(cols, "categoria 1", "categoría 1", "categoria1")
            or _pick(cols, "categoria 1")
        )
        and (
            _pick(cols, "subcategoria nivel 2", "subcategoría nivel 2", "subcategoria nivel2")
            or _pick(cols, "subcategoria nivel 2")
        )
        and (
            _pick(cols, "subcategoria nivel 3", "subcategoría nivel 3", "subcategoria nivel3")
            or _pick(cols, "subcategoria nivel 3")
        )
    )


def importar_desde_archivo(path: str) -> tuple[int, int]:
    """Upsert categorías y subcategorías. Devuelve (n_categorías, n_subcategorías) tocadas."""
    df = _load_dataframe(path)
    cols = _norm_map(df)

    if _es_formato_cod_ct(cols):
        return _importar_tres_niveles(df, cols)
    return _importar_dos_niveles(df, cols)


def _importar_tres_niveles(df: pd.DataFrame, cols: dict[str, str]) -> tuple[int, int]:
    col_c1 = _pick(cols, "categoria 1", "categoría 1", "categoria1") or _pick(cols, "categoria 1")
    col_cod1 = _pick(cols, "cod-ct1", "cod_ct1")
    col_n2 = _pick(cols, "subcategoria nivel 2", "subcategoría nivel 2", "subcategoria nivel2")
    col_cod3 = _pick(cols, "cod-ct3", "cod_ct3")
    col_n3 = _pick(cols, "subcategoria nivel 3", "subcategoría nivel 3", "subcategoria nivel3")

    if not col_c1 or not col_n2 or not col_n3:
        raise SystemExit(
            "Excel 3 niveles: faltan columnas esperadas. Encontradas: " + ", ".join(map(str, df.columns))
        )

    cat_first_line: dict[str, int] = {}
    cat_declared: dict[str, int] = {}
    seq = 0
    for _, row in df.iterrows():
        cn = str(row[col_c1]).strip()[:80]
        if not cn:
            continue
        if cn not in cat_first_line:
            seq += 1
            cat_first_line[cn] = seq
        if col_cod1:
            o = _int_or(row[col_cod1], cat_first_line[cn])
            if cn not in cat_declared:
                cat_declared[cn] = o
            else:
                cat_declared[cn] = min(cat_declared[cn], o)

    cat_orden = {c: cat_declared.get(c, cat_first_line[c]) for c in cat_first_line}

    # (categoria, nivel2, nivel3) -> orden (COD-CT3)
    triples: OrderedDict[tuple[str, str, str], int] = OrderedDict()
    for _, row in df.iterrows():
        cn = str(row[col_c1]).strip()[:80]
        n2 = str(row[col_n2]).strip()[:80]
        n3 = str(row[col_n3]).strip()[:80]
        if not cn or not n2 or not n3:
            continue
        key = (cn, n2, n3)
        o3 = _int_or(row[col_cod3], 0) if col_cod3 else 0
        if not o3:
            o3 = len([1 for (c, nv, _) in triples if c == cn and nv == n2]) + 1
        if key not in triples:
            triples[key] = o3
        else:
            triples[key] = min(triples[key], o3)

    n_cat = n_sub = 0
    cat_by_name: dict[str, CatalogoCategoria] = {}

    for nombre, orden in sorted(cat_orden.items(), key=lambda x: (x[1], x[0])):
        row = CatalogoCategoria.query.filter_by(nombre=nombre).first()
        if not row:
            row = CatalogoCategoria(nombre=nombre, orden=orden, activo=True)
            db.session.add(row)
            n_cat += 1
        else:
            if row.orden != orden:
                row.orden = orden
                n_cat += 1
        db.session.flush()
        cat_by_name[nombre] = row

    for (cn, n2, n3), orden_sub in triples.items():
        cat = cat_by_name.get(cn)
        if not cat:
            continue
        sub = CatalogoSubcategoria.query.filter_by(
            categoria_id=cat.id,
            nivel2=n2,
            nombre=n3,
        ).first()
        if not sub:
            sub = CatalogoSubcategoria(
                categoria_id=cat.id,
                nivel2=n2,
                nombre=n3,
                orden=orden_sub,
                activo=True,
            )
            db.session.add(sub)
            n_sub += 1
        else:
            if sub.orden != orden_sub or not sub.activo:
                sub.orden = orden_sub
                sub.activo = True
                n_sub += 1

    db.session.commit()
    return n_cat, n_sub


def _importar_dos_niveles(df: pd.DataFrame, cols: dict[str, str]) -> tuple[int, int]:
    col_cat = _pick(cols, "categoria", "categoría", "category", "cat")
    col_sub = _pick(cols, "subcategoria", "subcategoría", "sub_categoria", "subcategory", "sub")
    col_oc = _pick(cols, "orden_categoria", "orden categoria", "orden_cat", "ord_cat", "orden cat")
    col_os = _pick(cols, "orden_subcategoria", "orden subcategoria", "orden_sub", "ord_sub", "orden sub")

    if not col_cat or not col_sub:
        raise SystemExit(
            "El archivo debe incluir columnas de categoría y subcategoría "
            "(p. ej. categoria, subcategoria) o el maestro COD-CT / CATEGORIA 1. "
            "Columnas encontradas: " + ", ".join(map(str, df.columns))
        )

    cat_first_line: dict[str, int] = {}
    cat_declared: dict[str, int] = {}
    seq = 0
    for _, row in df.iterrows():
        cn = str(row[col_cat]).strip()[:80]
        if not cn:
            continue
        if cn not in cat_first_line:
            seq += 1
            cat_first_line[cn] = seq
        if col_oc:
            o = _int_or(row[col_oc], cat_first_line[cn])
            if cn not in cat_declared:
                cat_declared[cn] = o
            else:
                cat_declared[cn] = min(cat_declared[cn], o)

    cat_orden = {c: cat_declared.get(c, cat_first_line[c]) for c in cat_first_line}

    sub_pairs: OrderedDict[tuple[str, str, str], int] = OrderedDict()
    sub_seq_by_cat: dict[str, int] = {}
    for _, row in df.iterrows():
        cn = str(row[col_cat]).strip()[:80]
        sn = str(row[col_sub]).strip()[:80]
        if not cn or not sn:
            continue
        key = (cn, "", sn)
        if col_os:
            default_os = len([1 for (c, _, _) in sub_pairs if c == cn]) + 1
            osub = _int_or(row[col_os], default_os)
        else:
            sub_seq_by_cat[cn] = sub_seq_by_cat.get(cn, 0) + 1
            osub = sub_seq_by_cat[cn]
        if key not in sub_pairs:
            sub_pairs[key] = osub
        else:
            sub_pairs[key] = min(sub_pairs[key], osub)

    n_cat = n_sub = 0
    cat_by_name: dict[str, CatalogoCategoria] = {}

    for nombre, orden in sorted(cat_orden.items(), key=lambda x: (x[1], x[0])):
        row = CatalogoCategoria.query.filter_by(nombre=nombre).first()
        if not row:
            row = CatalogoCategoria(nombre=nombre, orden=orden, activo=True)
            db.session.add(row)
            n_cat += 1
        else:
            if row.orden != orden:
                row.orden = orden
                n_cat += 1
        db.session.flush()
        cat_by_name[nombre] = row

    for (cn, n2, sn), orden_sub in sub_pairs.items():
        cat = cat_by_name.get(cn)
        if not cat:
            continue
        sub = CatalogoSubcategoria.query.filter_by(
            categoria_id=cat.id,
            nivel2=n2,
            nombre=sn,
        ).first()
        if not sub:
            sub = CatalogoSubcategoria(
                categoria_id=cat.id,
                nivel2=n2 or "",
                nombre=sn,
                orden=orden_sub,
                activo=True,
            )
            db.session.add(sub)
            n_sub += 1
        else:
            if sub.orden != orden_sub or not sub.activo:
                sub.orden = orden_sub
                sub.activo = True
                n_sub += 1

    db.session.commit()
    return n_cat, n_sub


def backfill_productos() -> int:
    """Asigna productos.subcategoria_catalogo_id según texto categoria + subcategoria."""
    rows = (
        db.session.query(
            CatalogoSubcategoria.id,
            CatalogoCategoria.nombre.label("cn"),
            CatalogoSubcategoria.nivel2,
            CatalogoSubcategoria.nombre.label("sn"),
        )
        .join(CatalogoCategoria, CatalogoCategoria.id == CatalogoSubcategoria.categoria_id)
        .all()
    )

    idx_triple: dict[tuple[str, str, str], int] = {}
    idx_path: dict[tuple[str, str], int] = {}
    leaf_under_cat: Counter[tuple[str, str]] = Counter()

    for sid, cn, n2, sn in rows:
        n2s = (n2 or "").strip()[:80]
        cn_u = cn.strip().upper()
        sn_u = sn.strip().upper()
        idx_triple[(cn_u, n2s, sn_u)] = sid
        leaf_under_cat[(cn_u, sn_u)] += 1
        if n2s:
            combined = f"{n2s} / {sn}".strip()[:50].upper()
            idx_path[(cn_u, combined)] = sid

    idx_double: dict[tuple[str, str], int] = {}
    for sid, cn, n2, sn in rows:
        cn_u = cn.strip().upper()
        sn_u = sn.strip().upper()
        if leaf_under_cat[(cn_u, sn_u)] == 1:
            idx_double[(cn_u, sn_u)] = sid

    updated = 0
    for p in Producto.query.filter(Producto.subcategoria_catalogo_id.is_(None)).yield_per(500):
        cn_u = (p.categoria or "").strip().upper()
        sn_raw = (p.subcategoria or "").strip()
        sn_u = sn_raw.upper()
        if not cn_u or not sn_u:
            continue
        sid = idx_double.get((cn_u, sn_u))
        if not sid:
            sid = idx_triple.get((cn_u, "", sn_u))
        if not sid:
            sid = idx_path.get((cn_u, sn_u))
        if not sid:
            sid = idx_path.get((cn_u, sn_raw[:50].strip().upper()))
        if sid:
            p.subcategoria_catalogo_id = sid
            updated += 1
    db.session.commit()
    return updated


def main():
    ap = argparse.ArgumentParser(description="Importar catálogo categorías/subcategorías")
    ap.add_argument(
        "archivo",
        nargs="?",
        default=None,
        help="CSV o Excel (por defecto: ../Categorias.xlsx o ./categorias.csv según exista)",
    )
    ap.add_argument(
        "--backfill",
        action="store_true",
        help="Tras importar, enlazar productos sin FK usando categoria/subcategoria texto",
    )
    args = ap.parse_args()
    path = args.archivo if args.archivo else _default_archivo()

    with app.app_context():
        try:
            nc, ns = importar_desde_archivo(path)
        except FileNotFoundError:
            print(f"No existe el archivo: {os.path.abspath(path)}", file=sys.stderr)
            sys.exit(1)
        print(f"Archivo: {os.path.abspath(path)}")
        print(f"Catálogo actualizado. Categorías (filas tocadas/creadas): {nc}, subcategorías: {ns}")

        if args.backfill:
            n = backfill_productos()
            print(f"Productos enlazados al catálogo (subcategoria_catalogo_id): {n}")


if __name__ == "__main__":
    main()
