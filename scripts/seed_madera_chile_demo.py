"""
Carga productos de PRUEBA (referencial): terciados/tabulería y madera dimensionada Chile-demo.

Los precios no son cotización real; sirven para tener inventario completo en esa línea.

Para alinear precios al mercado local sin automatizar sitios de terceros: exportá el Excel
desde Gestión de inventario → productos, ajustá precio_compra / precio_venta / categorías
y volvé a subir la planilla (ver también codigo_interno / codigo_chilemat en la exportación).

Uso (desde la raíz del proyecto):
    python scripts/seed_madera_chile_demo.py

Idempotente: no duplica por codigo_interno MADERA-CHL-*.
Requiere misma configuración de BD que la app (DATABASE_URL / SQLALCHEMY_DATABASE_URI).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    Almacen,
    MovimientoInventario,
    Producto,
    StockPorAlmacen,
    app,
    db,
    _tablas_inventario_almacen_existen,
)


def money(valor: float) -> float:
    return float(int(round(valor / 10.0) * 10))


def get_or_create_almacen(codigo: str, nombre: str) -> Almacen:
    a = Almacen.query.filter_by(codigo=codigo).first()
    if a:
        return a
    a = Almacen(codigo=codigo, nombre=nombre, activo=True)
    db.session.add(a)
    db.session.flush()
    return a


# Paquetes típicos Chile: láminas estándar 1,22 x 2,44 m y madera por metro lineal (precios demo CLP).
ITEMS: list[tuple[str, str, str, float, float, float, int, int]] = [
    # nombre (≤100), codigo_interno sufijo, unidad_venta, compra, venta, mayoreo, st_tienda, st_bodega
    ("Terciado estructural fenólico 9 mm 1,22x2,44 m (lámina)", "TER-FEN-009", "Plancha", 18500, 25990, 23990, 18, 42),
    ("Terciado estructural fenólico 12 mm 1,22x2,44 m (lámina)", "TER-FEN-012", "Plancha", 22800, 31990, 29490, 14, 38),
    ("Terciado estructural fenólico 15 mm 1,22x2,44 m (lámina)", "TER-FEN-015", "Plancha", 27200, 38990, 35990, 12, 36),
    ("Terciado estructural fenólico 18 mm 1,22x2,44 m (lámina)", "TER-FEN-018", "Plancha", 31800, 44990, 41490, 10, 34),
    ("Terciado estructural fenólico 20 mm 1,22x2,44 m (lámina)", "TER-FEN-020", "Plancha", 36200, 50990, 46990, 8, 30),
    ("Terciado común CD 15 mm 1,22x2,44 m (lámina uso interior)", "TER-CD-015", "Plancha", 14800, 20990, 19290, 16, 40),
    ("OSB estructural 11 mm 1,22x2,44 m (lámina)", "OSB-011", "Plancha", 23600, 32990, 30290, 14, 38),
    ("OSB estructural 15 mm 1,22x2,44 m (lámina)", "OSB-015", "Plancha", 29800, 41990, 38590, 10, 28),
    ("MDF hidrófugo verde 18 mm 1,22x2,44 m", "MDF-H18", "Plancha", 38500, 53990, 49690, 6, 22),
    ("Melamina blanca 18 mm 1,22x2,44 m (dos caras)", "MEL-B18", "Plancha", 35200, 48990, 45290, 8, 26),
    ("Tablero contrachapado marítimo 15 mm 1,22x2,44 m", "MAR-015", "Plancha", 42800, 59990, 55290, 5, 18),
    ("Durpanel / cementicio 8 mm 1,20x2,40 m (placa)", "CEM-008", "Plancha", 12900, 17990, 16590, 20, 44),
    ("Tabla cepillo pino radiata 1x4\" x metro lineal secado", "PIN-1x4-ML", "Metro lineal", 1180, 1790, 1650, 180, 420),
    ("Tabla cepillo pino radiata 1x6\" x metro lineal secado", "PIN-1x6-ML", "Metro lineal", 1560, 2390, 2190, 140, 360),
    ("Tabla cepillo pino radiata 1x8\" x metro lineal secado", "PIN-1x8-ML", "Metro lineal", 2050, 3090, 2840, 110, 290),
    ("Madera dimensionada 2x2\" cepillo pino x metro lineal", "PIN-2x2-ML", "Metro lineal", 780, 1290, 1190, 220, 520),
    ("Madera dimensionada 2x3\" cepillo pino x metro lineal", "PIN-2x3-ML", "Metro lineal", 1490, 2290, 2100, 160, 400),
    ("Madera dimensionada 2x4\" cepillo pino x metro lineal", "PIN-2x4-ML", "Metro lineal", 2180, 3490, 3210, 190, 460),
    ("Madera dimensionada 2x6\" cepillo pino x metro lineal", "PIN-2x6-ML", "Metro lineal", 3480, 5290, 4860, 130, 340),
    ("Madera dimensionada 2x8\" cepillo pino x metro lineal", "PIN-2x8-ML", "Metro lineal", 4720, 7190, 6620, 95, 260),
    ("Viga laminada GLULAM referencial 6x12 cm x metro (pedido)", "GLU-6x12-ML", "Metro lineal", 8900, 12990, 11990, 40, 80),
    ("Polín pino impregnado CCA 4x4\" x 3,20 m", "POL-4x4-320", "Unidad", 8200, 11990, 11090, 35, 70),
    ("Tablón pino bruto 2x6\" x 4,80 m (pieza)", "BRU-2x6-480", "Unidad", 6500, 9490, 8720, 45, 95),
    ("Solera / ripiera pino 2x4\" x 3,05 m cepillo", "SOL-2x4-305", "Unidad", 5400, 7890, 7260, 55, 110),
    ("Pack tacos madera cuadrados surtidos bolsa 15 u", "ACC-TACOS15", "Unidad", 3200, 4990, 4590, 40, 85),
    ("Clavo helico corrugado madera 90 mm bolsa 5 kg", "ACC-CLV90-5K", "Unidad", 9800, 13990, 12890, 25, 55),
    ("Tornillo tire-fond madera 6x80 mm c/taco bolsa 50 u", "ACC-TF680-50", "Unidad", 4200, 6490, 5970, 35, 75),
    ("Cola carpintero poliuretánica interior 250 g", "ACC-COLA250", "Unidad", 2800, 4290, 3950, 60, 120),
    ("Zócalo MDF blanco 15x240 cm premoldeado", "ZOC-15x240", "Unidad", 2100, 3290, 3020, 48, 96),
]


def main() -> None:
    prefijo = "MADERA-CHL-"
    barra_base = 7809200735000

    with app.app_context():
        multi_almacen = _tablas_inventario_almacen_existen()
        tienda = bodega = None
        if multi_almacen:
            tienda = get_or_create_almacen("TIENDA", "Tienda")
            bodega = get_or_create_almacen("BODEGA", "Bodega")

        existentes = {
            (p.codigo_interno or "").strip()
            for p in Producto.query.filter(Producto.codigo_interno.like(f"{prefijo}%")).all()
        }

        creados = 0
        for idx, row in enumerate(ITEMS, start=1):
            nombre, suf, u_venta, c_compra, c_venta, c_mayo, st_t, st_b = row
            codigo_interno = f"{prefijo}{suf}"
            if codigo_interno in existentes:
                continue
            if len(nombre) > 100:
                nombre = nombre[:97] + "..."

            codigo_barra = str(barra_base + idx)
            codigo_chilemat = f"MD-CHL-{suf.replace('/', '-')}"

            compra = money(float(c_compra))
            venta = money(float(c_venta))
            mayoreo = money(float(c_mayo))
            stock_total = int(st_t + st_b)

            p = Producto(
                nombre=nombre,
                codigo_barra=codigo_barra,
                codigo_interno=codigo_interno,
                codigo_chilemat=codigo_chilemat,
                precio_compra=compra,
                precio_venta=venta,
                precio_mayoreo=mayoreo,
                unidad=u_venta if len(u_venta) <= 20 else u_venta[:20],
                unidad_compra=u_venta if len(u_venta) <= 20 else u_venta[:20],
                unidad_venta=u_venta if len(u_venta) <= 20 else u_venta[:20],
                factor_conversion=1.0,
                stock=stock_total,
                categoria="Construccion",
                subcategoria="Maderas y tableros",
                ubicacion_pasillo="P15",
                ubicacion_estante="E03",
                ubicacion_nivel="N01",
                activo=True,
            )
            db.session.add(p)
            db.session.flush()

            if multi_almacen and tienda and bodega:
                db.session.merge(
                    StockPorAlmacen(id_producto=p.id, id_almacen=tienda.id, cantidad=int(st_t))
                )
                db.session.merge(
                    StockPorAlmacen(id_producto=p.id, id_almacen=bodega.id, cantidad=int(st_b))
                )
                now = datetime.now()
                db.session.add(
                    MovimientoInventario(
                        id_producto=p.id,
                        id_almacen=tienda.id,
                        tipo_movimiento="ENTRADA",
                        cantidad=int(st_t),
                        motivo="Carga demo madera Chile (tienda)",
                        usuario="seed_madera_chile_demo",
                        fecha=now,
                        referencia_tipo="seed",
                        stock_saldo=int(st_t),
                    )
                )
                db.session.add(
                    MovimientoInventario(
                        id_producto=p.id,
                        id_almacen=bodega.id,
                        tipo_movimiento="ENTRADA",
                        cantidad=int(st_b),
                        motivo="Carga demo madera Chile (bodega)",
                        usuario="seed_madera_chile_demo",
                        fecha=now,
                        referencia_tipo="seed",
                        stock_saldo=int(st_b),
                    )
                )

            creados += 1

        db.session.commit()
        total_cat = Producto.query.filter(Producto.codigo_interno.like(f"{prefijo}%")).count()
        print(
            {
                "productos_nuevos_esta_corrida": creados,
                "productos_madera_chile_total": total_cat,
                "multi_almacen": multi_almacen,
            }
        )


if __name__ == "__main__":
    main()
