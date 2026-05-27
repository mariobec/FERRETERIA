"""Sincronización catálogo Chilemat (API VTEX pública) → staging + producto_relacion."""
from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

CHILEMAT_BASE = 'https://www.chilemat.com'
_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
_CROSSSELL_TIPOS = (
    ('whoboughtalsobought', 'co_comprado', 0.85),
    ('whosawalsosaw', 'co_visto', 0.65),
)


def _fetch_json(url: str, *, timeout: int = 60, retries: int = 4) -> Any:
    last_ex: Exception | None = None
    for attempt in range(max(1, retries)):
        req = Request(
            url,
            headers={'User-Agent': _USER_AGENT, 'Accept': 'application/json'},
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8', errors='replace'))
        except (HTTPError, URLError, TimeoutError) as ex:
            last_ex = ex
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    if last_ex:
        raise last_ex
    raise RuntimeError('fetch_json sin respuesta')


def _precio_oferta(producto: dict) -> float | None:
    items = producto.get('items') or []
    if not items:
        return None
    sellers = (items[0].get('sellers') or [])
    if not sellers:
        return None
    offer = sellers[0].get('commertialOffer') or {}
    price = offer.get('Price')
    if price is None:
        return None
    try:
        return float(price)
    except (TypeError, ValueError):
        return None


def _ean_item(producto: dict) -> str | None:
    items = producto.get('items') or []
    if not items:
        return None
    ean = (items[0].get('ean') or '').strip()
    return ean[:32] if ean else None


def _categoria_path(producto: dict) -> str | None:
    cats = producto.get('categories') or []
    if not cats:
        return None
    return str(cats[0])[:300]


def fetch_category_tree(depth: int = 3) -> list[dict]:
    data = _fetch_json(f'{CHILEMAT_BASE}/api/catalog_system/pub/category/tree/{depth}')
    return data if isinstance(data, list) else []


def detect_total_productos() -> int:
    """Lee total del catálogo desde cabecera REST-Content-Total."""
    from_i, to_i = 0, 0
    url = f'{CHILEMAT_BASE}/api/catalog_system/pub/products/search?_from={from_i}&_to={to_i}'
    req = Request(
        url,
        headers={'User-Agent': _USER_AGENT, 'Accept': 'application/json'},
    )
    with urlopen(req, timeout=60) as resp:
        hdr = resp.headers.get('REST-Content-Total') or ''
        # formato "0-0/4891"
        if '/' in hdr:
            try:
                return int(hdr.split('/')[-1].strip())
            except ValueError:
                pass
    return 4891


# VTEX limita paginación global (_from > ~2500 → HTTP 400).
VTEX_MAX_GLOBAL_FROM = 2400


def fetch_products_page(from_i: int, to_i: int, *, categoria_vtex_id: int | None = None) -> list[dict]:
    if from_i < 0:
        from_i = 0
    if to_i < from_i:
        to_i = from_i
    if categoria_vtex_id:
        url = (
            f'{CHILEMAT_BASE}/api/catalog_system/pub/products/search'
            f'?fq=C:{int(categoria_vtex_id)}&_from={from_i}&_to={to_i}'
        )
    else:
        url = f'{CHILEMAT_BASE}/api/catalog_system/pub/products/search?_from={from_i}&_to={to_i}'
    try:
        data = _fetch_json(url)
        return data if isinstance(data, list) else []
    except HTTPError as ex:
        if ex.code == 400 and to_i > from_i:
            mid = (from_i + to_i) // 2
            left = fetch_products_page(from_i, mid, categoria_vtex_id=categoria_vtex_id)
            right = fetch_products_page(mid + 1, to_i, categoria_vtex_id=categoria_vtex_id)
            return left + right
        raise


def fetch_crosssell(vtex_product_id: str, endpoint: str) -> list[dict]:
    url = (
        f'{CHILEMAT_BASE}/api/catalog_system/pub/products/crossselling/'
        f'{endpoint}/{vtex_product_id}'
    )
    try:
        data = _fetch_json(url, timeout=30)
        return data if isinstance(data, list) else []
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as ex:
        _log.debug('crosssell %s %s: %s', endpoint, vtex_product_id, ex)
        return []


def sync_categorias(*, commit: bool = True, solo_faltantes: bool = False) -> dict[str, int]:
    from app import ChilematCategoria, db

    _asegurar()
    tree = fetch_category_tree(3)
    creadas = actualizadas = omitidas = 0

    def walk(nodes, parent_id: int | None, depth: int) -> None:
        nonlocal creadas, actualizadas, omitidas
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            vid = int(node.get('id') or 0)
            if not vid:
                continue
            slug_raw = str(node.get('url') or '').strip().strip('/')
            slug = slug_raw.split('/')[-1] if slug_raw else f'cat-{vid}'
            nombre = str(node.get('name') or slug)[:120]
            row = ChilematCategoria.query.filter_by(vtex_id=vid).first()
            if row is None:
                row = ChilematCategoria(vtex_id=vid, slug=slug[:120], nombre=nombre, parent_vtex_id=parent_id, depth=depth)
                db.session.add(row)
                creadas += 1
            elif solo_faltantes:
                omitidas += 1
            else:
                row.slug = slug[:120]
                row.nombre = nombre
                row.parent_vtex_id = parent_id
                row.depth = depth
                actualizadas += 1
            walk(node.get('children') or [], vid, depth + 1)

    walk(tree, None, 0)
    if commit:
        db.session.commit()
    total_bd = ChilematCategoria.query.count()
    return {
        'creadas': creadas,
        'actualizadas': actualizadas,
        'omitidas_existentes': omitidas,
        'nodos': creadas + actualizadas,
        'total_bd': total_bd,
    }


def _db_or_chilemat_ref(ref: str):
    from app import Producto, db

    r = ref.strip()
    return db.or_(
        Producto.codigo_chilemat == r,
        Producto.codigo_interno == r,
        Producto.codigo_interno == f'CHM-{r}',
        Producto.codigo_barra == r,
    )


def _match_producto_erp(product_reference: str | None, ean: str | None):
    from app import Producto

    ref = (product_reference or '').strip()
    if ref:
        p = Producto.query.filter(
            Producto.activo.isnot(False),
            _db_or_chilemat_ref(ref),
        ).first()
        if p:
            return p
    en = (ean or '').strip()
    if en and len(en) >= 8:
        p = Producto.query.filter(
            Producto.activo.isnot(False),
            Producto.codigo_barra == en,
        ).first()
        if p:
            return p
    return None


def _upsert_vtex_producto(prod: dict) -> tuple[bool, bool]:
    """Retorna (insertado_o_actualizado, vinculado_erp)."""
    from datetime import datetime

    from app import ChilematVtexProducto, db
    from services.chilemat_ficha_service import extraer_ficha_de_json_vtex

    vid = str(prod.get('productId') or '').strip()
    if not vid:
        return False, False
    ref = str(prod.get('productReference') or '').strip() or None
    ficha = extraer_ficha_de_json_vtex(prod)
    row = ChilematVtexProducto.query.get(vid)
    if row is None:
        row = ChilematVtexProducto(vtex_product_id=vid)
        db.session.add(row)
    row.product_reference = (ref or '')[:80] or None
    row.nombre = str(prod.get('productName') or ficha.get('nombre') or '')[:200] or None
    row.link = str(prod.get('link') or ficha.get('link') or '')[:500] or None
    row.categoria_path = _categoria_path(prod)
    row.brand = str(prod.get('brand') or ficha.get('marca') or '')[:80] or None
    row.precio_lista = _precio_oferta(prod) or ficha.get('precio_lista')
    row.ean = _ean_item(prod)
    if ficha.get('imagen_url'):
        row.imagen_url = ficha['imagen_url'][:500]
    if ficha.get('descripcion_html'):
        row.descripcion_web = ficha['descripcion_html'][:8000]
    if ficha.get('descripcion_corta'):
        row.descripcion_corta = ficha['descripcion_corta'][:500]
    row.synced_at = datetime.utcnow()
    vinc = False
    p = _match_producto_erp(ref, row.ean)
    if p:
        row.producto_id = p.id
        vinc = True
    return True, vinc


def sync_productos_vtex(
    *,
    max_productos: int | None = None,
    pausa_seg: float = 0.12,
    commit_cada: int = 200,
    solo_faltantes: bool = False,
) -> dict[str, int]:
    from app import ChilematCategoria, ChilematVtexProducto, db

    _asegurar()
    if ChilematCategoria.query.count() == 0:
        sync_categorias()

    existentes: set[str] = {
        r[0]
        for r in db.session.query(ChilematVtexProducto.vtex_product_id).all()
        if r[0]
    }

    nuevos = 0
    actualizados = 0
    omitidos = 0
    vinculados = 0
    page_size = 49
    categorias_procesadas = 0
    total_api: int | None = None
    try:
        total_api = detect_total_productos()
    except Exception as ex:
        _log.debug('detect_total_productos: %s', ex)

    def _procesar_batch(batch: list[dict]) -> None:
        nonlocal nuevos, actualizados, omitidos, vinculados, existentes
        for prod in batch:
            vid = str(prod.get('productId') or '').strip()
            if solo_faltantes and vid and vid in existentes:
                omitidos += 1
                continue
            era_nuevo = bool(vid and vid not in existentes)
            ok, vinc = _upsert_vtex_producto(prod)
            if ok:
                if era_nuevo:
                    nuevos += 1
                else:
                    actualizados += 1
                if vid:
                    existentes.add(vid)
                if vinc:
                    vinculados += 1

    # Fase 1: global — omitir si solo faltantes y ya tenemos el tramo global cubierto
    en_bd_antes = len(existentes)
    skip_global = solo_faltantes and en_bd_antes >= 2000
    if not skip_global:
        from_i = 0
        while from_i < VTEX_MAX_GLOBAL_FROM:
            if max_productos and nuevos >= max_productos:
                break
            to_i = from_i + page_size
            try:
                batch = fetch_products_page(from_i, to_i)
            except Exception as ex:
                _log.warning('Chilemat global %s-%s: %s', from_i, to_i, ex)
                break
            if not batch:
                break
            _procesar_batch(batch)
            if (nuevos + actualizados) % commit_cada < len(batch):
                db.session.commit()
            from_i = to_i + 1
            time.sleep(pausa_seg)

    # Fase 2: por categoría (cubre catálogo completo sin tope _from global)
    cats = ChilematCategoria.query.order_by(ChilematCategoria.depth.desc(), ChilematCategoria.vtex_id).all()
    for cat in cats:
        if max_productos and nuevos >= max_productos:
            break
        categorias_procesadas += 1
        vacias = 0
        from_i = 0
        while vacias < 2:
            if max_productos and nuevos >= max_productos:
                break
            to_i = from_i + page_size
            try:
                batch = fetch_products_page(from_i, to_i, categoria_vtex_id=cat.vtex_id)
            except Exception as ex:
                _log.warning('Chilemat cat %s pag %s-%s: %s', cat.vtex_id, from_i, to_i, ex)
                break
            if not batch:
                vacias += 1
                from_i = to_i + 1
                continue
            vacias = 0
            antes = nuevos
            _procesar_batch(batch)
            if nuevos > antes and categorias_procesadas % 20 == 0:
                _log.info(
                    'Chilemat cat %s (%s): +%s nuevos (total BD ~%s)',
                    cat.vtex_id,
                    cat.nombre,
                    nuevos - antes,
                    len(existentes),
                )
            if (nuevos + actualizados) % commit_cada < len(batch):
                db.session.commit()
            from_i = to_i + 1
            time.sleep(pausa_seg)

    db.session.commit()
    total_rows = ChilematVtexProducto.query.count()
    faltan_api = None
    if total_api is not None:
        faltan_api = max(0, int(total_api) - int(total_rows))
    return {
        'productos_nuevos': nuevos,
        'productos_actualizados': actualizados,
        'productos_omitidos_existentes': omitidos,
        'productos_upsert': nuevos + actualizados,
        'vinculados_erp': vinculados,
        'filas_unicas_vtex': total_rows,
        'total_api_estimado': total_api,
        'faltan_vs_api': faltan_api,
        'categorias_procesadas': categorias_procesadas,
        'fase_global_omitida': skip_global,
        'en_bd_antes': en_bd_antes,
    }


def sync_relaciones_chilemat_vtex(
    *,
    max_anclas: int | None = None,
    pausa_seg: float = 0.15,
    commit_cada: int = 100,
) -> dict[str, int]:
    from app import ChilematVtexProducto

    from services.producto_relacion_service import upsert_relacion

    _asegurar()
    q = ChilematVtexProducto.query.filter(ChilematVtexProducto.producto_id.isnot(None))
    if max_anclas:
        q = q.limit(int(max_anclas))
    anclas = q.all()
    relaciones = 0
    omitidos = 0

    for idx, ancla in enumerate(anclas):
        pid_ancla = int(ancla.producto_id)
        for endpoint, tipo, peso in _CROSSSELL_TIPOS:
            relacionados = fetch_crosssell(ancla.vtex_product_id, endpoint)
            for rel in relacionados:
                vid_rel = str(rel.get('productId') or '').strip()
                if not vid_rel or vid_rel == ancla.vtex_product_id:
                    continue
                row_rel = ChilematVtexProducto.query.get(vid_rel)
                if not row_rel or not row_rel.producto_id:
                    ref = str(rel.get('productReference') or '').strip()
                    if row_rel is None and ref:
                        from app import ChilematVtexProducto as CVP, db

                        row_rel = CVP(
                            vtex_product_id=vid_rel,
                            product_reference=ref[:80],
                            nombre=str(rel.get('productName') or '')[:200],
                        )
                        db.session.add(row_rel)
                        p = _match_producto_erp(ref, None)
                        if p:
                            row_rel.producto_id = p.id
                        db.session.flush()
                    if not row_rel or not row_rel.producto_id:
                        omitidos += 1
                        continue
                pid_rel = int(row_rel.producto_id)
                if pid_ancla == pid_rel:
                    continue
                if upsert_relacion(
                    pid_ancla,
                    pid_rel,
                    tipo=tipo,
                    fuente='chilemat_vtex',
                    peso=peso,
                    commit=False,
                ):
                    relaciones += 1
        if (idx + 1) % commit_cada == 0:
            from app import db

            db.session.commit()
        time.sleep(pausa_seg)

    from app import db

    db.session.commit()
    return {'anclas': len(anclas), 'relaciones_upsert': relaciones, 'omitidos_sin_erp': omitidos}


def sync_relaciones_historico_ventas(
    *,
    dias: int = 420,
    min_coocurrencias: int = 3,
    max_pares: int = 5000,
) -> dict[str, int]:
    from collections import defaultdict
    from datetime import datetime, timedelta

    from app import DetalleVenta, Venta, db
    from services.producto_relacion_service import upsert_relacion

    _asegurar()
    desde = datetime.utcnow() - timedelta(days=max(30, int(dias)))
    q = (
        db.session.query(DetalleVenta.id_venta, DetalleVenta.id_producto)
        .join(Venta, Venta.id == DetalleVenta.id_venta)
        .filter(
            Venta.fecha >= desde,
            DetalleVenta.id_producto.isnot(None),
            db.or_(Venta.estado.is_(None), Venta.estado != 'Anulada'),
        )
    )
    por_venta: dict[int, set[int]] = defaultdict(set)
    for vid, pid in q.all():
        if pid:
            por_venta[int(vid)].add(int(pid))

    pares: dict[tuple[int, int], int] = defaultdict(int)
    for pids in por_venta.values():
        lst = sorted(pids)
        for i, a in enumerate(lst):
            for b in lst[i + 1 :]:
                pares[(a, b)] += 1

    relaciones = 0
    for (a, b), n in sorted(pares.items(), key=lambda x: -x[1])[:max_pares]:
        if n < min_coocurrencias:
            continue
        peso = min(1.0, 0.5 + (n / 20.0))
        for origen, destino in ((a, b), (b, a)):
            if upsert_relacion(
                origen,
                destino,
                tipo='co_comprado',
                fuente='historico_sd',
                peso=peso,
                commit=False,
            ):
                relaciones += 1
    db.session.commit()
    return {'pares_calificados': relaciones, 'ventas_analizadas': len(por_venta)}


def sync_all(
    *,
    productos: bool = True,
    categorias: bool = True,
    relaciones_vtex: bool = True,
    relaciones_historico: bool = True,
    max_productos: int | None = None,
    max_anclas_vtex: int | None = None,
    solo_faltantes: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {'ok': True}
    if categorias:
        out['categorias'] = sync_categorias(solo_faltantes=solo_faltantes)
    if productos:
        out['productos'] = sync_productos_vtex(
            max_productos=max_productos,
            solo_faltantes=solo_faltantes,
        )
    if relaciones_vtex:
        out['relaciones_vtex'] = sync_relaciones_chilemat_vtex(max_anclas=max_anclas_vtex)
    if relaciones_historico:
        out['relaciones_historico'] = sync_relaciones_historico_ventas()
    return out


def _asegurar() -> None:
    import app as erp

    fn = getattr(erp, '_asegurar_tablas_chilemat_relaciones', None)
    if callable(fn):
        fn()
    try:
        from services.chilemat_ficha_service import _asegurar_columnas_ficha

        _asegurar_columnas_ficha()
    except Exception:
        pass
