"""Resetea las secuencias de auto-incremento en PostgreSQL para todas las tablas
con columna `id`. Evita el error de unique violation en caja_pkey, ventas_pkey, etc.
cuando se han insertado registros manualmente o restaurado un dump.

Uso:
    python scripts/_reset_secuencias.py local
    python scripts/_reset_secuencias.py neon
"""
import sys
import psycopg2


def _leer_env_local():
    env = {}
    try:
        with open(".env.local", "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, _, v = ln.partition("=")
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


_env = _leer_env_local()
target = sys.argv[1] if len(sys.argv) > 1 else "local"
url = _env["DATABASE_URL"] if target == "local" else _env["NEON_DATABASE_URL"]

print(f">> Reseteando secuencias en {target}: {url.split('@')[-1].split('/')[0]}")

conn = psycopg2.connect(url)
cur = conn.cursor()

# Detectar tablas del schema 'public' que tengan columna 'id'.
cur.execute(
    """
    SELECT table_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = 'id'
    ORDER BY table_name;
    """
)
tablas_con_id = [r[0] for r in cur.fetchall()]

ajustadas = 0
saltadas = 0
for tabla in tablas_con_id:
    # Resolver la secuencia (si la columna no es serial/identity, devuelve None)
    cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (tabla,))
    seq = cur.fetchone()[0]
    if not seq:
        saltadas += 1
        continue
    cur.execute(f'SELECT COALESCE(MAX(id), 0) FROM "{tabla}"')
    max_id = cur.fetchone()[0] or 0
    nuevo = max(max_id, 1)
    cur.execute("SELECT setval(%s, %s, true)", (seq, nuevo))
    actual = cur.fetchone()[0]
    print(f"  {tabla:<35s} max(id)={max_id:>6} -> setval -> {actual}")
    ajustadas += 1

if saltadas:
    print(f"  ({saltadas} tablas con id sin secuencia: ignoradas)")

conn.commit()
cur.close()
conn.close()
print(f">> OK: {ajustadas} secuencias ajustadas.")
