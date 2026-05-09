import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db, Producto, Proveedor, OrdenCompra, DetalleOrdenCompra


SKU_ROTACION = [
    ("CHM-FAST-0001", "Disco Corte Metal 4 1/2", "Herramientas Electricas", "Esmeriles", 780, 1490),
    ("CHM-FAST-0002", "Disco Desbaste 4 1/2", "Herramientas Electricas", "Esmeriles", 920, 1690),
    ("CHM-FAST-0003", "Silicona Neutra Transparente", "Construccion", "Adhesivos", 1650, 2890),
    ("CHM-FAST-0004", "Espuma Expansiva 750ml", "Construccion", "Aislantes", 3400, 5490),
    ("CHM-FAST-0005", "Guante Nitrilo Industrial", "Seguridad", "Guantes", 950, 1790),
    ("CHM-FAST-0006", "Lente Seguridad Antiempano", "Seguridad", "Lentes", 1200, 2290),
    ("CHM-FAST-0007", "Candado Laton 40mm", "Quincalleria", "Candados", 2700, 4290),
    ("CHM-FAST-0008", "Cerradura Sobreponer", "Quincalleria", "Cerraduras", 7200, 10990),
    ("CHM-FAST-0009", "Manguera Jardin 1/2 20m", "Jardin", "Mangueras", 8900, 12990),
    ("CHM-FAST-0010", "Regador Plastico 9 Funciones", "Jardin", "Regadores", 2100, 3490),
    ("CHM-FAST-0011", "Llave Punta Corona 13mm", "Herramientas Manuales", "Llaves", 1850, 3190),
    ("CHM-FAST-0012", "Destornillador Cruz PH2", "Herramientas Manuales", "Destornilladores", 1400, 2590),
]


def upsert_producto(codigo, nombre, categoria, subcategoria, compra, venta):
    p = Producto.query.filter_by(codigo_interno=codigo).first()
    nuevo = False
    if not p:
        p = Producto(codigo_interno=codigo, codigo_barra=f"7810{codigo[-4:]}{len(codigo)}", activo=True)
        db.session.add(p)
        nuevo = True
    p.nombre = nombre
    p.categoria = categoria
    p.subcategoria = subcategoria
    p.precio_compra = float(compra)
    p.precio_venta = float(venta)
    p.precio_mayoreo = round(float(venta) * 0.93, 0)
    p.unidad = p.unidad or "Unidad"
    p.unidad_compra = p.unidad_compra or "Unidad"
    p.unidad_venta = p.unidad_venta or "Unidad"
    p.factor_conversion = p.factor_conversion or 1.0
    p.stock = max(int(p.stock or 0), 10)
    return p, nuevo


def ensure_oc(proveedor_id, numero, estado, dias_atras, lineas, observacion):
    oc = OrdenCompra.query.filter_by(proveedor_id=proveedor_id, numero=numero).first()
    if oc:
        return False
    oc = OrdenCompra(
        proveedor_id=proveedor_id,
        numero=numero,
        fecha_emision=(datetime.now() - timedelta(days=dias_atras)).date(),
        estado=estado,
        observacion=observacion,
        usuario_creador="Seed LexIA",
    )
    db.session.add(oc)
    db.session.flush()
    for prod, qty in lineas:
        db.session.add(
            DetalleOrdenCompra(
                orden_compra_id=oc.id,
                producto_id=prod.id,
                cantidad=float(qty),
                precio_unitario=float(prod.precio_compra or 0),
            )
        )
    return True


def main():
    with app.app_context():
        db.session.execute(
            db.text(
                """
                SELECT setval(
                    pg_get_serial_sequence('productos', 'id'),
                    COALESCE((SELECT MAX(id) FROM productos), 1),
                    true
                )
                """
            )
        )
        nuevos = 0
        productos = {}
        for row in SKU_ROTACION:
            p, was_new = upsert_producto(*row)
            productos[p.codigo_interno] = p
            if was_new:
                nuevos += 1
        db.session.flush()

        prov = {p.nombre: p.id for p in Proveedor.query.all()}
        req = [
            "Chilemat Central de Compras",
            "Aceros Chilemat",
            "Electricidad y Iluminacion Chilemat",
            "Ferreteria Santo Domingo - Convenios",
        ]
        faltan = [n for n in req if n not in prov]
        if faltan:
            raise RuntimeError(f"Faltan proveedores demo: {', '.join(faltan)}")

        creadas = 0
        creadas += 1 if ensure_oc(
            prov["Aceros Chilemat"],
            "OC-CHM-DEMO-005",
            "Recibida",
            14,
            [
                (productos["CHM-FAST-0001"], 500),
                (productos["CHM-FAST-0002"], 350),
                (productos["CHM-FAST-0011"], 140),
            ],
            "[SEED] Top rotacion recibido",
        ) else 0
        creadas += 1 if ensure_oc(
            prov["Chilemat Central de Compras"],
            "OC-CHM-DEMO-006",
            "Parcial",
            9,
            [
                (productos["CHM-FAST-0003"], 180),
                (productos["CHM-FAST-0004"], 120),
                (productos["CHM-FAST-0005"], 260),
            ],
            "[SEED] Top rotacion parcial",
        ) else 0
        creadas += 1 if ensure_oc(
            prov["Electricidad y Iluminacion Chilemat"],
            "OC-CHM-DEMO-007",
            "Enviada",
            5,
            [
                (productos["CHM-FAST-0006"], 240),
                (productos["CHM-FAST-0012"], 220),
            ],
            "[SEED] Top rotacion enviada",
        ) else 0
        creadas += 1 if ensure_oc(
            prov["Ferreteria Santo Domingo - Convenios"],
            "OC-CHM-DEMO-008",
            "Anulada",
            3,
            [
                (productos["CHM-FAST-0007"], 90),
                (productos["CHM-FAST-0008"], 70),
                (productos["CHM-FAST-0009"], 40),
                (productos["CHM-FAST-0010"], 110),
            ],
            "[SEED] Top rotacion anulada por quiebre proveedor",
        ) else 0

        db.session.commit()
        print(f"Seed top rotacion completado: productos_nuevos={nuevos}, oc_nuevas={creadas}, sku_total={len(SKU_ROTACION)}")


if __name__ == "__main__":
    main()

