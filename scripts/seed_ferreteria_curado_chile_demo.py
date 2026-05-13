"""
Catálogo curado de DEMOSTRACIÓN — ferretería Chile (referencial, no precios de mercado).

Cubre todas las familias típicas con nombres legibles, categoría/subcategoría, unidades,
factor de conversión donde aplica, ubicación y stock por almacén. Prefijo codigo_interno
DEMO-CUR-* para no mezclar con DEMO-* masivo ni MADERA-CHL-*.

Tras cargar, el tótem /demo/ejecutivo-comercial asigna fotos según palabras clave en
nombre+categoría (ver _get_product_image y _DEMO_* en app.py).

Uso (raíz del proyecto):
    python scripts/seed_ferreteria_curado_chile_demo.py

Idempotente por codigo_interno. Requiere DATABASE_URL / SQLALCHEMY_DATABASE_URI como la app.
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


def _u(s: str, max_len: int = 20) -> str:
    s = (s or "").strip()
    return s[:max_len] if len(s) > max_len else s


# nombre, sufijo DEMO-CUR-{sufijo}, categoria, subcategoria,
# unidad, unidad_compra, unidad_venta, factor, compra, venta, mayoreo, st_tienda, st_bodega
ITEMS: list[tuple[str, str, str, str, str, str, str, float, float, float, float, int, int]] = [
    ("Martillo carpintero mango fibra 27 oz referencial demo", "HM-MART27", "Herramientas Manuales", "Martillos", "Unidad", "Unidad", "Unidad", 1, 8900, 13990, 12890, 25, 70),
    ("Martillo de bola cabeza 450 g mango madera demo", "HM-MART450", "Herramientas Manuales", "Martillos", "Unidad", "Unidad", "Unidad", 1, 6200, 9790, 8990, 30, 85),
    ("Alicate universal 8\" cromado mango doble material demo", "HM-ALIC8", "Herramientas Manuales", "Alicates", "Unidad", "Unidad", "Unidad", 1, 5400, 8490, 7790, 28, 72),
    ("Alicate punta larga 6\" electricista demo", "HM-ALICPL6", "Herramientas Manuales", "Alicates", "Unidad", "Unidad", "Unidad", 1, 4100, 6490, 5970, 35, 90),
    ("Destornillador estrella PH2 x 100 mm punta imantada demo", "HM-DESTPH2", "Herramientas Manuales", "Destornilladores", "Unidad", "Unidad", "Unidad", 1, 1800, 2890, 2650, 60, 140),
    ("Juego destornilladores 6 piezas punta mixta demo", "HM-DESTJ6", "Herramientas Manuales", "Destornilladores", "Unidad", "Unidad", "Unidad", 1, 4900, 7690, 7070, 40, 95),
    ("Llave ajustable 12\" mandíbula cromada demo", "HM-LLV12", "Herramientas Manuales", "Llaves", "Unidad", "Unidad", "Unidad", 1, 7200, 11290, 10390, 22, 55),
    ("Llave combinada 17 mm forjada demo", "HM-LLV17", "Herramientas Manuales", "Llaves", "Unidad", "Unidad", "Unidad", 1, 2900, 4590, 4210, 45, 110),
    ("Serrucho costilla 22\" dientes templados demo", "HM-SERR22", "Herramientas Manuales", "Serruchos", "Unidad", "Unidad", "Unidad", 1, 9800, 14990, 13790, 18, 48),
    ("Taladro percutor 13 mm 750 W cable demo", "HE-TAL750", "Herramientas Electricas", "Taladros", "Unidad", "Unidad", "Unidad", 1, 45900, 68990, 63490, 12, 35),
    ("Taladro atornillador 12 V 2 baterías Li demo", "HE-TAL12V", "Herramientas Electricas", "Taladros", "Unidad", "Unidad", "Unidad", 1, 68900, 99990, 91990, 10, 28),
    ("Esmeril angular 4½\" 850 W referencial demo", "HE-ESM45", "Herramientas Electricas", "Esmeriles", "Unidad", "Unidad", "Unidad", 1, 32900, 48990, 45090, 14, 38),
    ("Sierra circular 7¼\" 185 mm 1400 W demo", "HE-SIRC7", "Herramientas Electricas", "Sierras", "Unidad", "Unidad", "Unidad", 1, 78900, 114990, 105790, 6, 18),
    ("Lijadora orbital 240 W base 125 mm demo", "HE-LIJ240", "Herramientas Electricas", "Lijadoras", "Unidad", "Unidad", "Unidad", 1, 41900, 61990, 56990, 11, 30),
    ("Rotomartillo SDS Plus 800 W demo", "HE-ROT800", "Herramientas Electricas", "Rotomartillos", "Unidad", "Unidad", "Unidad", 1, 97900, 142990, 131590, 5, 14),
    ("Tornillo drywall negro 6x1\" bolsa 500 u demo", "FJ-TDW500", "Fijaciones", "Tornillos", "Unidad", "Caja", "Unidad", 500, 8900, 12990, 11940, 40, 120),
    ("Tornillo madera Tirafondo 6x60 mm bolsa 50 u demo", "FJ-TF6060", "Fijaciones", "Tornillos", "Unidad", "Bolsa", "Unidad", 50, 4200, 6490, 5970, 55, 140),
    ("Clavo acero común 2\" bolsa 1 kg demo", "FJ-CLV2-1K", "Fijaciones", "Clavos", "Kg", "Bolsa", "Kg", 1, 3800, 5890, 5410, 70, 200),
    ("Tarugo nylon 8 mm bolsa 50 u demo", "FJ-TAR850", "Fijaciones", "Tarugos", "Unidad", "Bolsa", "Unidad", 50, 2600, 3990, 3670, 48, 130),
    ("Perno galvanizado ⅜\" x 4\" tuerca arandela demo", "FJ-PER38", "Fijaciones", "Pernos", "Unidad", "Unidad", "Unidad", 1, 890, 1490, 1370, 200, 480),
    ("Abrazadera manguera inox ½\" 2 u blister demo", "FJ-ABZ12", "Fijaciones", "Abrazaderas", "Par", "Blister", "Par", 1, 1900, 2990, 2750, 80, 190),
    ("Arandela plana zinc surtido estuche 200 u demo", "FJ-ARAN200", "Fijaciones", "Pernos", "Unidad", "Estuche", "Unidad", 200, 2100, 3290, 3020, 36, 95),
    ("Tornillo autoroscante punta broca hexagonal bolsa 100 u demo", "FJ-TAUT100", "Fijaciones", "Tornillos", "Unidad", "Bolsa", "Unidad", 100, 6400, 9490, 8720, 42, 115),
    ("Clavo para concreto acero 3\" bolsa 500 g demo", "FJ-CLC500", "Fijaciones", "Clavos", "Unidad", "Bolsa", "Unidad", 1, 5200, 7890, 7250, 40, 105),
    ("Látex interior blanco 20 L cubeta demo", "PT-LTX20", "Pinturas", "Latex", "Litro", "Cubeta", "Litro", 20, 38900, 55990, 51490, 8, 22),
    ("Látex exterior premium blanco 10 L demo", "PT-LTX10", "Pinturas", "Latex", "Litro", "Cubeta", "Litro", 10, 28900, 41990, 38590, 12, 30),
    ("Esmalte sintético negro brillante ¼ galón demo", "PT-ESM025", "Pinturas", "Esmaltes", "Litro", "Envase", "Litro", 1, 6900, 10590, 9740, 45, 115),
    ("Barniz marino brillante 1 L demo", "PT-BRN1", "Pinturas", "Barnices", "Litro", "Envase", "Litro", 1, 9800, 14990, 13790, 28, 72),
    ("Brocha cerda natural 3\" mango madera demo", "PT-BRO3", "Pinturas", "Brochas", "Unidad", "Unidad", "Unidad", 1, 3200, 4990, 4590, 50, 125),
    ("Rodillo felpa 9\" mango plástico demo", "PT-ROD9", "Pinturas", "Rodillos", "Unidad", "Unidad", "Unidad", 1, 4100, 6390, 5870, 38, 98),
    ("Enduido pasta interior 25 kg bolsa demo", "PT-END25", "Pinturas", "Latex", "Unidad", "Bolsa", "Unidad", 1, 12900, 18990, 17440, 22, 58),
    ("Sellador acrílico 5 L demo", "PT-SEL5", "Pinturas", "Latex", "Litro", "Cubeta", "Litro", 5, 14900, 21990, 20240, 18, 46),
    ("Tubo PVC sanitario 110 mm x 3 m SN4 demo", "GF-PVC110", "Gasfiteria", "PVC", "Metro", "Barra", "Metro", 3, 8900, 13290, 12210, 26, 68),
    ("Tubo PVC presión ¾\" x 5 m clase 10 demo", "GF-PVC034", "Gasfiteria", "PVC", "Metro", "Barra", "Metro", 5, 5200, 7990, 7340, 34, 88),
    ("Codo PVC 90° 110 mm demo", "GF-C11090", "Gasfiteria", "PVC", "Unidad", "Unidad", "Unidad", 1, 2100, 3290, 3020, 120, 300),
    ("Llave de paso compresión ½\" demo", "GF-LLV12", "Gasfiteria", "Llaves de paso", "Unidad", "Unidad", "Unidad", 1, 3800, 5890, 5410, 55, 145),
    ("Flexible lavamanos 40 cm acero demo", "GF-FLX40", "Gasfiteria", "Flexibles", "Unidad", "Unidad", "Unidad", 1, 2900, 4590, 4210, 70, 175),
    ("Sifón botella lavaplato plástico demo", "GF-SIFBOT", "Gasfiteria", "Sifones", "Unidad", "Unidad", "Unidad", 1, 4200, 6590, 6050, 44, 112),
    ("Teflón gas rojo rollo 12 mm x 10 m demo", "GF-TEF12", "Gasfiteria", "Sellos", "Unidad", "Unidad", "Unidad", 1, 900, 1490, 1370, 150, 380),
    ("Masilla plástica epóxica tubo bicomponente demo", "GF-MAS2K", "Gasfiteria", "Sellos", "Unidad", "Unidad", "Unidad", 1, 5900, 8990, 8260, 33, 85),
    ("Unión PVC con reducción 110 a 90 mm demo", "GF-RED110", "Gasfiteria", "PVC", "Unidad", "Unidad", "Unidad", 1, 3400, 5290, 4860, 40, 105),
    ("Te PVC sanitario 110 mm demo", "GF-TE110", "Gasfiteria", "PVC", "Unidad", "Unidad", "Unidad", 1, 4600, 7090, 6520, 36, 94),
    ("Cable THHN 2.5 mm² rollo 100 m negro demo", "EL-CAB25", "Electricidad", "Cables", "Metro", "Rollo", "Metro", 100, 52900, 76990, 70790, 14, 38),
    ("Cable subterráneo 3x2.5 mm² metro demo", "EL-CABSUB", "Electricidad", "Cables", "Metro", "Metro", "Metro", 1, 1890, 2790, 2560, 280, 620),
    ("Interruptor simple 10 A embutir demo", "EL-INTS10", "Electricidad", "Interruptores", "Unidad", "Unidad", "Unidad", 1, 1200, 1890, 1730, 140, 340),
    ("Interruptor doble 10 A embutir demo", "EL-INTD10", "Electricidad", "Interruptores", "Unidad", "Unidad", "Unidad", 1, 2100, 3290, 3020, 95, 245),
    ("Enchufe polarizado embutir 10 A demo", "EL-ENCH10", "Electricidad", "Enchufes", "Unidad", "Unidad", "Unidad", 1, 980, 1590, 1460, 160, 400),
    ("Canaleta PVC adherente 25x16 mm rollo 2 m demo", "EL-CAN2516", "Electricidad", "Canaletas", "Metro", "Caja", "Metro", 24, 8400, 12490, 11490, 30, 78),
    ("Ampolleta LED fría 9 W E27 demo", "EL-LED9", "Electricidad", "Ampolletas", "Unidad", "Unidad", "Unidad", 1, 890, 1390, 1270, 220, 520),
    ("Pack ampolletas LED 10 W cálida blister 4 u demo", "EL-LED4P", "Electricidad", "Ampolletas", "Unidad", "Blister", "Unidad", 4, 5900, 8790, 8080, 55, 140),
    ("Breaker monofásico 16 A curva C demo", "EL-BRK16", "Electricidad", "Interruptores", "Unidad", "Unidad", "Unidad", 1, 6900, 10490, 9640, 42, 108),
    ("Zapatilla 6 tomas sobretensión demo", "EL-ZAP6", "Electricidad", "Enchufes", "Unidad", "Unidad", "Unidad", 1, 7900, 11790, 10840, 35, 92),
    ("Cemento Polpaço 25 kg bolsa demo", "CO-CEM25", "Construccion", "Cemento", "Unidad", "Bolsa", "Unidad", 1, 7200, 10490, 9640, 180, 420),
    ("Yeso saco 25 kg demo", "CO-YES25", "Construccion", "Yeso", "Unidad", "Bolsa", "Unidad", 1, 6900, 10290, 9460, 65, 155),
    ("Adhesivo cerámico interior 25 kg demo", "CO-ADC25", "Construccion", "Adhesivos", "Unidad", "Bolsa", "Unidad", 1, 9900, 14490, 13320, 48, 118),
    ("Autonivelante saco 20 kg demo", "CO-NVL20", "Construccion", "Niveladores", "Unidad", "Bolsa", "Unidad", 1, 14900, 21990, 20240, 22, 56),
    ("Lana mineral rollo 50 mm x 9 m² demo", "CO-LAN50", "Construccion", "Aislantes", "Unidad", "Rollo", "Unidad", 1, 18900, 27490, 25270, 14, 38),
    ("Espuma poliuretano PU750 ml pistola demo", "CO-PU750", "Construccion", "Adhesivos", "Unidad", "Unidad", "Unidad", 1, 5900, 8890, 8170, 44, 112),
    ("Melamina blanca 15 mm 1,22x2,44 m lámina demo", "CO-MEL15", "Construccion", "Maderas y tableros", "Plancha", "Plancha", "Plancha", 1, 28900, 41990, 38590, 12, 32),
    ("MDF crudo 12 mm 1,22x2,44 m lámina demo", "CO-MDF12", "Construccion", "Maderas y tableros", "Plancha", "Plancha", "Plancha", 1, 23900, 34990, 32160, 10, 28),
    ("Clavo acero arpillera 1½\" bolsa 500 g demo", "FJ-ARP500", "Fijaciones", "Clavos", "Unidad", "Bolsa", "Unidad", 1, 2900, 4590, 4210, 62, 158),
    ("Gas guantes nitrilo negro par talla M demo", "SG-GASN-M", "Seguridad", "Guantes", "Par", "Blister", "Par", 1, 1800, 2790, 2560, 85, 210),
    ("Guantes vaqueta refuerzo palma demo", "SG-VAQ", "Seguridad", "Guantes", "Par", "Par", "Par", 1, 2900, 4590, 4210, 72, 185),
    ("Lentes seguridad anti-rayado demo", "SG-LENT", "Seguridad", "Lentes", "Unidad", "Unidad", "Unidad", 1, 3200, 4990, 4590, 48, 125),
    ("Casco seguridad blanco arnés ratchet demo", "SG-CASC", "Seguridad", "Cascos", "Unidad", "Unidad", "Unidad", 1, 8900, 13490, 12400, 28, 72),
    ("Mascarilla respirador válvula FFP2 blister demo", "SG-MASKFF", "Seguridad", "Mascarillas", "Unidad", "Blister", "Unidad", 5, 4900, 7390, 6790, 55, 140),
    ("Zapatilla seguridad puntera acero talla 42 demo", "SG-ZAP42", "Seguridad", "Calzado", "Par", "Par", "Par", 1, 35900, 51990, 47840, 12, 32),
    ("Manguera jardín ½\" 25 m capas verde demo", "JR-MAN25", "Jardin", "Mangueras", "Metro", "Rollo", "Metro", 25, 12900, 18990, 17440, 20, 54),
    ("Pala construcción mango fibra demo", "JR-PALA", "Jardin", "Palas", "Unidad", "Unidad", "Unidad", 1, 9800, 14990, 13790, 28, 74),
    ("Rastrillo metálico 14 dientes mango demo", "JR-RAST14", "Jardin", "Rastrillos", "Unidad", "Unidad", "Unidad", 1, 7600, 11790, 10840, 22, 58),
    ("Regador plástico 10 L verde demo", "JR-REG10", "Jardin", "Regadores", "Unidad", "Unidad", "Unidad", 1, 2900, 4590, 4210, 44, 112),
    ("Tijeras podar bypass 8\" demo", "JR-TIJ8", "Jardin", "Tijeras", "Unidad", "Unidad", "Unidad", 1, 6900, 10490, 9640, 26, 68),
    ("Azadón forjado mango madera demo", "JR-AZAD", "Jardin", "Palas", "Unidad", "Unidad", "Unidad", 1, 8900, 13490, 12400, 18, 46),
    ("Bisagra hierro 3\" par zincado demo", "QN-BIS3", "Quincalleria", "Bisagras", "Par", "Blister", "Par", 1, 2400, 3790, 3480, 66, 168),
    ("Candado laminado 50 mm 2 llaves demo", "QN-CAN50", "Quincalleria", "Candados", "Unidad", "Unidad", "Unidad", 1, 4900, 7390, 6790, 42, 108),
    ("Cerradura sobreponer 60 mm latón demo", "QN-CER60", "Quincalleria", "Cerraduras", "Unidad", "Unidad", "Unidad", 1, 15900, 22990, 21140, 18, 48),
    ("Riel cajón telescópico 35 cm par demo", "QN-RIEL35", "Quincalleria", "Rieles", "Par", "Par", "Par", 1, 7900, 11790, 10840, 24, 62),
    ("Soporte estantería L 250 mm par demo", "QN-SOP250", "Quincalleria", "Soportes", "Par", "Blister", "Par", 1, 4200, 6590, 6050, 38, 98),
    ("Pasador pestillo 4\" acero demo", "QN-PAS4", "Quincalleria", "Bisagras", "Unidad", "Unidad", "Unidad", 1, 1800, 2790, 2560, 90, 225),
    ("Picaporte aluminio plateado demo", "QN-PICA", "Quincalleria", "Cerraduras", "Unidad", "Unidad", "Unidad", 1, 6900, 10490, 9640, 32, 82),
    ("Escuadra refuerzo estantería zincada demo", "QN-ESC90", "Quincalleria", "Soportes", "Unidad", "Unidad", "Unidad", 1, 1200, 1890, 1730, 110, 275),
]


def main() -> None:
    prefijo = "DEMO-CUR-"
    barra_base = 7809200850000

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
        pasillo = 3
        for idx, row in enumerate(ITEMS, start=1):
            nombre, suf, cat, sub, unidad, uc, uv, fac, pc, pv, pm, st_t, st_b = row
            codigo_interno = f"{prefijo}{suf}"
            if codigo_interno in existentes:
                continue
            if len(nombre) > 100:
                nombre = nombre[:97] + "..."

            codigo_barra = str(barra_base + idx)
            codigo_chilemat = f"CHM-DEMO-{suf.replace('/', '-')}"

            compra = money(float(pc))
            venta = money(float(pv))
            mayoreo = money(float(pm))
            stock_total = int(st_t + st_b)

            pasillo = (pasillo % 18) + 1

            p = Producto(
                nombre=nombre,
                codigo_barra=codigo_barra,
                codigo_interno=codigo_interno,
                codigo_chilemat=codigo_chilemat,
                precio_compra=compra,
                precio_venta=venta,
                precio_mayoreo=mayoreo,
                unidad=_u(unidad),
                unidad_compra=_u(uc),
                unidad_venta=_u(uv),
                factor_conversion=float(fac),
                stock=stock_total,
                categoria=cat,
                subcategoria=sub,
                ubicacion_pasillo=f"P{pasillo:02d}",
                ubicacion_estante=f"E{(idx % 12) + 1:02d}",
                ubicacion_nivel=f"N{(idx % 5) + 1:02d}",
                activo=True,
            )
            db.session.add(p)
            db.session.flush()

            if multi_almacen and tienda and bodega:
                db.session.merge(StockPorAlmacen(id_producto=p.id, id_almacen=tienda.id, cantidad=int(st_t)))
                db.session.merge(StockPorAlmacen(id_producto=p.id, id_almacen=bodega.id, cantidad=int(st_b)))
                now = datetime.now()
                db.session.add(
                    MovimientoInventario(
                        id_producto=p.id,
                        id_almacen=tienda.id,
                        tipo_movimiento="ENTRADA",
                        cantidad=int(st_t),
                        motivo="Carga demo catálogo curado Chile (tienda)",
                        usuario="seed_ferreteria_curado_chile_demo",
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
                        motivo="Carga demo catálogo curado Chile (bodega)",
                        usuario="seed_ferreteria_curado_chile_demo",
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
                "productos_demo_cur_total": total_cat,
                "multi_almacen": multi_almacen,
            }
        )


if __name__ == "__main__":
    main()
