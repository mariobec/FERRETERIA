#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lector IMAP — descarga adjuntos XML (DTE compra), etiqueta Gmail por RUT receptor e importa al ERP.

Variables en .env.local (no subir a git):

    IMAP_HOST=imap.gmail.com
    IMAP_PORT=993
    IMAP_USER=ferreteria426@gmail.com
    IMAP_PASSWORD=contraseña_de_aplicacion
    IMAP_FOLDER=INBOX
    IMAP_USE_SSL=1
    DTE_CORREO_CARPETA=datos_rcv
    DTE_RUT_RECEPTOR=8054120-1
    DTE_GMAIL_LABEL_ENTRADA=DTE-XML-Entrada
    DTE_GMAIL_LABEL_SD=DTE-8054120-1
    DTE_GMAIL_LABEL_OTRO=DTE-Otra-Sociedad

Gmail: crear filtro al recibir → MANUALES DE OPERACIÓN/GMAIL_FILTRO_DTE_SD.md

Uso:
    python scripts/lector_correo_dte.py --dry-run --limite 50
    python scripts/lector_correo_dte.py --solo-etiquetar --recientes --limite 200
    python scripts/lector_correo_dte.py --carpeta-imap "DTE-8054120-1"
"""
from __future__ import annotations

import argparse
import email
import imaplib
import io
import logging
import os
import re
import sys
from datetime import date, datetime
from email.header import decode_header
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger('lector_correo_dte')


def _load_env_local() -> None:
    """Carga .env.local en os.environ (setdefault, como importar_rcv_sii)."""
    p = ROOT / '.env.local'
    if not p.is_file():
        return
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k, v)


def _decodificar_header(valor: str | None) -> str:
    if not valor:
        return ''
    partes = decode_header(valor)
    out: list[str] = []
    for frag, enc in partes:
        if isinstance(frag, bytes):
            codec = (enc or 'utf-8').strip().lower()
            if codec in ('unknown-8bit', 'unknown', 'x-unknown', 'default'):
                codec = 'utf-8'
            try:
                out.append(frag.decode(codec, errors='replace'))
            except LookupError:
                out.append(frag.decode('utf-8', errors='replace'))
        else:
            out.append(str(frag))
    return ''.join(out).strip()


def _nombre_seguro(nombre: str, *, default: str = 'adjunto.xml') -> str:
    base = Path(nombre).name or default
    base = re.sub(r'[^\w.\- ]', '_', base, flags=re.UNICODE).strip()
    if not base.lower().endswith('.xml'):
        base = f'{base}.xml'
    return base[:180] or default


def _ruta_unica(carpeta: Path, nombre: str) -> Path:
    dest = carpeta / nombre
    if not dest.exists():
        return dest
    stem = dest.stem
    suf = dest.suffix
    n = 2
    while True:
        cand = carpeta / f'{stem}_{n}{suf}'
        if not cand.exists():
            return cand
        n += 1


def _iter_partes_xml(msg: email.message.Message) -> Iterator[tuple[str, bytes]]:
    """Genera (nombre_archivo, contenido_bytes) por cada adjunto .xml."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' not in disp and 'inline' not in disp:
                if ctype not in ('text/xml', 'application/xml'):
                    continue
            fname = part.get_filename()
            if fname:
                fname = _decodificar_header(fname)
            elif ctype in ('text/xml', 'application/xml'):
                fname = 'documento.xml'
            else:
                continue
            if not fname.lower().endswith('.xml'):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            yield _nombre_seguro(fname), payload
    else:
        fname = msg.get_filename()
        if fname:
            fname = _decodificar_header(fname)
        ctype = (msg.get_content_type() or '').lower()
        if fname and fname.lower().endswith('.xml'):
            payload = msg.get_payload(decode=True)
            if payload:
                yield _nombre_seguro(fname), payload
        elif ctype in ('text/xml', 'application/xml'):
            payload = msg.get_payload(decode=True)
            if payload:
                yield 'documento.xml', payload


# Avisos SII (no facturas de compra) — omitir en carga histórica.
_PATRONES_ASUNTO_RUIDO_SII = (
    'resultado de revision envio',
    'resultado de revisión envío',
    'resultado de revision del envio',
    'revision de envio',
    'revisión de envío',
    'acuse de recibo',
    'resultado envio dte',
    'envio dte',
)
_TIPOS_DTE_COMPRA = frozenset({33, 34, 46, 52})
_MARCAS_XML_RUIDO_SII = (
    b'respuestadte',
    b'recepciondte',
    b'resultadoenviodte',
    b'consumo folios',
)


def _omitir_correos_sii_habilitado() -> bool:
    return (os.getenv('DTE_OMITIR_CORREOS_SII') or '1').strip().lower() not in ('0', 'false', 'no')


def _es_correo_ruido_sii(remitente: str, asunto: str, *, omitir: bool = True) -> bool:
    """Correos siidte@sii.cl / acuses de envío — no traen factura compra parseable."""
    if not omitir or not _omitir_correos_sii_habilitado():
        return False
    rem = (remitente or '').lower()
    asu = (asunto or '').lower()
    if 'siidte@' in rem or '@sii.cl' in rem:
        return True
    if any(p in asu for p in _PATRONES_ASUNTO_RUIDO_SII):
        return True
    return False


def _es_xml_ruido_sii(contenido: bytes) -> bool:
    """XML acuse/respuesta SII sin factura compra embebida."""
    if not contenido:
        return True
    head = contenido[:12000].lower()
    if any(m in head for m in _MARCAS_XML_RUIDO_SII):
        return True
    if b'enviodte' in head and b'<documento' not in head and b':documento' not in head:
        return True
    return False


def _filtrar_xml_factura_compra(
    partes: list[tuple[str, bytes]],
) -> tuple[list[tuple[str, bytes]], int]:
    """Conserva solo adjuntos XML parseables como factura/guía compra SD."""
    from services.parser_xml_compra import ParserXmlCompraError, parsear_stream_dte_compra
    from services.dte_rut_receptor_service import rut_receptor_permitido

    utiles: list[tuple[str, bytes]] = []
    omitidos = 0
    for fname, data in partes:
        if _es_xml_ruido_sii(data):
            omitidos += 1
            continue
        try:
            dte = parsear_stream_dte_compra(io.BytesIO(data), archivo_origen=fname)
        except ParserXmlCompraError:
            omitidos += 1
            continue
        if int(dte.cabecera.tipo_dte) not in _TIPOS_DTE_COMPRA:
            omitidos += 1
            continue
        if not rut_receptor_permitido(dte.cabecera.rut_receptor):
            omitidos += 1
            continue
        utiles.append((fname, data))
    return utiles, omitidos


_MESES_IMAP = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def _fecha_imap(d: date) -> str:
    return f'{d.day:02d}-{_MESES_IMAP[d.month - 1]}-{d.year}'


def _parsear_fecha_desde(valor: str | None) -> date | None:
    if not valor:
        return None
    v = valor.strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise SystemExit(f'Fecha --desde inválida: {valor!r} (use YYYY-MM-DD)')


def _armar_criterio_imap(*, todos: bool, desde: date | None, hasta: date | None = None) -> str:
    partes = ['ALL' if todos else 'UNSEEN']
    if desde:
        partes.extend(['SINCE', _fecha_imap(desde)])
    if hasta:
        partes.extend(['BEFORE', _fecha_imap(hasta)])
    return ' '.join(partes)


def _conectar_imap() -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    host = (os.getenv('IMAP_HOST') or '').strip()
    user = (os.getenv('IMAP_USER') or '').strip()
    password = (os.getenv('IMAP_PASSWORD') or '').strip()
    if not host or not user or not password:
        raise SystemExit(
            'Configure IMAP_HOST, IMAP_USER e IMAP_PASSWORD en .env.local'
        )
    port = int(os.getenv('IMAP_PORT') or '993')
    use_ssl = (os.getenv('IMAP_USE_SSL') or '1').strip().lower() in ('1', 'true', 'yes')
    logger.info('Conectando IMAP %s:%s (ssl=%s) usuario=%s', host, port, use_ssl, user)
    if use_ssl:
        client = imaplib.IMAP4_SSL(host, port)
    else:
        client = imaplib.IMAP4(host, port)
    client.login(user, password)
    return client


def _parsear_rut_receptor_xml(contenido: bytes) -> str | None:
    from services.parser_xml_compra import ParserXmlCompraError, parsear_stream_dte_compra

    try:
        dte = parsear_stream_dte_compra(io.BytesIO(contenido), archivo_origen='correo.xml')
        return dte.cabecera.rut_receptor
    except ParserXmlCompraError as ex:
        logger.debug('XML sin RUT receptor parseable: %s', ex)
        return None


def _clasificar_correo_xml(xml_partes: list[tuple[str, bytes]]) -> tuple[str | None, bool]:
    """
    Devuelve (rut_receptor_representativo, es_permitido).
    Si hay varios XML, prioriza el primero con RUT permitido; si ninguno, el primero parseado.
    """
    from services.dte_rut_receptor_service import rut_receptor_permitido

    ruts: list[str] = []
    for _, data in xml_partes:
        rut = _parsear_rut_receptor_xml(data)
        if rut:
            ruts.append(rut)
    if not ruts:
        return None, False
    for rut in ruts:
        if rut_receptor_permitido(rut):
            return rut, True
    return ruts[0], False


def _aplicar_etiqueta_gmail(
    client: imaplib.IMAP4_SSL | imaplib.IMAP4,
    num: bytes,
    etiqueta: str,
    *,
    dry_run: bool = False,
) -> bool:
    if not etiqueta:
        return False
    if dry_run:
        logger.info('[dry-run] Etiqueta Gmail «%s» → correo id=%s', etiqueta, num.decode(errors='replace'))
        return True
    try:
        typ, dat = client.store(num, '+X-GM-LABELS', f'({etiqueta})')
        if typ != 'OK':
            logger.warning('No se pudo etiquetar «%s»: %s %s', etiqueta, typ, dat)
            return False
        logger.info('Etiqueta «%s» aplicada (id=%s)', etiqueta, num.decode(errors='replace'))
        return True
    except imaplib.IMAP4.error as ex:
        logger.warning('Error IMAP etiquetando «%s»: %s', etiqueta, ex)
        return False


def procesar_buzon(
    *,
    carpeta_destino: Path,
    dry_run: bool = False,
    marcar_leidos: bool = True,
    limite: int | None = None,
    recientes: bool = False,
    solo_etiquetar: bool = False,
    etiquetar: bool = True,
    importar_sd: bool = True,
    criterio: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    todos: bool = False,
    omitir_sii: bool | None = None,
    offset: int = 0,
) -> dict[str, int]:
    from services.parser_xml_compra import ParserXmlCompraError, procesar_xml_dte
    from services.dte_rut_receptor_service import etiqueta_gmail_para_rut, rut_receptor_permitido

    carpeta_destino.mkdir(parents=True, exist_ok=True)
    mailbox = (os.getenv('IMAP_FOLDER') or 'INBOX').strip() or 'INBOX'

    stats = {
        'correos_buscados': 0,
        'correos_procesados': 0,
        'correos_pendientes': 0,
        'correos_omitidos_sii': 0,
        'xml_omitidos_sii': 0,
        'correos_con_xml': 0,
        'etiquetados_sd': 0,
        'etiquetados_otra_sociedad': 0,
        'etiquetados_sin_rut': 0,
        'xml_descargados': 0,
        'xml_procesados_ok': 0,
        'xml_procesados_error': 0,
        'recepciones_erp': 0,
        'omitidos_rut': 0,
        'correos_marcados_leidos': 0,
        'offset_usado': max(0, int(offset or 0)),
    }

    if omitir_sii is None:
        omitir_sii = _omitir_correos_sii_habilitado()

    client = _conectar_imap()
    try:
        status, _ = client.select(mailbox, readonly=dry_run)
        if status != 'OK':
            raise RuntimeError(f'No se pudo abrir carpeta IMAP: {mailbox}')

        if criterio is None:
            criterio = _armar_criterio_imap(todos=todos, desde=desde, hasta=hasta)

        status, data = client.search(None, criterio)
        if status != 'OK':
            raise RuntimeError(f'Error al buscar correos {criterio}')
        ids = (data[0] or b'').split()
        stats['correos_buscados'] = len(ids)
        if recientes:
            ids = list(reversed(ids))
        desplaz = max(0, int(offset or 0))
        if desplaz:
            ids = ids[desplaz:]
        if limite and limite > 0:
            ids = ids[:limite]
        stats['correos_procesados'] = len(ids)
        stats['correos_pendientes'] = max(0, stats['correos_buscados'] - desplaz - len(ids))
        stats['offset_siguiente'] = desplaz + len(ids) if stats['correos_pendientes'] else desplaz + len(ids)

        logger.info(
            'Carpeta «%s» · criterio %s · encontrados %d (procesando %d · offset %d · pendientes %d%s%s)',
            mailbox,
            criterio,
            stats['correos_buscados'],
            len(ids),
            desplaz,
            stats['correos_pendientes'],
            ' · más recientes primero' if recientes else ' · más antiguos primero',
            ' · omitir SII' if omitir_sii else '',
        )

        for num in ids:
            status, fetched = client.fetch(num, '(RFC822)')
            if status != 'OK' or not fetched or not fetched[0]:
                logger.warning('No se pudo leer correo id=%s', num.decode(errors='replace'))
                continue

            raw = fetched[0][1]
            msg = email.message_from_bytes(raw)
            asunto = _decodificar_header(msg.get('Subject'))
            remitente = _decodificar_header(msg.get('From'))

            if _es_correo_ruido_sii(remitente, asunto, omitir=omitir_sii):
                stats['correos_omitidos_sii'] += 1
                logger.debug('Omitido SII: «%s» de %s', asunto[:60], remitente[:50])
                continue

            xml_en_correo = list(_iter_partes_xml(msg))

            if not xml_en_correo:
                continue

            if omitir_sii:
                xml_en_correo, n_xml_omit = _filtrar_xml_factura_compra(xml_en_correo)
                stats['xml_omitidos_sii'] += n_xml_omit
                if not xml_en_correo:
                    continue

            stats['correos_con_xml'] += 1
            rut_repr, es_sd = _clasificar_correo_xml(xml_en_correo)
            logger.info(
                'Correo XML: «%s» de %s · %d adj. · RUT receptor=%s · SD=%s',
                asunto[:80],
                remitente[:60],
                len(xml_en_correo),
                rut_repr or '?',
                es_sd,
            )

            if etiquetar:
                if rut_repr:
                    label = etiqueta_gmail_para_rut(rut_repr)
                    if _aplicar_etiqueta_gmail(client, num, label, dry_run=dry_run):
                        if es_sd:
                            stats['etiquetados_sd'] += 1
                        else:
                            stats['etiquetados_otra_sociedad'] += 1
                else:
                    label_sin = (os.getenv('DTE_GMAIL_LABEL_SIN_RUT') or 'DTE-XML-Sin-RUT').strip()
                    if _aplicar_etiqueta_gmail(client, num, label_sin, dry_run=dry_run):
                        stats['etiquetados_sin_rut'] += 1

            if solo_etiquetar:
                continue

            if not importar_sd or not es_sd:
                if rut_repr and not es_sd:
                    stats['omitidos_rut'] += len(xml_en_correo)
                continue

            descargados_en_correo = 0
            for fname, contenido in xml_en_correo:
                rut_xml = _parsear_rut_receptor_xml(contenido)
                if rut_xml and not rut_receptor_permitido(rut_xml):
                    stats['omitidos_rut'] += 1
                    continue

                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                prefijo = f'dte_{ts}_'
                destino = _ruta_unica(carpeta_destino, prefijo + fname)

                if dry_run:
                    logger.info('[dry-run] Guardaría %s (%d bytes)', destino.name, len(contenido))
                    stats['xml_descargados'] += 1
                    continue

                destino.write_bytes(contenido)
                stats['xml_descargados'] += 1
                descargados_en_correo += 1
                logger.info('Guardado: %s', destino)

                try:
                    res = procesar_xml_dte(destino, guardar_json=True, carpeta_json=carpeta_destino)
                    stats['xml_procesados_ok'] += 1
                    cab = res.get('cabecera') or {}
                    logger.info(
                        '  DTE OK folio=%s tipo=%s emisor=%s líneas=%s',
                        cab.get('folio'),
                        cab.get('tipo_dte'),
                        cab.get('rut_emisor'),
                        res.get('total_lineas'),
                    )
                    try:
                        import app as erp_app
                        from services.ingreso_dte_correo_service import persistir_recepcion_desde_xml_dte

                        with erp_app.app.app_context():
                            ing = persistir_recepcion_desde_xml_dte(destino, usuario_bodega='DTE-Correo')
                        if ing.ok and ing.recepcion_id:
                            stats['recepciones_erp'] += 1
                            logger.info(
                                '  Recepción documental #%s (%s) líneas=%s sin_match=%s',
                                ing.recepcion_id,
                                'nueva' if ing.recepcion_creada else 'actualizada',
                                ing.lineas_documentales,
                                len(ing.lineas_sin_match),
                            )
                        elif ing.omitida_duplicado:
                            logger.warning('  Recepción omitida (duplicado/finalizada): %s', ing.errores)
                        else:
                            logger.warning('  Recepción no persistida: %s', ing.errores)
                    except Exception as ex_erp:
                        logger.exception('  Error persistiendo recepción ERP: %s', ex_erp)
                except ParserXmlCompraError as ex:
                    stats['xml_procesados_error'] += 1
                    logger.error('  Error parser XML %s: %s', destino.name, ex)
                except Exception as ex:
                    stats['xml_procesados_error'] += 1
                    logger.exception('  Error inesperado procesando %s: %s', destino.name, ex)

            if not dry_run and marcar_leidos and descargados_en_correo > 0:
                client.store(num, '+FLAGS', '\\Seen')
                stats['correos_marcados_leidos'] += 1
                logger.info('Correo marcado como leído (id=%s)', num.decode(errors='replace'))

        return stats
    finally:
        try:
            client.logout()
        except Exception:
            pass


def main() -> int:
    _load_env_local()

    ap = argparse.ArgumentParser(description='DTE XML desde IMAP: etiqueta Gmail por RUT e importa al ERP.')
    ap.add_argument(
        '--carpeta',
        default=os.getenv('DTE_CORREO_CARPETA') or 'datos_rcv',
        help='Carpeta destino para XML (default: datos_rcv)',
    )
    ap.add_argument(
        '--carpeta-imap',
        default=os.getenv('IMAP_FOLDER') or 'INBOX',
        help='Carpeta/etiqueta IMAP a leer (ej. DTE-XML-Entrada o DTE-8054120-1)',
    )
    ap.add_argument('--dry-run', action='store_true', help='Simular; no escribe archivos ni etiquetas reales.')
    ap.add_argument(
        '--solo-etiquetar',
        action='store_true',
        help='Solo clasificar y etiquetar por RUT; no descargar XML ni ERP.',
    )
    ap.add_argument(
        '--sin-etiquetar',
        action='store_true',
        help='No aplicar etiquetas Gmail (solo importación clásica).',
    )
    ap.add_argument(
        '--no-marcar-leidos',
        action='store_true',
        help='No marcar correos como leídos tras importar XML SD.',
    )
    ap.add_argument(
        '--recientes',
        action='store_true',
        help='Procesar los correos más recientes primero (útil con buzón grande).',
    )
    ap.add_argument(
        '--todos',
        action='store_true',
        help='Buscar ALL en lugar de solo UNSEEN (etiquetar histórico).',
    )
    ap.add_argument(
        '--desde',
        metavar='YYYY-MM-DD',
        help='Solo correos desde esta fecha (IMAP SINCE). Ej: 2023-06-04 para 3 años atrás.',
    )
    ap.add_argument(
        '--hasta',
        metavar='YYYY-MM-DD',
        help='Hasta esta fecha exclusiva (IMAP BEFORE). Ej: 2026-02-01 para enero 2026.',
    )
    ap.add_argument(
        '--historial-anios',
        type=int,
        metavar='N',
        help='Atajo: --todos --desde hace N años (ej. 3). No marca leídos.',
    )
    ap.add_argument('--limite', type=int, default=0, help='Máximo de correos a revisar (0=todos).')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    if args.carpeta_imap:
        os.environ['IMAP_FOLDER'] = args.carpeta_imap.strip()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s %(message)s',
    )

    desde = _parsear_fecha_desde(args.desde) if args.desde else None
    hasta = _parsear_fecha_desde(args.hasta) if args.hasta else None
    todos = args.todos
    marcar = not args.dry_run and not args.no_marcar_leidos and not args.solo_etiquetar

    if args.historial_anios and args.historial_anios > 0:
        from datetime import timedelta
        todos = True
        if not args.desde:
            desde = date.today() - timedelta(days=365 * args.historial_anios)
        marcar = False
        logger.info(
            'Modo historial %d años: desde %s · ALL · no marcar leídos',
            args.historial_anios,
            desde.isoformat() if desde else '?',
        )

    carpeta = ROOT / args.carpeta
    limite = args.limite if args.limite > 0 else None

    try:
        stats = procesar_buzon(
            carpeta_destino=carpeta,
            dry_run=args.dry_run,
            marcar_leidos=marcar,
            limite=limite,
            recientes=args.recientes,
            solo_etiquetar=args.solo_etiquetar,
            etiquetar=not args.sin_etiquetar,
            criterio=None,
            desde=desde,
            hasta=hasta,
            todos=todos,
        )
    except imaplib.IMAP4.error as ex:
        logger.error('Error IMAP: %s', ex)
        return 1
    except Exception as ex:
        logger.exception('Fallo: %s', ex)
        return 1

    print('=== Lector correo DTE ===')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    if stats['xml_procesados_error']:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
