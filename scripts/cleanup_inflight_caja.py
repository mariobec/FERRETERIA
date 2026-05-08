import argparse

import psycopg2


def main():
    parser = argparse.ArgumentParser(description="Anula documentos en vuelo de la caja abierta.")
    parser.add_argument("--db-url", required=True, help="PostgreSQL URL")
    args = parser.parse_args()

    conn = psycopg2.connect(args.db_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM caja WHERE estado='Abierta' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                print("No hay caja abierta.")
                conn.rollback()
                return
            caja_id = row[0]
            print(f"caja_abierta={caja_id}")

            cur.execute(
                "SELECT COUNT(*) FROM ventas WHERE caja_id=%s AND estado='Pendiente' AND (metodo_pago IS NULL OR metodo_pago='')",
                (caja_id,),
            )
            pend = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM ventas WHERE caja_id=%s AND estado='Abierta'",
                (caja_id,),
            )
            abiertas = cur.fetchone()[0]
            print(f"antes_pend_sin_metodo={pend}")
            print(f"antes_abiertas={abiertas}")

            cur.execute(
                "UPDATE ventas SET estado='Anulada' WHERE caja_id=%s AND estado='Pendiente' AND (metodo_pago IS NULL OR metodo_pago='')",
                (caja_id,),
            )
            cur.execute(
                "UPDATE ventas SET estado='Anulada' WHERE caja_id=%s AND estado='Abierta'",
                (caja_id,),
            )

            cur.execute(
                "SELECT COUNT(*) FROM ventas WHERE caja_id=%s AND estado='Pendiente' AND (metodo_pago IS NULL OR metodo_pago='')",
                (caja_id,),
            )
            print(f"despues_pend_sin_metodo={cur.fetchone()[0]}")
            cur.execute(
                "SELECT COUNT(*) FROM ventas WHERE caja_id=%s AND estado='Abierta'",
                (caja_id,),
            )
            print(f"despues_abiertas={cur.fetchone()[0]}")

        conn.commit()
        print("Cleanup completado.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
