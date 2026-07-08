#!/usr/bin/env python3
"""Descubre Zebra en LAN (MAC OUI) y prueba ZPL por TCP puerto 9100."""
from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ZEBRA_OUI = ('b0-fc-36', '00-07-4d', '00-16-25', 'ac-3f-a4')
ZPL_TEST = (
    b"^XA\n^FO20,20^A0N,36,36^FDPRUEBA ZEBRA RJ45^FS\n"
    b"^FO20,70^BY2^BCN,60,Y,N,N^FD123456789012^FS\n^XZ\n"
)


def _arp_hosts() -> list[tuple[str, str]]:
    out = subprocess.check_output(['arp', '-a'], text=True, encoding='utf-8', errors='replace')
    hosts: list[tuple[str, str]] = []
    for line in out.splitlines():
        m = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})', line, re.I)
        if m:
            hosts.append((m.group(1), m.group(2).lower()))
    return hosts


def _puerto_abierto(ip: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _enviar_zpl(ip: str, port: int) -> dict:
    from services.ticket_impresion_escpos import _enviar_zpl_tcp

    return _enviar_zpl_tcp(ZPL_TEST, host=ip, port=port)


def main() -> int:
    ap = argparse.ArgumentParser(description='Descubrir y probar Zebra en red (RJ45 / TCP 9100)')
    ap.add_argument('--ip', help='IP fija (si ya la conoce del rótulo de la impresora)')
    ap.add_argument('--puerto', type=int, default=9100)
    ap.add_argument('--imprimir', action='store_true', help='Enviar etiqueta de prueba')
    args = ap.parse_args()

    candidatos: list[tuple[str, str, bool]] = []
    if args.ip:
        mac = ''
        for ip, m in _arp_hosts():
            if ip == args.ip:
                mac = m
                break
        candidatos.append((args.ip, mac, _puerto_abierto(args.ip, args.puerto)))
    else:
        for ip, mac in _arp_hosts():
            es_zebra = any(mac.startswith(oui) for oui in ZEBRA_OUI)
            if es_zebra or _puerto_abierto(ip, args.puerto):
                candidatos.append((ip, mac, _puerto_abierto(ip, args.puerto)))

    print('=== Candidatos Zebra / puerto 9100 ===')
    if not candidatos:
        print('Ninguno. Imprima etiqueta de configuración en la Zebra (apagar, FEED+encender).')
        return 1
    for ip, mac, ok in candidatos:
        tag = 'ZEBRA?' if any(mac.startswith(o) for o in ZEBRA_OUI) else 'host'
        print(f'  {ip}  mac={mac or "?"}  puerto_{args.puerto}={ok}  ({tag})')

    target = args.ip or next((ip for ip, _, ok in candidatos if ok), candidatos[0][0])
    print(f'\nObjetivo: {target}:{args.puerto}')

    if not args.imprimir:
        print('Use --imprimir para enviar etiqueta de prueba.')
        return 0

    res = _enviar_zpl(target, args.puerto)
    print(res)
    if res.get('ok'):
        print('\nOK — revise si salió etiqueta «PRUEBA ZEBRA RJ45».')
        print(f'Configure en .env.local: ZEBRA_ZPL_HOST={target}')
        print('ZEBRA_ZPL_METODO=tcp')
        return 0
    print('\nFALLO — verifique IP en etiqueta de config de la impresora y que puerto RAW 9100 esté activo.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
