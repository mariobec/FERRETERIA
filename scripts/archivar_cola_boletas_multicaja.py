#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marca boletas PENDIENTE_ENVIO como EXTERNO_MULTICAJA (no se envían desde LhexIA)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import app as m
    from services.facturacion_electronica_service import (
        DTE_ESTADO_EXTERNO_BOLETA,
        DTE_ESTADO_PENDIENTE_ENVIO,
        DTE_TIPO_BOLETA_AFECTA,
        marcar_venta_boleta_sin_fe_erp,
    )

    m._load_env_archivos(force_local_overwrite=True)
    with m.app.app_context():
        m._asegurar_tabla_cafs_y_columnas_ventas_fe()
        q = m.Venta.query.filter(
            m.Venta.dte_tipo == DTE_TIPO_BOLETA_AFECTA,
            m.Venta.dte_estado == DTE_ESTADO_PENDIENTE_ENVIO,
        )
        rows = q.all()
        for v in rows:
            marcar_venta_boleta_sin_fe_erp(v)
        m.db.session.commit()
        print(f'Archivadas {len(rows)} venta(s) boleta -> {DTE_ESTADO_EXTERNO_BOLETA}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
