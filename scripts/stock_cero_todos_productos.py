"""
Pone stock en 0 de todos los productos (productos.stock + stock_por_almacen).

No modifica precios ni kardex histórico.

Uso:
  python scripts/stock_cero_todos_productos.py              # simulación
  python scripts/stock_cero_todos_productos.py --aplicar    # ejecutar (BD local)
  python scripts/stock_cero_todos_productos.py --aplicar --confirm-remoto  # Neon/PRD
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

CLOUD_HOSTS = ("neon.tech", "render.com", "railway.app", "supabase.co")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def _apply_db_url() -> str:
    env_local = _parse_env_file(ROOT / ".env.local")
    env_dot = _parse_env_file(ROOT / ".env")
    url = (
        os.environ.get("DATABASE_URL")
        or env_dot.get("DATABASE_URL")
        or env_local.get("DATABASE_URL")
        or ""
    ).strip()
    if url:
        os.environ["DATABASE_URL"] = url
    return url


def _es_remota(url: str) -> bool:
    return any(h in (url or "").lower() for h in CLOUD_HOSTS)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stock 0 en todos los productos")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--confirm-remoto", action="store_true", help="Permitir BD cloud (dump antes)")
    args = ap.parse_args()

    url = _apply_db_url()
    if not url:
        print("ERROR: configure DATABASE_URL en .env o .env.local")
        return 1

    if _es_remota(url) and args.aplicar and not args.confirm_remoto:
        print("ERROR: BD remota. Use --confirm-remoto solo si tiene respaldo.")
        return 1

    from sqlalchemy import func, text

    import app as m
    from app import Producto, StockPorAlmacen, db

    dry = not args.aplicar
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "respaldos" / f"stock_cero_todos_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    with m.app.app_context():
        n_prod = Producto.query.count()
        sum_stock = db.session.query(func.coalesce(func.sum(Producto.stock), 0)).scalar() or 0
        n_spa = StockPorAlmacen.query.count() if m._tablas_inventario_almacen_existen() else 0
        sum_spa = 0
        if n_spa:
            sum_spa = (
                db.session.query(func.coalesce(func.sum(StockPorAlmacen.cantidad), 0)).scalar() or 0
            )

        print("=== Stock cero — todos los productos ===")
        print("BD:", url[:60] + "..." if len(url) > 60 else url)
        print("Tipo:", "REMOTA" if _es_remota(url) else "LOCAL")
        print("Modo:", "SIMULACIÓN" if dry else "APLICAR")
        print("Productos:", n_prod)
        print("Suma productos.stock:", int(sum_stock))
        print("Filas stock_por_almacen:", n_spa)
        print("Unidades en almacenes:", int(sum_spa))

        csv_path = backup_dir / "antes_stock.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["producto_id", "codigo_barra", "nombre", "stock_total"])
            for p in Producto.query.order_by(Producto.id).limit(100000).all():
                w.writerow([p.id, p.codigo_barra or "", (p.nombre or "")[:120], int(p.stock or 0)])
        print("Respaldo:", csv_path)

        if dry:
            print("\nPara aplicar: python scripts/stock_cero_todos_productos.py --aplicar")
            return 0

        try:
            if m._tablas_inventario_almacen_existen():
                n_upd_spa = db.session.execute(
                    text("UPDATE stock_por_almacen SET cantidad = 0 WHERE cantidad <> 0")
                ).rowcount
            else:
                n_upd_spa = 0
            n_upd_prod = db.session.execute(
                text("UPDATE productos SET stock = 0 WHERE stock IS DISTINCT FROM 0")
            ).rowcount
            db.session.commit()

            sum_after = db.session.query(func.coalesce(func.sum(Producto.stock), 0)).scalar() or 0
            sum_spa_after = 0
            if m._tablas_inventario_almacen_existen():
                sum_spa_after = (
                    db.session.query(func.coalesce(func.sum(StockPorAlmacen.cantidad), 0)).scalar()
                    or 0
                )
            print("\nAplicado:")
            print("  productos actualizados:", n_upd_prod)
            print("  stock_por_almacen actualizados:", n_upd_spa)
            print("Verificación suma productos.stock:", int(sum_after))
            print("Verificación unidades almacenes:", int(sum_spa_after))
        except Exception as ex:
            db.session.rollback()
            print("ERROR:", ex)
            return 2

    (backup_dir / "meta.txt").write_text(
        f"productos={n_prod}\nstock_antes={sum_stock}\nunidades_spa_antes={sum_spa}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
