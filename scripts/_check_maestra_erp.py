#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
p = ROOT / ".env.local"
if p.is_file():
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")

from app import app, Producto, ProductoCodigoProveedor

with app.app_context():
    url = (os.environ.get("DATABASE_URL") or "")[:60]
    print("DB:", url, "...")
    print("productos_total", Producto.query.count())
    print("puentes_chilemat", ProductoCodigoProveedor.query.filter_by(proveedor_id=1).count())
    print("productos_CM", Producto.query.filter(Producto.codigo_interno.like("CM-%")).count())
    print("activos", Producto.query.filter(Producto.activo.isnot(False)).count())
    print("inactivos_maestra", Producto.query.filter(Producto.activo.is_(False)).count())
    for r in ProductoCodigoProveedor.query.filter_by(proveedor_id=1).limit(3).all():
        prod = Producto.query.get(r.producto_id)
        print(
            "ej",
            r.codigo_factura_proveedor,
            "->",
            r.producto_id,
            prod.codigo_barra if prod else None,
            prod.precio_compra if prod else None,
        )
