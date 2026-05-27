#!/usr/bin/env python3
"""
Reset local de catálogo ERP usando Chilemat VTEX como fuente.

Acciones:
1) Sincroniza staging Chilemat (categorías + productos VTEX).
2) Reemplaza catalogo_categorias / catalogo_subcategorias.
3) Borra productos ERP locales (TRUNCATE ... CASCADE) y recarga desde Chilemat.
4) Relinka chilemat_vtex_producto.producto_id al nuevo producto ERP.

Uso:
  python scripts/reset_local_catalogo_a_chilemat.py
  python scripts/reset_local_catalogo_a_chilemat.py --sin-sync
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _partes_path(path: str | None) -> tuple[str, str, str]:
    partes = [p.strip() for p in (path or "").split("/") if p.strip()]
    rubro = partes[0] if len(partes) > 0 else ""
    sub = partes[1] if len(partes) > 1 else ""
    sub2 = partes[2] if len(partes) > 2 else ""
    return rubro, sub, sub2


def _uniq_barcode(base: str, usados: set[str], vid: str) -> str:
    b = (base or "").strip()[:50]
    if not b:
        b = f"CHM-BC-{vid}"[:50]
    if b not in usados:
        usados.add(b)
        return b
    i = 2
    while True:
        cand = f"{b[:42]}-{i}"[:50]
        if cand not in usados:
            usados.add(cand)
            return cand
        i += 1


def run(*, hacer_sync: bool = True) -> dict:
    from app import (
        CatalogoCategoria,
        CatalogoSubcategoria,
        ChilematVtexProducto,
        Producto,
        app,
        db,
    )
    from services.chilemat_catalogo_service import sync_categorias, sync_productos_vtex

    with app.app_context():
        if hacer_sync:
            sync_categorias(solo_faltantes=False)
            sync_productos_vtex(max_productos=None, solo_faltantes=False)

        vt_rows = (
            ChilematVtexProducto.query
            .order_by(ChilematVtexProducto.nombre.asc().nullslast(), ChilematVtexProducto.vtex_product_id.asc())
            .all()
        )
        if not vt_rows:
            raise RuntimeError("No hay productos Chilemat en staging (chilemat_vtex_producto).")
        vt_data = [
            {
                "vtex_product_id": (r.vtex_product_id or "").strip(),
                "product_reference": (r.product_reference or "").strip(),
                "nombre": (r.nombre or "").strip(),
                "link": (r.link or "").strip(),
                "categoria_path": (r.categoria_path or "").strip(),
                "brand": (r.brand or "").strip(),
                "precio_lista": float(r.precio_lista or 0) if r.precio_lista else 0.0,
                "ean": (r.ean or "").strip(),
                "imagen_url": (getattr(r, "imagen_url", None) or "").strip(),
                "descripcion_web": (getattr(r, "descripcion_web", None) or ""),
                "descripcion_corta": (getattr(r, "descripcion_corta", None) or "").strip(),
            }
            for r in vt_rows
            if (r.vtex_product_id or "").strip()
        ]

        # 1) Reemplazar maestro de categorías ERP.
        db.session.query(CatalogoSubcategoria).delete(synchronize_session=False)
        db.session.query(CatalogoCategoria).delete(synchronize_session=False)
        db.session.flush()

        cat_map: dict[str, int] = {}
        sub_map: dict[tuple[str, str, str], int] = {}
        for r in vt_data:
            rubro, sub, sub2 = _partes_path(r.get("categoria_path"))
            if not rubro:
                continue
            if rubro not in cat_map:
                cat = CatalogoCategoria(nombre=rubro[:80], orden=0, activo=True)
                db.session.add(cat)
                db.session.flush()
                cat_map[rubro] = cat.id
            if sub:
                n2 = sub[:80]
                leaf = (sub2 or sub)[:80]
                key = (rubro, n2, leaf)
                if key not in sub_map:
                    sc = CatalogoSubcategoria(
                        categoria_id=cat_map[rubro],
                        nivel2=n2,
                        nombre=leaf,
                        orden=0,
                        activo=True,
                    )
                    db.session.add(sc)
                    db.session.flush()
                    sub_map[key] = sc.id

        # 2) Limpiar productos ERP locales.
        db.session.execute(db.text("TRUNCATE TABLE productos RESTART IDENTITY CASCADE"))
        db.session.flush()
        # TRUNCATE ... CASCADE puede vaciar staging Chilemat; lo reponemos desde snapshot.
        db.session.query(ChilematVtexProducto).delete(synchronize_session=False)
        db.session.flush()

        usados_barra: set[str] = set()
        cargados = 0
        linked = 0
        for r in vt_data:
            vid = (r.get("vtex_product_id") or "").strip()
            if not vid:
                continue
            rubro, sub, sub2 = _partes_path(r.get("categoria_path"))
            cat_txt = (rubro or "Chilemat")[:50]
            sub_txt = ((sub2 or sub or "")[:50] if (sub or sub2) else None)
            sub_fk = None
            if rubro and sub:
                sub_fk = sub_map.get((rubro, sub[:80], (sub2 or sub)[:80]))

            ref = (r.get("product_reference") or "").strip()
            ean = (r.get("ean") or "").strip()
            barcode_base = ean or ref or f"CHM-BC-{vid}"
            codigo_barra = _uniq_barcode(barcode_base, usados_barra, vid)

            precio = float(r.get("precio_lista") or 0)
            row = ChilematVtexProducto(
                vtex_product_id=vid,
                product_reference=ref[:80] if ref else None,
                nombre=(r.get("nombre") or f"Chilemat {vid}")[:200],
                link=(r.get("link") or "")[:500] or None,
                categoria_path=(r.get("categoria_path") or "")[:300] or None,
                brand=(r.get("brand") or "")[:80] or None,
                precio_lista=precio,
                ean=ean[:32] if ean else None,
                imagen_url=(r.get("imagen_url") or "")[:500] or None,
                descripcion_web=(r.get("descripcion_web") or "")[:8000] or None,
                descripcion_corta=(r.get("descripcion_corta") or "")[:500] or None,
            )
            db.session.add(row)
            db.session.flush()

            p = Producto(
                nombre=((r.get("nombre") or f"Chilemat {vid}")[:100]),
                codigo_barra=codigo_barra,
                codigo_chilemat=ref[:80] if ref else None,
                codigo_interno=(f"CHM-{vid}")[:32],
                imagen_url=((r.get("imagen_url") or "").strip()[:500] or None),
                precio_compra=(round(precio * 0.75, 2) if precio > 0 else 0.0),
                precio_venta=precio,
                precio_mayoreo=precio,
                unidad="UN",
                unidad_compra="UN",
                unidad_venta="UN",
                factor_conversion=1.0,
                stock=0,
                categoria=cat_txt,
                subcategoria=sub_txt,
                subcategoria_catalogo_id=sub_fk,
                activo=True,
            )
            db.session.add(p)
            db.session.flush()
            cargados += 1

            row.producto_id = p.id
            linked += 1

        db.session.commit()
        return {
            "ok": True,
            "chilemat_staging": len(vt_data),
            "categorias_erp": len(cat_map),
            "subcategorias_erp": len(sub_map),
            "productos_cargados": cargados,
            "vtex_linked": linked,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset local ERP con catálogo Chilemat")
    ap.add_argument("--sin-sync", action="store_true", help="No llamar API; usar staging actual")
    args = ap.parse_args()
    out = run(hacer_sync=not args.sin_sync)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

