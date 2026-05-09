import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db, Producto, Proveedor, OrdenCompra, DetalleOrdenCompra, guardar_canal_compra_proveedor


SKU_DEMO = [
    ("CHM-OC-0001", "Cemento Estructural 25kg", "Construccion", "Cemento", 6100, 7990),
    ("CHM-OC-0002", "Mortero Predosificado 25kg", "Construccion", "Adhesivos", 4500, 5990),
    ("CHM-OC-0003", "Yeso Construccion 25kg", "Construccion", "Yeso", 3900, 5290),
    ("CHM-OC-0004", "Adhesivo Ceramico Premium 25kg", "Construccion", "Adhesivos", 5200, 7390),
    ("CHM-OC-0005", "Tornillo Volcanita 6x1 1/4", "Fijaciones", "Tornillos", 35, 70),
    ("CHM-OC-0006", "Tarugo Nylon 8mm", "Fijaciones", "Tarugos", 28, 55),
    ("CHM-OC-0007", "Perno Coche 3/8 x 3", "Fijaciones", "Pernos", 210, 390),
    ("CHM-OC-0008", "Clavo Corriente 2 1/2", "Fijaciones", "Clavos", 42, 85),
    ("CHM-OC-0009", "Cable THHN 2.5mm (metro)", "Electricidad", "Cables", 430, 690),
    ("CHM-OC-0010", "Interruptor Simple Blanco", "Electricidad", "Interruptores", 1100, 1890),
    ("CHM-OC-0011", "Enchufe Doble 10A", "Electricidad", "Enchufes", 1450, 2290),
    ("CHM-OC-0012", "Ampolleta LED 9W Luz Fria", "Electricidad", "Ampolletas", 980, 1690),
    ("CHM-OC-0013", "Llave de Paso 1/2", "Gasfiteria", "Llaves de paso", 1700, 2890),
    ("CHM-OC-0014", "Flexible Agua 1/2 x 40cm", "Gasfiteria", "Flexibles", 1200, 1990),
    ("CHM-OC-0015", "Sifon Lavaplatos Doble", "Gasfiteria", "Sifones", 3200, 4890),
    ("CHM-OC-0016", "Cinta Teflon 19mm", "Gasfiteria", "Sellos", 280, 690),
    ("CHM-OC-0017", "Brocha Profesional 2", "Pinturas", "Brochas", 1850, 2990),
    ("CHM-OC-0018", "Rodillo Antigota 9", "Pinturas", "Rodillos", 2400, 3890),
    ("CHM-OC-0019", "Esmalte al Agua Blanco 1GL", "Pinturas", "Esmaltes", 10900, 14990),
    ("CHM-OC-0020", "Latex Interior Mate 1GL", "Pinturas", "Latex", 9600, 13490),
    ("CHM-OC-0021", "Martillo Carpintero 16oz", "Herramientas Manuales", "Martillos", 5400, 8490),
    ("CHM-OC-0022", "Alicate Universal 8", "Herramientas Manuales", "Alicates", 4900, 7990),
    ("CHM-OC-0023", "Taladro Percutor 13mm", "Herramientas Electricas", "Taladros", 38900, 54990),
    ("CHM-OC-0024", "Esmeril Angular 4 1/2", "Herramientas Electricas", "Esmeriles", 32900, 46990),
]


def upsert_producto(codigo_interno, nombre, categoria, subcategoria, compra, venta):
    p = Producto.query.filter_by(codigo_interno=codigo_interno).first()
    creado = False
    if not p:
        p = Producto(
            codigo_interno=codigo_interno,
            codigo_barra=f"7809{codigo_interno[-4:]}{1000 + len(codigo_interno)}",
            nombre=nombre,
            activo=True,
        )
        db.session.add(p)
        creado = True
    p.nombre = nombre
    p.categoria = categoria
    p.subcategoria = subcategoria
    p.precio_compra = float(compra)
    p.precio_venta = float(venta)
    p.precio_mayoreo = round(float(venta) * 0.92, 0)
    p.unidad = p.unidad or "Unidad"
    p.unidad_compra = p.unidad_compra or "Unidad"
    p.unidad_venta = p.unidad_venta or "Unidad"
    p.factor_conversion = p.factor_conversion or 1.0
    p.stock = max(int(p.stock or 0), 8)
    return p, creado


def ensure_oc(proveedor, numero, estado, fecha_emision, lineas, observacion="Seed demo Chilemat"):
    oc = OrdenCompra.query.filter_by(proveedor_id=proveedor.id, numero=numero).first()
    if not oc:
        oc = OrdenCompra(
            proveedor_id=proveedor.id,
            numero=numero,
            fecha_emision=fecha_emision.date(),
            estado=estado,
            observacion=observacion,
            usuario_creador="Seed LexIA",
        )
        db.session.add(oc)
        db.session.flush()
    if oc.detalles:
        return oc, False
    for prod, qty in lineas:
        db.session.add(
            DetalleOrdenCompra(
                orden_compra_id=oc.id,
                producto_id=prod.id,
                cantidad=float(qty),
                precio_unitario=float(prod.precio_compra or 0),
            )
        )
    return oc, True


def main():
    with app.app_context():
        # Bases restauradas desde dump a veces dejan secuencias desfasadas.
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
        productos = []
        creados = 0
        for row in SKU_DEMO:
            p, was_new = upsert_producto(*row)
            productos.append(p)
            if was_new:
                creados += 1
        db.session.flush()

        proveedores = {p.nombre: p for p in Proveedor.query.all()}
        req = [
            "Chilemat Central de Compras",
            "Aceros Chilemat",
            "Cementos y Morteros Chilemat",
            "Electricidad y Iluminacion Chilemat",
        ]
        faltan = [n for n in req if n not in proveedores]
        if faltan:
            raise RuntimeError(f"Faltan proveedores demo: {', '.join(faltan)}. Ejecuta primero seed_chilemat_proveedores.py")

        guardar_canal_compra_proveedor(proveedores["Chilemat Central de Compras"].id, "chilemat_portal")
        guardar_canal_compra_proveedor(proveedores["Aceros Chilemat"].id, "email")
        guardar_canal_compra_proveedor(proveedores["Cementos y Morteros Chilemat"].id, "chilemat_portal")
        guardar_canal_compra_proveedor(proveedores["Electricidad y Iluminacion Chilemat"].id, "whatsapp")

        pmap = {p.codigo_interno: p for p in productos}
        hoy = datetime.now()
        ocs_creadas = 0

        _, c1 = ensure_oc(
            proveedores["Cementos y Morteros Chilemat"],
            "OC-CHM-DEMO-001",
            "Enviada",
            hoy - timedelta(days=8),
            [(pmap["CHM-OC-0001"], 120), (pmap["CHM-OC-0002"], 90), (pmap["CHM-OC-0004"], 60)],
            observacion="[SEED] OC demo materiales de construccion",
        )
        ocs_creadas += 1 if c1 else 0

        _, c2 = ensure_oc(
            proveedores["Aceros Chilemat"],
            "OC-CHM-DEMO-002",
            "Parcial",
            hoy - timedelta(days=6),
            [(pmap["CHM-OC-0005"], 2500), (pmap["CHM-OC-0007"], 700), (pmap["CHM-OC-0008"], 3000)],
            observacion="[SEED] OC demo fijaciones y acero",
        )
        ocs_creadas += 1 if c2 else 0

        _, c3 = ensure_oc(
            proveedores["Electricidad y Iluminacion Chilemat"],
            "OC-CHM-DEMO-003",
            "Borrador",
            hoy - timedelta(days=2),
            [(pmap["CHM-OC-0009"], 1800), (pmap["CHM-OC-0010"], 220), (pmap["CHM-OC-0012"], 340)],
            observacion="[SEED] OC demo electricidad",
        )
        ocs_creadas += 1 if c3 else 0

        _, c4 = ensure_oc(
            proveedores["Chilemat Central de Compras"],
            "OC-CHM-DEMO-004",
            "Enviada",
            hoy - timedelta(days=4),
            [(pmap["CHM-OC-0021"], 80), (pmap["CHM-OC-0022"], 90), (pmap["CHM-OC-0023"], 25), (pmap["CHM-OC-0024"], 20)],
            observacion="[SEED] OC demo herramientas",
        )
        ocs_creadas += 1 if c4 else 0

        db.session.commit()
        print(f"Seed OCs Chilemat completado: productos_nuevos={creados}, oc_nuevas={ocs_creadas}, productos_total_seed={len(SKU_DEMO)}")


if __name__ == "__main__":
    main()

