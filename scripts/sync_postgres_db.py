import argparse
from typing import List, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


def list_tables(conn) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        return [r[0] for r in cur.fetchall()]


def list_columns(conn, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return [r[0] for r in cur.fetchall()]


def copy_table(source_conn, target_conn, table_name: str) -> Tuple[int, int]:
    columns = list_columns(source_conn, table_name)
    if not columns:
        return 0, 0

    select_sql = sql.SQL("SELECT {} FROM {}").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        sql.Identifier(table_name),
    )
    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
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


def main():
    parser = argparse.ArgumentParser(description="Sync Postgres source DB into target DB.")
    parser.add_argument("--source", required=True, help="Source PostgreSQL URL")
    parser.add_argument("--target", required=True, help="Target PostgreSQL URL")
    args = parser.parse_args()

    src = psycopg2.connect(args.source)
    dst = psycopg2.connect(args.target)
    src.autocommit = False
    dst.autocommit = False

    try:
        src_tables = list_tables(src)
        dst_tables = set(list_tables(dst))
        tables = [t for t in src_tables if t in dst_tables]
        if not tables:
            raise RuntimeError("No matching public tables found between source and target.")

        with dst.cursor() as cur:
            cur.execute("SET session_replication_role = replica;")
            truncate_stmt = "TRUNCATE TABLE {} RESTART IDENTITY CASCADE;".format(
                ", ".join(f'"{t}"' for t in tables)
            )
            cur.execute(truncate_stmt)

        print(f"Tables to sync: {len(tables)}")
        for t in tables:
            rows, batches = copy_table(src, dst, t)
            print(f"- {t}: {rows} rows ({batches} batches)")

        with dst.cursor() as cur:
            cur.execute("SET session_replication_role = origin;")
        dst.commit()
        src.commit()
        print("Sync completed successfully.")
    except Exception:
        dst.rollback()
        src.rollback()
        raise
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
