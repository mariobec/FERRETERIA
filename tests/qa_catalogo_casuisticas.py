"""
Catálogo QA — casuísticas de venta, caja, crédito, saldo a favor y obra (C360 / cross-sell).

Prefijos:
  - Productos: codigo_barra `TEST-CAS-*`
  - Clientes: nombre `TEST CAS *` y RUTs dedicados

Usado por `tests/conftest.py`, `scripts/seed_ventas_casuisticas_qa.py` y
`tests/test_ventas_casuisticas_flujo.py`.
"""
from __future__ import annotations

QA_CAS_PREFIX_BARCODE = 'TEST-CAS-'
QA_CAS_USER = 'QA_CAS_TEST'

# ── Productos ───────────────────────────────────────────────────────
PRODUCTOS_CASUISTICAS = [
    dict(
        nombre='TEST CAS Cemento especial 25kg',
        codigo_barra='TEST-CAS-CEM-001',
        codigo_interno='TCAS-CEM-001',
        precio_compra=4500,
        precio_venta=7990,
        stock=80,
        unidad='Saco',
        categoria='Materiales',
        subcategoria='Cemento',
        fase_obra='OBRA_GRUESA',
        activo=True,
    ),
    dict(
        nombre='TEST CAS Arena gruesa m3',
        codigo_barra='TEST-CAS-ARE-001',
        codigo_interno='TCAS-ARE-001',
        precio_compra=12000,
        precio_venta=18990,
        stock=40,
        unidad='M3',
        categoria='Materiales',
        subcategoria='Arena',
        fase_obra='OBRA_GRUESA',
        activo=True,
    ),
    dict(
        nombre='TEST CAS Tuberia PVC 32mm 3m',
        codigo_barra='TEST-CAS-PVC-001',
        codigo_interno='TCAS-PVC-001',
        precio_compra=2200,
        precio_venta=4490,
        stock=60,
        unidad='Unidad',
        categoria='Gasfiteria',
        subcategoria='PVC',
        fase_obra='INSTALACIONES',
        activo=True,
    ),
    dict(
        nombre='TEST CAS Pegamento PVC 250cc',
        codigo_barra='TEST-CAS-PEG-001',
        codigo_interno='TCAS-PEG-001',
        precio_compra=1800,
        precio_venta=3290,
        stock=90,
        unidad='Unidad',
        categoria='Gasfiteria',
        subcategoria='Pegamentos',
        fase_obra='INSTALACIONES',
        activo=True,
    ),
    dict(
        nombre='TEST CAS Llave stillson 14"',
        codigo_barra='TEST-CAS-LLV-001',
        codigo_interno='TCAS-LLV-001',
        precio_compra=6500,
        precio_venta=11990,
        stock=25,
        unidad='Unidad',
        categoria='Herramientas',
        subcategoria='Llaves',
        fase_obra='TERMINACIONES',
        activo=True,
    ),
    dict(
        nombre='TEST CAS OFERTA Clavo 3" promo',
        codigo_barra='TEST-CAS-OFE-001',
        codigo_interno='TCAS-OFE-001',
        precio_compra=900,
        precio_venta=1990,
        stock=500,
        unidad='Caja',
        categoria='Fijaciones',
        subcategoria='Clavos',
        fase_obra='OBRA_GRUESA',
        pos_descuento_preautorizado=True,
        pos_descuento_preautorizado_pct=15.0,
        activo=True,
    ),
    dict(
        nombre='TEST CAS OFERTA Brocha 4" promo',
        codigo_barra='TEST-CAS-OFE-002',
        codigo_interno='TCAS-OFE-002',
        precio_compra=1200,
        precio_venta=2990,
        stock=120,
        unidad='Unidad',
        categoria='Pinturas',
        subcategoria='Brochas',
        fase_obra='ACABADOS',
        pos_descuento_preautorizado=True,
        pos_descuento_preautorizado_pct=10.0,
        activo=True,
    ),
]

CLIENTES_CASUISTICAS = [
    dict(
        rut='22.222.222-2',
        nombre='TEST CAS Cliente Saldo Favor',
        giro='Particular',
        direccion='Calle Saldo 100, Santiago',
        telefono='+56922222222',
        correo='saldo.favor@cas-test.cl',
        limite_credito=500_000,
        c360_etapa_actual='ACABADOS',
        saldo_favor_inicial=25_000,
    ),
    dict(
        rut='33.333.333-3',
        nombre='TEST CAS Cliente Obra Gruesa',
        giro='Constructor',
        direccion='Av. Obra 2000, Santiago',
        telefono='+56933333333',
        correo='obra.gruesa@cas-test.cl',
        limite_credito=3_000_000,
        c360_etapa_actual='OBRA_GRUESA',
        saldo_favor_inicial=0,
    ),
    dict(
        rut='44.444.444-4',
        nombre='TEST CAS Cliente Credito Cupo',
        giro='Electricista',
        direccion='Pasaje Volt 55, Maipu',
        telefono='+56944444444',
        correo='credito.cupo@cas-test.cl',
        limite_credito=800_000,
        saldo_deudor_inicial=150_000,
        c360_etapa_actual='INSTALACIONES',
        saldo_favor_inicial=0,
    ),
]

# Matriz documentada (ID → escenario)
ESCENARIOS_VENTA = {
    'CAS-V01': 'POS emitir -> cobro efectivo retiro Tienda',
    'CAS-V02': 'POS emitir -> cobro efectivo retiro Bodega -> preparacion bodega',
    'CAS-V03': 'Vale mixto: linea Tienda + linea Bodega (retiro por linea)',
    'CAS-V04': 'Cliente credito: cobro metodo Credito incrementa saldo_deudor',
    'CAS-V05': 'Cliente saldo a favor: cobro con usar_saldo_favor parcial',
    'CAS-V06': 'Producto OFERTA preautorizado (descuento POS sin supervisor)',
    'CAS-V07': 'Cross-sell: carrito cemento sugiere arena/herramientas',
    'CAS-V08': 'Cliente obra: historial cemento alimenta C360 / recomendaciones',
    'CAS-C01': 'OC borrador con producto CAS -> recepcion parcial',
}


def upsert_catalogo_casuisticas(db, m):
    """Crea/actualiza productos y clientes del catálogo CAS en la BD actual."""
    productos = []
    for data in PRODUCTOS_CASUISTICAS:
        row = dict(data)
        pos_pre = row.pop('pos_descuento_preautorizado', None)
        pos_pct = row.pop('pos_descuento_preautorizado_pct', None)
        p = m.Producto.query.filter_by(codigo_barra=row['codigo_barra']).first()
        if not p:
            p = m.Producto(**row)
            db.session.add(p)
        else:
            for k, v in row.items():
                setattr(p, k, v)
        if pos_pre is not None:
            p.pos_descuento_preautorizado = bool(pos_pre)
        if pos_pct is not None:
            p.pos_descuento_preautorizado_pct = float(pos_pct)
        productos.append(p)
    db.session.flush()

    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    for p in productos:
        if aid_t:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_t).first()
            if not spa:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_t, cantidad=p.stock or 0))
            else:
                spa.cantidad = max(float(spa.cantidad or 0), float(p.stock or 0))
        if aid_b:
            spb = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
            qty_b = max(10, int((p.stock or 0) // 2))
            if not spb:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_b, cantidad=qty_b))
            else:
                spb.cantidad = max(float(spb.cantidad or 0), float(qty_b))

    clientes = []
    for data in CLIENTES_CASUISTICAS:
        row = dict(data)
        sf_ini = float(row.pop('saldo_favor_inicial', 0) or 0)
        deuda_ini = float(row.pop('saldo_deudor_inicial', 0) or 0)
        cli = m.Cliente.query.filter_by(rut=row['rut']).first()
        if not cli:
            cli = m.Cliente(**row)
            db.session.add(cli)
        else:
            for k, v in row.items():
                setattr(cli, k, v)
        cli.saldo_deudor = deuda_ini
        db.session.flush()
        if sf_ini > 0:
            reg = m.ClienteSaldoFavor.query.filter_by(cliente_id=cli.id).first()
            if not reg:
                reg = m.ClienteSaldoFavor(cliente_id=cli.id, saldo=0)
                db.session.add(reg)
                db.session.flush()
            reg.saldo = sf_ini
            db.session.add(
                m.MovimientoSaldoFavor(
                    cliente_id=cli.id,
                    cambio_id=None,
                    tipo='CREDITO',
                    monto=sf_ini,
                    saldo_resultante=sf_ini,
                    observacion='Seed QA casuísticas — saldo inicial',
                )
            )
        clientes.append(cli)

    db.session.commit()
    return productos, clientes


def limpiar_catalogo_casuisticas(db, m, sa_text):
    """Borra ventas y maestros TEST-CAS (orden FK)."""
    db.session.rollback()
    try:
        ruts = tuple(c['rut'] for c in CLIENTES_CASUISTICAS)
        cli_ids = [r[0] for r in db.session.execute(
            sa_text('SELECT id FROM clientes WHERE rut IN :r'), {'r': ruts}).fetchall()]
        if cli_ids:
            ct = tuple(cli_ids)
            vids = [r[0] for r in db.session.execute(
                sa_text('SELECT id FROM ventas WHERE cliente_id IN :c'), {'c': ct}).fetchall()]
            if vids:
                vt = tuple(vids)
                for tbl, col in (
                    ('ventas_cuotas_credito', 'venta_id'),
                    ('ventas_a_pedido', 'venta_id'),
                    ('detalle_ventas', 'id_venta'),
                ):
                    try:
                        db.session.execute(sa_text(f'DELETE FROM {tbl} WHERE {col} IN :v'), {'v': vt})
                    except Exception:
                        db.session.rollback()
                db.session.execute(sa_text('DELETE FROM ventas WHERE id IN :v'), {'v': vt})
            for dep in ('movimientos_saldo_favor', 'clientes_saldos_favor', 'abonos_credito'):
                try:
                    db.session.execute(sa_text(f'DELETE FROM {dep} WHERE cliente_id IN :c'), {'c': ct})
                except Exception:
                    db.session.rollback()

        pids = [r[0] for r in db.session.execute(
            sa_text("SELECT id FROM productos WHERE codigo_barra LIKE 'TEST-CAS-%'")).fetchall()]
        if pids:
            pt = tuple(pids)
            dv_vids = [r[0] for r in db.session.execute(
                sa_text('SELECT DISTINCT id_venta FROM detalle_ventas WHERE id_producto IN :p'),
                {'p': pt}).fetchall()]
            if dv_vids:
                dvt = tuple(dv_vids)
                db.session.execute(sa_text('DELETE FROM ventas_cuotas_credito WHERE venta_id IN :v'), {'v': dvt})
                db.session.execute(sa_text('DELETE FROM detalle_ventas WHERE id_venta IN :v'), {'v': dvt})
                db.session.execute(sa_text('DELETE FROM ventas WHERE id IN :v'), {'v': dvt})
            db.session.execute(sa_text('DELETE FROM movimientos_inventario WHERE id_producto IN :p'), {'p': pt})
            db.session.execute(sa_text('DELETE FROM stock_por_almacen WHERE id_producto IN :p'), {'p': pt})
            db.session.execute(sa_text('DELETE FROM detalle_orden_compra WHERE producto_id IN :p'), {'p': pt})
            db.session.execute(sa_text('DELETE FROM productos WHERE id IN :p'), {'p': pt})

        db.session.execute(sa_text('DELETE FROM clientes WHERE rut IN :r'), {'r': ruts})
        db.session.execute(sa_text('DELETE FROM ventas WHERE usuario = :u'), {'u': QA_CAS_USER})
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
