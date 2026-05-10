"""
Versión rápida del seed demo (SQL directo). Misma política que seed_demo_data.py: solo datos de prueba.

Ejecutar: python scripts/seed_demo_data_fast.py  (requiere DATABASE_URL / Postgres)

Opcional — alinear cartera demo (Flask + RUT 77%) después del seed SQL:
  set PATCH_DEMO_CARTERA=1   (Windows PowerShell: $env:PATCH_DEMO_CARTERA='1')
  python scripts/seed_demo_data_fast.py
"""
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


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

# Costo neto por familia (CLP) — rangos típicos ferretería Chile / demo creíble.
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


def money(valor):
    return float(int(round(valor / 10.0) * 10))


def pick_unit_profile(categoria, subcategoria):
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


def fetch_scalar(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()[0]


def ensure_almacen(cur, codigo, nombre):
    cur.execute("SELECT id FROM almacenes WHERE codigo = %s", (codigo,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO almacenes (codigo, nombre, activo) VALUES (%s, %s, TRUE) RETURNING id",
        (codigo, nombre),
    )
    return cur.fetchone()[0]


def insert_productos(cur, tienda_id, bodega_id):
    cur.execute("SELECT codigo_interno FROM productos WHERE codigo_interno LIKE 'DEMO-%'")
    existentes = {row[0] for row in cur.fetchall()}
    rows = []
    stock_rows = []
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
        rows.append((
            f"{subcategoria} {random.choice(ADJETIVOS)} {random.choice(MARCAS)} {i}",
            f"7809{200000000 + i}",
            f"CHM-{i:06d}",
            codigo,
            compra,
            venta,
            money(venta * 0.9),
            unidad,
            u_compra,
            u_venta,
            factor,
            stock_tienda + stock_bodega,
            categoria,
            subcategoria,
            f"P{random.randint(1, 18):02d}",
            f"E{random.randint(1, 12):02d}",
            f"N{random.randint(1, 5):02d}",
            True,
        ))
        stock_rows.append((codigo, stock_tienda, stock_bodega))
    if not rows:
        return 0
    inserted = execute_values(
        cur,
        """
        INSERT INTO productos (
            nombre, codigo_barra, codigo_chilemat, codigo_interno, precio_compra,
            precio_venta, precio_mayoreo, unidad, unidad_compra, unidad_venta,
            factor_conversion, stock, categoria, subcategoria, ubicacion_pasillo,
            ubicacion_estante, ubicacion_nivel, activo
        ) VALUES %s
        ON CONFLICT (codigo_barra) DO NOTHING
        RETURNING id, codigo_interno
        """,
        rows,
        fetch=True,
        page_size=500,
    )
    by_code = {codigo: pid for pid, codigo in inserted}
    stock_insert = []
    kardex_insert = []
    now = datetime.now()
    for codigo, stock_tienda, stock_bodega in stock_rows:
        pid = by_code.get(codigo)
        if not pid:
            continue
        stock_insert.append((pid, tienda_id, stock_tienda))
        stock_insert.append((pid, bodega_id, stock_bodega))
        kardex_insert.append((pid, tienda_id, "ENTRADA", stock_tienda, "Carga inicial demo tienda", "Demo ERP", now, "demo", None, stock_tienda))
        kardex_insert.append((pid, bodega_id, "ENTRADA", stock_bodega, "Carga inicial demo bodega", "Demo ERP", now, "demo", None, stock_bodega))
    execute_values(
        cur,
        """
        INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
        VALUES %s
        ON CONFLICT (id_producto, id_almacen) DO UPDATE SET cantidad = EXCLUDED.cantidad
        """,
        stock_insert,
        page_size=1000,
    )
    execute_values(
        cur,
        """
        INSERT INTO movimientos_inventario (
            id_producto, id_almacen, tipo_movimiento, cantidad, motivo,
            usuario, fecha, referencia_tipo, referencia_id, stock_saldo
        ) VALUES %s
        """,
        kardex_insert,
        page_size=1000,
    )
    return len(inserted)


def insert_clientes(cur):
    cur.execute("SELECT rut FROM clientes WHERE rut LIKE '77%'")
    existentes = {row[0] for row in cur.fetchall()}
    rows = []
    for i in range(1, 201):
        rut = rut_demo(i)
        if rut in existentes:
            continue
        comuna = random.choice(COMUNAS)
        rows.append((
            rut,
            f"{random.choice(NOMBRES)} Demo {i:03d}",
            random.choice(["Ferreteria", "Construccion", "Mantencion", "Retail", "Servicios tecnicos"]),
            f"Av. Demo {random.randint(100, 9900)}",
            f"+569{random.randint(40000000, 99999999)}",
            f"cliente.demo{i:03d}@example.com",
            comuna,
            "Santiago",
            money(random.choice([0, 0, 0, random.randint(5000, 165000)])),
            money(random.randint(250000, 1600000)),
            "Activo",
        ))
    if not rows:
        return 0
    execute_values(
        cur,
        """
        INSERT INTO clientes (
            rut, nombre, giro, direccion, telefono, correo, comuna, ciudad,
            saldo_deudor, limite_credito, estado_credito
        ) VALUES %s
        ON CONFLICT (rut) DO NOTHING
        """,
        rows,
        page_size=500,
    )
    return len(rows)


def ensure_caja(cur):
    cur.execute("SELECT id FROM caja WHERE estado = 'Abierta' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO caja (fecha_apertura, monto_inicial, estado, usuario_apertura)
        VALUES (%s, %s, %s, %s) RETURNING id
        """,
        (datetime.now() - timedelta(days=1), 420000, "Abierta", "Demo ERP"),
    )
    return cur.fetchone()[0]


def insert_ventas(cur, caja_id):
    existentes = fetch_scalar(cur, "SELECT COUNT(*) FROM ventas WHERE usuario = 'Demo ERP'")
    if existentes >= 500:
        return 0
    cur.execute("SELECT id, precio_venta FROM productos WHERE codigo_interno LIKE 'DEMO-%' ORDER BY id")
    productos = cur.fetchall()
    cur.execute("SELECT id FROM clientes WHERE rut LIKE '77%' ORDER BY id")
    clientes = [row[0] for row in cur.fetchall()]
    ventas_rows = []
    detalles_por_venta = []
    for i in range(existentes + 1, 501):
        fecha = datetime.now() - timedelta(days=random.randint(0, 89), hours=random.randint(0, 10), minutes=random.randint(0, 59))
        cliente_id = random.choice(clientes) if clientes and random.random() < 0.72 else None
        metodo = random.choices(["Efectivo", "Debito", "Credito"], weights=[55, 32, 13])[0]
        estado = "Pendiente" if metodo == "Credito" else "Pagado"
        detalles = []
        total = 0
        for producto_id, precio in random.sample(productos, random.randint(1, 5)):
            cantidad = random.randint(1, 6)
            descuento = random.choice([0, 0, 0, 5, 10, 15])
            precio = float(precio or 0)
            subtotal = money(cantidad * precio * (1 - descuento / 100))
            detalles.append((producto_id, cantidad, precio, descuento, subtotal))
            total += subtotal
        monto_total = float(round(total))
        neto = round(monto_total / 1.19) if monto_total > 0 else 0
        iva = monto_total - neto
        monto_recibido = 0 if estado != "Pagado" else monto_total + random.choice([0, 0, 0, 1000, 5000, 10000])
        vuelto = max(0, monto_recibido - monto_total)
        ventas_rows.append((
            fecha, monto_total, "Demo ERP", estado, random.choice(["Boleta", "Boleta", "Factura"]),
            neto, iva, metodo, monto_recibido, vuelto, 0.0, random.randint(1, 3),
            random.choice(["Tienda", "Bodega"]), caja_id, cliente_id
        ))
        detalles_por_venta.append(detalles)
    inserted = execute_values(
        cur,
        """
        INSERT INTO ventas (
            fecha, monto_total, usuario, estado, tipo_documento, neto, iva,
            metodo_pago, monto_recibido, vuelto, saldo_favor_usado, prioridad,
            punto_retiro, caja_id, cliente_id
        ) VALUES %s
        RETURNING id
        """,
        ventas_rows,
        fetch=True,
        page_size=250,
    )
    detalle_rows = []
    for (venta_id,), detalles in zip(inserted, detalles_por_venta):
        for producto_id, cantidad, precio, descuento, subtotal in detalles:
            detalle_rows.append((venta_id, producto_id, cantidad, precio, descuento, subtotal))
    execute_values(
        cur,
        """
        INSERT INTO detalle_ventas (
            id_venta, id_producto, cantidad, precio_unitario, descuento, subtotal
        ) VALUES %s
        """,
        detalle_rows,
        page_size=1000,
    )
    return len(inserted)


def insert_saldos(cur):
    cur.execute("SELECT id FROM clientes WHERE rut LIKE '77%' ORDER BY id")
    clientes = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT cliente_id FROM clientes_saldos_favor WHERE saldo > 0")
    con_saldo = {row[0] for row in cur.fetchall()}
    candidatos = [cliente_id for cliente_id in clientes if cliente_id not in con_saldo]
    elegidos = random.sample(candidatos, min(35, len(candidatos)))
    if not elegidos:
        return 0
    rows_saldo = []
    rows_mov = []
    now = datetime.now()
    for cliente_id in elegidos:
        saldo = money(random.randint(1200, 38000))
        rows_saldo.append((cliente_id, saldo, now))
        rows_mov.append((now, cliente_id, None, "CREDITO", saldo, saldo, "Saldo demo por devolucion comercial"))
    execute_values(
        cur,
        """
        INSERT INTO clientes_saldos_favor (cliente_id, saldo, actualizado_en)
        VALUES %s
        ON CONFLICT (cliente_id) DO UPDATE
        SET saldo = EXCLUDED.saldo, actualizado_en = EXCLUDED.actualizado_en
        """,
        rows_saldo,
        page_size=500,
    )
    execute_values(
        cur,
        """
        INSERT INTO movimientos_saldo_favor (
            fecha, cliente_id, cambio_id, tipo, monto, saldo_resultante, observacion
        ) VALUES %s
        """,
        rows_mov,
        page_size=500,
    )
    return len(elegidos)


def main():
    url = os.environ["DATABASE_URL"]
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            tienda_id = ensure_almacen(cur, "TIENDA", "Tienda")
            bodega_id = ensure_almacen(cur, "BODEGA", "Bodega")
            caja_id = ensure_caja(cur)
            resumen = {
                "productos_creados": insert_productos(cur, tienda_id, bodega_id),
                "clientes_creados": insert_clientes(cur),
                "ventas_creadas": insert_ventas(cur, caja_id),
                "saldos_creados": insert_saldos(cur),
            }
            conn.commit()
            resumen.update({
                "productos_demo_total": fetch_scalar(cur, "SELECT COUNT(*) FROM productos WHERE codigo_interno LIKE 'DEMO-%'"),
                "clientes_demo_total": fetch_scalar(cur, "SELECT COUNT(*) FROM clientes WHERE rut LIKE '77%'"),
                "ventas_demo_total": fetch_scalar(cur, "SELECT COUNT(*) FROM ventas WHERE usuario = 'Demo ERP'"),
                "clientes_saldo_favor_total": fetch_scalar(cur, "SELECT COUNT(*) FROM clientes_saldos_favor WHERE saldo > 0"),
            })
            print(resumen)

    flag = (os.environ.get("PATCH_DEMO_CARTERA") or "").strip().lower()
    if flag in ("1", "true", "yes", "on", "si"):
        root = Path(__file__).resolve().parents[1]
        patch_py = root / "scripts" / "patch_demo_credito_cartera.py"
        print(f"PATCH_DEMO_CARTERA={flag!r} -> ejecutando {patch_py.name} ...", flush=True)
        r = subprocess.run(
            [sys.executable, str(patch_py)],
            cwd=str(root),
            env=os.environ.copy(),
        )
        if r.returncode != 0:
            print(f"ADVERTENCIA: {patch_py.name} terminó con código {r.returncode}", flush=True)


if __name__ == "__main__":
    main()
