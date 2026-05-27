"""
Producto ERP de ejemplo vinculado a Chilemat (imagen + ficha) para probar POS local.

Uso (raíz del proyecto, DATABASE_URL en .env.local):
    python scripts/seed_pos_chilemat_ejemplo.py
    python scripts/seed_pos_chilemat_ejemplo.py --vtex-id 34891
    python scripts/seed_pos_chilemat_ejemplo.py --purge

Código de barras fijo: DEMO-CHM-BARNIZ (idempotente).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    Almacen,
    ChilematVtexProducto,
    Producto,
    StockPorAlmacen,
    _asegurar_tablas_chilemat_relaciones,
    _refrescar_stock_total_producto,
    app,
    db,
    id_almacen_bodega,
    id_almacen_tienda,
    _tablas_inventario_almacen_existen,
)
from services.chilemat_ficha_service import (  # noqa: E402
    _asegurar_columnas_ficha,
    extraer_ficha_de_json_vtex,
    fetch_vtex_producto_api,
)

CODIGO_BARRA = 'DEMO-CHM-BARNIZ'
VTEX_DEFAULT = '34891'


def _ensure_stock(pid: int, qty_tienda: int = 12, qty_bodega: int = 8) -> None:
    tienda = id_almacen_tienda()
    bodega = id_almacen_bodega()
    if not tienda:
        a = Almacen(codigo='TIENDA', nombre='Tienda / Mostrador', activo=True)
        db.session.add(a)
        db.session.flush()
        tienda = a.id
    if not bodega:
        a = Almacen(codigo='BODEGA', nombre='Bodega', activo=True)
        db.session.add(a)
        db.session.flush()
        bodega = a.id
    if _tablas_inventario_almacen_existen():
        for id_alm, qty in ((tienda, qty_tienda), (bodega, qty_bodega)):
            spa = StockPorAlmacen.query.filter_by(id_producto=pid, id_almacen=id_alm).first()
            if spa:
                spa.cantidad = int(qty)
            else:
                db.session.add(
                    StockPorAlmacen(id_producto=pid, id_almacen=id_alm, cantidad=int(qty))
                )
    p = Producto.query.get(pid)
    if p:
        _refrescar_stock_total_producto(p)


def seed(*, vtex_id: str = VTEX_DEFAULT, refrescar_api: bool = True) -> dict:
    _asegurar_tablas_chilemat_relaciones()
    _asegurar_columnas_ficha()

    ficha = fetch_vtex_producto_api(vtex_id) if refrescar_api else None
    if not ficha:
        from services.chilemat_catalogo_service import _fetch_json, CHILEMAT_BASE

        data = _fetch_json(
            f'{CHILEMAT_BASE}/api/catalog_system/pub/products/search'
            f'?fq=productId:{vtex_id}&_from=0&_to=0'
        )
        if not data:
            raise SystemExit(f'No se encontró producto VTEX {vtex_id} en chilemat.com')
        ficha = extraer_ficha_de_json_vtex(data[0])

    nombre = (ficha.get('nombre') or 'Producto demo Chilemat')[:200]
    ref = (ficha.get('product_reference') or '')[:80]
    img = (ficha.get('imagen_url') or '')[:500]
    link = (ficha.get('link') or '')[:500]
    precio = float(ficha.get('precio_lista') or 5690)

    p = Producto.query.filter_by(codigo_barra=CODIGO_BARRA).first()
    if not p:
        p = Producto(
            codigo_barra=CODIGO_BARRA,
            codigo_interno='DEMO-CHM-001',
            nombre=nombre,
            activo=True,
        )
        db.session.add(p)
        db.session.flush()
    else:
        p.nombre = nombre
        p.activo = True

    p.codigo_chilemat = ref or p.codigo_chilemat
    p.precio_venta = precio
    p.precio_compra = round(precio * 0.72, 2)
    p.categoria = p.categoria or 'Pinturas'
    p.subcategoria = p.subcategoria or 'Barnices'
    if img:
        p.imagen_url = img

    row = ChilematVtexProducto.query.get(vtex_id)
    if not row:
        row = ChilematVtexProducto(vtex_product_id=vtex_id)
        db.session.add(row)
    row.product_reference = ref or None
    row.producto_id = p.id
    row.nombre = nombre
    row.link = link or None
    row.brand = (ficha.get('marca') or 'Chilemat')[:80]
    row.precio_lista = precio
    row.imagen_url = img or None
    row.descripcion_web = (ficha.get('descripcion_html') or '')[:8000] or None
    row.descripcion_corta = (ficha.get('descripcion_corta') or nombre)[:500]
    row.synced_at = datetime.utcnow()

    _ensure_stock(p.id)
    db.session.commit()

    return {
        'producto_id': p.id,
        'codigo_barra': CODIGO_BARRA,
        'nombre': p.nombre,
        'vtex_product_id': vtex_id,
        'imagen_url': p.imagen_url,
        'link': link,
        'precio_venta': p.precio_venta,
        'stock': int(p.stock or 0),
    }


def purge() -> None:
    p = Producto.query.filter_by(codigo_barra=CODIGO_BARRA).first()
    if p:
        ChilematVtexProducto.query.filter_by(producto_id=p.id).update({'producto_id': None})
        db.session.delete(p)
    row = ChilematVtexProducto.query.get(VTEX_DEFAULT)
    if row and (row.product_reference or '').startswith('0101006'):
        db.session.delete(row)
    db.session.commit()
    print('Eliminado demo', CODIGO_BARRA)


def main() -> None:
    ap = argparse.ArgumentParser(description='Seed producto demo Chilemat para POS local')
    ap.add_argument('--vtex-id', default=VTEX_DEFAULT, help='ID VTEX Chilemat (default 34891 barniz)')
    ap.add_argument('--purge', action='store_true', help='Quitar producto demo')
    ap.add_argument('--sin-api', action='store_true', help='No llamar API (usar solo si ya hay fila VTEX)')
    args = ap.parse_args()

    with app.app_context():
        if args.purge:
            purge()
            return
        info = seed(vtex_id=str(args.vtex_id).strip(), refrescar_api=not args.sin_api)
        print('OK — producto demo Chilemat cargado:')
        for k, v in info.items():
            print(f'  {k}: {v}')
        print()
        print('En POS: busque o escanee', CODIGO_BARRA)
        print('  /punto_venta -> agregar al carrito -> miniatura + ficha')


if __name__ == '__main__':
    main()
