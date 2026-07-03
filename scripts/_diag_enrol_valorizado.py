"""Diagnóstico stock valorizado vs enrolamiento (últimos N días). Uso interno."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datetime import datetime, timedelta, timezone

from app import (
    EnrolamientoTomaLinea,
    EnrolamientoTomaSesion,
    Producto,
    ProductoCodigoEscaneo,
    _tablas_inventario_almacen_existen,
    app,
    db,
    id_almacen_bodega,
    id_almacen_tienda,
    precio_efectivo_pos_producto,
    stock_bodega_por_producto_ids,
    stock_tienda_por_producto_ids,
)


def main(dias: int = 3) -> int:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    with app.app_context():
        print(f"=== DIAGNÓSTICO ENROLAMIENTO / STOCK VALORIZADO (últimos {dias} días) ===")
        print(f"Desde UTC: {desde.isoformat()}")
        print(f"Multi-almacén: {_tablas_inventario_almacen_existen()}")
        print(f"Almacén tienda id: {id_almacen_tienda()} | bodega id: {id_almacen_bodega()}")

        sesiones = (
            EnrolamientoTomaSesion.query.filter(EnrolamientoTomaSesion.iniciado_at >= desde)
            .order_by(EnrolamientoTomaSesion.iniciado_at.desc())
            .all()
        )
        print(f"\nSesiones enrolamiento: {len(sesiones)}")
        for s in sesiones[:20]:
            n_lineas = EnrolamientoTomaLinea.query.filter_by(sesion_id=s.id).count()
            print(
                f"  sesión={s.id} inicio={s.iniciado_at} almacén={s.id_almacen} líneas={n_lineas}"
            )

        alias_pids = {
            int(r[0])
            for r in db.session.query(ProductoCodigoEscaneo.producto_id)
            .filter(ProductoCodigoEscaneo.creado_at >= desde)
            .distinct()
            .all()
        }
        toma_pids = {
            int(r[0])
            for r in db.session.query(EnrolamientoTomaLinea.producto_id)
            .join(EnrolamientoTomaSesion)
            .filter(EnrolamientoTomaSesion.iniciado_at >= desde)
            .distinct()
            .all()
        }
        pids = sorted(alias_pids | toma_pids)
        print(f"\nProductos enrolados (alias ∪ toma): {len(pids)}")
        print(f"  vía alias: {len(alias_pids)} | vía toma: {len(toma_pids)}")

        if not pids:
            print("Sin productos enrolados en el período.")
            return 0

        stocks_t = stock_tienda_por_producto_ids(pids)
        stocks_b = stock_bodega_por_producto_ids(pids)
        prods = Producto.query.filter(Producto.id.in_(pids)).all()

        merc_tienda = merc_bodega = merc_maestro = cap_tienda = cap_bodega = 0.0
        stock_mismatch = []
        sin_precio = []
        solo_bodega = []

        for p in prods:
            st_t = int(stocks_t.get(p.id, 0) or 0)
            st_b = int(stocks_b.get(p.id, 0) or 0)
            st_m = int(p.stock or 0)
            costo = float(p.precio_compra or 0)
            venta_sd = float(precio_efectivo_pos_producto(p) or 0)
            venta_lista = float(p.precio_venta or 0)
            venta_calc = venta_sd if venta_sd > 0 else venta_lista

            merc_tienda += st_t * costo
            merc_bodega += st_b * costo
            merc_maestro += st_m * costo
            cap_tienda += st_t * venta_calc
            cap_bodega += st_b * venta_calc

            if _tablas_inventario_almacen_existen() and st_m != st_t + st_b:
                stock_mismatch.append((p.id, (p.nombre or "")[:45], st_m, st_t, st_b))
            if costo <= 0 or venta_calc <= 0:
                sin_precio.append(
                    (p.id, (p.nombre or "")[:45], costo, venta_sd, venta_lista, st_t, st_b)
                )
            if st_t == 0 and st_b > 0:
                solo_bodega.append((p.id, (p.nombre or "")[:45], st_b, costo, venta_calc))

        print("\n--- Valorización costo (mercadería) ---")
        print(f"  Pantalla actual (solo TIENDA):     ${merc_tienda:,.0f}")
        print(f"  Si incluyera BODEGA:             ${merc_bodega:,.0f}")
        print(f"  TIENDA + BODEGA:                 ${merc_tienda + merc_bodega:,.0f}")
        print(f"  Usando stock MAESTRO (producto.stock): ${merc_maestro:,.0f}")
        print(f"  Capital activo (tienda × precio POS): ${cap_tienda:,.0f}")
        print(f"  Capital activo (bodega × precio POS): ${cap_bodega:,.0f}")

        print(f"\n--- Problemas detectados ---")
        print(f"Desajuste maestro ≠ tienda+bodega: {len(stock_mismatch)}")
        for row in stock_mismatch[:12]:
            print(f"  id={row[0]} maestro={row[2]} tienda={row[3]} bodega={row[4]} | {row[1]}")

        print(f"\nSin precio compra o venta usable: {len(sin_precio)}")
        for row in sin_precio[:12]:
            print(
                f"  id={row[0]} compra={row[2]} sd={row[3]} lista={row[4]} "
                f"st_t={row[5]} st_b={row[6]} | {row[1]}"
            )

        print(f"\nStock solo en BODEGA (invisible en valorización tienda): {len(solo_bodega)}")
        merc_perdida = sum(st_b * costo for _, _, st_b, costo, _ in solo_bodega)
        print(f"  Mercadería no contada en pantalla: ~${merc_perdida:,.0f}")
        for row in solo_bodega[:12]:
            print(f"  id={row[0]} bodega={row[2]} costo={row[3]} | {row[1]}")

    return 0


if __name__ == "__main__":
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    raise SystemExit(main(dias))
