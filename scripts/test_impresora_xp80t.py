#!/usr/bin/env python3
"""Prueba impresión térmica ESC/POS (XPrinter XP-80T). Uso en PC tienda Windows."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description='Prueba ticket térmico 80mm')
    parser.add_argument('--list', action='store_true', help='Listar impresoras Windows')
    parser.add_argument('--nombre', default='', help='Nombre impresora (override .env)')
    parser.add_argument('--diagnostico', action='store_true', help='Solo diagnóstico')
    args = parser.parse_args()

    from services.ticket_impresion_escpos import (
        build_vale_escpos_bytes,
        enviar_raw_escpos,
        listar_impresoras_windows,
    )
    from services.ticket_impresion_service import diagnostico_impresora

    if args.list:
        for p in listar_impresoras_windows():
            print(p)
        return 0

    diag = diagnostico_impresora()
    print('Diagnóstico:', diag)
    if args.diagnostico:
        return 0

    ctx = {
        'venta_id': 99999,
        'empresa': 'Ferreteria Santo Domingo (PRUEBA)',
        'fecha_fmt': '01/06/2026 12:00',
        'prioridad': 'A',
        'vendedor': 'TEST',
        'cliente': 'Cliente prueba impresora',
        'punto_retiro': 'Tienda',
        'es_borrador': False,
        'total': 12345,
        'lineas': [
            {'prefijo': '[T]', 'nombre': 'Producto demo XP-80T', 'cantidad': 2, 'subtotal': 5000},
            {'prefijo': '[B]', 'nombre': 'Otro item bodega', 'cantidad': 1, 'subtotal': 7345},
        ],
        'bloques': [],
    }
    data = build_vale_escpos_bytes(ctx)
    printer = (args.nombre or '').strip() or None
    res = enviar_raw_escpos(data, printer_name=printer)
    print('Resultado:', res)
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
