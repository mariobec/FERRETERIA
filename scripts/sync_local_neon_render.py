"""
Neon igual que Postgres local (y Render igual que local si usa esa Neon).

Render no guarda otra base: si en Render la variable DATABASE_URL es la misma Neon que
NEON_DATABASE_URL aquí, al copiar local -> Neon Render muestra los mismos datos que tu PC.

.env.local en la raiz del repo:
  DATABASE_URL        = Postgres en tu PC (origen)
  NEON_DATABASE_URL   = Neon directo (sin "-pooler" en el host) recomendado para este script.

Pasos del script:
  1) Migraciones SQL en local y en Neon
  2) TRUNCATE tablas comunes en Neon y copia desde local
  3) Conteos de verificacion

Uso:
  cd <raiz_repo>
  python scripts/sync_local_neon_render.py
  python scripts/sync_local_neon_render.py --verify-only

Opcion --verify-only: solo compara conteos (local vs Neon) sin copiar ni migrar.

Cuidado: pisa datos en Neon en esas tablas. Backup antes si dudas.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import sys
import time

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

_SYNC_PATH = Path(__file__).with_name("sync_postgres_db.py")
_SPEC = importlib.util.spec_from_file_location("sync_postgres_db", _SYNC_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("No se pudo cargar sync_postgres_db.py")
sync = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync)


MIGRACIONES = [
    "sql/2026_05_07_neon_postgres_migracion_completa.sql",
    "sql/2026_05_08_cotizaciones.sql",
]

TABLAS_CHECK = [
    "productos",
    "clientes",
    "ventas",
    "detalle_ventas",
    "cotizaciones",
    "cotizacion_detalles",
    "ordenes_compra",
    "detalle_orden_compra",
    "recepciones_compra",
]

PARENT_CHILD_ORDER = [
    ("ventas", "detalle_ventas"),
    ("ventas", "cambios_operacion"),
    ("cambios_operacion", "cambios_detalle"),
    ("cotizaciones", "cotizacion_detalles"),
    ("ordenes_compra", "detalle_orden_compra"),
    ("recepciones_compra", "detalle_recepcion"),
]

ORDER_PREFIX = [
    "almacenes",
    "roles",
    "permisos",
    "rol_permisos",
    "usuarios",
    "clientes",
    "caja",
    "proveedores",
    "catalogo_categorias",
    "catalogo_subcategorias",
    "chilemat_categoria",
    "productos",
    "producto_codigo_proveedor",
    "producto_relacion",
    "stock_por_almacen",
    "movimientos_inventario",
    "ventas",
    "detalle_ventas",
    "cambios_operacion",
    "cambios_detalle",
]

COPY_EXCLUDE_COLS = {
    "ventas": {"cotizacion_origen_id"},
    "cotizaciones": {"venta_id"},
}


def leer_env_local() -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(".env.local")
    if not p.exists():
        return env
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        env[k] = v
    return env


def aplicar_migraciones(url: str, tag: str) -> None:
    conn = psycopg2.connect(url)
    try:
        cur = conn.cursor()
        for f in MIGRACIONES:
            sql = Path(f).read_text(encoding="utf-8")
            cur.execute(sql)
        conn.commit()
        cur.close()
        print(f"migracion_ok:{tag}", flush=True)
    finally:
        conn.close()


def sync_data(src_url: str, dst_url: str) -> None:
    src = psycopg2.connect(src_url)
    dst = psycopg2.connect(dst_url)
    src.autocommit = False
    dst.autocommit = False
    try:
        src_tables = sync.list_tables(src)
        dst_tables = set(sync.list_tables(dst))
        tables = [t for t in src_tables if t in dst_tables]
        deps = sync.list_fk_dependencies(src, tables)
        tables = sync.sort_tables_by_dependencies(tables, deps)
        tables = _forzar_orden_parent_child(tables)

        with dst.cursor() as cur:
            try:
                cur.execute("SET session_replication_role = replica;")
            except Exception as ex:
                dst.rollback()
                print(f"warn: replica_role_no_aplicado:{ex}", flush=True)
            trunc = "TRUNCATE TABLE {} RESTART IDENTITY CASCADE;".format(
                ", ".join(f'"{t}"' for t in tables)
            )
            cur.execute(trunc)
        dst.commit()

        for t in tables:
            rows, _ = _copy_table_custom(src, dst, t)
            dst.commit()
            print(f"sync:{t}:{rows}", flush=True)

        _restaurar_relaciones_cotizacion_venta(src, dst)
        dst.commit()
        src.commit()
        print("sync_completed", flush=True)
    finally:
        src.close()
        dst.close()


def _forzar_orden_parent_child(tables: list[str]) -> list[str]:
    ordered = []
    ts = list(tables)
    for t in ORDER_PREFIX:
        if t in ts and t not in ordered:
            ordered.append(t)
    for t in ts:
        if t not in ordered:
            ordered.append(t)
    for parent, child in PARENT_CHILD_ORDER:
        if parent not in ordered or child not in ordered:
            continue
        ip = ordered.index(parent)
        ic = ordered.index(child)
        if ip > ic:
            ordered.pop(ip)
            ic2 = ordered.index(child)
            ordered.insert(ic2, parent)
    return ordered


def _copy_table_custom(source_conn, target_conn, table_name: str) -> tuple[int, int]:
    columns = sync.list_columns(source_conn, table_name)
    if not columns:
        return 0, 0
    excl = COPY_EXCLUDE_COLS.get(table_name, set())
    cols = [c for c in columns if c not in excl]
    if not cols:
        return 0, 0

    select_sql = sql.SQL("SELECT {} FROM {}").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        sql.Identifier(table_name),
    )
    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
    )

    total = 0
    batches = 0
    with source_conn.cursor(name=f"c_{table_name}") as src_cur, target_conn.cursor() as dst_cur:
        src_cur.itersize = 2000
        src_cur.execute(select_sql)
        while True:
            rows = src_cur.fetchmany(2000)
            if not rows:
                break
            execute_values(dst_cur, insert_sql.as_string(target_conn), rows, page_size=2000)
            total += len(rows)
            batches += 1
    return total, batches


def _restaurar_relaciones_cotizacion_venta(source_conn, target_conn) -> None:
    with source_conn.cursor() as s_cur, target_conn.cursor() as t_cur:
        s_cur.execute(
            "SELECT id, cotizacion_origen_id FROM ventas WHERE cotizacion_origen_id IS NOT NULL"
        )
        ventas_links = s_cur.fetchall()
        if ventas_links:
            execute_values(
                t_cur,
                """
                UPDATE ventas AS v
                SET cotizacion_origen_id = x.cotizacion_origen_id
                FROM (VALUES %s) AS x(id, cotizacion_origen_id)
                WHERE v.id = x.id
                """,
                ventas_links,
                page_size=2000,
            )

        s_cur.execute("SELECT id, venta_id FROM cotizaciones WHERE venta_id IS NOT NULL")
        cot_links = s_cur.fetchall()
        if cot_links:
            execute_values(
                t_cur,
                """
                UPDATE cotizaciones AS c
                SET venta_id = x.venta_id
                FROM (VALUES %s) AS x(id, venta_id)
                WHERE c.id = x.id
                """,
                cot_links,
                page_size=2000,
            )


def conteos_check(local_url: str, neon_url: str) -> list[tuple[str, int, int]]:
    """Devuelve (tabla, count_local, count_neon) para cada entrada en TABLAS_CHECK."""
    lc = psycopg2.connect(local_url)
    nc = psycopg2.connect(neon_url)
    out: list[tuple[str, int, int]] = []
    try:
        lcur = lc.cursor()
        ncur = nc.cursor()
        for t in TABLAS_CHECK:
            q = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(t))
            lcur.execute(q)
            lv = int(lcur.fetchone()[0])
            ncur.execute(q)
            nv = int(ncur.fetchone()[0])
            out.append((t, lv, nv))
        lcur.close()
        ncur.close()
    finally:
        lc.close()
        nc.close()
    return out


def print_checks(filas: list[tuple[str, int, int]]) -> None:
    print("check_table|local|neon|ok", flush=True)
    for t, lv, nv in filas:
        ok = "si" if lv == nv else "NO"
        print(f"{t}|{lv}|{nv}|{ok}", flush=True)


def verificar_conteos(filas: list[tuple[str, int, int]]) -> bool:
    """
    True si local y Neon tienen los mismos conteos en TABLAS_CHECK.
    Imprime resumen en consola.
    """
    mal = [(t, lv, nv) for t, lv, nv in filas if lv != nv]
    if not mal:
        print("verificacion_ok: todos los conteos coinciden.", flush=True)
        return True
    print("verificacion_falla: tablas con conteo distinto (local vs neon):", flush=True)
    for t, lv, nv in mal:
        print(f"  {t}: {lv} != {nv}", flush=True)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Sincronizar Postgres local -> Neon o solo verificar conteos.")
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="Solo comparar conteos entre DATABASE_URL y NEON_DATABASE_URL (.env.local).",
    )
    args = ap.parse_args()

    env = leer_env_local()
    local_url = env.get("DATABASE_URL")
    neon_url = env.get("NEON_DATABASE_URL")
    if not local_url or not neon_url:
        raise RuntimeError("Faltan DATABASE_URL o NEON_DATABASE_URL en .env.local")

    if args.verify_only:
        filas = conteos_check(local_url, neon_url)
        print_checks(filas)
        if not verificar_conteos(filas):
            sys.exit(1)
        return

    aplicar_migraciones(local_url, "local")
    print(
        "migraciones: conectando a Neon y aplicando SQL (si se queda aqui, revisar red, URL o bloqueos en Neon)...",
        flush=True,
    )
    aplicar_migraciones(neon_url, "neon")
    print("sync_data: copiando tablas local -> Neon (puede tardar varios minutos)...", flush=True)
    sync_data(local_url, neon_url)
    # Breve pausa: Neon pooler/replica puede retrasar lecturas justo tras el commit masivo.
    print("verificacion: comparando conteos local vs Neon...", flush=True)
    time.sleep(5)
    filas = conteos_check(local_url, neon_url)
    print_checks(filas)
    if not verificar_conteos(filas):
        print(
            "Sugerencia: pausar Render (o cualquier app que use la misma Neon) durante el sync; "
            "luego volver a ejecutar este script. Si persiste, confirmar en el panel de Neon "
            "que NEON_DATABASE_URL apunta al branch correcto.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

