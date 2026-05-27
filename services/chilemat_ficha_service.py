"""Ficha Chilemat (imagen + descripción) desde API VTEX — uso ERP, Liz, TV cliente."""
from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any

from services.chilemat_catalogo_service import CHILEMAT_BASE, _fetch_json

_log = logging.getLogger(__name__)


def _asegurar_columnas_ficha() -> None:
    import app as erp
    from sqlalchemy import inspect as sa_inspect

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()
    if erp.app.config.get('_CHILEMAT_FICHA_COLS_OK'):
        return
    db = erp.db
    try:
        insp = sa_inspect(db.engine)
        if 'chilemat_vtex_producto' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('chilemat_vtex_producto')}
        alters: list[str] = []
        if 'imagen_url' not in cols:
            alters.append('ADD COLUMN imagen_url VARCHAR(500)')
        if 'descripcion_web' not in cols:
            alters.append('ADD COLUMN descripcion_web TEXT')
        if 'descripcion_corta' not in cols:
            alters.append('ADD COLUMN descripcion_corta VARCHAR(500)')
        for clause in alters:
            db.session.execute(db.text(f'ALTER TABLE chilemat_vtex_producto {clause}'))
        if alters:
            db.session.commit()
        erp.app.config['_CHILEMAT_FICHA_COLS_OK'] = True
    except Exception as ex:
        db.session.rollback()
        _log.warning('chilemat_ficha columnas: %s', ex)


def _html_a_texto(html: str, *, max_len: int = 4000) -> str:
    if not html:
        return ''
    t = unescape(str(html))
    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.I)
    t = re.sub(r'</p\s*>', '\n', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > max_len:
        t = t[: max_len - 1].rstrip() + '…'
    return t


def extraer_ficha_de_json_vtex(prod: dict) -> dict[str, Any]:
    """Normaliza payload VTEX products/search a ficha usable en UI."""
    if not prod or not isinstance(prod, dict):
        return {}
    vid = str(prod.get('productId') or '').strip()
    nombre = str(prod.get('productName') or prod.get('productTitle') or '').strip()
    link = str(prod.get('link') or '').strip()
    if link and not link.startswith('http'):
        link = f'{CHILEMAT_BASE}{link}' if link.startswith('/') else f'{CHILEMAT_BASE}/{link}'
    ref = str(prod.get('productReference') or prod.get('productReferenceCode') or '').strip()
    desc_html = str(prod.get('description') or '').strip()
    desc_corta = str(prod.get('metaTagDescription') or prod.get('productTitle') or '').strip()
    imagen = ''
    items = prod.get('items') or []
    if items and isinstance(items[0], dict):
        imgs = items[0].get('images') or []
        if imgs and isinstance(imgs[0], dict):
            imagen = str(imgs[0].get('imageUrl') or '').strip()
        if not ref:
            ref = str(items[0].get('referenceId') or items[0].get('ean') or '').strip()
    marca = str(prod.get('brand') or '').strip()
    precio = None
    if items:
        sellers = (items[0].get('sellers') or [])
        if sellers and isinstance(sellers[0], dict):
            offer = sellers[0].get('commertialOffer') or {}
            try:
                precio = float(offer.get('Price') or 0)
            except (TypeError, ValueError):
                precio = None
    return {
        'vtex_product_id': vid,
        'nombre': nombre[:200],
        'product_reference': ref[:80] if ref else '',
        'link': link[:500] if link else '',
        'imagen_url': imagen[:500] if imagen else '',
        'descripcion_html': desc_html[:8000] if desc_html else '',
        'descripcion_texto': _html_a_texto(desc_html) or desc_corta[:500],
        'descripcion_corta': desc_corta[:500],
        'marca': marca[:80],
        'precio_lista': int(round(precio)) if precio and precio > 0 else None,
    }


def fetch_vtex_producto_api(vtex_product_id: str) -> dict[str, Any] | None:
    vid = (vtex_product_id or '').strip()
    if not vid:
        return None
    url = (
        f'{CHILEMAT_BASE}/api/catalog_system/pub/products/search'
        f'?fq=productId:{vid}&_from=0&_to=0'
    )
    try:
        data = _fetch_json(url)
        if isinstance(data, list) and data:
            return extraer_ficha_de_json_vtex(data[0])
    except Exception as ex:
        _log.debug('fetch_vtex_producto_api %s: %s', vid, ex)
    return None


def _persistir_ficha_en_row(row, ficha: dict[str, Any]) -> None:
    if not row or not ficha:
        return
    if ficha.get('imagen_url'):
        row.imagen_url = ficha['imagen_url'][:500]
    if ficha.get('descripcion_html'):
        row.descripcion_web = (ficha.get('descripcion_html') or '')[:8000] or None
    if ficha.get('descripcion_corta'):
        row.descripcion_corta = ficha['descripcion_corta'][:500]
    if ficha.get('nombre') and not row.nombre:
        row.nombre = ficha['nombre'][:200]
    if ficha.get('link') and not row.link:
        row.link = ficha['link'][:500]


def ficha_por_vtex_id(vtex_product_id: str, *, refrescar_api: bool = False) -> dict[str, Any]:
    from app import ChilematVtexProducto, db

    _asegurar_columnas_ficha()
    vid = (vtex_product_id or '').strip()
    if not vid:
        return {'ok': False, 'error': 'vtex_id_requerido'}

    row = ChilematVtexProducto.query.get(vid)
    ficha_api: dict[str, Any] | None = None
    if refrescar_api or not row or not getattr(row, 'imagen_url', None):
        ficha_api = fetch_vtex_producto_api(vid)
        if ficha_api and row:
            _persistir_ficha_en_row(row, ficha_api)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    if row:
        img = (getattr(row, 'imagen_url', None) or '').strip()
        desc_html = (getattr(row, 'descripcion_web', None) or '').strip()
        desc_corta = (getattr(row, 'descripcion_corta', None) or '').strip()
        if img or desc_html or desc_corta:
            return {
                'ok': True,
                'vtex_product_id': vid,
                'nombre': (row.nombre or '').strip(),
                'product_reference': (row.product_reference or '').strip(),
                'link': (row.link or '').strip(),
                'imagen_url': img,
                'descripcion_html': desc_html,
                'descripcion_texto': _html_a_texto(desc_html) or desc_corta,
                'descripcion_corta': desc_corta,
                'marca': (row.brand or '').strip(),
                'precio_lista': int(round(float(row.precio_lista or 0))) if row.precio_lista else None,
                'producto_id': row.producto_id,
                'fuente': 'bd',
            }

    if ficha_api:
        ficha_api['ok'] = True
        ficha_api['fuente'] = 'api'
        return ficha_api

    if row:
        return {
            'ok': True,
            'vtex_product_id': vid,
            'nombre': (row.nombre or '').strip(),
            'link': (row.link or '').strip(),
            'imagen_url': '',
            'descripcion_html': '',
            'descripcion_texto': (row.nombre or '').strip(),
            'producto_id': row.producto_id,
            'fuente': 'bd_parcial',
        }

    return {'ok': False, 'error': 'no_encontrado', 'vtex_product_id': vid}


def ficha_por_producto_erp(producto_id: int, *, refrescar_api: bool = False) -> dict[str, Any]:
    from app import ChilematVtexProducto, Producto

    _asegurar_columnas_ficha()
    try:
        pid = int(producto_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'producto_id_invalido'}

    p = Producto.query.get(pid)
    if not p:
        return {'ok': False, 'error': 'producto_no_encontrado'}

    row = (
        ChilematVtexProducto.query.filter_by(producto_id=pid)
        .order_by(ChilematVtexProducto.synced_at.desc())
        .first()
    )
    if not row:
        ref = (p.codigo_chilemat or '').strip()
        if ref:
            row = ChilematVtexProducto.query.filter_by(product_reference=ref).first()
    if row:
        f = ficha_por_vtex_id(row.vtex_product_id, refrescar_api=refrescar_api)
        if f.get('ok'):
            f['producto_id'] = pid
        return f

    return {
        'ok': True,
        'producto_id': pid,
        'nombre': (p.nombre or '').strip(),
        'imagen_url': (p.imagen_url or '').strip(),
        'descripcion_texto': (p.nombre or '').strip(),
        'fuente': 'erp_solo',
    }


def _normalizar_link_chilemat(link: str) -> str:
    u = (link or '').strip()
    if not u:
        return ''
    if u.startswith('http'):
        return u[:500]
    if u.startswith('/'):
        return f'{CHILEMAT_BASE}{u}'[:500]
    return f'{CHILEMAT_BASE}/{u}'[:500]


def fichas_resumen_carrito_por_productos(producto_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Resumen ligero para carrito POS: imagen, VTEX, link web (sin llamar API por línea)."""
    from app import ChilematVtexProducto, Producto

    _asegurar_columnas_ficha()
    pids: list[int] = []
    for x in producto_ids or []:
        try:
            pids.append(int(x))
        except (TypeError, ValueError):
            continue
    if not pids:
        return {}

    productos = Producto.query.filter(Producto.id.in_(pids)).all()
    chm_by_pid: dict[int, Any] = {}
    for row in ChilematVtexProducto.query.filter(ChilematVtexProducto.producto_id.in_(pids)).all():
        pid = int(row.producto_id or 0)
        if pid and pid not in chm_by_pid:
            chm_by_pid[pid] = row

    refs: list[str] = []
    for p in productos:
        if p.id in chm_by_pid:
            continue
        ref = (p.codigo_chilemat or '').strip()
        if ref:
            refs.append(ref[:80])

    chm_by_ref: dict[str, Any] = {}
    if refs:
        for row in ChilematVtexProducto.query.filter(
            ChilematVtexProducto.product_reference.in_(list(set(refs)))
        ).all():
            ref = (row.product_reference or '').strip()
            if ref and ref not in chm_by_ref:
                chm_by_ref[ref] = row

    out: dict[int, dict[str, Any]] = {}
    for p in productos:
        img = (p.imagen_url or '').strip()
        row = chm_by_pid.get(p.id)
        if not row:
            ref_erp = (p.codigo_chilemat or '').strip()
            if ref_erp:
                row = chm_by_ref.get(ref_erp)
        vtex_id = ''
        link = ''
        ref_web = (p.codigo_chilemat or '').strip()
        if row:
            vtex_id = (row.vtex_product_id or '').strip()
            link = _normalizar_link_chilemat(row.link or '')
            ref_web = (row.product_reference or ref_web or '').strip()
            if not img:
                img = (getattr(row, 'imagen_url', None) or '').strip()
        out[p.id] = {
            'producto_id': p.id,
            'imagen_url': img[:500] if img else '',
            'vtex_product_id': vtex_id,
            'product_reference': ref_web[:80] if ref_web else '',
            'link': link,
            'tiene_ficha': bool(vtex_id or link),
        }
    return out


def imagen_url_para_producto_erp(producto_id: int) -> str:
    """Imagen para TV / Liz: ERP → Chilemat vinculado → vacío."""
    from app import Producto

    try:
        pid = int(producto_id)
    except (TypeError, ValueError):
        return ''

    p = Producto.query.get(pid)
    if not p:
        return ''

    img = (p.imagen_url or '').strip()
    if img:
        return img[:500]

    ficha = ficha_por_producto_erp(pid, refrescar_api=False)
    if ficha.get('ok') and ficha.get('imagen_url'):
        return str(ficha['imagen_url'])[:500]
    return ''


def aplicar_ficha_a_producto_erp(
    producto_id: int,
    *,
    vtex_product_id: str | None = None,
    copiar_imagen: bool = True,
    copiar_descripcion: bool = False,
) -> dict[str, Any]:
    from app import Producto, db

    try:
        pid = int(producto_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'producto_id_invalido'}

    p = Producto.query.get(pid)
    if not p:
        return {'ok': False, 'error': 'producto_no_encontrado'}

    if vtex_product_id:
        ficha = ficha_por_vtex_id(vtex_product_id, refrescar_api=True)
    else:
        ficha = ficha_por_producto_erp(pid, refrescar_api=True)

    if not ficha.get('ok'):
        return ficha

    cambios: list[str] = []
    if copiar_imagen and ficha.get('imagen_url') and not (p.imagen_url or '').strip():
        p.imagen_url = str(ficha['imagen_url'])[:500]
        cambios.append('imagen_url')

    if copiar_descripcion and ficha.get('descripcion_texto'):
        # Sin campo descripcion largo en Producto: guardamos en notas futuras; hoy solo si hay columna
        pass

    ref = (ficha.get('product_reference') or '').strip()
    if ref and not (p.codigo_chilemat or '').strip():
        p.codigo_chilemat = ref[:80]
        cambios.append('codigo_chilemat')

    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return {'ok': False, 'error': str(ex)}

    return {'ok': True, 'producto_id': pid, 'cambios': cambios, 'imagen_url': (p.imagen_url or '').strip()}
