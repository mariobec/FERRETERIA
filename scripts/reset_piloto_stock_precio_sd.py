"""
Reinicia piloto mostrador: stock tienda/bodega → 0 y precio_venta_sd → vacío.

No modifica precio_venta (lista), precio_mayoreo ni precio_compra.
Excluye productos QA/DEMO (TEST-%, DEMO_%, DEMO-%).

Uso:
  python scripts/reset_piloto_stock_precio_sd.py              # simulación
  python scripts/reset_piloto_stock_precio_sd.py --aplicar    # ejecutar (BD local)
  python scripts/reset_piloto_stock_precio_sd.py --aplicar --confirm-neon  # Neon/PRD

Requiere respaldo previo en piso crítico (git tag / dump).
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
EXCLUIR_BARRA = ("TEST-%", "DEMO_%", "DEMO-%")


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


def _apply_db_url(use_neon: bool) -> str:
    env_local = _parse_env_file(ROOT / ".env.local")
    env_dot = _parse_env_file(ROOT / ".env")
    if use_neon:
        url = (env_local.get("NEON_DATABASE_URL") or env_dot.get("NEON_DATABASE_URL") or "").strip()
        if url:
            os.environ["DATABASE_URL"] = url
            return url
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
    u = (url or "").lower()
    return any(h in u for h in CLOUD_HOSTS)


def _filtro_excluir_q(Producto, db):
    from sqlalchemy import or_

    conds = []
    for pat in EXCLUIR_BARRA:
        conds.append(Producto.codigo_barra.ilike(pat))
        conds.append(Producto.codigo_interno.ilike(pat))
    return or_(*conds) if conds else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Reinicia stock piloto y precio_venta_sd")
    ap.add_argument("--aplicar", action="store_true", help="Ejecutar cambios (sin esto: solo simulación)")
    ap.add_argument("--confirm-neon", action="store_true", help="Permitir BD remota (Neon/Render)")
    ap.add_argument("--use-neon", action="store_true", help="Usar NEON_DATABASE_URL de .env.local")
    ap.add_argument(
        "--solo-activos",
        action="store_true",
        default=True,
        help="Solo productos activos (default: sí)",
    )
    ap.add_argument(
        "--incluir-inactivos",
        action="store_true",
        help="Incluir también productos inactivos",
    )
    ap.add_argument(
        "--incluir-test",
        action="store_true",
        help="Incluir productos TEST-/DEMO- (por defecto se excluyen)",
    )
    args = ap.parse_args()

    url = _apply_db_url(args.use_neon)
    if not url:
        print("ERROR: configure DATABASE_URL o NEON_DATABASE_URL en .env / .env.local")
        return 1

    if _es_remota(url) and args.aplicar and not args.confirm_neon:
        print("ERROR: BD remota detectada. Use --confirm-neon si es intencional (haga dump antes).")
        return 1

    from sqlalchemy import func

    import app as m
    from app import Producto, StockPorAlmacen, db

    dry = not args.aplicar
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "respaldos" / f"reset_piloto_stock_sd_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    with m.app.app_context():
        excl = _filtro_excluir_q(Producto, db)
        q = Producto.query
        if not args.incluir_inactivos:
            q = q.filter(Producto.activo == True)  # noqa: E712
        if excl is not None and not args.incluir_test:
            q = q.filter(~excl)
        productos = q.all()
        pids = [int(p.id) for p in productos]

        aid_t = m.id_almacen_tienda()
        aid_b = m.id_almacen_bodega()
        almacenes = [a for a in (aid_t, aid_b) if a]

        con_sd = sum(1 for p in productos if float(getattr(p, "precio_venta_sd", None) or 0) > 0)
        stock_total = sum(int(p.stock or 0) for p in productos)

        filas_spa = 0
        unidades_spa = 0
        if pids and almacenes and m._tablas_inventario_almacen_existen():
            rows = (
                StockPorAlmacen.query.filter(
                    StockPorAlmacen.id_producto.in_(pids),
                    StockPorAlmacen.id_almacen.in_(almacenes),
                )
                .all()
            )
            filas_spa = len(rows)
            unidades_spa = sum(int(r.cantidad or 0) for r in rows)

        print("=== Reinicio piloto stock + precio_venta_sd ===")
        print("BD:", "REMOTA" if _es_remota(url) else "LOCAL")
        print("Modo:", "SIMULACIÓN" if dry else "APLICAR")
        print("Productos afectados:", len(pids))
        print("Con precio_venta_sd > 0:", con_sd)
        print("Suma productos.stock:", stock_total)
        print("Filas stock_por_almacen (tienda/bodega):", filas_spa)
        print("Unidades en almacenes:", unidades_spa)

        # Respaldo CSV
        csv_path = backup_dir / "antes_reset.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "producto_id",
                    "codigo_barra",
                    "nombre",
                    "precio_venta_sd",
                    "precio_venta",
                    "stock_total",
                    "stock_tienda",
                    "stock_bodega",
                ]
            )
            st_map_t, st_map_b = {}, {}
            if pids and m._tablas_inventario_almacen_existen():
                st_map_t, st_map_b = m.stock_tienda_bodega_por_producto_ids(pids)
            for p in productos[:50000]:
                pid = int(p.id)
                w.writerow(
                    [
                        pid,
                        (p.codigo_barra or "").strip(),
                        (p.nombre or "")[:120],
                        float(getattr(p, "precio_venta_sd", None) or 0),
                        float(p.precio_venta or 0),
                        int(p.stock or 0),
                        int(st_map_t.get(pid, 0)),
                        int(st_map_b.get(pid, 0)),
                    ]
                )
        print("Respaldo:", csv_path)

        if dry:
            print("\nPara ejecutar: python scripts/reset_piloto_stock_precio_sd.py --aplicar")
            return 0

        try:
            n_sd = 0
            n_stock_prod = 0
            for p in productos:
                if float(getattr(p, "precio_venta_sd", None) or 0) > 0 or getattr(
                    p, "precio_venta_sd", None
                ) is not None:
                    p.precio_venta_sd = None
                    n_sd += 1
                if int(p.stock or 0) != 0:
                    p.stock = 0
                    n_stock_prod += 1

            n_spa = 0
            if pids and almacenes and m._tablas_inventario_almacen_existen():
                n_spa = (
                    StockPorAlmacen.query.filter(
                        StockPorAlmacen.id_producto.in_(pids),
                        StockPorAlmacen.id_almacen.in_(almacenes),
                    )
                    .update({StockPorAlmacen.cantidad: 0}, synchronize_session=False)
                )

            db.session.commit()
            print("\nAplicado:")
            print("  precio_venta_sd limpiados (filas tocadas):", n_sd)
            print("  productos.stock -> 0:", n_stock_prod)
            print("  stock_por_almacen -> 0 (filas):", n_spa)

            # Verificación
            rest_sd = (
                db.session.query(func.count(Producto.id))
                .filter(Producto.id.in_(pids))
                .filter(Producto.precio_venta_sd > 0)
                .scalar()
                or 0
            )
            print("Verificación precio_venta_sd > 0 en alcance:", int(rest_sd))
        except Exception as ex:
            db.session.rollback()
            print("ERROR:", ex)
            return 2

    (backup_dir / "meta.txt").write_text(
        f"aplicar={not dry}\nproductos={len(pids)}\nunidades_spa_antes={unidades_spa}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
