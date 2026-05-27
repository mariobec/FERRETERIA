#!/usr/bin/env python3
"""Alta proveedores de la maestra SD que faltan en ERP (sin tocar productos)."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MAESTRA = Path(r"C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx")


def norm(s) -> str:
    if pd.isna(s):
        return ""
    t = str(s).strip().upper()
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maestra", type=Path, default=DEFAULT_MAESTRA)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    df = pd.read_excel(args.maestra)
    col = [c for c in df.columns if "proveedor" in str(c).lower()][0]
    nombres = sorted({str(x).strip() for x in df[col].dropna().unique() if str(x).strip()})

    import app as m
    from app import Proveedor, db

    with m.app.app_context():
        exist = {norm(p.nombre): p for p in Proveedor.query.all()}
        crear = []
        for nom in nombres:
            k = norm(nom)
            if not k or k in exist:
                continue
            matched = False
            for ek in exist:
                if k in ek or ek in k:
                    matched = True
                    break
            if not matched:
                crear.append(nom[:100])

        print("Proveedores en maestra:", len(nombres))
        print("A crear:", len(crear))
        if args.dry_run:
            for n in crear[:15]:
                print(" -", n)
            if len(crear) > 15:
                print(f" ... y {len(crear) - 15} mas")
            return

        for nom in crear:
            db.session.add(Proveedor(nombre=nom))
        db.session.commit()
        print("Creados:", len(crear))


if __name__ == "__main__":
    main()
