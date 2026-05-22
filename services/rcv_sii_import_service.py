"""Importación RCV SII (compras) → borradores de RecepcionCompra."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

# Estado visible en UI; debe existir en recepciones_estado_enum (ver sql/2026_05_22_rcv_sii_recepciones.sql).
ESTADO_PENDIENTE_ITEMS = 'Pendiente de Items'
ESTADO_ARCHIVADO_RCV = 'Archivado RCV'
ESTADOS_RECEPCION_EDITABLE = ('Pendiente', ESTADO_PENDIENTE_ITEMS, 'Incompleta')
ORIGEN_RCV_SII = 'rcv_sii'

# Factura electrónica afecta (compras habituales ferretería).
TIPOS_DOC_COMPRA_DEFAULT = frozenset({33, 34, 46})

_ALIASES: dict[str, list[str]] = {
    'tipo_doc': [
        'tipo doc',
        'tipo documento',
        'tipo dte',
        'tipo dcto',
        'tipo',
        'cod doc',
        'codigo documento',
        'cod documento',
        'tipo de documento',
    ],
    'rut': [
        'rut emisor',
        'rut proveedor',
        'rut de su proveedor',
        'rut contraparte',
        'rut del emisor',
        'rut',
    ],
    'razon_social': [
        'razon social',
        'razon social emisor',
        'nombre emisor',
        'nombre proveedor',
        'proveedor',
        'nombre o razon social',
    ],
    'folio': ['folio', 'nro folio', 'numero folio', 'folio documento', 'n folio'],
    'fecha': [
        'fecha docto',
        'fecha documento',
        'fecha doc',
        'fch documento',
        'fecha',
        'fecha emision',
    ],
    'monto_neto': [
        'monto neto',
        'neto',
        'monto afecto',
        'valor neto',
    ],
    'monto_total': [
        'monto total',
        'total',
        'monto documento',
        'valor total',
    ],
    'estado_doc': [
        'estado documento',
        'estado',
        'estado dte',
    ],
}


@dataclass
class LineaRcvCompra:
    tipo_doc: int
    rut: str
    razon_social: str
    folio: str
    fecha: date | None
    monto_neto: float | None
    monto_total: float | None
    estado_doc: str
    fila_origen: int


@dataclass
class ResultadoImportRcv:
    ok: bool
    dry_run: bool
    archivo: str
    filas_leidas: int = 0
    filas_compra: int = 0
    creadas: int = 0
    omitidas_duplicado: int = 0
    omitidas_filtro: int = 0
    proveedores_creados: int = 0
    errores: list[str] = field(default_factory=list)
    muestra_ids: list[int] = field(default_factory=list)


def _norm_header(value: str) -> str:
    s = str(value or '').strip().lower()
    s = re.sub(r'[\s_\-]+', ' ', s)
    s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    s = s.replace('ñ', 'n')
    return s


def _resolver_columnas(headers: list[str]) -> dict[str, int | None]:
    norm = {_norm_header(h): i for i, h in enumerate(headers)}
    out: dict[str, int | None] = {}
    for key, aliases in _ALIASES.items():
        idx = None
        for alias in aliases:
            if alias in norm:
                idx = norm[alias]
                break
        out[key] = idx
    return out


def _detectar_delimitador(linea: str) -> str:
    if linea.count(';') >= linea.count(',') and linea.count(';') > 0:
        return ';'
    if linea.count('\t') > linea.count(','):
        return '\t'
    return ','


def _leer_filas_texto(contenido: bytes) -> list[list[str]]:
    texto = None
    for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
        try:
            texto = contenido.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ValueError('No se pudo decodificar el archivo (UTF-8 / Latin-1).')

    lineas = [ln for ln in texto.splitlines() if ln.strip()]
    if not lineas:
        return []

    delim = _detectar_delimitador(lineas[0])
    reader = csv.reader(io.StringIO('\n'.join(lineas)), delimiter=delim)
    return [row for row in reader if any(str(c).strip() for c in row)]


def normalizar_rut(rut: str | None) -> str:
    s = re.sub(r'[^0-9kK]', '', str(rut or '').strip().upper())
    if len(s) < 2:
        return ''
    cuerpo, dv = s[:-1], s[-1]
    try:
        cuerpo = str(int(cuerpo))
    except ValueError:
        return ''
    return f'{cuerpo}-{dv}'


def _parse_tipo_doc(raw: Any) -> int | None:
    s = str(raw or '').strip().lower()
    if not s:
        return None
    s = s.split('.')[0]
    if not s.isdigit():
        return None
    return int(s)


def _parse_folio(raw: Any) -> str:
    s = str(raw or '').strip()
    if not s:
        return ''
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s[:50]


def _parse_fecha(raw: Any) -> date | None:
    s = str(raw or '').strip()
    if not s:
        return None
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%y', '%d/%m/%y'):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_monto(raw: Any) -> float | None:
    s = str(raw or '').strip()
    if not s:
        return None
    s = s.replace('$', '').replace(' ', '')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    else:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _celda(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ''
    return str(row[idx]).strip()


def parsear_rcv_compras(
    contenido: bytes,
    *,
    tipos_doc: frozenset[int] | None = None,
) -> tuple[list[LineaRcvCompra], dict[str, int | None], int]:
    """Parsea export RCV/libro compras SII. Retorna líneas válidas, mapa columnas y total filas datos."""
    tipos = tipos_doc or TIPOS_DOC_COMPRA_DEFAULT
    filas = _leer_filas_texto(contenido)
    if not filas:
        return [], {}, 0

    header_idx = 0
    cols: dict[str, int | None] = {}
    for i, row in enumerate(filas[:15]):
        trial = _resolver_columnas(row)
        if trial.get('tipo_doc') is not None and trial.get('folio') is not None:
            header_idx = i
            cols = trial
            break
    if not cols:
        cols = _resolver_columnas(filas[0])
        header_idx = 0

    if cols.get('tipo_doc') is None or cols.get('folio') is None:
        raise ValueError(
            'No se detectaron columnas Tipo Doc y Folio. '
            'Verifique que sea export de compras del RCV SII.'
        )

    out: list[LineaRcvCompra] = []
    omitidas = 0
    data_rows = filas[header_idx + 1 :]
    for i, row in enumerate(data_rows, start=header_idx + 2):
        tipo = _parse_tipo_doc(_celda(row, cols.get('tipo_doc')))
        if tipo is None or tipo not in tipos:
            omitidas += 1
            continue
        folio = _parse_folio(_celda(row, cols.get('folio')))
        if not folio:
            omitidas += 1
            continue
        rut = normalizar_rut(_celda(row, cols.get('rut')))
        if not rut:
            omitidas += 1
            continue
        estado_doc = _celda(row, cols.get('estado_doc')).lower()
        if estado_doc and any(x in estado_doc for x in ('anul', 'rechaz', 'invalid')):
            omitidas += 1
            continue
        out.append(
            LineaRcvCompra(
                tipo_doc=tipo,
                rut=rut,
                razon_social=_celda(row, cols.get('razon_social'))[:200],
                folio=folio,
                fecha=_parse_fecha(_celda(row, cols.get('fecha'))),
                monto_neto=_parse_monto(_celda(row, cols.get('monto_neto'))),
                monto_total=_parse_monto(_celda(row, cols.get('monto_total'))),
                estado_doc=estado_doc,
                fila_origen=i,
            )
        )
    return out, cols, len(data_rows)


def _proveedor_por_rut_o_nombre(
    *,
    rut: str,
    razon: str,
    Proveedor,
    db,
    cache: dict[str, int],
    on_create: Callable[[], None] | None = None,
) -> int | None:
    if rut in cache:
        return cache[rut]

    prov = None
    if hasattr(Proveedor, 'rut'):
        prov = Proveedor.query.filter(Proveedor.rut == rut).first()
    if not prov and razon:
        like = f'%{razon[:80]}%'
        prov = Proveedor.query.filter(Proveedor.nombre.ilike(like)).first()
    if not prov:
        nombre = (razon or f'Proveedor {rut}').strip()[:100] or f'Proveedor {rut}'
        prov = Proveedor(nombre=nombre)
        if hasattr(prov, 'rut'):
            prov.rut = rut
        db.session.add(prov)
        db.session.flush()
        if on_create:
            on_create()
    elif hasattr(prov, 'rut') and not (prov.rut or '').strip():
        prov.rut = rut

    cache[rut] = int(prov.id)
    return cache[rut]


def importar_archivo_rcv(
    path: str,
    *,
    dry_run: bool = False,
    tipos_doc: frozenset[int] | None = None,
    usuario_bodega: str = 'RCV-SII',
    crear_proveedor: bool = True,
) -> ResultadoImportRcv:
    """Crea recepciones Pendiente de Items desde archivo RCV."""
    from pathlib import Path

    from app import RecepcionCompra, Proveedor, db

    p = Path(path)
    if not p.is_file():
        return ResultadoImportRcv(ok=False, dry_run=dry_run, archivo=str(p), errores=['Archivo no encontrado.'])

    contenido = p.read_bytes()
    res = ResultadoImportRcv(ok=True, dry_run=dry_run, archivo=str(p.resolve()))

    try:
        lineas, _cols, filas_datos = parsear_rcv_compras(contenido, tipos_doc=tipos_doc)
    except ValueError as ex:
        res.ok = False
        res.errores.append(str(ex))
        return res

    res.filas_leidas = filas_datos
    res.filas_compra = len(lineas)
    cache_prov: dict[str, int] = {}
    creados_prov = [0]

    for ln in lineas:
        try:
            if not crear_proveedor and dry_run:
                prov_id = 0
            else:
                prov_id = _proveedor_por_rut_o_nombre(
                    rut=ln.rut,
                    razon=ln.razon_social,
                    Proveedor=Proveedor,
                    db=db,
                    cache=cache_prov,
                    on_create=lambda: creados_prov.__setitem__(0, creados_prov[0] + 1),
                )
            if not prov_id:
                res.errores.append(f'Fila {ln.fila_origen}: sin proveedor para RUT {ln.rut}')
                continue

            dup = RecepcionCompra.query.filter_by(
                proveedor_id=prov_id,
                documento_tipo='Factura',
                documento_numero=ln.folio,
            ).first()
            if dup:
                res.omitidas_duplicado += 1
                continue

            if dry_run:
                res.creadas += 1
                continue

            rec = RecepcionCompra(
                proveedor_id=prov_id,
                documento_tipo='Factura',
                documento_numero=ln.folio,
                usuario_bodega=usuario_bodega[:100],
                estado=ESTADO_PENDIENTE_ITEMS,
                origen_importacion=ORIGEN_RCV_SII,
            )
            if hasattr(rec, 'rut_proveedor_doc'):
                rec.rut_proveedor_doc = ln.rut
            if hasattr(rec, 'razon_social_doc'):
                rec.razon_social_doc = ln.razon_social or None
            if hasattr(rec, 'monto_neto'):
                rec.monto_neto = ln.monto_neto
            if hasattr(rec, 'monto_total'):
                rec.monto_total = ln.monto_total
            if hasattr(rec, 'fecha_documento') and ln.fecha:
                rec.fecha_documento = ln.fecha
            if ln.fecha and rec.fecha_recepcion is not None:
                rec.fecha_recepcion = datetime.combine(ln.fecha, datetime.min.time())

            db.session.add(rec)
            db.session.flush()
            res.creadas += 1
            if len(res.muestra_ids) < 15:
                res.muestra_ids.append(int(rec.id))

        except Exception as ex:
            res.errores.append(f'Fila {ln.fila_origen}: {ex}')

    res.proveedores_creados = creados_prov[0]
    if not dry_run and res.creadas:
        db.session.commit()
    elif not dry_run:
        db.session.rollback()

    return res
