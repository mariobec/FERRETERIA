"""Impresión térmica ESC/POS (XPrinter XP-80T y compatibles 80 mm)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Any

ESC = b'\x1b'
GS = b'\x1d'

# Ancho típico XP-80T en fuente A
COLS = 48
# Ct (4) + Producto (28) + $ (10)
COL_CT = 4
COL_PROD = 28
COL_PRECIO = 10


def _enc(text: str) -> bytes:
    """Codificación compatible con térmicas CP850/CP437 en Chile."""
    if not text:
        return b''
    return text.encode('cp850', errors='replace')


def _cmd_init() -> bytes:
    return ESC + b'@'


def _cmd_cut() -> bytes:
    return GS + b'V\x00'


def _align(mode: int) -> bytes:
    return ESC + b'a' + bytes([max(0, min(2, mode))])


def _bold(on: bool) -> bytes:
    return ESC + b'E' + (b'\x01' if on else b'\x00')


def _line(text: str = '') -> bytes:
    return _enc((text or '')[:COLS]) + b'\n'


def _sep(char: str = '-') -> bytes:
    c = (char or '-')[:1]
    return _line(c * COLS)


def _wrap(text: str, width: int | None = None) -> list[str]:
    w = width or COLS
    words = (text or '').split()
    lines: list[str] = []
    cur = ''
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= w:
            cur += ' ' + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or ['']


def _money_clp(n: float | int) -> str:
    return '$' + f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _size_double(on: bool) -> bytes:
    """Doble alto+ancho (solo montos cortos; nombres largos se rompen en XP-80)."""
    return GS + b'!' + (bytes([0x11]) if on else bytes([0x00]))


def _size_double_height(on: bool) -> bytes:
    """Solo doble alto: cabe el nombre completo a 48 columnas."""
    return GS + b'!' + (bytes([0x10]) if on else bytes([0x00]))


def _fold_thermal(text: str) -> str:
    """Quita tildes / símbolos raros para que la térmica no desalineé con CP850."""
    if not text:
        return ''
    table = str.maketrans({
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ü': 'U', 'Ñ': 'N',
        '·': '-', '•': '-', '–': '-', '—': '-', '°': ' ',
    })
    return (text or '').translate(table)


def _empresa_lineas_marca(empresa: str) -> list[str]:
    """Misma jerarquía que cotización: FERRETERIA / SANTO DOMINGO."""
    raw = _fold_thermal((empresa or 'Ferreteria Santo Domingo').strip())
    parts = [p for p in raw.replace('  ', ' ').split(' ') if p]
    if not parts:
        return ['FERRETERIA', 'SANTO DOMINGO']
    first = parts[0].upper()
    if first.startswith('FERRETER'):
        line1 = 'FERRETERIA'
        line2 = ' '.join(parts[1:]).upper() or 'SANTO DOMINGO'
        return [line1[:COLS], line2[:COLS]]
    wrapped = _wrap(raw.upper(), COLS)
    return [ln[:COLS] for ln in wrapped[:3]]


def _raster_gs_v0(img_path: str, *, max_width_px: int = 384) -> bytes:
    """Logo monocromo ESC/POS (GS v 0) para XP-80 / Epson-compat."""
    try:
        from PIL import Image
    except Exception:
        return b''
    try:
        im = Image.open(img_path)
        im = im.convert('RGBA')
        # Fondo blanco bajo transparencia
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.paste(im, mask=im.split()[3] if 'A' in im.getbands() else None)
        im = bg.convert('L')
        w, h = im.size
        if w > max_width_px:
            nh = max(1, int(round(h * (max_width_px / float(w)))))
            im = im.resize((max_width_px, nh), Image.Resampling.LANCZOS)
            w, h = im.size
        # Umbral: logo oscuro sobre blanco
        bw = im.point(lambda x: 0 if x < 200 else 255, mode='1')
        row_bytes = (w + 7) // 8
        data = bytearray()
        px = bw.load()
        for y in range(h):
            for xb in range(row_bytes):
                byte = 0
                for bit in range(8):
                    x = xb * 8 + bit
                    if x < w and px[x, y] == 0:
                        byte |= 0x80 >> bit
                data.append(byte)
        out = bytearray()
        out += _align(1)
        # GS v 0 m xL xH yL yH d...
        out += GS + b'v0' + bytes([0, row_bytes % 256, row_bytes // 256, h % 256, h // 256])
        out += bytes(data)
        out += b'\n'
        out += _align(0)
        return bytes(out)
    except Exception:
        return b''


def _cabecera_marca_bytes(empresa: str) -> bytes:
    """Logo Chilemat (si hay PNG) + FERRETERIA / SANTO DOMINGO centrados."""
    from pathlib import Path

    out = bytearray()
    out += _align(1)
    root = Path(__file__).resolve().parents[1]
    logo = root / 'static' / 'img' / 'chilemat_logo_oficial.png'
    raster = b''
    if logo.is_file():
        # ~48mm de ancho en 80mm (deja márgenes)
        raster = _raster_gs_v0(str(logo), max_width_px=280)
    if raster:
        out += raster
    else:
        out += _bold(True)
        out += _line('CHILEMAT')
        out += _bold(False)
        out += _line('TRADICION FERRETERA')
    out += _bold(True)
    out += _size_double_height(True)
    for ln in _empresa_lineas_marca(empresa):
        out += _line(ln)
    out += _size_double_height(False)
    out += _bold(False)
    out += _align(0)
    return bytes(out)


def _barcode_code128(code: str) -> bytes:
    """CODE128 centrado con HRI debajo (folio VL000000)."""
    raw = (code or '').strip().encode('ascii', errors='ignore')
    if not raw:
        return b''
    out = bytearray()
    out += GS + b'h' + bytes([72])
    out += GS + b'w' + bytes([2])
    out += GS + b'H' + bytes([2])
    out += _align(1)
    out += GS + b'k' + bytes([73, len(raw)]) + raw
    out += _align(0)
    out += b'\n'
    return bytes(out)


def _qr_model2(text: str, module_size: int = 5) -> bytes:
    """QR modelo 2 (Epson / XPrinter XP-80) — secuencia GS ( k correcta."""
    data = (text or '').strip().encode('utf-8')
    if not data:
        return b''
    size = max(1, min(16, int(module_size or 5)))
    out = bytearray()
    out += _align(1)
    # Modelo 2: GS ( k 04 00 31 41 32 00
    out += GS + b'(k' + bytes([4, 0, 49, 65, 50, 0])
    # Tamaño módulo: GS ( k 03 00 31 43 n
    out += GS + b'(k' + bytes([3, 0, 49, 67, size])
    # Corrección M (15%): GS ( k 03 00 31 45 31
    out += GS + b'(k' + bytes([3, 0, 49, 69, 49])
    # Guardar datos: GS ( k pL pH 31 50 30 d1..dk
    store = bytes([49, 80, 48]) + data
    pl = len(store)
    out += GS + b'(k' + bytes([pl % 256, pl // 256]) + store
    # Imprimir: GS ( k 03 00 31 51 30
    out += GS + b'(k' + bytes([3, 0, 49, 81, 48])
    out += b'\n'
    return bytes(out)


def _fmt_clp_tabla(n: float | int) -> str:
    return f'{int(round(float(n or 0))):,}'.replace(',', '.')


def _line_tabla_producto(pref: str, nombre: str, cant: int, subtotal: float | int) -> bytes:
    """Ct a la izquierda; precio a la derecha (evita confundir 1 con 1.500)."""
    ct = str(int(cant or 0)).rjust(2).ljust(COL_CT)
    nom = f'{(pref or "").strip()}{(nombre or "")}'.strip()[:COL_PROD]
    sub = _fmt_clp_tabla(subtotal).rjust(COL_PRECIO)
    return _line(f'{ct}{nom.ljust(COL_PROD)}{sub}')


def _line_tabla_header() -> bytes:
    hdr = 'Ct'.ljust(COL_CT) + 'Producto'.ljust(COL_PROD) + '$'.rjust(COL_PRECIO)
    return _line(hdr)


def build_vale_escpos_bytes(ctx: dict[str, Any]) -> bytes:
    """Arma ticket vale en ESC/POS alineado a ticket_vale.html."""
    out = bytearray()
    out += _cmd_init()

    empresa = (ctx.get('empresa') or 'Ferreteria Santo Domingo').strip()
    venta_id = ctx.get('venta_id')
    folio = (ctx.get('folio_barcode') or f'VL{int(venta_id or 0):06d}').strip()

    # --- Cabecera: logo Chilemat + FERRETERIA / SANTO DOMINGO (sin doble ancho) ---
    out += _cabecera_marca_bytes(empresa)
    out += _align(1)
    direccion = _fold_thermal((ctx.get('direccion_empresa') or '').strip())
    tel_hdr = (ctx.get('telefono_contacto') or '').strip()
    if direccion:
        for ln in _wrap(direccion, COLS):
            out += _line(ln)
    if tel_hdr:
        out += _line(tel_hdr[:COLS])
    out += _align(0)

    out += _line('')
    out += _align(1)
    out += _bold(True)
    out += _line('VALE INTERNO')
    out += _bold(False)
    out += _line('NO ES BOLETA')
    out += _line('Presente en caja para pagar')
    out += _bold(True)
    out += _line(f'N {venta_id}')
    out += _bold(False)
    out += _line(ctx.get('fecha_fmt') or '')
    out += _line(f"Turno: {ctx.get('prioridad') or '-'} · {ctx.get('vendedor') or '-'}")
    if ctx.get('cotizacion_origen'):
        out += _line(f"Origen: Cot. {ctx['cotizacion_origen']}")
    if ctx.get('punto_retiro'):
        out += _line(f"Retiro vale: {ctx['punto_retiro']}")
    if ctx.get('cliente'):
        out += _line(str(ctx['cliente'])[:COLS])
    out += _align(0)

    # --- Código de barras folio (cabecera; QR va al final para lector bodega) ---
    out += b'\n'
    out += _barcode_code128(folio)

    qr_url = (ctx.get('qr_url') or '').strip()
    sin_qr = (os.getenv('POS_TICKET_TERMICA_SIN_QR') or '').strip().lower() in (
        '1',
        'true',
        'si',
        'yes',
        'on',
    )

    def _tabla_lineas(lineas: list) -> None:
        out.extend(_sep('='))
        out.extend(_bold(True))
        out.extend(_line_tabla_header())
        out.extend(_bold(False))
        out.extend(_sep('-'))
        for ln in lineas or []:
            out.extend(
                _line_tabla_producto(
                    ln.get('prefijo') or '',
                    ln.get('nombre') or '',
                    int(ln.get('cantidad') or 0),
                    ln.get('subtotal', 0),
                )
            )

    bloques = ctx.get('bloques') or []
    if bloques:
        for bloque in bloques:
            titulo = bloque.get('titulo')
            lineas = bloque.get('lineas') or []
            if not lineas:
                continue
            out += _sep('=')
            out += _align(1)
            out += _bold(True)
            out += _line(str(titulo or '')[:COLS])
            out += _bold(False)
            out += _align(0)
            _tabla_lineas(lineas)
        subs = ctx.get('subtotales') or {}
        if subs:
            out += _sep('=')
            out += _align(1)
            out += _bold(True)
            out += _line('RESUMEN')
            out += _bold(False)
            out += _align(0)
            for key, lab in (
                ('Tienda', 'TOTAL TIENDA'),
                ('Bodega', 'TOTAL BODEGA'),
                ('Despacho', 'TOTAL DESPACHO'),
            ):
                v = float(subs.get(key) or 0)
                if v > 0:
                    out += _line(f'{lab}: ${_fmt_clp_tabla(v)}')
    else:
        lineas = ctx.get('lineas') or []
        if lineas:
            _tabla_lineas(lineas)

    promos = ctx.get('promociones') or []
    dto_promo = int(ctx.get('descuento_promos') or 0)
    if promos and dto_promo > 0:
        out += _sep('-')
        out += _align(1)
        out += _bold(True)
        out += _line('PROMOCIONES')
        out += _bold(False)
        out += _align(0)
        if ctx.get('subtotal_lineas') is not None:
            out += _line(f'Subtotal ${_fmt_clp_tabla(ctx.get("subtotal_lineas", 0))}')
        for pr in promos:
            etq = str(pr.get('etiqueta_ticket') or pr.get('codigo') or 'Promo')[:28]
            mon = int(pr.get('monto_descuento') or 0)
            out += _line(f'{etq} -${_fmt_clp_tabla(mon)}')

    out += _sep('=')
    out += _align(2)
    out += _bold(True)
    out += _size_double_height(True)
    if bloques:
        out += _line('TOTAL A PAGAR')
    out += _line(f'${_fmt_clp_tabla(ctx.get("total", 0))}')
    out += _size_double_height(False)
    out += _bold(False)
    out += _align(0)

    out += b'\n'
    out += _align(1)
    out += _bold(True)
    if ctx.get('es_borrador'):
        out += _line('*** BORRADOR POS ***')
        out += _line('EMITA EL VALE DESDE POS')
    else:
        out += _line('*** PENDIENTE DE COBRO EN CAJA ***')
        out += _line('Ticket retiro con QR')
        out += _line('se imprime tras el cobro')
    out += _bold(False)
    out += _align(0)
    # Margen de avance antes del corte (evita cortar el pie en XP-80)

    # --- QR al pie (lector fijo bodega) ---
    if qr_url and not sin_qr:
        out += _sep('-')
        out += _align(1)
        out += _bold(True)
        out += _line('ESCANEO BODEGA')
        out += _bold(False)
        out += b'\n'
        out += _qr_model2(qr_url, module_size=6)
        out += _line('QR despacho · tienda y bodega')
        out += _align(0)

    out += b'\n\n\n\n\n'
    out += _cmd_cut()
    return bytes(out)


def build_retiro_escpos_bytes(ctx: dict[str, Any]) -> bytes:
    """Ticket de retiro post-cobro alineado a ticket_retiro_qr.html → XP-80."""
    out = bytearray()
    out += _cmd_init()

    empresa = (ctx.get('empresa') or 'Ferreteria Santo Domingo').strip()
    venta_id = ctx.get('venta_id')
    folio = (ctx.get('folio_barcode') or f'VL{int(venta_id or 0):06d}').strip()
    fecha = (ctx.get('fecha_fmt') or '').strip()
    cliente = _fold_thermal(str(ctx.get('cliente') or 'Cliente final'))
    slices = ctx.get('slices') or []
    sin_qr = (os.getenv('POS_TICKET_TERMICA_SIN_QR') or '').strip().lower() in (
        '1',
        'true',
        'si',
        'yes',
        'on',
    )

    if not slices:
        out += _cabecera_marca_bytes(empresa)
        out += _align(1)
        out += _bold(True)
        out += _line('TICKET DE RETIRO')
        out += _bold(False)
        out += _line(f'N {venta_id} · {folio}')
        out += _align(0)
        out += _barcode_code128(folio)
        out += b'\n\n\n\n\n'
        out += _cmd_cut()
        return bytes(out)

    for i, sl in enumerate(slices):
        # Misma jerarquía que la vista HTML
        out += _cabecera_marca_bytes(empresa)
        out += _align(1)
        out += _bold(True)
        out += _line('TICKET DE RETIRO')
        out += _bold(False)
        out += _line('NO ES BOLETA')
        out += _line('Comprobante para retirar mercaderia')
        canal = (sl.get('canal') or 'Tienda').strip()
        label = _fold_thermal(str(sl.get('canal_label') or f'RETIRO - {canal}'))
        out += _bold(True)
        out += _size_double_height(True)
        out += _line(label.upper()[:COLS])
        out += _size_double_height(False)
        out += _bold(False)
        out += _line(f'{folio} - Ticket N {venta_id}')
        if fecha:
            out += _line(fecha)
        out += _line(f'Cliente: {cliente}'[:COLS])
        out += _align(0)

        # HTML: QR primero, luego Code128 (lector Retiros)
        qr_url = (sl.get('qr_url') or '').strip()
        out += b'\n'
        out += _align(1)
        if qr_url and not sin_qr:
            out += _qr_model2(qr_url, module_size=6)
        out += _barcode_code128(folio)
        out += _line('Escanee QR o barras en Retiros')
        out += _align(0)

        out += _sep('-')
        out += _bold(True)
        out += _line('PRODUCTO'.ljust(COLS - 6) + 'CANT'.rjust(6))
        out += _bold(False)
        out += _sep('-')
        for ln in sl.get('lineas') or []:
            nom = _fold_thermal(str(ln.get('nombre') or '-'))[: COLS - 6]
            cant = str(int(ln.get('cantidad') or 0)).rjust(6)
            out += _line(f'{nom.ljust(COLS - 6)}{cant}')
        out += _sep('=')
        out += _align(2)
        out += _bold(True)
        out += _line(f"Subtotal {canal}: ${_fmt_clp_tabla(sl.get('subtotal', 0))}")
        out += _bold(False)
        out += _align(0)

        out += _align(1)
        out += _line('La boleta fiscal es la de su pago')
        out += _align(0)

        # Precicado físico: corte total entre mitades (dos papeles, no un solo rollo).
        out += b'\n\n\n'
        if i < len(slices) - 1:
            out += _align(1)
            out += _bold(True)
            out += _line('>>> Corte / Precicado <<<')
            out += _bold(False)
            out += _align(0)
            out += b'\n\n'
            out += _cmd_cut()
            out += _cmd_init()
        else:
            out += b'\n\n'
            out += _cmd_cut()

    return bytes(out)


def listar_impresoras_windows() -> list[str]:
    if sys.platform != 'win32':
        return []
    try:
        import win32print

        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []


def _zpl_preferir_copy_b() -> bool:
    """COPY /b alternativo; en algunos PCs win32 RAW es el que realmente imprime."""
    v = (os.getenv('ZEBRA_ZPL_METODO') or 'win32').strip().lower()
    return v in ('copy', 'copy_b')


def _zebra_zpl_host() -> str:
    return (os.getenv('ZEBRA_ZPL_HOST') or os.getenv('ZEBRA_IMPRESORA_HOST') or '').strip()


def _zebra_zpl_port() -> int:
    raw = (os.getenv('ZEBRA_ZPL_PORT') or '9100').strip()
    try:
        return int(raw)
    except ValueError:
        return 9100


def _zpl_metodo_tcp_forzado() -> bool:
    return (os.getenv('ZEBRA_ZPL_METODO') or '').strip().lower() == 'tcp'


def _enviar_zpl_tcp(data: bytes, host: str | None = None, port: int | None = None) -> dict[str, Any]:
    """ZPL directo por RJ45 / red (puerto RAW 9100 típico en Zebra)."""
    import socket

    h = (host or _zebra_zpl_host()).strip()
    p = int(port or _zebra_zpl_port())
    if not h:
        return {'ok': False, 'error': 'sin_host', 'mensaje': 'Configure ZEBRA_ZPL_HOST (IP de la impresora).'}
    payload = _zpl_a_bytes(data)
    try:
        with socket.create_connection((h, p), timeout=10) as sock:
            sock.sendall(payload)
        return {'ok': True, 'metodo': 'tcp_zpl', 'host': h, 'port': p, 'bytes': len(payload)}
    except Exception as ex:
        return {
            'ok': False,
            'error': 'tcp_zpl',
            'mensaje': str(ex)[:300],
            'host': h,
            'port': p,
        }


def _zpl_a_bytes(data: bytes | str) -> bytes:
    if isinstance(data, bytes):
        raw = data
    else:
        raw = (data or '').encode('ascii', errors='replace')
    if not raw.startswith(b'^XA'):
        raw = b'^XA\n' + raw
    if not raw.rstrip().endswith(b'^XZ'):
        raw = raw.rstrip() + b'\n^XZ\n'
    return raw


def _enviar_raw_copy_b(data: bytes, printer_name: str) -> dict[str, Any]:
    """Envía binario a cola Windows con COPY /b (recomendado Zebra ZPL)."""
    nombre = (printer_name or '').strip()
    if not nombre:
        return {'ok': False, 'error': 'sin_nombre', 'mensaje': 'Sin nombre de impresora.'}
    path = ''
    try:
        fd, path = tempfile.mkstemp(suffix='.zpl', prefix='lhexia_')
        os.write(fd, data)
        os.close(fd)
        cmd = ['cmd', '/c', 'copy', '/b', path, nombre]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or '').strip()[:300]
            return {'ok': False, 'error': 'copy_b', 'mensaje': err or 'COPY /b falló', 'impresora': nombre}
        return {'ok': True, 'impresora': nombre, 'bytes': len(data), 'metodo': 'copy_b'}
    except Exception as ex:
        return {'ok': False, 'error': 'copy_b', 'mensaje': str(ex)[:300], 'impresora': nombre}
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _escribir_raw_win32(data: bytes, printer_name: str, *, titulo: str = 'LhexIA RAW') -> dict[str, Any]:
    """WritePrinter con DOC_INFO nivel 2 (datatype RAW explícito)."""
    try:
        import win32print
    except ImportError:
        return {'ok': False, 'error': 'pywin32', 'mensaje': 'Instale pywin32: pip install pywin32'}

    hprinter = None
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        # Nivel 1 + tupla RAW (compatible pywin32; el dict nivel 2 falla en algunos builds).
        win32print.StartDocPrinter(hprinter, 1, (titulo, None, 'RAW'))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
        return {'ok': True, 'impresora': printer_name, 'bytes': len(data), 'metodo': 'win32_raw'}
    except Exception as ex:
        return {'ok': False, 'error': 'impresion', 'mensaje': str(ex)[:300], 'impresora': printer_name}
    finally:
        if hprinter:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass


def _impresora_abrible(nombre: str) -> bool:
    """True si la cola existe y no es puerto FILE (sin enviar trabajo de prueba al spooler)."""
    info = describir_cola_impresora(nombre)
    return bool(info.get('abrible'))


def describir_cola_impresora(nombre: str) -> dict[str, Any]:
    """Puerto, driver y advertencias de una cola Windows (Zebra / RAW)."""
    nombre = (nombre or '').strip()
    out: dict[str, Any] = {
        'nombre': nombre,
        'puerto': '',
        'driver': '',
        'abrible': False,
        'advertencias': [],
    }
    if sys.platform != 'win32' or not nombre:
        return out
    hprinter = None
    try:
        import win32print

        hprinter = win32print.OpenPrinter(nombre)
        info = win32print.GetPrinter(hprinter, 2)
        port = (info.get('pPortName') or '').strip()
        driver = (info.get('pDriverName') or '').strip()
        out['puerto'] = port
        out['driver'] = driver
        out['print_processor'] = (info.get('pPrintProcessor') or '').strip()
        out['abrible'] = True
        proc = (out.get('print_processor') or '').lower()
        if proc and proc != 'winprint':
            out['advertencias'].append(
                f'Procesador de impresión «{out["print_processor"]}» — en Propiedades → Avanzado '
                'debe ser WinPrint para ZPL RAW.'
            )
        port_u = port.upper()
        if port_u.startswith('FILE:'):
            out['abrible'] = False
            out['advertencias'].append(
                'La cola usa puerto FILE (guarda documentos en disco). En Propiedades de impresora '
                'cambie el puerto a USB de la Zebra.'
            )
        elif not port_u or port_u in ('NUL:', 'NULL:'):
            out['abrible'] = False
            out['advertencias'].append('La cola no tiene puerto físico asignado.')
        drv_l = driver.lower()
        nom_l = nombre.lower()
        if 'generic printer' in drv_l or 'generic printer' in nom_l:
            out['advertencias'].append(
                'Driver «Generic Printer» es virtual (SDK Zebra): guarda archivos, no imprime en hardware. '
                'Use «ZDesigner GX420d» o «Zebra GX420d - ZPL» con puerto USB.'
            )
        if 'for developers' in nom_l:
            out['advertencias'].append(
                '«ZDesigner for Developers» no imprime en la GX420d física; elija la cola USB/ZPL.'
            )
    except Exception as ex:
        out['advertencias'].append(str(ex)[:160])
    finally:
        if hprinter:
            try:
                import win32print

                win32print.ClosePrinter(hprinter)
            except Exception:
                pass
    return out


def _es_impresora_virtual(nombre: str) -> bool:
    n = (nombre or '').lower()
    return any(
        x in n
        for x in (
            'pdf',
            'onenote',
            'fax',
            'xps',
            'microsoft print',
            'send to',
        )
    )


def _es_cola_zebra(nombre: str) -> bool:
    """True si la cola Windows parece impresora de etiquetas Zebra (no XP-80 / POS)."""
    n = (nombre or '').strip().lower()
    if not n or _es_impresora_virtual(n):
        return False
    virtuales_zebra = (
        'generic printer',
        'for developers',
        'redirected',
        'print to file',
    )
    if any(v in n for v in virtuales_zebra):
        return False
    bloqueadas = ('xp-80', 'xprinter', 'x-printer', 'epson', 'canon', 'hp ', 'brother')
    if any(b in n for b in bloqueadas):
        return False
    hints = (
        'zebra',
        'zdesigner',
        'gx420',
        'gk420',
        'gt800',
        'zd420',
        'zd620',
        'lp2824',
        'tlp2844',
        'zpl',
        '105sl',
    )
    return any(h in n for h in hints)


def listar_impresoras_zebra() -> list[str]:
    return [p for p in listar_impresoras_windows() if _es_cola_zebra(p)]


def listar_colas_zebra_detalle() -> list[dict[str, Any]]:
    """Colas Zebra con puerto/driver; las usables (USB, etc.) primero."""
    out: list[dict[str, Any]] = []
    for nombre in listar_impresoras_zebra():
        d = describir_cola_impresora(nombre)
        d['usable'] = bool(d.get('abrible'))
        out.append(d)
    out.sort(
        key=lambda x: (
            0 if x.get('usable') else 1,
            0 if str(x.get('puerto') or '').upper().startswith('USB') else 1,
            (x.get('nombre') or '').lower(),
        )
    )
    return out


def elegir_cola_zebra_preferida(preferida: str | None = None) -> str:
    """Cola Zebra para imprimir: prioriza USB/hardware sobre FILE/LPT mal configurados."""
    colas = listar_colas_zebra_detalle()
    pref = (preferida or '').strip()
    if pref:
        for d in colas:
            if d.get('nombre') == pref and d.get('usable'):
                return pref
    for d in colas:
        if d.get('usable') and str(d.get('puerto') or '').upper().startswith('USB'):
            return str(d.get('nombre') or '')
    for d in colas:
        if d.get('usable'):
            return str(d.get('nombre') or '')
    return pref or (str(colas[0].get('nombre') or '') if colas else '')


def _candidatos_impresora_termica(
    configurada: str | None = None,
    *,
    lista: list[str] | None = None,
) -> list[str]:
    """Orden de preferencia: nombre exacto en lista → match parcial → XP-80* → default Windows."""
    lista = lista if lista is not None else listar_impresoras_windows()
    cfg = (configurada or os.getenv('POS_IMPRESORA_NOMBRE') or '').strip()
    out: list[str] = []

    def _add(n: str | None) -> None:
        n = (n or '').strip()
        if not n or n in out:
            return
        out.append(n)

    if cfg:
        if cfg in lista:
            _add(cfg)
        else:
            cfg_l = cfg.lower()
            for p in lista:
                if cfg_l in p.lower() or p.lower() in cfg_l:
                    _add(p)
        _add(cfg)

    for p in lista:
        if _es_impresora_virtual(p):
            continue
        pl = p.lower()
        if 'xp-80' in pl or 'xprinter' in pl or 'thermal' in pl or 'termica' in pl:
            _add(p)

    for p in lista:
        if not _es_impresora_virtual(p):
            _add(p)

    if sys.platform == 'win32':
        try:
            import win32print

            _add(win32print.GetDefaultPrinter())
        except Exception:
            pass

    return out


def _candidatos_impresora_zebra(
    configurada: str | None = None,
    *,
    lista: list[str] | None = None,
) -> list[str]:
    """Cola Zebra/ZPL: no usa XP-80 ni impresora POS por defecto."""
    lista = lista if lista is not None else listar_impresoras_windows()
    cfg = (
        (configurada or '').strip()
        or (os.getenv('ZEBRA_IMPRESORA_NOMBRE') or '').strip()
        or (os.getenv('ETIQUETAS_ZEBRA_IMPRESORA') or '').strip()
    )
    out: list[str] = []

    def _add(n: str | None) -> None:
        n = (n or '').strip()
        if not n or n in out:
            return
        out.append(n)

    if cfg:
        if not _es_cola_zebra(cfg):
            pass  # ignorar cola POS (XP-80, etc.) aunque esté en la lista Windows
        elif cfg in lista:
            _add(cfg)
        else:
            cfg_l = cfg.lower()
            for p in lista:
                if _es_cola_zebra(p) and (cfg_l in p.lower() or p.lower() in cfg_l):
                    _add(p)
            if _es_cola_zebra(cfg):
                _add(cfg)

    zebra_cols = [p for p in lista if _es_cola_zebra(p) and not _es_impresora_virtual(p)]
    usables = [p for p in zebra_cols if _impresora_abrible(p)]
    for p in usables + [p for p in zebra_cols if p not in usables]:
        _add(p)

    return out


def resolver_nombre_impresora(configurada: str | None = None) -> str | None:
    """Primera impresora de la lista que Windows puede abrir (cola válida)."""
    for candidato in _candidatos_impresora_termica(configurada):
        if _impresora_abrible(candidato):
            return candidato
    return None


def resolver_nombre_impresora_zebra(configurada: str | None = None) -> str | None:
    """Primera cola Zebra abrible; no hace fallback a XP-80 / default Windows."""
    for candidato in _candidatos_impresora_zebra(configurada):
        if _impresora_abrible(candidato):
            return candidato
    return None


def enviar_raw_escpos(data: bytes, printer_name: str | None = None) -> dict[str, Any]:
    """Envía bytes RAW a impresora Windows."""
    if sys.platform != 'win32':
        return {'ok': False, 'error': 'plataforma', 'mensaje': 'Solo Windows (PC tienda).'}
    if not data:
        return {'ok': False, 'error': 'vacio', 'mensaje': 'Sin datos para imprimir.'}
    candidatos = _candidatos_impresora_termica(printer_name)
    nombre = resolver_nombre_impresora(printer_name)
    if not nombre:
        lista = listar_impresoras_windows()
        return {
            'ok': False,
            'error': 'sin_impresora',
            'mensaje': (
                'No hay impresora térmica usable. En .env.local use POS_IMPRESORA_NOMBRE=XP-80 '
                '(evite nombres eliminados en Windows). '
                f'Detectadas: {", ".join(lista[:6]) or "ninguna"}'
            ),
            'candidatos': candidatos[:8],
        }
    try:
        import win32print
    except ImportError:
        return {
            'ok': False,
            'error': 'pywin32',
            'mensaje': 'Instale pywin32: pip install pywin32',
        }

    hprinter = None
    try:
        hprinter = win32print.OpenPrinter(nombre)
        job = win32print.StartDocPrinter(hprinter, 1, ('LhexIA Vale', None, 'RAW'))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
        return {'ok': True, 'impresora': nombre, 'bytes': len(data)}
    except Exception as ex:
        return {'ok': False, 'error': 'impresion', 'mensaje': str(ex)[:300], 'impresora': nombre}
    finally:
        if hprinter:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass


def enviar_raw_zpl(data: bytes, printer_name: str | None = None, *, host: str | None = None) -> dict[str, Any]:
    """Envía ZPL RAW a Zebra: TCP (RJ45) si hay host, si no cola Windows."""
    if sys.platform != 'win32':
        return {'ok': False, 'error': 'plataforma', 'mensaje': 'Solo Windows (PC tienda).'}
    if not data:
        return {'ok': False, 'error': 'vacio', 'mensaje': 'Sin datos para imprimir.'}

    host_tcp = (host or _zebra_zpl_host()).strip()
    if host_tcp or _zpl_metodo_tcp_forzado():
        res_tcp = _enviar_zpl_tcp(data, host=host_tcp or None)
        if res_tcp.get('ok') or _zpl_metodo_tcp_forzado():
            if res_tcp.get('ok'):
                res_tcp['tipo'] = 'zebra_zpl'
            return res_tcp

    explicit = (printer_name or '').strip()
    if explicit and not _es_cola_zebra(explicit):
        return {
            'ok': False,
            'error': 'impresora_no_zebra',
            'mensaje': (
                f'«{explicit}» no es una cola Zebra. En el panel elija '
                '«Zebra GX420d - ZPL» o «ZDesigner GX420d» (no XP-80 de tickets).'
            ),
        }
    candidatos = _candidatos_impresora_zebra(printer_name)
    nombre = resolver_nombre_impresora_zebra(printer_name)
    if not nombre:
        lista = listar_impresoras_windows()
        return {
            'ok': False,
            'error': 'sin_impresora_zebra',
            'mensaje': (
                'No hay impresora Zebra usable. Elija la cola en el panel Zebra o configure '
                'ZEBRA_IMPRESORA_NOMBRE en .env.local (nombre exacto de Windows). '
                f'Detectadas: {", ".join(lista[:8]) or "ninguna"}'
            ),
            'candidatos': candidatos[:8],
        }
    try:
        import win32print
    except ImportError:
        return {
            'ok': False,
            'error': 'pywin32',
            'mensaje': 'Instale pywin32: pip install pywin32',
        }

    desc = describir_cola_impresora(nombre)
    if not desc.get('abrible'):
        msg = (
            desc['advertencias'][0]
            if desc.get('advertencias')
            else f'La cola «{nombre}» no acepta impresión RAW en hardware.'
        )
        return {
            'ok': False,
            'error': 'cola_no_hardware',
            'mensaje': msg,
            'impresora': nombre,
            'puerto': desc.get('puerto') or '',
            'driver': desc.get('driver') or '',
        }

    payload = _zpl_a_bytes(data)
    advertencias = list(desc.get('advertencias') or [])

    res = _escribir_raw_win32(payload, nombre, titulo='LhexIA ZPL')
    if not res.get('ok') and _zpl_preferir_copy_b():
        res = _enviar_raw_copy_b(payload, nombre)
    elif not res.get('ok'):
        res_fb = _enviar_raw_copy_b(payload, nombre)
        if res_fb.get('ok'):
            res = res_fb
        else:
            res['mensaje'] = (
                (res.get('mensaje') or 'win32 RAW falló')
                + ' · copy: '
                + (res_fb.get('mensaje') or 'error')
            )

    if res.get('ok'):
        res['tipo'] = 'zebra_zpl'
        res['puerto'] = desc.get('puerto') or ''
        if advertencias:
            res['advertencia'] = advertencias[0]
        return res
    res['impresora'] = nombre
    return res
