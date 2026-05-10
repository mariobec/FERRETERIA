"""
Parche de datos DEMO (RUT 77%): alinea crédito con la lógica real del ERP, rellena vacíos
y deja cartera / cuotas / abonos visibles de forma coherente para presentaciones.

Idempotente: puede ejecutarse varias veces; revierte abonos marcados [demo-cartera],
recalcula saldos y regenera cuotas de ventas Demo ERP al crédito.

Uso (desde la raíz del proyecto):
  python scripts/patch_demo_credito_cartera.py

Requiere la columna ventas_cuotas_credito.monto_pagado (ver sql/2026_05_08_cuotas_monto_pagado.sql).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, inspect as sa_inspect, text

from app import (
    PLANES_CUOTA_CREDITO_DIAS,
    AbonoCredito,
    Caja,
    Cliente,
    Usuario,
    Venta,
    VentaCuotaCredito,
    _aplicar_abono_cascada_cuotas_cliente,
    _registrar_cuotas_credito_venta,
    app,
    db,
)

MARKER = '[demo-cartera]'
DEMO_USUARIO = 'Demo ERP'


def _ensure_monto_pagado_column() -> bool:
    try:
        insp = sa_inspect(db.engine)
        tables = set(insp.get_table_names())
        if 'ventas_cuotas_credito' not in tables:
            print('Tabla ventas_cuotas_credito no existe; omita o ejecute sql/2026_05_08_ventas_cuotas_credito.sql')
            return False
        cols = {c['name'] for c in insp.get_columns('ventas_cuotas_credito')}
        if 'monto_pagado' in cols:
            return True
        dn = (db.engine.dialect.name or '').lower()
        if dn == 'postgresql':
            db.session.execute(
                text(
                    'ALTER TABLE ventas_cuotas_credito ADD COLUMN IF NOT EXISTS '
                    'monto_pagado DOUBLE PRECISION NOT NULL DEFAULT 0'
                )
            )
            db.session.execute(
                text("UPDATE ventas_cuotas_credito SET monto_pagado = COALESCE(monto,0) WHERE estado = 'Pagada'")
            )
        else:
            try:
                db.session.execute(
                    text('ALTER TABLE ventas_cuotas_credito ADD COLUMN monto_pagado FLOAT NOT NULL DEFAULT 0')
                )
            except Exception:
                db.session.rollback()
            db.session.execute(
                text("UPDATE ventas_cuotas_credito SET monto_pagado = COALESCE(monto,0) WHERE estado = 'Pagada'")
            )
        db.session.commit()
        return True
    except Exception as ex:
        db.session.rollback()
        print(f'No se pudo asegurar monto_pagado: {ex}')
        return False


def _delete_abonos_demo_marcados() -> int:
    n = AbonoCredito.query.filter(AbonoCredito.comentario.like(f'%{MARKER}%')).delete(synchronize_session=False)
    db.session.commit()
    return int(n or 0)


def _fix_credito_ventas_demo_estado() -> int:
    """En caja real, Credito deja la venta Pendiente; el seed antiguo mezclaba Pagado + Credito."""
    n = (
        Venta.query.filter(
            Venta.usuario == DEMO_USUARIO,
            Venta.metodo_pago == 'Credito',
            Venta.estado == 'Pagado',
        ).update({Venta.estado: 'Pendiente'}, synchronize_session=False)
    )
    db.session.commit()
    return int(n or 0)


def _recalc_saldo_deudor_demo_clientes() -> tuple[int, int]:
    """saldo_deudor = sum(vales Credito Pendiente) - sum(abonos). Solo RUT 77%."""
    clientes = Cliente.query.filter(Cliente.rut.like('77%')).all()
    touched = 0
    for c in clientes:
        cargo = (
            db.session.query(func.coalesce(func.sum(Venta.monto_total), 0.0))
            .filter(
                Venta.cliente_id == c.id,
                Venta.metodo_pago == 'Credito',
                Venta.estado == 'Pendiente',
            )
            .scalar()
            or 0.0
        )
        ab = (
            db.session.query(func.coalesce(func.sum(AbonoCredito.monto_abono), 0.0))
            .filter(AbonoCredito.cliente_id == c.id)
            .scalar()
            or 0.0
        )
        nuevo = max(0.0, float(cargo) - float(ab))
        if abs(float(c.saldo_deudor or 0) - nuevo) > 0.5:
            c.saldo_deudor = nuevo
            touched += 1
    db.session.commit()
    return touched, len(clientes)


def _fill_telefonos_demo() -> int:
    n = 0
    for c in Cliente.query.filter(Cliente.rut.like('77%')).all():
        t = (c.telefono or '').strip().replace(' ', '')
        if len(t) >= 10:
            continue
        c.telefono = f'+569{random.randint(30000000, 98999999)}'
        n += 1
    db.session.commit()
    return n


def _delete_cuotas_demo_credito() -> int:
    ids = [
        row[0]
        for row in Venta.query.filter(Venta.usuario == DEMO_USUARIO, Venta.metodo_pago == 'Credito')
        .with_entities(Venta.id)
        .all()
    ]
    if not ids:
        return 0
    n = VentaCuotaCredito.query.filter(VentaCuotaCredito.venta_id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return int(n or 0)


def _assign_planes_y_cuotas_demo() -> int:
    planes = list(PLANES_CUOTA_CREDITO_DIAS.keys())
    ventas = (
        Venta.query.filter(
            Venta.usuario == DEMO_USUARIO,
            Venta.metodo_pago == 'Credito',
            Venta.estado == 'Pendiente',
            Venta.cliente_id.isnot(None),
            Venta.monto_total >= 8000,
        )
        .order_by(Venta.id.asc())
        .limit(60)
        .all()
    )
    changed = 0
    for i, v in enumerate(ventas):
        plan = planes[i % len(planes)]
        v.credito_plan_codigo = plan
        VentaCuotaCredito.query.filter_by(venta_id=v.id).delete(synchronize_session=False)
        db.session.flush()
        _registrar_cuotas_credito_venta(v, plan, v.fecha)
        changed += 1
    db.session.commit()
    return changed


def _seed_abonos_demo() -> int:
    caja = Caja.query.filter_by(estado='Abierta').order_by(Caja.id.desc()).first()
    if not caja:
        print('Sin caja Abierta: no se insertan abonos demo.')
        return 0
    uid_row = db.session.query(Usuario.id).order_by(Usuario.id.asc()).first()
    uid = int(uid_row[0]) if uid_row else None
    candidatos = [
        c
        for c in Cliente.query.filter(Cliente.rut.like('77%')).all()
        if float(c.saldo_deudor or 0) > 85000
    ]
    random.seed(20260508)
    random.shuffle(candidatos)
    candidatos = candidatos[:14]
    outs = 0
    for c in candidatos:
        saldo = float(c.saldo_deudor or 0)
        m = int(min(max(12000, saldo * 0.2), min(92000, saldo * 0.48)))
        if m < 8000 or saldo <= m:
            continue
        sa = saldo
        ns = saldo - m
        c.saldo_deudor = ns
        lineas = _aplicar_abono_cascada_cuotas_cliente(c, m)
        com = f'Abono demo cobranza {MARKER}'
        if lineas:
            com += ' | Cascada: ' + '; '.join(lineas[:5])
        db.session.add(
            AbonoCredito(
                cliente_id=c.id,
                monto_abono=float(m),
                saldo_anterior=sa,
                nuevo_saldo=ns,
                metodo_pago='Efectivo',
                caja_id=caja.id,
                usuario_id=uid,
                comentario=com,
            )
        )
        outs += 1
    db.session.commit()
    return outs


def main() -> None:
    random.seed(20260508)
    with app.app_context():
        if not _ensure_monto_pagado_column():
            raise SystemExit(1)
        res = {
            'abonos_demo_eliminados': _delete_abonos_demo_marcados(),
            'ventas_credito_pagado_corregidas': _fix_credito_ventas_demo_estado(),
        }
        res['telefonos_rellenados'] = _fill_telefonos_demo()
        res['cuotas_demo_eliminadas'] = _delete_cuotas_demo_credito()
        res['ventas_con_plan_y_cuotas'] = _assign_planes_y_cuotas_demo()
        t, tot = _recalc_saldo_deudor_demo_clientes()
        res['clientes_saldo_recalculado'] = t
        res['clientes_demo_total'] = tot
        res['abonos_demo_insertados'] = _seed_abonos_demo()
        t2, _ = _recalc_saldo_deudor_demo_clientes()
        res['clientes_saldo_recalculado_post_abono'] = t2
        print(res)


if __name__ == '__main__':
    main()
