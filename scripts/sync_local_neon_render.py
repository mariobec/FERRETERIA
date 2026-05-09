"""
Sincroniza base local -> Neon/Render para mantener ambas iguales.

Pasos:
1) Aplica migraciones SQL en local y en Neon.
2) Clona todas las tablas public comunes desde local hacia Neon.
3) Muestra conteos de verificación en tablas clave.

Uso:
  python scripts/sync_local_neon_render.py
"""

from __future__ import annotations

from pathlib import Path
import importlib.util
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
    "productos",
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
        env[k.strip()] = v.strip()
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
        print(f"migracion_ok:{tag}")
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
            replica_role_set = False
            try:
                cur.execute("SET session_replication_role = replica;")
                replica_role_set = True
            except Exception as ex:
                dst.rollback()
                print(f"warn: replica_role_no_aplicado:{ex}")
            trunc = "TRUNCATE TABLE {} RESTART IDENTITY CASCADE;".format(
                ", ".join(f'"{t}"' for t in tables)
            )
            cur.execute(trunc)

        for t in tables:
            rows, _ = _copy_table_custom(src, dst, t)
            print(f"sync:{t}:{rows}")

        _restaurar_relaciones_cotizacion_venta(src, dst)

        with dst.cursor() as cur:
            try:
                cur.execute("SET session_replication_role = origin;")
            except Exception:
                pass
        dst.commit()
        src.commit()
        print("sync_completed")
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


def print_checks(local_url: str, neon_url: str) -> None:
    lc = psycopg2.connect(local_url)
    nc = psycopg2.connect(neon_url)
    try:
        lcur = lc.cursor()
        ncur = nc.cursor()
        print("check_table|local|neon")
        for t in TABLAS_CHECK:
            lcur.execute(f'SELECT COUNT(*) FROM "{t}"')
            lv = int(lcur.fetchone()[0])
            ncur.execute(f'SELECT COUNT(*) FROM "{t}"')
            nv = int(ncur.fetchone()[0])
            print(f"{t}|{lv}|{nv}")
        lcur.close()
        ncur.close()
    finally:
        lc.close()
        nc.close()


def main() -> None:
    env = leer_env_local()
    local_url = env.get("DATABASE_URL")
    neon_url = env.get("NEON_DATABASE_URL")
    if not local_url or not neon_url:
        raise RuntimeError("Faltan DATABASE_URL o NEON_DATABASE_URL en .env.local")

    aplicar_migraciones(local_url, "local")
    aplicar_migraciones(neon_url, "neon")
    sync_data(local_url, neon_url)
    print_checks(local_url, neon_url)


if __name__ == "__main__":
    main()

