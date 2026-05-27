"""Persistencia Postgres — escaneos Radar Precios."""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

_TABLES_OK = False


def asegurar_tablas(app) -> bool:
    global _TABLES_OK
    if _TABLES_OK:
        return True
    db = app.db
    try:
        db.session.execute(
            db.text(
                """
                CREATE TABLE IF NOT EXISTS radar_precios_escaneo (
                    id VARCHAR(36) PRIMARY KEY,
                    url TEXT NOT NULL,
                    url_final TEXT,
                    proveedor_id INTEGER,
                    usuario VARCHAR(120),
                    status VARCHAR(32) NOT NULL DEFAULT 'en_proceso',
                    parser VARCHAR(64),
                    titulo VARCHAR(300),
                    total INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ
                )
                """
            )
        )
        db.session.execute(
            db.text(
                """
                CREATE TABLE IF NOT EXISTS radar_precios_linea (
                    id VARCHAR(36) PRIMARY KEY,
                    escaneo_id VARCHAR(36) NOT NULL REFERENCES radar_precios_escaneo(id) ON DELETE CASCADE,
                    indice INTEGER NOT NULL DEFAULT 0,
                    sku_proveedor VARCHAR(64),
                    descripcion TEXT,
                    precio_lista_clp INTEGER NOT NULL DEFAULT 0,
                    producto_id INTEGER,
                    codigo_erp VARCHAR(64),
                    costo_actual DOUBLE PRECISION,
                    venta_actual DOUBLE PRECISION,
                    delta_pct DOUBLE PRECISION,
                    estado VARCHAR(32),
                    confianza DOUBLE PRECISION,
                    metodo VARCHAR(64),
                    aplicado BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        db.session.execute(
            db.text(
                'CREATE INDEX IF NOT EXISTS ix_radar_linea_escaneo ON radar_precios_linea (escaneo_id)'
            )
        )
        db.session.commit()
        _TABLES_OK = True
        return True
    except Exception as ex:
        db.session.rollback()
        _log.warning('radar_precios_db: no se pudieron crear tablas: %s', ex)
        return False


def crear_escaneo_db(
    app,
    *,
    job_id: str,
    url: str,
    proveedor_id: int | None,
    usuario: str,
) -> None:
    if not asegurar_tablas(app):
        return
    db = app.db
    db.session.execute(
        db.text(
            """
            INSERT INTO radar_precios_escaneo (id, url, proveedor_id, usuario, status)
            VALUES (:id, :url, :pid, :usuario, 'en_proceso')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            'id': job_id,
            'url': url,
            'pid': proveedor_id,
            'usuario': (usuario or '')[:120],
        },
    )
    db.session.commit()


def actualizar_escaneo_db(app, job_id: str, **campos) -> None:
    if not asegurar_tablas(app):
        return
    permitidos = {
        'url_final', 'status', 'parser', 'titulo', 'total', 'error', 'finished_at'
    }
    sets = []
    params: dict[str, Any] = {'id': job_id}
    for k, v in campos.items():
        if k not in permitidos:
            continue
        sets.append(f'{k} = :{k}')
        params[k] = v
    if not sets:
        return
    db = app.db
    db.session.execute(
        db.text(f'UPDATE radar_precios_escaneo SET {", ".join(sets)} WHERE id = :id'),
        params,
    )
    db.session.commit()


def insertar_linea_db(app, job_id: str, indice: int, linea: dict[str, Any]) -> None:
    if not asegurar_tablas(app):
        return
    db = app.db
    db.session.execute(
        db.text(
            """
            INSERT INTO radar_precios_linea (
                id, escaneo_id, indice, sku_proveedor, descripcion, precio_lista_clp,
                producto_id, codigo_erp, costo_actual, venta_actual, delta_pct,
                estado, confianza, metodo, aplicado
            ) VALUES (
                :id, :escaneo_id, :indice, :sku, :desc, :precio,
                :producto_id, :codigo_erp, :costo, :venta, :delta,
                :estado, :confianza, :metodo, :aplicado
            )
            ON CONFLICT (id) DO UPDATE SET
                sku_proveedor = EXCLUDED.sku_proveedor,
                descripcion = EXCLUDED.descripcion,
                precio_lista_clp = EXCLUDED.precio_lista_clp,
                producto_id = EXCLUDED.producto_id,
                codigo_erp = EXCLUDED.codigo_erp,
                costo_actual = EXCLUDED.costo_actual,
                venta_actual = EXCLUDED.venta_actual,
                delta_pct = EXCLUDED.delta_pct,
                estado = EXCLUDED.estado,
                confianza = EXCLUDED.confianza,
                metodo = EXCLUDED.metodo
            """
        ),
        {
            'id': linea['id'],
            'escaneo_id': job_id,
            'indice': indice,
            'sku': (linea.get('sku_proveedor') or '')[:64],
            'desc': (linea.get('descripcion') or '')[:2000],
            'precio': int(linea.get('precio_lista_clp') or 0),
            'producto_id': linea.get('producto_id'),
            'codigo_erp': (linea.get('codigo_erp') or '')[:64],
            'costo': linea.get('costo_actual'),
            'venta': linea.get('venta_actual'),
            'delta': linea.get('delta_pct'),
            'estado': (linea.get('estado') or '')[:32],
            'confianza': linea.get('confianza'),
            'metodo': (linea.get('metodo') or '')[:64],
            'aplicado': bool(linea.get('aplicado')),
        },
    )
    db.session.commit()


def marcar_linea_aplicada_db(app, linea_id: str) -> None:
    if not asegurar_tablas(app):
        return
    db = app.db
    db.session.execute(
        db.text(
            "UPDATE radar_precios_linea SET aplicado = TRUE, estado = 'aplicado' WHERE id = :id"
        ),
        {'id': linea_id},
    )
    db.session.commit()


def historial_escaneos_db(app, limit: int = 15) -> list[dict[str, Any]]:
    if not asegurar_tablas(app):
        return []
    db = app.db
    rows = db.session.execute(
        db.text(
            """
            SELECT e.id, e.url, e.url_final, e.titulo, e.total, e.parser, e.status,
                   e.finished_at, e.created_at,
                   (SELECT COUNT(*) FROM radar_precios_linea l WHERE l.escaneo_id = e.id AND l.producto_id IS NOT NULL) AS mapeados
            FROM radar_precios_escaneo e
            ORDER BY COALESCE(e.finished_at, e.created_at) DESC
            LIMIT :lim
            """
        ),
        {'lim': max(1, min(limit, 50))},
    ).mappings().all()
    out = []
    for r in rows:
        out.append({
            'job_id': r['id'],
            'url': r['url'],
            'url_final': r['url_final'],
            'titulo': r['titulo'],
            'total': r['total'] or 0,
            'parser': r['parser'] or '',
            'status': r['status'],
            'finished_at': r['finished_at'].isoformat() if r['finished_at'] else None,
            'mapeados': int(r['mapeados'] or 0),
        })
    return out
