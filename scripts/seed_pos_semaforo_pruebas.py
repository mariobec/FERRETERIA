"""
Set de productos PRUEBA POS — semáforo (verde / amarillo / azul) y venta en verde.

Catálogo: pruebas/pos_semaforo/productos.json
Checklist: pruebas/pos_semaforo/CHECKLIST.md

Uso (raíz del proyecto, DATABASE_URL de .env.local):
    python scripts/seed_pos_semaforo_pruebas.py
    python scripts/seed_pos_semaforo_pruebas.py --list
    python scripts/seed_pos_semaforo_pruebas.py --purge

Idempotente por codigo_barra POS-SEM-*.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGO = ROOT / "pruebas" / "pos_semaforo" / "productos.json"

sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    Almacen,
    Producto,
    StockPorAlmacen,
    app,
    db,
    id_almacen_bodega,
    id_almacen_tienda,
    _refrescar_stock_total_producto,
    _tablas_inventario_almacen_existen,
)
from services.pos_busqueda_service import clasificar_semaforo, etiqueta_semaforo  # noqa: E402


def _load_catalog() -> dict:
    data = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return data


def _ensure_almacenes() -> tuple[int, int]:
    tienda = id_almacen_tienda()
    bodega = id_almacen_bodega()
    if not tienda:
        a = Almacen(codigo="TIENDA", nombre="Tienda / Mostrador", activo=True)
        db.session.add(a)
        db.session.flush()
        tienda = a.id
    if not bodega:
        a = Almacen(codigo="BODEGA", nombre="Bodega", activo=True)
        db.session.add(a)
        db.session.flush()
        bodega = a.id
    return int(tienda), int(bodega)


def _upsert_stock(pid: int, id_tienda: int, id_bodega: int, st_t: int, st_b: int) -> None:
    if not _tablas_inventario_almacen_existen():
        p = Producto.query.get(pid)
        if p:
            p.stock = int(st_t) + int(st_b)
        return
    for id_alm, qty in ((id_tienda, st_t), (id_bodega, st_b)):
        spa = StockPorAlmacen.query.filter_by(id_producto=pid, id_almacen=id_alm).first()
        if spa:
            spa.cantidad = int(qty)
        else:
            db.session.add(
                StockPorAlmacen(id_producto=pid, id_almacen=id_alm, cantidad=int(qty))
            )
    p = Producto.query.get(pid)
    if p:
        _refrescar_stock_total_producto(p)


def seed_items(*, dry_run: bool = False) -> list[dict]:
    cat = _load_catalog()
    items = cat.get("items") or []
    categoria = cat.get("categoria") or "PRUEBA_POS"
    marca = cat.get("marca") or "PRUEBA POS"
    report: list[dict] = []

    with app.app_context():
        id_tienda, id_bodega = _ensure_almacenes()
        for it in items:
            codigo = (it.get("codigo_barra") or "").strip()
            if not codigo:
                continue
            nombre = (it.get("nombre") or codigo).strip()
            precio = float(it.get("precio_venta") or 0)
            st_t = int(it.get("stock_tienda") or 0)
            st_b = int(it.get("stock_bodega") or 0)
            sem = clasificar_semaforo(st_t, st_b)
            fila = {
                "id": it.get("id"),
                "codigo_barra": codigo,
                "stock_tienda": st_t,
                "stock_bodega": st_b,
                "semaforo": sem,
                "etiqueta": etiqueta_semaforo(sem),
                "accion": "dry-run" if dry_run else "ok",
            }
            if dry_run:
                report.append(fila)
                continue

            p = Producto.query.filter_by(codigo_barra=codigo).first()
            if not p:
                p = Producto(
                    nombre=nombre,
                    codigo_barra=codigo,
                    precio_venta=precio,
                    precio_mayoreo=0,
                    precio_compra=max(0, int(precio * 0.55)),
                    stock=0,
                    categoria=categoria,
                    activo=True,
                    unidad="Unidad",
                    unidad_venta="Unidad",
                )
                db.session.add(p)
                db.session.flush()
                fila["accion"] = "creado"
            else:
                p.nombre = nombre
                p.precio_venta = precio
                p.categoria = categoria
                p.activo = True
                fila["accion"] = "actualizado"

            cols = {c.name for c in Producto.__table__.columns}
            if "marca" in cols:
                setattr(p, "marca", marca)
            if "fabricante" in cols:
                setattr(p, "fabricante", marca)

            _upsert_stock(p.id, id_tienda, id_bodega, st_t, st_b)
            report.append(fila)

        if not dry_run:
            db.session.commit()

    return report


def purge_items(*, dry_run: bool = False) -> int:
    codigos = [
        (it.get("codigo_barra") or "").strip()
        for it in (_load_catalog().get("items") or [])
        if (it.get("codigo_barra") or "").strip()
    ]
    n = 0
    with app.app_context():
        for codigo in codigos:
            p = Producto.query.filter_by(codigo_barra=codigo).first()
            if not p:
                continue
            if dry_run:
                n += 1
                continue
            if _tablas_inventario_almacen_existen():
                StockPorAlmacen.query.filter_by(id_producto=p.id).delete()
            db.session.delete(p)
            n += 1
        if not dry_run and n:
            db.session.commit()
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed productos POS semáforo (POS-SEM-*)")
    parser.add_argument("--list", action="store_true", help="Solo listar catálogo JSON")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en BD")
    parser.add_argument("--purge", action="store_true", help="Elimina productos POS-SEM-* del catálogo")
    args = parser.parse_args()

    if args.list:
        cat = _load_catalog()
        print(f"Catálogo {CATALOGO.name} ({len(cat.get('items') or [])} ítems)\n")
        for it in cat.get("items") or []:
            st_t = int(it.get("stock_tienda") or 0)
            st_b = int(it.get("stock_bodega") or 0)
            sem = clasificar_semaforo(st_t, st_b)
            print(
                f"  {it.get('codigo_barra'):14}  {sem:8}  T={st_t:3} B={st_b:3}  {it.get('nombre', '')[:50]}"
            )
        return 0

    if args.purge:
        n = purge_items(dry_run=args.dry_run)
        print(f"{'[dry-run] ' if args.dry_run else ''}Eliminados o a eliminar: {n} producto(s).")
        return 0

    rows = seed_items(dry_run=args.dry_run)
    print(f"{'[dry-run] ' if args.dry_run else ''}Procesados {len(rows)} producto(s):\n")
    print(f"{'Código':14} {'Semáforo':8} {'Tienda':>6} {'Bodega':>6}  Acción")
    print("-" * 60)
    for r in rows:
        print(
            f"{r['codigo_barra']:14} {r['semaforo']:8} {r['stock_tienda']:6} {r['stock_bodega']:6}  {r['accion']}"
        )
    print("\nChecklist: pruebas/pos_semaforo/CHECKLIST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
