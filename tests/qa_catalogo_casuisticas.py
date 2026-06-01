"""
Catálogo QA — casuísticas venta, caja, crédito, saldo a favor, obra (C360 / cross-sell).

Prefijos Santo Domingo prueba:
  - Productos: nombre `SD PRUEBA PRODUCTO …`, barras `SD-PRUEBA-*`
  - Clientes: nombre `SD PRUEBA CLIENTE …`

Precios: cada ítem trae `precio_compra`; `precio_venta` se calcula con margen
objetivo (mark-up sobre costo) y terminación $90 salvo override.

Usado por conftest, `scripts/seed_ventas_casuisticas_qa.py`, `scripts/seed_sd_prueba_casuisticas.py`.
"""
from __future__ import annotations

import csv
from pathlib import Path

QA_CAS_PREFIX_BARCODE = 'SD-PRUEBA-'
QA_CAS_PREFIX_NOMBRE = 'SD PRUEBA PRODUCTO '
QA_CAS_PREFIX_CLIENTE = 'SD PRUEBA CLIENTE '
QA_CAS_USER = 'QA_CAS_TEST'

# Margen objetivo medio (~32 % sobre costo → markup tipo ferretería)
MARGEN_VENTA_DEFAULT = 0.32
TERMINACION_PRECIO_DEFAULT = 90

# Códigos de barras estables (tests y seeds referencian estas constantes)
BC_CEMENTO = 'SD-PRUEBA-CEM-001'
BC_ARENA = 'SD-PRUEBA-ARE-001'
BC_PVC = 'SD-PRUEBA-PVC-001'
BC_PEGAMENTO = 'SD-PRUEBA-PEG-001'
BC_LLAVE = 'SD-PRUEBA-LLV-001'
BC_OFERTA_CLAVO = 'SD-PRUEBA-OFE-001'
BC_OFERTA_BROCHA = 'SD-PRUEBA-OFE-002'
BC_STOCK_BAJO = 'SD-PRUEBA-STK-001'
BC_ALTO_ROTACION = 'SD-PRUEBA-VAR-001'

# Legacy TEST-CAS (limpieza); ya no se crean en upsert
LEGACY_BARCODE_PREFIX = 'TEST-CAS-'


def precio_venta_desde_costo(
    precio_compra: float,
    margen: float = MARGEN_VENTA_DEFAULT,
    terminacion: int = TERMINACION_PRECIO_DEFAULT,
) -> float:
    """Misma lógica que `_precio_sugerido_redondeado` en app.py (terminación 90)."""
    try:
        costo = float(precio_compra or 0)
        margen = float(margen or MARGEN_VENTA_DEFAULT)
    except (TypeError, ValueError):
        return 0.0
    margen = min(max(margen, 0.01), 0.90)
    if costo <= 0:
        return 0.0
    base = costo / (1 - margen)
    entero = int(round(base))
    term = int(terminacion or 0)
    if term == 90:
        red = (entero // 100) * 100 + 90
        if red < base:
            red += 100
        return float(red)
    if term == 990:
        miles = entero // 1000
        red = miles * 1000 + 990
        if red < base:
            red = (miles + 1) * 1000 + 990
        return float(red)
    if term == 50:
        red = (entero // 100) * 100 + 50
        if red < base:
            red += 100
        return float(red)
    return float(entero)


def _producto(
    codigo: str,
    desc: str,
    precio_compra: float,
    *,
    stock: int = 60,
    unidad: str = 'Unidad',
    categoria: str = 'Ferreteria',
    subcategoria: str = '',
    fase_obra: str | None = None,
    margen: float | None = None,
    precio_venta: float | None = None,
    escenarios: tuple[str, ...] = (),
    pos_oferta: bool = False,
    pos_oferta_pct: float = 0.0,
    codigo_chilemat: str | None = None,
) -> dict:
    mg = margen if margen is not None else MARGEN_VENTA_DEFAULT
    pv = float(precio_venta) if precio_venta is not None else precio_venta_desde_costo(precio_compra, mg)
    slug = codigo.replace(QA_CAS_PREFIX_BARCODE, '').replace('-', '')
    row = dict(
        nombre=f'{QA_CAS_PREFIX_NOMBRE}{desc}',
        codigo_barra=codigo,
        codigo_interno=f'SDPR-{slug}',
        codigo_chilemat=codigo_chilemat or f'SDPR-{slug}',
        precio_compra=float(precio_compra),
        precio_venta=pv,
        precio_venta_sd=pv,
        precio_mayoreo=max(0, int(round(pv * 0.94 / 10) * 10)),
        stock=int(stock),
        unidad=unidad,
        categoria=categoria,
        subcategoria=subcategoria or None,
        fase_obra=fase_obra,
        activo=True,
        _escenarios=escenarios,
    )
    if pos_oferta:
        row['_pos_descuento_preautorizado'] = True
        row['_pos_descuento_preautorizado_pct'] = float(pos_oferta_pct)
    return row


# ── Productos (precio_compra obligatorio; venta = costo + margen medio) ──
_PRODUCTOS_RAW = [
    _producto(
        BC_CEMENTO,
        'Cemento especial 25kg',
        4500,
        stock=80,
        unidad='Saco',
        categoria='Materiales',
        subcategoria='Cemento',
        fase_obra='OBRA_GRUESA',
        escenarios=('CAS-V01', 'CAS-V04', 'CAS-V07', 'CAS-V08', 'CAS-C01'),
    ),
    _producto(
        BC_ARENA,
        'Arena gruesa m3',
        12000,
        stock=40,
        unidad='M3',
        categoria='Materiales',
        subcategoria='Arena',
        fase_obra='OBRA_GRUESA',
        escenarios=('CAS-V05', 'CAS-V07'),
    ),
    _producto(
        BC_PVC,
        'Tuberia PVC 32mm 3m',
        2200,
        stock=60,
        categoria='Gasfiteria',
        subcategoria='PVC',
        fase_obra='INSTALACIONES',
        escenarios=('CAS-V02', 'CAS-V03'),
    ),
    _producto(
        BC_PEGAMENTO,
        'Pegamento PVC 250cc',
        1800,
        stock=90,
        categoria='Gasfiteria',
        subcategoria='Pegamentos',
        fase_obra='INSTALACIONES',
        escenarios=('CAS-V07',),
    ),
    _producto(
        BC_LLAVE,
        'Llave stillson 14 pulg',
        6500,
        stock=25,
        categoria='Herramientas',
        subcategoria='Llaves',
        fase_obra='TERMINACIONES',
        escenarios=('CAS-V08',),
    ),
    _producto(
        BC_OFERTA_CLAVO,
        'Clavo 3 pulg promo POS',
        900,
        stock=500,
        unidad='Caja',
        categoria='Fijaciones',
        subcategoria='Clavos',
        fase_obra='OBRA_GRUESA',
        escenarios=('CAS-V01', 'CAS-V03', 'CAS-V06'),
        pos_oferta=True,
        pos_oferta_pct=15.0,
    ),
    _producto(
        BC_OFERTA_BROCHA,
        'Brocha 4 pulg promo POS',
        1200,
        stock=120,
        categoria='Pinturas',
        subcategoria='Brochas',
        fase_obra='ACABADOS',
        escenarios=('CAS-V06',),
        pos_oferta=True,
        pos_oferta_pct=10.0,
    ),
    _producto(
        BC_STOCK_BAJO,
        'Guante nitrilo par (stock critico QA)',
        1500,
        stock=3,
        categoria='Seguridad',
        subcategoria='EPP',
        escenarios=('stock_critico',),
        margen=0.28,
    ),
    _producto(
        BC_ALTO_ROTACION,
        'Tornillo drywall 6x1 caja',
        2800,
        stock=200,
        unidad='Caja',
        categoria='Fijaciones',
        subcategoria='Tornillos',
        escenarios=('rotacion',),
    ),
]

PRODUCTOS_CASUISTICAS = []
for _raw in _PRODUCTOS_RAW:
    row = dict(_raw)
    row.pop('_escenarios', None)
    row.pop('_pos_descuento_preautorizado', None)
    row.pop('_pos_descuento_preautorizado_pct', None)
    PRODUCTOS_CASUISTICAS.append(row)

# Metadatos por código (documentación / CSV)
PRODUCTO_ESCENARIOS = {
    r['codigo_barra']: _raw['_escenarios']
    for r, _raw in zip(PRODUCTOS_CASUISTICAS, _PRODUCTOS_RAW)
}

CLIENTES_CASUISTICAS = [
    dict(
        rut='22.222.222-2',
        nombre=f'{QA_CAS_PREFIX_CLIENTE}Saldo Favor',
        giro='Particular',
        direccion='Calle Saldo 100, Santiago',
        telefono='+56922222222',
        correo='sd.prueba.saldo.favor@lhexia.cl',
        limite_credito=500_000,
        c360_etapa_actual='ACABADOS',
        saldo_favor_inicial=25_000,
    ),
    dict(
        rut='33.333.333-3',
        nombre=f'{QA_CAS_PREFIX_CLIENTE}Obra Gruesa',
        giro='Constructor',
        direccion='Av. Obra 2000, Santiago',
        telefono='+56933333333',
        correo='sd.prueba.obra@lhexia.cl',
        limite_credito=3_000_000,
        c360_etapa_actual='OBRA_GRUESA',
        saldo_favor_inicial=0,
    ),
    dict(
        rut='44.444.444-4',
        nombre=f'{QA_CAS_PREFIX_CLIENTE}Credito Cupo',
        giro='Electricista',
        direccion='Pasaje Volt 55, Maipu',
        telefono='+56944444444',
        correo='sd.prueba.credito@lhexia.cl',
        limite_credito=800_000,
        saldo_deudor_inicial=150_000,
        c360_etapa_actual='INSTALACIONES',
        saldo_favor_inicial=0,
    ),
]

ESCENARIOS_VENTA = {
    'CAS-V01': 'POS emitir -> cobro efectivo retiro Tienda (oferta clavo)',
    'CAS-V02': 'POS emitir -> cobro efectivo retiro Bodega -> preparacion bodega (PVC)',
    'CAS-V03': 'Vale mixto: linea Tienda + linea Bodega (oferta + PVC)',
    'CAS-V04': 'Cliente credito: cobro Credito incrementa saldo_deudor (cemento)',
    'CAS-V05': 'Cliente saldo a favor: cobro con usar_saldo_favor parcial (arena)',
    'CAS-V06': 'Producto OFERTA preautorizado (clavo / brocha)',
    'CAS-V07': 'Cross-sell: carrito cemento sugiere arena / complementos',
    'CAS-V08': 'Cliente obra: etapa OBRA_GRUESA + producto fase_obra',
    'CAS-C01': 'OC borrador con producto SD-PRUEBA -> recepcion',
    'STOCK-BAJO': 'Producto SD-PRUEBA-STK-001 con stock <= umbral critico',
}


def _producto_row_para_upsert(data: dict) -> tuple[dict, dict | None]:
    """Separa campos Producto vs flags POS opcionales."""
    row = dict(data)
    pos_pre = row.pop('pos_descuento_preautorizado', None)
    pos_pct = row.pop('pos_descuento_preautorizado_pct', None)
    meta = None
    raw = next((r for r in _PRODUCTOS_RAW if r['codigo_barra'] == data.get('codigo_barra')), None)
    if raw:
        if raw.get('_pos_descuento_preautorizado'):
            pos_pre = True
            pos_pct = raw.get('_pos_descuento_preautorizado_pct')
    if pos_pre is not None or pos_pct is not None:
        meta = {'pos_pre': pos_pre, 'pos_pct': pos_pct}
    return row, meta


def upsert_catalogo_casuisticas(db, m):
    """Crea/actualiza productos y clientes SD-PRUEBA en la BD actual."""
    productos = []
    for data in PRODUCTOS_CASUISTICAS:
        row, meta = _producto_row_para_upsert(dict(data))
        p = m.Producto.query.filter_by(codigo_barra=row['codigo_barra']).first()
        if not p:
            p = m.Producto(**row)
            db.session.add(p)
        else:
            for k, v in row.items():
                setattr(p, k, v)
        if not float(getattr(p, 'precio_venta_sd', None) or 0):
            p.precio_venta_sd = float(p.precio_venta or 0)
        if meta:
            if meta.get('pos_pre') is not None:
                p.pos_descuento_preautorizado = bool(meta['pos_pre'])
            if meta.get('pos_pct') is not None:
                p.pos_descuento_preautorizado_pct = float(meta['pos_pct'])
        productos.append(p)
    db.session.flush()

    aid_t = m.id_almacen_tienda()
    aid_b = m.id_almacen_bodega()
    for p in productos:
        st = int(p.stock or 0)
        if aid_t:
            spa = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_t).first()
            qty_t = max(st, 5) if p.codigo_barra != BC_STOCK_BAJO else st
            if not spa:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_t, cantidad=qty_t))
            else:
                spa.cantidad = max(float(spa.cantidad or 0), float(qty_t))
        if aid_b:
            spb = m.StockPorAlmacen.query.filter_by(id_producto=p.id, id_almacen=aid_b).first()
            qty_b = max(10, st // 2) if p.codigo_barra != BC_STOCK_BAJO else max(0, st)
            if not spb:
                db.session.add(m.StockPorAlmacen(id_producto=p.id, id_almacen=aid_b, cantidad=qty_b))
            else:
                spb.cantidad = max(float(spb.cantidad or 0), float(qty_b))
        if hasattr(m, '_refrescar_stock_total_producto'):
            m._refrescar_stock_total_producto(p)

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
                    observacion='Seed SD-PRUEBA casuísticas — saldo inicial',
                )
            )
        clientes.append(cli)

    db.session.commit()
    return productos, clientes


def export_csv_casuisticas(path: str | Path) -> Path:
    """Exporta catálogo a CSV (carga masiva / revisión de márgenes)."""
    path = Path(path)
    cols = [
        'nombre', 'codigo_chilemat', 'codigo_interno', 'codigo_barra',
        'precio_compra', 'precio_venta', 'precio_mayoreo',
        'unidad_compra', 'unidad_venta', 'factor_conversion', 'stock',
        'categoria', 'subcategoria', 'escenarios_qa',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in PRODUCTOS_CASUISTICAS:
            esc = ','.join(PRODUCTO_ESCENARIOS.get(p['codigo_barra'], ()))
            w.writerow({
                'nombre': p['nombre'],
                'codigo_chilemat': p.get('codigo_chilemat', ''),
                'codigo_interno': p.get('codigo_interno', ''),
                'codigo_barra': p['codigo_barra'],
                'precio_compra': p['precio_compra'],
                'precio_venta': p['precio_venta'],
                'precio_mayoreo': p.get('precio_mayoreo', ''),
                'unidad_compra': p.get('unidad', 'Unidad'),
                'unidad_venta': p.get('unidad', 'Unidad'),
                'factor_conversion': 1,
                'stock': p['stock'],
                'categoria': p.get('categoria', ''),
                'subcategoria': p.get('subcategoria', '') or '',
                'escenarios_qa': esc,
            })
    return path


def limpiar_catalogo_casuisticas(db, m, sa_text):
    """Borra ventas y maestros SD-PRUEBA y legacy TEST-CAS (orden FK)."""
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

        for like in (f'{QA_CAS_PREFIX_BARCODE}%', f'{LEGACY_BARCODE_PREFIX}%'):
            pids = [r[0] for r in db.session.execute(
                sa_text('SELECT id FROM productos WHERE codigo_barra LIKE :p'), {'p': like}).fetchall()]
            if not pids:
                continue
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
