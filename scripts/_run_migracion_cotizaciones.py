"""Ejecuta la migracion de cotizaciones en la base de datos indicada."""
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

print(f">> Aplicando migracion en {target}: {url.split('@')[-1].split('/')[0]}")

with open("sql/2026_05_08_cotizaciones.sql", "r", encoding="utf-8") as f:
    sql = f.read()

conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute(sql)
conn.commit()

cur.execute("SELECT COUNT(*) FROM cotizaciones")
print("  cotizaciones rows:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM cotizacion_detalles")
print("  cotizacion_detalles rows:", cur.fetchone()[0])
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='ventas' AND column_name='cotizacion_origen_id'"
)
row = cur.fetchone()
print("  ventas.cotizacion_origen_id:", "OK" if row else "FALTANTE")

cur.close()
conn.close()
print(">> Migracion OK")
