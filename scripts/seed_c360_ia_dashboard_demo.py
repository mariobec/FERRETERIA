"""
Datos ficticios (1 semana) para probar el dashboard ROI IA · C360.

Crea clientes marcados [demo-c360-ia], filas en c360_llamadas_snapshot_dia y ventas Pagado
con usuario=seed_c360_ia para simular conversiones día a día.

Uso (desde la raíz del proyecto):
  python scripts/seed_c360_ia_dashboard_demo.py
  python scripts/seed_c360_ia_dashboard_demo.py --dias 7
  python scripts/seed_c360_ia_dashboard_demo.py --hasta 2026-05-08
  python scripts/seed_c360_ia_dashboard_demo.py --undo

Requiere la misma DATABASE_URL / .env que la app.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    C360LlamadaSnapshotDia,
    Cliente,
    Venta,
    _asegurar_columnas_customer_360_legacy,
    _asegurar_tabla_c360_llamadas_snapshot,
    app,
    db,
)

MARK = "[demo-c360-ia]"
VENTA_USUARIO = "seed_c360_ia"
N_CLIENTES = 12
RNG_SEED = 20260508


def _rut_demo_desde(cuerpo_base: int, i: int) -> str:
    cuerpo = cuerpo_base + i
    suma = 0
    multiplicador = 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    dv = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return f"{cuerpo}-{dv}"


def _ensure_demo_clientes():
    # Cuerpos 8 dígitos fuera del bloque típico 77.000.xxx del seed masivo DEMO
    base_cuerpo = 77_990_000
    creados = []
    for i in range(1, N_CLIENTES + 1):
        rut = _rut_demo_desde(base_cuerpo, i)
        ex = Cliente.query.filter_by(rut=rut).first()
        if ex:
            creados.append(ex)
            continue
        c = Cliente(
            rut=rut,
            nombre=f"Constructora Demo {i:02d} {MARK}",
            telefono=f"+569900{i:05d}",
            correo=f"demo-c360-ia-{i}@example.invalid",
            comuna="Santiago",
            ciudad="Santiago",
            saldo_deudor=0.0,
            limite_credito=1_500_000.0,
            estado_credito="Activo",
        )
        db.session.add(c)
        db.session.flush()
        creados.append(c)
    db.session.commit()
    return [c.id for c in creados]


def _undo():
    with app.app_context():
        cli_ids = [c.id for c in Cliente.query.filter(Cliente.nombre.contains(MARK)).all()]
        if not cli_ids:
            print("No hay clientes demo para borrar.")
            return
        n_v = Venta.query.filter(Venta.usuario == VENTA_USUARIO).delete(synchronize_session=False)
        n_s = C360LlamadaSnapshotDia.query.filter(C360LlamadaSnapshotDia.cliente_id.in_(cli_ids)).delete(
            synchronize_session=False
        )
        n_c = Cliente.query.filter(Cliente.id.in_(cli_ids)).delete(synchronize_session=False)
        db.session.commit()
        print(f"Eliminado: ventas={n_v}, snapshots={n_s}, clientes={n_c}")


def _seed(hasta: date, dias: int):
    import random

    rng = random.Random(RNG_SEED)
    with app.app_context():
        if not _asegurar_columnas_customer_360_legacy():
            print("WARN: columnas C360 no aseguradas; puede fallar en BD legacy.")
        if not _asegurar_tabla_c360_llamadas_snapshot():
            print("ERROR: no se pudo crear tabla c360_llamadas_snapshot_dia.")
            return 1
        ids = _ensure_demo_clientes()
        etapas = ("INSTALACIONES", "ACABADOS", "TERMINACIONES")
        dias_list = [hasta - timedelta(days=dias - 1 - k) for k in range(dias)]
        total_snaps = 0
        total_ventas = 0
        # Evitar duplicar ventas si se re-ejecuta el script el mismo día
        Venta.query.filter(Venta.usuario == VENTA_USUARIO).delete(synchronize_session=False)
        C360LlamadaSnapshotDia.query.filter(C360LlamadaSnapshotDia.cliente_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.session.commit()

        for idx, fd in enumerate(dias_list):
            # 5..11 recomendaciones según el día (patrón visible en el dashboard)
            n_rec = 5 + (idx % 7)
            orden = list(ids)
            rng.shuffle(orden)
            rec_ids = orden[:n_rec]
            run_at = datetime.combine(fd, datetime.min.time()) + timedelta(hours=3, minutes=17 + idx)

            for j, cid in enumerate(rec_ids):
                cupo = 45_000 + j * 12_000 + idx * 3_000
                score = 91.0 + (j % 5) * 0.7
                et = etapas[j % len(etapas)]
                db.session.add(
                    C360LlamadaSnapshotDia(
                        fecha=fd,
                        cliente_id=cid,
                        etapa_sugerida=et,
                        cupo_sugerido_clp=int(cupo),
                        score_snapshot=round(score, 2),
                        run_at=run_at + timedelta(minutes=j),
                    )
                )
                total_snaps += 1

            # Conversiones: proporción sube hacia fin de semana simulado (últimos días más ventas)
            tasa_dia = 0.18 + 0.085 * idx + rng.uniform(-0.06, 0.07)
            tasa_dia = max(0.0, min(0.78, tasa_dia))
            # Piso entero: algunos días pueden quedar en 0 conversiones
            n_conv = min(n_rec, int(n_rec * tasa_dia + 1e-9))
            conv_ids = rec_ids[:n_conv]
            rng.shuffle(conv_ids)

            for k, cid in enumerate(conv_ids):
                monto = float(35_000 + k * 18_500 + idx * 7_200 + rng.randint(0, 25_000))
                monto = float(int(round(monto / 100.0)) * 100)
                hora = 10 + k + (idx % 3)
                fv = datetime.combine(fd, datetime.min.time()) + timedelta(hours=hora, minutes=20 + k * 7)
                v = Venta(
                    fecha=fv,
                    usuario=VENTA_USUARIO,
                    estado="Pagado",
                    tipo_documento="Boleta",
                    metodo_pago="Efectivo",
                    cliente_id=cid,
                    monto_total=monto,
                    monto_recibido=monto,
                    vuelto=0.0,
                )
                v.desglosar_iva()
                db.session.add(v)
                total_ventas += 1

            db.session.commit()

        print(
            f"OK: {dias} día(s) hasta {hasta.isoformat()} — "
            f"snapshots={total_snaps}, ventas demo={total_ventas}, clientes={len(ids)}."
        )
        print(f"Abrir: /gerencia/c360-ia-dashboard?fecha={dias_list[0].strftime('%Y-%m-%d')} (y días siguientes).")
        return 0


def main():
    p = argparse.ArgumentParser(description="Semana ficticia para dashboard ROI C360")
    p.add_argument("--undo", action="store_true", help="Borra datos insertados por este script")
    p.add_argument("--dias", type=int, default=7, help="Cantidad de días (default 7)")
    p.add_argument("--hasta", type=str, default="", help="Último día inclusive YYYY-MM-DD (default hoy)")
    args = p.parse_args()
    if args.undo:
        _undo()
        return 0
    dias = max(1, min(31, args.dias))
    if args.hasta:
        try:
            hasta = datetime.strptime(args.hasta.strip(), "%Y-%m-%d").date()
        except ValueError:
            print("ERROR: --hasta debe ser YYYY-MM-DD")
            return 1
    else:
        hasta = datetime.now().date()
    return _seed(hasta, dias)


if __name__ == "__main__":
    raise SystemExit(main())
