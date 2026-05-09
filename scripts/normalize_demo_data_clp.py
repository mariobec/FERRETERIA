"""
Corrige precios y montos de datos DEMO ya cargados para rangos creíbles en CLP (Chile).

Uso (desde la raíz del proyecto):
  python scripts/normalize_demo_data_clp.py

Afecta:
  - productos con codigo_interno LIKE 'DEMO-%' (precio_compra / precio_venta / precio_mayoreo)
  - clientes con RUT que empieza en 77 (demo) — saldo_deudor y limite_credito
  - clientes_saldos_favor de esos mismos clientes — tope de saldo

No modifica ventas históricas ni detalle_ventas (evita romper consistencia de tickets pasados).
Para demo fresca, mejor re-ejecutar seed_demo_data*.py con los rangos ya corregidos.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app, db, Cliente, ClienteSaldoFavor, Producto


CATEGORY_COST_BAND_CLP = {
    "Fijaciones": (35, 2800),
    "Electricidad": (260, 13200),
    "Gasfiteria": (390, 10500),
    "Pinturas": (890, 17500),
    "Herramientas Manuales": (2100, 36900),
    "Herramientas Electricas": (27900, 148000),
    "Construccion": (3600, 13200),
    "Seguridad": (690, 28900),
    "Jardin": (2300, 36900),
    "Quincalleria": (520, 24800),
}

DEFAULT_BAND = (400, 11000)


def money_clp(x: float) -> float:
    return float(int(round(x / 10.0)) * 10)


def compra_demo_deterministica(producto_id: int, lo: int, hi: int) -> float:
    if hi <= lo:
        hi = lo + 1
    span = hi - lo + 1
    off = (producto_id * 1103515245 + 12345) % span
    return money_clp(lo + off)


def multiplicador_venta(producto_id: int) -> float:
    # 1.22 .. 1.52 en pasos finitos
    step = ((producto_id * 9973) % 31) / 100.0
    return round(1.22 + step, 2)


def normalizar_productos_demo() -> int:
    q = Producto.query.filter(Producto.codigo_interno.like("DEMO-%"))
    total = 0
    productos = q.order_by(Producto.id).all()
    for p in productos:
        cat = (p.categoria or "").strip()
        lo, hi = CATEGORY_COST_BAND_CLP.get(cat, DEFAULT_BAND)
        compra = compra_demo_deterministica(p.id or 1, lo, hi)
        m = multiplicador_venta(p.id or 1)
        venta = money_clp(compra * m)
        if venta < compra:
            venta = money_clp(compra * 1.25)
        mayoreo = money_clp(venta * 0.92)
        p.precio_compra = compra
        p.precio_venta = venta
        p.precio_mayoreo = mayoreo
        total += 1
        if total % 200 == 0:
            db.session.commit()
    db.session.commit()
    return total


def normalizar_clientes_demo() -> tuple[int, int]:
    """Retorna (clientes tocados, saldos favor tocados)."""
    lim_min, lim_max = 250000.0, 1600000.0
    n_cli = 0
    clientes = Cliente.query.filter(Cliente.rut.like("77%")).all()
    for c in clientes:
        prev_sd = float(c.saldo_deudor or 0)
        prev_lc = float(c.limite_credito or 0)

        sd = prev_sd
        if sd > 165000:
            sd = float(money_clp(min(165000, 85000 + (c.id % 160) * 500)))
        elif sd != 0:
            sd = float(money_clp(sd))
        c.saldo_deudor = sd

        lc = prev_lc if prev_lc else lim_min
        if lc > lim_max:
            lc = lim_max
        if lc < lim_min:
            lc = lim_min
        if lc < sd + 50000:
            lc = min(lim_max, sd + 180000)
        c.limite_credito = float(money_clp(lc))

        if abs(prev_sd - float(c.saldo_deudor or 0)) > 0.5 or abs(prev_lc - float(c.limite_credito or 0)) > 0.5:
            n_cli += 1

    n_sf = 0
    for c in clientes:
        reg = ClienteSaldoFavor.query.filter_by(cliente_id=c.id).first()
        if not reg:
            continue
        s = float(reg.saldo or 0)
        if s > 38000 or s < 0:
            nuevo = money_clp(5000 + (c.id % 330) * 100)
        else:
            nuevo = money_clp(min(38000, max(1200, s)))
        if abs(nuevo - s) > 0.5:
            reg.saldo = nuevo
            n_sf += 1
    db.session.commit()
    return n_cli, n_sf


def main():
    with app.app_context():
        n_prod = normalizar_productos_demo()
        n_cli, n_sf = normalizar_clientes_demo()
        print(
            f"OK — productos DEMO actualizados: {n_prod}, "
            f"clientes DEMO ajustados: {n_cli}, saldos a favor recortados: {n_sf}"
        )


if __name__ == "__main__":
    main()
