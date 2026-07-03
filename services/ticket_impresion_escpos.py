"""Impresión térmica ESC/POS (XPrinter XP-80T y compatibles 80 mm)."""
from __future__ import annotations

import os
import sys
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
    """Doble alto+ancho (cabecera tipo ticket HTML)."""
    return GS + b'!' + (bytes([0x11]) if on else bytes([0x00]))


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
    """QR modelo 2 (compatible Epson / XPrinter XP-80)."""
    data = (text or '').strip().encode('utf-8')
    if not data:
        return b''
    out = bytearray()
    # Almacenar símbolo QR (fn=80)
    store_params = bytes([0x31, 0x50, 0x30, module_size, 0x31]) + data
    pl = len(store_params)
    out += GS + b'(k' + bytes([pl % 256, pl // 256]) + store_params
    # Imprimir QR almacenado (fn=81)
    out += GS + b'(k' + bytes([3, 0, 0x31, 0x51, 0x30])
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

    empresa = (ctx.get('empresa') or 'Ferreteria').strip()
    venta_id = ctx.get('venta_id')
    folio = (ctx.get('folio_barcode') or f'VL{int(venta_id or 0):06d}').strip()

    # --- Cabecera (como HTML: nombre comercial centrado) ---
    out += _align(1)
    out += _size_double(True)
    out += _bold(True)
    out += _line(empresa[:COLS // 2])
    out += _bold(False)
    out += _size_double(False)
    direccion = (ctx.get('direccion_empresa') or '').strip()
    tel_hdr = (ctx.get('telefono_contacto') or '').strip()
    if direccion:
        out += _line(direccion[:COLS])
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

    out += _sep('=')
    out += _align(2)
    out += _bold(True)
    out += _size_double(True)
    if bloques:
        out += _line('TOTAL A PAGAR')
    out += _line(f'${_fmt_clp_tabla(ctx.get("total", 0))}')
    out += _size_double(False)
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

    out += b'\n\n\n'
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
        out['abrible'] = True
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


def enviar_raw_zpl(data: bytes, printer_name: str | None = None) -> dict[str, Any]:
    """Envía ZPL RAW solo a cola Zebra (no XP-80 / POS)."""
    if sys.platform != 'win32':
        return {'ok': False, 'error': 'plataforma', 'mensaje': 'Solo Windows (PC tienda).'}
    if not data:
        return {'ok': False, 'error': 'vacio', 'mensaje': 'Sin datos para imprimir.'}
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

    hprinter = None
    try:
        hprinter = win32print.OpenPrinter(nombre)
        job = win32print.StartDocPrinter(hprinter, 1, ('LhexIA ZPL', None, 'RAW'))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
        advertencias = list(desc.get('advertencias') or [])
        res: dict[str, Any] = {
            'ok': True,
            'impresora': nombre,
            'bytes': len(data),
            'tipo': 'zebra_zpl',
            'puerto': desc.get('puerto') or '',
        }
        if advertencias:
            res['advertencia'] = advertencias[0]
        return res
    except Exception as ex:
        return {'ok': False, 'error': 'impresion', 'mensaje': str(ex)[:300], 'impresora': nombre}
    finally:
        if hprinter:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass
