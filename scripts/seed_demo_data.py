"""
Datos de DEMOSTRACIÓN únicamente: precios y SKUs son referenciales (no cotización de mercado).

Objetivo: poblar el ERP con volumen (1500 ítems DEMO-*) y cubrir familia/categoría/subcategoría,
precios, stock por almacén, ubicación y variaciones típicas de unidad_compra / unidad_venta /
factor_conversion para pruebas de POS, inventario y export Excel.

Ejecutar desde la raíz del proyecto: python scripts/seed_demo_data.py
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (
    Almacen,
    Caja,
    Cliente,
    ClienteSaldoFavor,
    DetalleVenta,
    MovimientoInventario,
    MovimientoSaldoFavor,
    Producto,
    StockPorAlmacen,
    Venta,
    app,
    db,
)


random.seed(20260507)

CATEGORIAS = {
    "Herramientas Manuales": ["Martillos", "Alicates", "Destornilladores", "Llaves", "Serruchos"],
    "Herramientas Electricas": ["Taladros", "Esmeriles", "Sierras", "Lijadoras", "Rotomartillos"],
    "Fijaciones": ["Tornillos", "Clavos", "Tarugos", "Pernos", "Abrazaderas"],
    "Pinturas": ["Latex", "Esmaltes", "Barnices", "Brochas", "Rodillos"],
    "Gasfiteria": ["PVC", "Llaves de paso", "Flexibles", "Sifones", "Sellos"],
    "Electricidad": ["Cables", "Interruptores", "Enchufes", "Canaletas", "Ampolletas"],
    "Construccion": ["Cemento", "Yeso", "Adhesivos", "Niveladores", "Aislantes", "Maderas y tableros"],
    "Seguridad": ["Guantes", "Lentes", "Cascos", "Mascarillas", "Calzado"],
    "Jardin": ["Mangueras", "Palas", "Rastrillos", "Regadores", "Tijeras"],
    "Quincalleria": ["Bisagras", "Candados", "Cerraduras", "Rieles", "Soportes"],
}

# Costo neto aproximado por familia (CLP). Evita que tornillos queden al precio de un taladro.
CATEGORY_COST_BAND_CLP = {
    "Fijaciones": (35, 2800),
    "Electricidad": (260, 13200),
    "Gasfiteria": (390, 10500),
    "Pinturas": (890, 17500),
    "Herramientas Manuales": (2100, 36900),
    "Herramientas Electricas": (27900, 148000),
    "Construccion": (2800, 52900),
    "Seguridad": (690, 28900),
    "Jardin": (2300, 36900),
    "Quincalleria": (520, 24800),
}
ADJETIVOS = ["Profesional", "Reforzado", "Industrial", "Premium", "Estandar", "Heavy Duty", "Compacto", "Galvanizado", "Alta Resistencia", "Multiuso"]
MARCAS = ["Santo Domingo", "Forte", "Maestro", "Kraft", "Andes", "Bauker Pro", "MetalTec", "HogarFix", "Nordic", "TotalPro"]
COMUNAS = ["Santiago", "Providencia", "La Florida", "Maipu", "Puente Alto", "San Miguel", "Recoleta", "Quilicura", "Pudahuel", "Nunoa"]
NOMBRES = ["Comercial Los Aromos", "Constructora El Roble", "Ferreteria San Jose", "Maestranza Central", "Servicios Integrales Norte", "Inversiones Santa Clara", "Muebles y Obras SPA", "Instalaciones del Sur", "Mantenciones Express", "Hogar y Obra Ltda"]


def rut_demo(n):
    cuerpo = 77000000 + n
    suma = 0
    multiplicador = 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    dv = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return f"{cuerpo}-{dv}"


def money(valor):
    return float(int(round(valor / 10.0) * 10))


def pick_unit_profile(categoria, subcategoria):
    """Perfiles demo para ejercitar conversiones (1 compra = N ventas)."""
    r = random.random()
    if categoria == "Electricidad" and subcategoria == "Cables" and r < 0.62:
        factor = float(random.choice([25, 50, 100]))
        return ("Metro", "Rollo", "Metro", factor)
    if categoria == "Fijaciones" and r < 0.38:
        factor = float(random.choice([50, 100, 200, 500, 1000]))
        return ("Unidad", "Caja", "Unidad", factor)
    if categoria == "Pinturas" and subcategoria in ("Latex", "Esmaltes", "Barnices") and r < 0.28:
        factor = float(random.choice([4, 10, 20]))
        return ("Litro", "Cubeta", "Litro", factor)
    if categoria == "Gasfiteria" and subcategoria == "PVC" and r < 0.22:
        factor = float(random.choice([5, 6]))
        return ("Metro", "Barra", "Metro", factor)
    if categoria == "Jardin" and subcategoria == "Mangueras" and r < 0.35:
        factor = float(random.choice([15, 20, 25]))
        return ("Metro", "Rollo", "Metro", factor)
    return ("Unidad", "Unidad", "Unidad", 1.0)


def get_or_create_almacen(codigo, nombre):
    almacen = Almacen.query.filter_by(codigo=codigo).first()
    if almacen:
        return almacen
    almacen = Almacen(codigo=codigo, nombre=nombre, activo=True)
    db.session.add(almacen)
    db.session.flush()
    return almacen


def cargar_productos(tienda, bodega):
    productos_creados = 0
    existentes = {
        p.codigo_interno
        for p in Producto.query.filter(Producto.codigo_interno.like("DEMO-%")).all()
        if p.codigo_interno
    }
    for i in range(1, 1501):
        codigo = f"DEMO-{i:05d}"
        if codigo in existentes:
            continue
        categoria = random.choice(list(CATEGORIAS.keys()))
        subcategoria = random.choice(CATEGORIAS[categoria])
        lo, hi = CATEGORY_COST_BAND_CLP.get(categoria, (400, 11000))
        compra = money(random.randint(lo, hi))
        venta = money(compra * random.uniform(1.22, 1.52))
        unidad, u_compra, u_venta, factor = pick_unit_profile(categoria, subcategoria)
        stock_tienda = random.randint(3, 48)
        stock_bodega = random.randint(8, 140)
        producto = Producto(
            nombre=f"{subcategoria} {random.choice(ADJETIVOS)} {random.choice(MARCAS)} {i}",
            codigo_barra=f"7809{200000000 + i}",
            codigo_interno=codigo,
            codigo_chilemat=f"CHM-{i:06d}",
            precio_compra=compra,
            precio_venta=venta,
            precio_mayoreo=money(venta * 0.9),
            unidad=unidad,
            unidad_compra=u_compra,
            unidad_venta=u_venta,
            factor_conversion=factor,
            stock=stock_tienda + stock_bodega,
            categoria=categoria,
            subcategoria=subcategoria,
            ubicacion_pasillo=f"P{random.randint(1, 18):02d}",
            ubicacion_estante=f"E{random.randint(1, 12):02d}",
            ubicacion_nivel=f"N{random.randint(1, 5):02d}",
            activo=True,
        )
        db.session.add(producto)
        db.session.flush()
        db.session.merge(StockPorAlmacen(id_producto=producto.id, id_almacen=tienda.id, cantidad=stock_tienda))
        db.session.merge(StockPorAlmacen(id_producto=producto.id, id_almacen=bodega.id, cantidad=stock_bodega))
        db.session.add(MovimientoInventario(id_producto=producto.id, id_almacen=tienda.id, tipo_movimiento="ENTRADA", cantidad=stock_tienda, motivo="Carga inicial demo tienda", usuario="Demo ERP", referencia_tipo="demo", stock_saldo=stock_tienda))
        db.session.add(MovimientoInventario(id_producto=producto.id, id_almacen=bodega.id, tipo_movimiento="ENTRADA", cantidad=stock_bodega, motivo="Carga inicial demo bodega", usuario="Demo ERP", referencia_tipo="demo", stock_saldo=stock_bodega))
        productos_creados += 1
        if productos_creados % 250 == 0:
            db.session.commit()
    db.session.commit()
    return productos_creados


def cargar_clientes():
    clientes_creados = 0
    ruts = {c.rut for c in Cliente.query.filter(Cliente.rut.like("77%")).all()}
    for i in range(1, 201):
        rut = rut_demo(i)
        if rut in ruts:
            continue
        comuna = random.choice(COMUNAS)
        cliente = Cliente(
            rut=rut,
            nombre=f"{random.choice(NOMBRES)} Demo {i:03d}",
            giro=random.choice(["Ferreteria", "Construccion", "Mantencion", "Retail", "Servicios tecnicos"]),
            direccion=f"Av. Demo {random.randint(100, 9900)}",
            telefono=f"+569{random.randint(40000000, 99999999)}",
            correo=f"cliente.demo{i:03d}@example.com",
            comuna=comuna,
            ciudad="Santiago",
            saldo_deudor=money(random.choice([0, 0, 0, random.randint(5000, 165000)])),
            limite_credito=money(random.randint(250000, 1600000)),
            estado_credito="Activo",
        )
        db.session.add(cliente)
        clientes_creados += 1
    db.session.commit()
    return clientes_creados


def cargar_ventas(caja):
    productos = Producto.query.filter(Producto.codigo_interno.like("DEMO-%")).all()
    clientes = Cliente.query.filter(Cliente.rut.like("77%")).all()
    ventas_existentes = Venta.query.filter_by(usuario="Demo ERP").count()
    ventas_creadas = 0
    for i in range(ventas_existentes + 1, 501):
        fecha = datetime.now() - timedelta(days=random.randint(0, 89), hours=random.randint(0, 10), minutes=random.randint(0, 59))
        cliente = random.choice(clientes) if random.random() < 0.72 else None
        metodo = random.choices(["Efectivo", "Debito", "Credito"], weights=[55, 32, 13])[0]
        estado = "Pendiente" if metodo == "Credito" and random.random() < 0.35 else "Pagado"
        venta = Venta(
            fecha=fecha,
            usuario="Demo ERP",
            estado=estado,
            tipo_documento=random.choice(["Boleta", "Boleta", "Factura"]),
            metodo_pago=metodo,
            caja_id=caja.id,
            cliente_id=cliente.id if cliente else None,
            punto_retiro=random.choice(["Tienda", "Bodega"]),
        )
        db.session.add(venta)
        db.session.flush()
        total = 0
        for producto in random.sample(productos, random.randint(1, 5)):
            cantidad = random.randint(1, 6)
            descuento = random.choice([0, 0, 0, 5, 10, 15])
            subtotal = money(cantidad * float(producto.precio_venta or 0) * (1 - descuento / 100))
            db.session.add(DetalleVenta(id_venta=venta.id, id_producto=producto.id, cantidad=cantidad, precio_unitario=float(producto.precio_venta or 0), descuento=descuento, subtotal=subtotal))
            total += subtotal
        venta.monto_total = float(round(total))
        venta.desglosar_iva()
        if estado == "Pagado":
            venta.monto_recibido = venta.monto_total + random.choice([0, 0, 0, 1000, 5000, 10000])
            venta.vuelto = max(0, venta.monto_recibido - venta.monto_total)
        else:
            venta.monto_recibido = 0
            venta.vuelto = 0
        ventas_creadas += 1
        if ventas_creadas % 100 == 0:
            db.session.commit()
    db.session.commit()
    return ventas_creadas


def cargar_saldos_favor():
    clientes = Cliente.query.filter(Cliente.rut.like("77%")).all()
    saldos_creados = 0
    for cliente in random.sample(clientes, min(35, len(clientes))):
        existente = ClienteSaldoFavor.query.get(cliente.id)
        if existente and existente.saldo > 0:
            continue
        saldo = money(random.randint(1200, 38000))
        if existente:
            existente.saldo = saldo
        else:
            db.session.add(ClienteSaldoFavor(cliente_id=cliente.id, saldo=saldo))
        db.session.add(MovimientoSaldoFavor(cliente_id=cliente.id, cambio_id=None, tipo="CREDITO", monto=saldo, saldo_resultante=saldo, observacion="Saldo demo por devolucion comercial"))
        saldos_creados += 1
    db.session.commit()
    return saldos_creados


def main():
    with app.app_context():
        tienda = get_or_create_almacen("TIENDA", "Tienda")
        bodega = get_or_create_almacen("BODEGA", "Bodega")
        caja = Caja.query.filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
        if not caja:
            caja = Caja(fecha_apertura=datetime.now() - timedelta(days=1), monto_inicial=420000, estado="Abierta", usuario_apertura="Demo ERP")
            db.session.add(caja)
            db.session.flush()

        resumen = {
            "productos_creados": cargar_productos(tienda, bodega),
            "clientes_creados": cargar_clientes(),
            "ventas_creadas": cargar_ventas(caja),
            "saldos_creados": cargar_saldos_favor(),
            "productos_demo_total": Producto.query.filter(Producto.codigo_interno.like("DEMO-%")).count(),
            "clientes_demo_total": Cliente.query.filter(Cliente.rut.like("77%")).count(),
            "ventas_demo_total": Venta.query.filter_by(usuario="Demo ERP").count(),
            "clientes_saldo_favor_total": ClienteSaldoFavor.query.filter(ClienteSaldoFavor.saldo > 0).count(),
        }
        print(resumen)


if __name__ == "__main__":
    main()
