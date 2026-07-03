#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configura Gmail + ERP para transferencias bancarias (misma cuenta IMAP que DTE).

1. Crea etiquetas Gmail vía IMAP (si no existen).
2. Clasifica correos recientes en INBOX → Transferencias-Banco.
3. Sincroniza bandeja /caja/transferencias en BD local.

Uso:
    python scripts/setup_gmail_transferencias_correo.py
    python scripts/setup_gmail_transferencias_correo.py --solo-etiquetar --limite 200
    python scripts/setup_gmail_transferencias_correo.py --dry-run -v
"""
from __future__ import annotations

import argparse
import email
import imaplib
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger('setup_gmail_trf')

LABEL_ENTRADA = 'Transferencias-Entrada'
LABEL_BANCO = 'Transferencias-Banco'


def _load_env_local() -> None:
    p = ROOT / '.env.local'
    if not p.is_file():
        return
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def _labels_existentes(client) -> set[str]:
    typ, data = client.list()
    if typ != 'OK' or not data:
        return set()
    out: set[str] = set()
    for item in data:
        if not item:
            continue
        parts = item.decode(errors='replace').split('"')
        if len(parts) >= 2:
            out.add(parts[-2])
    return out


def ensure_gmail_label(client, nombre: str, *, dry_run: bool = False) -> bool:
    existentes = _labels_existentes(client)
    if nombre in existentes:
        logger.info('Etiqueta ya existe: %s', nombre)
        return False
    if dry_run:
        logger.info('[dry-run] Crearía etiqueta: %s', nombre)
        return True
    try:
        typ, dat = client.create(nombre)
        logger.info('Etiqueta creada: %s (%s %s)', nombre, typ, dat)
        return True
    except imaplib.IMAP4.error as ex:
        if 'exists' in str(ex).lower() or 'already' in str(ex).lower():
            return False
        raise


def _aplicar_etiqueta(client, num: bytes, etiqueta: str, *, dry_run: bool = False) -> bool:
    if dry_run:
        logger.info('[dry-run] Etiqueta %s → uid %s', etiqueta, num.decode(errors='replace'))
        return True
    typ, dat = client.store(num, '+X-GM-LABELS', f'({etiqueta})')
    return typ == 'OK'


def clasificar_inbox_transferencias(
    *,
    limite: int = 300,
    dias: int = 45,
    dry_run: bool = False,
) -> dict[str, int]:
    from services.imap_correo_util import (
        conectar_imap,
        decodificar_header,
        extraer_texto_plano,
        fecha_imap,
        parsear_fecha_correo,
    )
    from services.transferencia_correo_parser import parsear_correo_transferencia

    _load_env_local()
    desde = date.today() - timedelta(days=max(1, dias))
    criterio = f'(ALL SINCE {fecha_imap(desde)})'
    stats = {'escaneados': 0, 'etiquetados': 0, 'omitidos': 0, 'errores': 0}

    client = conectar_imap()
    try:
        typ, _ = client.select('INBOX')
        if typ != 'OK':
            raise RuntimeError('No se pudo abrir INBOX')
        typ, data = client.search(None, criterio)
        if typ != 'OK' or not data or not data[0]:
            return stats
        ids = data[0].split()
        if limite > 0:
            ids = ids[-limite:]

        for num in ids:
            stats['escaneados'] += 1
            try:
                typ, msg_data = client.fetch(num, '(RFC822)')
                if typ != 'OK' or not msg_data or not msg_data[0]:
                    stats['omitidos'] += 1
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                rem = decodificar_header(msg.get('From'))
                asu = decodificar_header(msg.get('Subject'))
                cuerpo = extraer_texto_plano(msg)
                parsed = parsear_correo_transferencia(remitente=rem, asunto=asu, cuerpo=cuerpo)
                if not parsed.es_transferencia:
                    stats['omitidos'] += 1
                    continue
                if _aplicar_etiqueta(client, num, LABEL_BANCO, dry_run=dry_run):
                    stats['etiquetados'] += 1
                    logger.debug(
                        'Etiquetado uid=%s monto=%s ref=%s fecha=%s',
                        num.decode(errors='replace'),
                        parsed.monto,
                        parsed.referencia,
                        parsear_fecha_correo(msg),
                    )
            except Exception as ex:
                stats['errores'] += 1
                logger.warning('Error uid %s: %s', num, ex)
        return stats
    finally:
        try:
            client.logout()
        except Exception:
            pass


def _asegurar_env_local_trf() -> None:
    """Añade variables TRF_* a .env.local si faltan."""
    p = ROOT / '.env.local'
    if not p.is_file():
        logger.warning('No existe .env.local — cree IMAP_* manualmente')
        return
    texto = p.read_text(encoding='utf-8')
    bloque = """

# --- Transferencias bancarias (bandeja /caja/transferencias) ---
TRF_CORREO_FOLDER=Transferencias-Banco
TRF_CORREO_DIAS=45
TRF_GMAIL_LABEL=Transferencias-Banco
TRF_GMAIL_LABEL_ENTRADA=Transferencias-Entrada
"""
    markers = ('TRF_CORREO_FOLDER=', 'TRF_GMAIL_LABEL=')
    if any(m in texto for m in markers):
        logger.info('.env.local ya tiene variables TRF_*')
        return
    with p.open('a', encoding='utf-8') as f:
        f.write(bloque)
    logger.info('Variables TRF_* añadidas a .env.local')


def main() -> int:
    parser = argparse.ArgumentParser(description='Setup Gmail transferencias + sync ERP')
    parser.add_argument('--solo-etiquetar', action='store_true', help='No sincronizar BD ERP')
    parser.add_argument('--limite', type=int, default=300)
    parser.add_argument('--dias', type=int, default=45)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s %(message)s')

    _load_env_local()
    _asegurar_env_local_trf()

    from services.imap_correo_util import conectar_imap, imap_configurado

    if not imap_configurado():
        print('ERROR: Configure IMAP_USER e IMAP_PASSWORD en .env.local')
        return 1

    client = conectar_imap()
    try:
        ensure_gmail_label(client, LABEL_ENTRADA, dry_run=args.dry_run)
        ensure_gmail_label(client, LABEL_BANCO, dry_run=args.dry_run)
    finally:
        try:
            client.logout()
        except Exception:
            pass

    stats = clasificar_inbox_transferencias(
        limite=args.limite,
        dias=args.dias,
        dry_run=args.dry_run,
    )
    print('Clasificacion INBOX ->', LABEL_BANCO, stats)

    if args.solo_etiquetar or args.dry_run:
        print('OK (solo etiquetado). Importe filtro Gmail: config/gmail_filtro_transferencias.xml')
        return 0

    from app import app
    from services.transferencia_correo_carga_service import sincronizar_correo_transferencias

    os.environ['TRF_CORREO_FOLDER'] = LABEL_BANCO
    with app.app_context():
        res = sincronizar_correo_transferencias(limite=args.limite, usuario='Setup-Gmail-TRF')
    if not res.get('ok'):
        print('ERROR sync ERP:', res.get('error'))
        return 1
    print('Sync ERP:', res.get('mensaje'))
    print('stats:', res.get('stats'))
    print('')
    print('Siguiente paso (una vez): Gmail → Configuración → Filtros → Importar filtros')
    print('  Archivo:', ROOT / 'config' / 'gmail_filtro_transferencias.xml')
    print('Bandeja ERP: /caja/transferencias')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
