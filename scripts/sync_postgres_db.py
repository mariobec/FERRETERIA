import argparse
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

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


def list_fk_dependencies(conn, table_names: List[str]) -> Dict[str, Set[str]]:
    """Map table -> referenced tables within the selected set."""
    deps: Dict[str, Set[str]] = {t: set() for t in table_names}
    if not table_names:
        return deps
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tc.table_name AS table_name,
                ccu.table_name AS referenced_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            """
        )
        valid = set(table_names)
        for table_name, referenced_table in cur.fetchall():
            if table_name in valid and referenced_table in valid and table_name != referenced_table:
                deps[table_name].add(referenced_table)
    return deps


def sort_tables_by_dependencies(table_names: List[str], deps: Dict[str, Set[str]]) -> List[str]:
    """Topological order so parent tables load before children."""
    indegree: Dict[str, int] = {t: 0 for t in table_names}
    reverse_adj: Dict[str, Set[str]] = defaultdict(set)
    for table, refs in deps.items():
        indegree[table] += len(refs)
        for ref in refs:
            reverse_adj[ref].add(table)

    queue = deque(sorted([t for t, d in indegree.items() if d == 0]))
    ordered: List[str] = []
    while queue:
        cur = queue.popleft()
        ordered.append(cur)
        for child in sorted(reverse_adj.get(cur, set())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered) == len(table_names):
        return ordered

    # If there are cycles, keep deterministic order and append unresolved tables.
    unresolved = sorted([t for t in table_names if t not in set(ordered)])
    print(f"Warn: dependency cycle detected on {len(unresolved)} table(s), appending unresolved tables.")
    return ordered + unresolved


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
        deps = list_fk_dependencies(src, tables)
        tables = sort_tables_by_dependencies(tables, deps)

        replica_role_set = False
        with dst.cursor() as cur:
            try:
                cur.execute("SET session_replication_role = replica;")
                replica_role_set = True
            except Exception as ex:
                dst.rollback()
                print(f"Warn: session_replication_role not applied ({ex}). Continuing without replica mode.")
            truncate_stmt = "TRUNCATE TABLE {} RESTART IDENTITY CASCADE;".format(
                ", ".join(f'"{t}"' for t in tables)
            )
            cur.execute(truncate_stmt)

        print(f"Tables to sync: {len(tables)}")
        for t in tables:
            rows, batches = copy_table(src, dst, t)
            print(f"- {t}: {rows} rows ({batches} batches)")

        if replica_role_set:
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
