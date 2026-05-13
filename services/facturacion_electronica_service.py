# -*- coding: utf-8 -*-
"""
Facturación electrónica Chile (SII) — Fase 1.

Orquestación, XML de prueba (lxml), stubs de firma XML-DSig y cliente SOAP.
El certificado digital (.pfx) no debe versionarse: colóquelo bajo `instance/certs/`
(carpeta ignorada por Git en este proyecto) o en otra ruta privada del servidor, y
apunte `SII_CERT_PFX_PATH` a esa ubicación (absoluta o relativa a la raíz del ERP).

Política de negocio (ERP): el cobro no se bloquea si el SII falla; las ventas pueden
quedar en dte_estado='PENDIENTE_ENVIO' para cola / reintento (worker o panel).
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Callable, Dict, Optional, Tuple

_logger_fe = logging.getLogger(__name__)

# Raíz del proyecto (carpeta que contiene `services/`) para resolver rutas .pfx relativas.
_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_ERP_ROOT = os.path.normpath(os.path.join(_SERVICES_DIR, '..'))

# Tipos DTE usados en ferretería / POS
DTE_TIPO_FACTURA_AFECTA = 33
DTE_TIPO_BOLETA_AFECTA = 39

# Estados persistidos en ventas.dte_estado
DTE_ESTADO_PENDIENTE_ENVIO = 'PENDIENTE_ENVIO'
DTE_ESTADO_ENVIADO = 'ENVIADO'
DTE_ESTADO_ACEPTADO = 'ACEPTADO'
DTE_ESTADO_RECHAZADO = 'RECHAZADO'
DTE_ESTADO_ERROR_FIRMA = 'ERROR_FIRMA'
DTE_ESTADO_ERROR_ENVIO = 'ERROR_ENVIO'


def _resolver_ruta_pfx(raw: str) -> str:
    """
    Normaliza la ruta al .pfx: absoluta tal cual; relativa respecto a la raíz del ERP
    (directorio padre de `services/`), p. ej. instance/certs/emisor.pfx
    """
    p = (raw or '').strip().strip('"').strip("'")
    if not p:
        return ''
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return os.path.normpath(p)
    return os.path.normpath(os.path.join(_ERP_ROOT, p))


def obtener_config_certificado() -> Dict[str, str]:
    """Ruta al .pfx y credenciales solo desde entorno (nunca en código ni Git)."""
    raw_path = (os.getenv('SII_CERT_PFX_PATH') or '').strip()
    amb = (os.getenv('SII_AMBIENTE') or 'certificacion').strip().lower()
    # Sinónimos habituales para entorno de certificación / Maullín
    if amb in ('cert', 'pruebas', 'prueba', 'qa', 'maullin'):
        amb = 'certificacion'
    if amb in ('prod', 'palena', 'produccion'):
        amb = 'produccion'
    return {
        'pfx_path': raw_path,
        'pfx_path_resolved': _resolver_ruta_pfx(raw_path),
        'pfx_password': (os.getenv('SII_CERT_PFX_PASSWORD') or '').strip(),
        'pfx_password_file': (os.getenv('SII_CERT_PFX_PASSWORD_FILE') or '').strip(),
        'ambiente': amb,
    }


def _leer_password_pfx_texto_plano(cfg: Dict[str, str]) -> str:
    """
    Contraseña del contenedor PKCS#12: variable de entorno o primera línea de archivo
    (SII_CERT_PFX_PASSWORD_FILE, ruta relativa al ERP o absoluta). Elimina BOM y espacios.
    """
    p = (cfg.get('pfx_password') or '').replace('\ufeff', '').strip()
    if p:
        return p
    raw_file = (cfg.get('pfx_password_file') or '').strip()
    if not raw_file:
        return ''
    path = _resolver_ruta_pfx(raw_file) if not os.path.isabs(raw_file) else os.path.normpath(raw_file)
    if not os.path.isfile(path):
        _logger_fe.warning('SII_CERT_PFX_PASSWORD_FILE no existe o no es legible: %s', path)
        return ''
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            line = fh.readline() or ''
    except OSError as ex:
        _logger_fe.warning('No se pudo leer SII_CERT_PFX_PASSWORD_FILE: %s', ex)
        return ''
    return line.replace('\ufeff', '').strip()


def construir_contexto_dte_prueba(dte_tipo: int, folio: int = 1) -> Dict[str, Any]:
    """Datos mínimos mock para generar XML de prueba (no válido ante el SII)."""
    if dte_tipo not in (DTE_TIPO_BOLETA_AFECTA, DTE_TIPO_FACTURA_AFECTA):
        dte_tipo = DTE_TIPO_BOLETA_AFECTA
    return {
        'dte_tipo': int(dte_tipo),
        'folio': int(folio),
        'rut_emisor': '76192028-5',
        'razon_social_emisor': 'DEMO FERRETERIA SPA',
        'rut_receptor': '66666666-6',
        'razon_social_receptor': 'CLIENTE BOLETA',
        'fecha_emision': date.today().isoformat(),
        'monto_neto': 1000,
        'monto_iva': 190,
        'monto_total': 1190,
        'items': [
            {'nombre': 'Producto demo 1', 'cantidad': 1, 'precio': 1190},
        ],
    }


def generar_xml_dte_prueba_lxml(contexto: Dict[str, Any]) -> bytes:
    """
    Arma un XML bien formado de referencia (estructura genérica tipo DTE).
    Fase posterior: namespaces oficiales, TED con CAF, validación XSD SII.
    """
    from lxml import etree

    NS = 'http://www.sii.cl/SiiDte'
    nsmap = {None: NS}
    root = etree.Element('{%s}DTE' % NS, nsmap=nsmap)
    root.set('version', '1.0')

    doc = etree.SubElement(root, '{%s}Documento' % NS)
    enc = etree.SubElement(doc, '{%s}Encabezado' % NS)
    iddoc = etree.SubElement(enc, '{%s}IdDoc' % NS)
    etree.SubElement(iddoc, '{%s}TipoDTE' % NS).text = str(int(contexto['dte_tipo']))
    etree.SubElement(iddoc, '{%s}Folio' % NS).text = str(int(contexto['folio']))
    etree.SubElement(iddoc, '{%s}FchEmis' % NS).text = str(contexto['fecha_emision'])

    emisor = etree.SubElement(enc, '{%s}Emisor' % NS)
    etree.SubElement(emisor, '{%s}RUTEmisor' % NS).text = str(contexto['rut_emisor'])
    etree.SubElement(emisor, '{%s}RznSoc' % NS).text = str(contexto['razon_social_emisor'])

    receptor = etree.SubElement(enc, '{%s}Receptor' % NS)
    etree.SubElement(receptor, '{%s}RUTRecep' % NS).text = str(contexto['rut_receptor'])
    etree.SubElement(receptor, '{%s}RznSocRecep' % NS).text = str(contexto['razon_social_receptor'])

    totales = etree.SubElement(enc, '{%s}Totales' % NS)
    etree.SubElement(totales, '{%s}MntNeto' % NS).text = str(int(contexto['monto_neto']))
    etree.SubElement(totales, '{%s}IVA' % NS).text = str(int(contexto['monto_iva']))
    etree.SubElement(totales, '{%s}MntTotal' % NS).text = str(int(contexto['monto_total']))

    detalle = etree.SubElement(doc, '{%s}Detalle' % NS)
    for i, it in enumerate(contexto.get('items') or [], start=1):
        item = etree.SubElement(detalle, '{%s}Item' % NS)
        item.set('NroLinDet', str(i))
        etree.SubElement(item, '{%s}NmbItem' % NS).text = str(it.get('nombre', 'Item'))
        etree.SubElement(item, '{%s}QtyItem' % NS).text = str(int(it.get('cantidad', 1)))
        etree.SubElement(item, '{%s}PrcItem' % NS).text = str(int(it.get('precio', 0)))

    stub = etree.SubElement(doc, '{%s}StubFase1' % NS)
    stub.text = 'Sin TED ni firma — solo prueba local de generación XML'

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding='utf-8',
        pretty_print=True,
    )


def validar_xml_bien_formado(xml_bytes: bytes) -> bool:
    try:
        from lxml import etree

        etree.fromstring(xml_bytes)
        return True
    except Exception:
        return False


def firmar_xml_dte(xml_bytes: bytes) -> Tuple[bytes, str]:
    """
    Firma XML-DSig del DTE con el .pfx centralizado del emisor (PKCS#12).
    Retorna (xml_firmado_o_original, estado).

    - Sin `SII_CERT_PFX_PATH` (vacío): no firma; estado STUB_SIN_CERTIFICADO.
    - Con ruta configurada pero archivo inexistente: STUB_ARCHIVO_INEXISTENTE.
    - Con archivo y clave válidos: FIRMADO (usa `SII_AMBIENTE` solo para lógica
      de envío SOAP cuando exista; la firma es la misma en certificación y producción).
    """
    cfg = obtener_config_certificado()
    raw = (cfg.get('pfx_path') or '').strip()
    path = cfg.get('pfx_path_resolved') or _resolver_ruta_pfx(raw)
    if not raw:
        return xml_bytes, 'STUB_SIN_CERTIFICADO'
    if not path or not os.path.isfile(path):
        return xml_bytes, 'STUB_ARCHIVO_INEXISTENTE'

    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from signxml import XMLSigner, methods

        with open(path, 'rb') as fh:
            pfx = fh.read()

        pw_plain = _leer_password_pfx_texto_plano(cfg)
        if pw_plain:
            password_candidates = [pw_plain.encode('utf-8')]
        else:
            # Algunos .pfx se exportan sin contraseña: cryptography acepta None o b'' según el archivo.
            password_candidates = [None, b'']

        private_key = certificate = None
        last_err: Optional[Exception] = None
        for password in password_candidates:
            try:
                private_key, certificate, _extra = pkcs12.load_key_and_certificates(pfx, password)
                if private_key is not None and certificate is not None:
                    break
            except ValueError as ex:
                last_err = ex
                continue
        else:
            if last_err is not None:
                raise last_err
            raise ValueError('PKCS12: no se pudo abrir el contenedor (contraseña o formato)')

        from lxml import etree

        root = etree.fromstring(xml_bytes)
        signer = XMLSigner(method=methods.enveloped, signature_algorithm='rsa-sha256')
        signed_root = signer.sign(root, key=private_key, cert=certificate)
        root_bytes = etree.tostring(
            signed_root, xml_declaration=True, encoding='utf-8', pretty_print=True
        )
        return root_bytes, 'FIRMADO'
    except ImportError:
        return xml_bytes, 'ERROR_FIRMA:dependencias_signxml'
    except Exception as ex:
        _logger_fe.exception(
            'firmar_xml_dte: fallo PKCS#12 / XML-DSig (ruta=%s)', path, exc_info=True
        )
        det = str(ex).replace('\n', ' ')
        if len(det) > 400:
            det = det[:400] + '...'
        hint = ''
        if 'Invalid password' in str(ex) or 'PKCS12' in str(ex) or 'invalid password' in det.lower():
            hint = (
                ' |Sugerencia: use la clave de EXPORTACIÓN del .pfx definida al descargar/crear el '
                'contenedor en el portal del proveedor (no el PIN del token). Revise espacios finales, '
                'comillas tipográficas en .env.local, o defina SII_CERT_PFX_PASSWORD_FILE con la clave '
                'en un archivo UTF-8 (una sola línea).'
            )
        return xml_bytes, f'ERROR_FIRMA:{type(ex).__name__}:{det}{hint}'


def crear_cliente_soap_sii() -> Any:
    """
    Cliente Zeep para Web Services SII (envío / estado).
    Fase 1: retorna None (sin WSDL ni URL activa).
    """
    try:
        import zeep  # noqa: F401
    except ImportError:
        return None
    return None


def resolver_dte_tipo_por_tipo_documento(tipo_documento: Optional[str]) -> int:
    """Mapea tipo_documento de venta (Boleta/Factura) a código SII."""
    t = (tipo_documento or '').strip().lower()
    if 'fact' in t:
        return DTE_TIPO_FACTURA_AFECTA
    return DTE_TIPO_BOLETA_AFECTA


def asignar_folio_disponible(db_session: Any, caf_model: Any, dte_tipo: int) -> Optional[Tuple[int, int]]:
    """
    Reserva el siguiente folio del primer CAF con cupo para el tipo DTE.
    Devuelve (folio, caf_id) o None si no hay CAF / agotado.
    """
    try:
        q = (
            db_session.query(caf_model)
            .filter(
                caf_model.tipo_dte == int(dte_tipo),
                caf_model.usado_hasta < caf_model.rango_hasta,
            )
            .order_by(caf_model.id.asc())
        )
        caf = q.first()
        if not caf:
            return None
        last = int(caf.usado_hasta or 0)
        r0 = int(caf.rango_desde or 0)
        r1 = int(caf.rango_hasta or 0)
        if r0 <= 0 or r1 < r0:
            return None
        if last < r0:
            nxt = r0
        elif last < r1:
            nxt = last + 1
        else:
            return None
        caf.usado_hasta = int(nxt)
        return int(nxt), int(caf.id)
    except Exception:
        return None


def construir_contexto_desde_venta(
    venta: Any,
    folio: int,
    dte_tipo: int,
    obtener_config_empresa: Callable[[], Dict[str, str]],
) -> Dict[str, Any]:
    """Contexto XML a partir de una venta cobrada (montos CLP enteros)."""
    cfg = obtener_config_empresa() if obtener_config_empresa else {}
    rut_emisor = (os.getenv('EMPRESA_RUT') or cfg.get('rut_emisor') or '76.192.028-5').strip()
    rs_emisor = (cfg.get('razon_social') or cfg.get('nombre_comercial') or 'EMPRESA').strip()
    cli = getattr(venta, 'cliente', None)
    rut_rec = '66666666-6'
    rs_rec = 'BOLETA'
    if cli:
        rut_rec = (getattr(cli, 'rut', None) or rut_rec).strip() or rut_rec
        rs_rec = (getattr(cli, 'nombre', None) or rs_rec).strip() or rs_rec
    items = []
    for d in list(getattr(venta, 'detalles', None) or []):
        prod = getattr(d, 'producto', None)
        nombre = (getattr(prod, 'nombre', None) or 'Item') if prod else 'Item'
        items.append(
            {
                'nombre': str(nombre)[:200],
                'cantidad': int(getattr(d, 'cantidad', 1) or 1),
                'precio': int(round(float(getattr(d, 'subtotal', 0) or 0))),
            }
        )
    if not items:
        items = [{'nombre': 'Venta', 'cantidad': 1, 'precio': int(round(float(venta.monto_total or 0)))}]
    neto = int(round(float(getattr(venta, 'neto', 0) or 0)))
    iva = int(round(float(getattr(venta, 'iva', 0) or 0)))
    total = int(round(float(getattr(venta, 'monto_total', 0) or 0)))
    if total <= 0:
        total = max(1, neto + iva)
    return {
        'dte_tipo': int(dte_tipo),
        'folio': int(folio),
        'rut_emisor': rut_emisor,
        'razon_social_emisor': rs_emisor,
        'rut_receptor': rut_rec,
        'razon_social_receptor': rs_rec,
        'fecha_emision': date.today().isoformat(),
        'monto_neto': neto,
        'monto_iva': iva,
        'monto_total': total,
        'items': items,
    }


def post_cobro_emision_fe(
    db_session: Any,
    venta: Any,
    caf_model: Any,
    obtener_config_empresa: Callable[[], Dict[str, str]],
    logger: Any,
) -> str:
    """
    Emisión FE tras commit del cobro: savepoint aísla folio CAF; si falla firma/SOAP
    revierte folio y deja la venta en PENDIENTE_ENVIO sin tocar cobro/stock.

    Retorna el `dte_estado` a mostrar al cliente (ENVIADO si SOAP ok con track_id;
    con stub SOAP suele caer en PENDIENTE_ENVIO).
    """
    dte_tipo = resolver_dte_tipo_por_tipo_documento(getattr(venta, 'tipo_documento', None))
    try:
        with db_session.begin_nested():
            pair = asignar_folio_disponible(db_session, caf_model, dte_tipo)
            if not pair:
                raise ValueError('sin_caf_o_folios')
            folio, caf_id = pair
            venta.nro_documento = int(folio)
            venta.caf_id = int(caf_id)
            ctx = construir_contexto_desde_venta(venta, folio, dte_tipo, obtener_config_empresa)
            xml_raw = generar_xml_dte_prueba_lxml(ctx)
            xml_firma, estado_firma = firmar_xml_dte(xml_raw)
            if (estado_firma or '').startswith('ERROR_FIRMA'):
                raise RuntimeError(estado_firma)
            ambiente = (obtener_config_certificado().get('ambiente') or '').strip()
            track_id, estado_envio = enviar_dte_soap(xml_firma, ambiente=ambiente)
            if estado_envio != 'ok' or not (track_id or '').strip():
                raise RuntimeError(estado_envio or 'soap_sin_track')
            venta.dte_tipo = int(dte_tipo)
            venta.dte_estado = DTE_ESTADO_ENVIADO
            venta.dte_track_id = (track_id or '')[:50]
        return str(getattr(venta, 'dte_estado', None) or DTE_ESTADO_ENVIADO)
    except Exception as ex:
        try:
            db_session.refresh(venta)
        except Exception:
            pass
        logger.error(
            'FE Error: Falló emisión inmediata. Pasando a cola de reintentos. venta_id=%s detalle=%s',
            getattr(venta, 'id', None),
            ex,
            exc_info=False,
        )
        try:
            marcar_venta_dte_pendiente_envio(venta, dte_tipo)
        except Exception:
            logger.exception('FE: no se pudo marcar PENDIENTE_ENVIO en venta_id=%s', getattr(venta, 'id', None))
        return DTE_ESTADO_PENDIENTE_ENVIO


def enviar_dte_soap(xml_firmado: bytes, ambiente: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Envía el DTE firmado al SII (stub Fase 1).
    Retorna (track_id, estado).
    """
    _ = xml_firmado, ambiente
    cli = crear_cliente_soap_sii()
    if cli is None:
        return None, 'STUB_NO_ENVIO'
    return None, 'STUB_NO_ENVIO'


def orquestar_emision_post_cobro(
    venta_id: int,
    dte_tipo: int,
    *,
    forzar_envio_sync: bool = False,
) -> Dict[str, Any]:
    """
    Compatibilidad / diagnóstico. La emisión acoplada al cobro usa `post_cobro_emision_fe`.
    """
    _ = venta_id, dte_tipo, forzar_envio_sync
    return {
        'ok': True,
        'pasos': [
            'asignar_folio_caf',
            'generar_xml',
            'timbrar_ted',
            'firmar',
            'persistir_xml',
            'enviar_soap_o_encolar',
        ],
        'nota': 'Stub Fase 1 — sin efecto en BD aquí; use marcar_venta_dte_pendiente_envio desde la capa de venta.',
    }


def marcar_venta_dte_pendiente_envio(venta_obj: Any, dte_tipo: int) -> None:
    """Marca la venta para reintento asíncrono (la sesión la confirma el llamador)."""
    try:
        venta_obj.dte_tipo = int(dte_tipo)
        venta_obj.dte_estado = DTE_ESTADO_PENDIENTE_ENVIO
    except Exception:
        pass


def emitir_prueba_xml(dte_tipo: int, folio: int = 1) -> Dict[str, Any]:
    """Usado por la ruta admin: genera XML mock, intento de firma opcional, validación."""
    ctx = construir_contexto_dte_prueba(dte_tipo, folio=folio)
    xml_raw = generar_xml_dte_prueba_lxml(ctx)
    xml_firma, estado_firma = firmar_xml_dte(xml_raw)
    track_id, estado_envio = enviar_dte_soap(xml_firma)
    cfg_cert = obtener_config_certificado()
    res = cfg_cert.get('pfx_path_resolved') or ''
    cert_ok = bool((cfg_cert.get('pfx_path') or '').strip() and res and os.path.isfile(res))
    return {
        'ok': True,
        'dte_tipo': ctx['dte_tipo'],
        'folio': ctx['folio'],
        'xml_utf8': xml_firma.decode('utf-8', errors='replace'),
        'xml_valido': validar_xml_bien_formado(xml_firma),
        'estado_firma': estado_firma,
        'estado_envio': estado_envio,
        'track_id': track_id,
        'cert_configurado': cert_ok,
        'sii_ambiente': cfg_cert.get('ambiente'),
    }


def reintentar_envio_dte_venta(venta_id: int) -> Dict[str, Any]:
    """Reservado para worker / panel admin (Fase 2)."""
    return {'ok': False, 'venta_id': venta_id, 'motivo': 'no_implementado_fase1'}
