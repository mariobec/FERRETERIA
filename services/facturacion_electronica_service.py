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
# Actividad económica SII: venta al por menor de ferretería y materiales de construcción
ACTECO_FERRETERIA_RETAIL = '475200'

# Estados persistidos en ventas.dte_estado
DTE_ESTADO_PENDIENTE_ENVIO = 'PENDIENTE_ENVIO'
DTE_ESTADO_ENVIADO = 'ENVIADO'
DTE_ESTADO_ACEPTADO = 'ACEPTADO'
DTE_ESTADO_RECHAZADO = 'RECHAZADO'
DTE_ESTADO_ERROR_FIRMA = 'ERROR_FIRMA'
DTE_ESTADO_ERROR_ENVIO = 'ERROR_ENVIO'
DTE_ESTADO_FALLO_MATEMATICO = 'FALLO_MATEMATICO'
# Boleta electrónica la emite Multicaja/Klap; el ERP no envía DTE 39 al SII.
DTE_ESTADO_EXTERNO_BOLETA = 'EXTERNO_MULTICAJA'


def fe_solo_factura_en_erp() -> bool:
    """Política Santo Domingo: LhexIA solo FE factura (33); boletas vía Multicaja."""
    v = (os.getenv('SII_FE_SOLO_FACTURA') or '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')


def debe_emitir_fe_en_erp(tipo_documento: Optional[str]) -> bool:
    if not fe_solo_factura_en_erp():
        return True
    return resolver_dte_tipo_por_tipo_documento(tipo_documento) == DTE_TIPO_FACTURA_AFECTA


def marcar_venta_boleta_sin_fe_erp(venta_obj: Any) -> None:
    """Venta cobrada con boleta: sin folio CAF ni cola SII en el ERP."""
    try:
        venta_obj.dte_tipo = int(DTE_TIPO_BOLETA_AFECTA)
        venta_obj.dte_estado = DTE_ESTADO_EXTERNO_BOLETA
        venta_obj.nro_documento = None
        venta_obj.caf_id = None
        venta_obj.dte_track_id = None
    except Exception:
        pass


def _persist_xml_dte_firmado_safe(
    erp_root: Optional[str],
    ambiente: str,
    venta_id: int,
    folio: int,
    dte_tipo: int,
    xml_firma: bytes,
) -> None:
    """Guarda copia local del XML firmado (no bloquea emisión si falla el disco)."""
    root = (erp_root or '').strip()
    if not root or not xml_firma or int(venta_id) <= 0:
        return
    try:
        from services import facturacion_dte_storage as _st

        _st.persistir_xml_dte_firmado(
            root, ambiente or 'certificacion', int(venta_id), int(folio), int(dte_tipo), xml_firma
        )
    except Exception:
        _logger_fe.warning('No se pudo persistir XML DTE firmado (venta_id=%s)', venta_id, exc_info=True)


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


def ambiente_sii_es_certificacion() -> bool:
    cfg = obtener_config_certificado()
    return (cfg.get('ambiente') or 'certificacion') == 'certificacion'


def construir_contexto_dte_prueba(dte_tipo: int, folio: int = 1) -> Dict[str, Any]:
    """Datos mock para XML de prueba / Maullín (boleta 39 o factura 33)."""
    if dte_tipo not in (DTE_TIPO_BOLETA_AFECTA, DTE_TIPO_FACTURA_AFECTA):
        dte_tipo = DTE_TIPO_BOLETA_AFECTA
    rut_em = (os.getenv('EMPRESA_RUT') or '8054120-1').strip()
    rs_em = (os.getenv('EMPRESA_RAZON_SOCIAL') or 'LUIS GASTON RIVERA PEREZ').strip()
    if int(dte_tipo) == DTE_TIPO_FACTURA_AFECTA:
        from core.domain.shared.iva_chile import desglosar_iva_clp, linea_dte_item
        from services.facturacion_sii_certificacion import RUT_RECEPTOR_PRUEBA_SII

        neto, iva, total = desglosar_iva_clp(119000)
        item = linea_dte_item('Venta factura certificacion', 1, 119000, DTE_TIPO_FACTURA_AFECTA, neto_linea_asignado=neto)
        return {
            'dte_tipo': DTE_TIPO_FACTURA_AFECTA,
            'folio': int(folio),
            'rut_emisor': rut_em,
            'razon_social_emisor': rs_em,
            'giro_emisor': 'FERRETERIA',
            'acteco_emisor': ACTECO_FERRETERIA_RETAIL,
            'rut_receptor': RUT_RECEPTOR_PRUEBA_SII,
            'razon_social_receptor': 'SERVICIO DE IMPUESTOS INTERNOS PRUEBA',
            'giro_receptor': 'PRUEBA',
            'dir_receptor': 'SANTIAGO',
            'cmna_receptor': 'SANTIAGO',
            'ciudad_receptor': 'SANTIAGO',
            'fecha_emision': date.today().isoformat(),
            'monto_neto': neto,
            'monto_iva': iva,
            'monto_total': total,
            'items': [item],
        }
    from core.domain.shared.iva_chile import desglosar_iva_clp, linea_dte_item

    neto, iva, total = desglosar_iva_clp(1190)
    return {
        'dte_tipo': DTE_TIPO_BOLETA_AFECTA,
        'folio': int(folio),
        'rut_emisor': rut_em,
        'razon_social_emisor': rs_em,
        'rut_receptor': '66666666-6',
        'razon_social_receptor': 'CLIENTE BOLETA',
        'fecha_emision': date.today().isoformat(),
        'monto_neto': neto,
        'monto_iva': iva,
        'monto_total': total,
        'items': [linea_dte_item('Producto demo 1', 1, 1190, DTE_TIPO_BOLETA_AFECTA)],
    }


def generar_xml_dte_prueba_lxml(
    contexto: Dict[str, Any],
    *,
    caf_autorizacion_xml: Optional[bytes] = None,
) -> bytes:
    """
    Arma XML DTE (namespace SiiDte). Si `caf_autorizacion_xml` incluye RSASK, timbra TED.
    Sin CAF válido deja StubFase1 (solo laboratorio local).
    """
    from lxml import etree

    NS = 'http://www.sii.cl/SiiDte'
    nsmap = {None: NS}
    root = etree.Element('{%s}DTE' % NS, nsmap=nsmap)
    root.set('version', '1.0')

    doc = etree.SubElement(root, '{%s}Documento' % NS)
    doc_id = 'F%sT%s' % (int(contexto['dte_tipo']), int(contexto['folio']))
    doc.set('ID', doc_id)
    enc = etree.SubElement(doc, '{%s}Encabezado' % NS)
    iddoc = etree.SubElement(enc, '{%s}IdDoc' % NS)
    etree.SubElement(iddoc, '{%s}TipoDTE' % NS).text = str(int(contexto['dte_tipo']))
    etree.SubElement(iddoc, '{%s}Folio' % NS).text = str(int(contexto['folio']))
    etree.SubElement(iddoc, '{%s}FchEmis' % NS).text = str(contexto['fecha_emision'])

    emisor = etree.SubElement(enc, '{%s}Emisor' % NS)
    etree.SubElement(emisor, '{%s}RUTEmisor' % NS).text = str(contexto['rut_emisor'])
    etree.SubElement(emisor, '{%s}RznSoc' % NS).text = str(contexto['razon_social_emisor'])
    if int(contexto['dte_tipo']) == DTE_TIPO_FACTURA_AFECTA:
        if contexto.get('giro_emisor'):
            etree.SubElement(emisor, '{%s}GiroEmis' % NS).text = str(contexto['giro_emisor'])
        if contexto.get('acteco_emisor'):
            etree.SubElement(emisor, '{%s}Acteco' % NS).text = str(contexto['acteco_emisor'])

    receptor = etree.SubElement(enc, '{%s}Receptor' % NS)
    etree.SubElement(receptor, '{%s}RUTRecep' % NS).text = str(contexto['rut_receptor'])
    etree.SubElement(receptor, '{%s}RznSocRecep' % NS).text = str(contexto['razon_social_receptor'])
    if int(contexto['dte_tipo']) == DTE_TIPO_FACTURA_AFECTA:
        for tag, key in (
            ('GiroRecep', 'giro_receptor'),
            ('DirRecep', 'dir_receptor'),
            ('CmnaRecep', 'cmna_receptor'),
            ('CiudadRecep', 'ciudad_receptor'),
        ):
            if contexto.get(key):
                etree.SubElement(receptor, '{%s}%s' % (NS, tag)).text = str(contexto[key])

    totales = etree.SubElement(enc, '{%s}Totales' % NS)
    etree.SubElement(totales, '{%s}MntNeto' % NS).text = str(int(contexto['monto_neto']))
    if int(contexto['dte_tipo']) == DTE_TIPO_FACTURA_AFECTA:
        etree.SubElement(totales, '{%s}TasaIVA' % NS).text = '19'
    etree.SubElement(totales, '{%s}IVA' % NS).text = str(int(contexto['monto_iva']))
    etree.SubElement(totales, '{%s}MntTotal' % NS).text = str(int(contexto['monto_total']))

    detalle = etree.SubElement(doc, '{%s}Detalle' % NS)
    dte_tipo_int = int(contexto['dte_tipo'])
    for i, it in enumerate(contexto.get('items') or [], start=1):
        item = etree.SubElement(detalle, '{%s}Item' % NS)
        item.set('NroLinDet', str(i))
        etree.SubElement(item, '{%s}NmbItem' % NS).text = str(it.get('nombre', 'Item'))
        qty = max(1, int(it.get('cantidad', 1) or 1))
        prc = int(it.get('prc_item', it.get('precio', 0)) or 0)
        monto_lin = int(it.get('monto_linea', prc * qty) or 0)
        etree.SubElement(item, '{%s}QtyItem' % NS).text = str(qty)
        etree.SubElement(item, '{%s}PrcItem' % NS).text = str(prc)
        if dte_tipo_int == DTE_TIPO_FACTURA_AFECTA:
            etree.SubElement(item, '{%s}MontoItem' % NS).text = str(monto_lin)

    xml_base = etree.tostring(
        root,
        xml_declaration=True,
        encoding='utf-8',
        pretty_print=True,
    )
    if caf_autorizacion_xml and caf_autorizacion_xml.strip():
        from services import facturacion_ted_service as ted_svc

        xml_ted, estado_ted = ted_svc.timbrar_dte_xml(xml_base, contexto, caf_autorizacion_xml)
        if estado_ted == 'TIMBRADO':
            return xml_ted
        _logger_fe.warning('generar_xml_dte: timbrado falló (%s), se conserva stub', estado_ted)

    stub = etree.SubElement(doc, '{%s}StubFase1' % NS)
    stub.text = 'Sin TED — CAF sin RSASK o timbrado falló'
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding='utf-8',
        pretty_print=True,
    )


def validar_contexto_antes_firma(contexto: Dict[str, Any]) -> None:
    """Pre-flight Status 7: aborta firma si Neto+IVA o líneas no cuadran."""
    from core.domain.shared.iva_chile import ErrorFallaMatematicaDTE, validar_contexto_dte_matematico

    validar_contexto_dte_matematico(contexto, dte_tipo_factura=DTE_TIPO_FACTURA_AFECTA)


def marcar_venta_dte_fallo_matematico(venta: Any, dte_tipo: int, detalle: str = '') -> None:
    """Estado tributario: no firmar ni enviar al SII."""
    try:
        venta.dte_tipo = int(dte_tipo)
        venta.dte_estado = DTE_ESTADO_FALLO_MATEMATICO
        venta.dte_track_id = None
        if detalle:
            _logger_fe.critical('FE FALLO_MATEMATICO venta_id=%s: %s', getattr(venta, 'id', None), detalle)
    except Exception:
        _logger_fe.exception('FE: no se pudo marcar FALLO_MATEMATICO venta_id=%s', getattr(venta, 'id', None))


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
        # signxml 4.x: `cert` debe ser lista (cadena de certificados), no un solo Certificate.
        signed_root = signer.sign(root, key=private_key, cert=[certificate])
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
    """Indica si Zeep está disponible y SOAP habilitado por entorno."""
    try:
        import zeep  # noqa: F401
    except ImportError:
        return None
    try:
        from services import facturacion_sii_soap as sii_soap

        if sii_soap.soap_habilitado():
            return 'zeep+soap_enabled'
    except Exception:
        pass
    return None


def resolver_dte_tipo_por_tipo_documento(tipo_documento: Optional[str]) -> int:
    """Mapea tipo_documento de venta (Boleta/Factura) a código SII."""
    t = (tipo_documento or '').strip().lower()
    if 'fact' in t:
        return DTE_TIPO_FACTURA_AFECTA
    return DTE_TIPO_BOLETA_AFECTA


def _caf_autorizacion_bytes(db_session: Any, caf_model: Any, caf_id: int) -> Optional[bytes]:
    try:
        caf_row = db_session.get(caf_model, int(caf_id))
        if caf_row and getattr(caf_row, 'caf_xml', None):
            return str(caf_row.caf_xml).encode('utf-8', errors='replace')
    except Exception:
        pass
    return None


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
    """Contexto XML a partir de una venta cobrada (montos CLP enteros, Decimal)."""
    from core.domain.shared.iva_chile import (
        desglosar_iva_clp,
        distribuir_neto_en_lineas,
        linea_dte_item,
        subtotal_linea_bruto_clp,
    )

    cfg = obtener_config_empresa() if obtener_config_empresa else {}
    rut_emisor = (os.getenv('EMPRESA_RUT') or cfg.get('rut_emisor') or '76.192.028-5').strip()
    rs_emisor = (cfg.get('razon_social') or cfg.get('nombre_comercial') or 'EMPRESA').strip()
    cli = getattr(venta, 'cliente', None)
    rut_rec = '66666666-6'
    rs_rec = 'BOLETA'
    giro_rec = dir_rec = cmna_rec = ciudad_rec = None
    if int(dte_tipo) == DTE_TIPO_FACTURA_AFECTA and ambiente_sii_es_certificacion():
        from services.facturacion_sii_certificacion import RUT_RECEPTOR_PRUEBA_SII

        rut_rec = RUT_RECEPTOR_PRUEBA_SII
        rs_rec = 'SERVICIO DE IMPUESTOS INTERNOS PRUEBA'
        giro_rec = 'PRUEBA'
        dir_rec = cmna_rec = ciudad_rec = 'SANTIAGO'
    elif cli:
        rut_rec = (getattr(cli, 'rut', None) or rut_rec).strip() or rut_rec
        rs_rec = (getattr(cli, 'nombre', None) or rs_rec).strip() or rs_rec
    brutos_linea: list[int] = []
    meta_lineas: list[tuple[str, int]] = []
    for d in list(getattr(venta, 'detalles', None) or []):
        prod = getattr(d, 'producto', None)
        nombre = (getattr(prod, 'nombre', None) or 'Item') if prod else 'Item'
        cant = int(getattr(d, 'cantidad', 1) or 1)
        bruto_lin = subtotal_linea_bruto_clp(
            cant,
            getattr(d, 'precio_unitario', 0),
            getattr(d, 'descuento', 0),
        )
        if bruto_lin <= 0 and getattr(d, 'subtotal', None) is not None:
            bruto_lin = max(0, int(round(float(getattr(d, 'subtotal', 0) or 0))))
        brutos_linea.append(bruto_lin)
        meta_lineas.append((str(nombre)[:200], cant))

    total_bruto = sum(brutos_linea) if brutos_linea else max(0, int(round(float(getattr(venta, 'monto_total', 0) or 0))))
    if not meta_lineas:
        meta_lineas = [('Venta', 1)]
        brutos_linea = [total_bruto]

    neto, iva, total = desglosar_iva_clp(total_bruto)
    netos_linea = distribuir_neto_en_lineas(brutos_linea, neto) if int(dte_tipo) == DTE_TIPO_FACTURA_AFECTA else [0] * len(brutos_linea)

    items = []
    for (nombre, cant), bruto_lin, neto_lin in zip(meta_lineas, brutos_linea, netos_linea):
        items.append(
            linea_dte_item(
                nombre,
                cant,
                bruto_lin,
                int(dte_tipo),
                neto_linea_asignado=neto_lin if int(dte_tipo) == DTE_TIPO_FACTURA_AFECTA else None,
            )
        )
    ctx: Dict[str, Any] = {
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
    if int(dte_tipo) == DTE_TIPO_FACTURA_AFECTA:
        ctx['giro_emisor'] = 'FERRETERIA'
        ctx['acteco_emisor'] = '523910'
        if giro_rec:
            ctx['giro_receptor'] = giro_rec
        if dir_rec:
            ctx['dir_receptor'] = dir_rec
            ctx['cmna_receptor'] = cmna_rec
            ctx['ciudad_receptor'] = ciudad_rec
    return ctx


def post_cobro_emision_fe(
    db_session: Any,
    venta: Any,
    caf_model: Any,
    obtener_config_empresa: Callable[[], Dict[str, str]],
    logger: Any,
    *,
    erp_root: Optional[str] = None,
) -> str:
    """
    Emisión FE tras commit del cobro: savepoint aísla folio CAF; si falla firma/SOAP
    revierte folio y deja la venta en PENDIENTE_ENVIO sin tocar cobro/stock.

    Retorna el `dte_estado` a mostrar al cliente (ENVIADO si SOAP ok con track_id;
    con stub SOAP suele caer en PENDIENTE_ENVIO). Boletas: EXTERNO_MULTICAJA.
    """
    if not debe_emitir_fe_en_erp(getattr(venta, 'tipo_documento', None)):
        marcar_venta_boleta_sin_fe_erp(venta)
        try:
            db_session.flush()
        except Exception:
            pass
        return DTE_ESTADO_EXTERNO_BOLETA

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
            try:
                validar_contexto_antes_firma(ctx)
            except Exception as ex_m:
                from core.domain.shared.iva_chile import ErrorFallaMatematicaDTE

                msg = getattr(ex_m, 'mensaje', None) or str(ex_m)
                if isinstance(ex_m, ErrorFallaMatematicaDTE):
                    logger.critical(
                        'FE FALLO_MATEMATICO: venta_id=%s folio=%s — %s',
                        getattr(venta, 'id', None),
                        folio,
                        msg,
                    )
                    raise ValueError('fallo_matematico_dte:%s' % msg) from ex_m
                raise
            caf_xml_b = _caf_autorizacion_bytes(db_session, caf_model, int(caf_id))
            xml_raw = generar_xml_dte_prueba_lxml(ctx, caf_autorizacion_xml=caf_xml_b)
            xml_firma, estado_firma = firmar_xml_dte(xml_raw)
            if (estado_firma or '').startswith('ERROR_FIRMA'):
                raise RuntimeError(estado_firma)
            ambiente = (obtener_config_certificado().get('ambiente') or '').strip()
            _persist_xml_dte_firmado_safe(
                erp_root, ambiente, int(getattr(venta, 'id', 0) or 0), int(folio), int(dte_tipo), xml_firma
            )
            track_id, estado_envio = enviar_dte_soap(
                xml_firma,
                ambiente=ambiente,
                rut_emisor=ctx.get('rut_emisor'),
                dte_tipo=dte_tipo,
            )
            venta.dte_tipo = int(dte_tipo)
            if estado_envio == 'ok' and (track_id or '').strip():
                venta.dte_estado = DTE_ESTADO_ENVIADO
                venta.dte_track_id = (track_id or '')[:50]
            else:
                # Fase 1: SOAP aún stub o SII no disponible — se conserva folio CAF y se marca cola.
                venta.dte_estado = DTE_ESTADO_PENDIENTE_ENVIO
                venta.dte_track_id = None
        return str(getattr(venta, 'dte_estado', None) or DTE_ESTADO_PENDIENTE_ENVIO)
    except Exception as ex:
        try:
            db_session.refresh(venta)
        except Exception:
            pass
        ex_msg = str(ex)
        if ex_msg.startswith('fallo_matematico_dte:'):
            det = ex_msg.split(':', 1)[-1]
            marcar_venta_dte_fallo_matematico(venta, dte_tipo, det)
            try:
                db_session.flush()
            except Exception:
                pass
            return DTE_ESTADO_FALLO_MATEMATICO
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


def enviar_dte_soap(
    xml_firmado: bytes,
    ambiente: Optional[str] = None,
    *,
    rut_emisor: Optional[str] = None,
    dte_tipo: int = DTE_TIPO_BOLETA_AFECTA,
) -> Tuple[Optional[str], str]:
    """
    Envía el DTE firmado al SII si `SII_SOAP_ENABLED=1` y hay certificado.
    Retorna (track_id, estado): ok | error_* | STUB_NO_ENVIO | deshabilitado.
    """
    try:
        from services import facturacion_sii_soap as sii_soap
    except ImportError:
        return None, 'STUB_NO_ENVIO'

    if not sii_soap.soap_habilitado():
        return None, 'STUB_NO_ENVIO'

    cfg_cert = obtener_config_certificado()
    if not (cfg_cert.get('pfx_path') or '').strip():
        return None, 'STUB_SIN_CERTIFICADO'

    rut = (rut_emisor or os.getenv('EMPRESA_RUT') or '8054120-1').strip()
    rut_env = (os.getenv('SII_RUT_ENVIA') or rut).strip()
    amb = ambiente or cfg_cert.get('ambiente')
    track_id, estado, _det = sii_soap.enviar_dte_firmado_al_sii(
        xml_firmado,
        rut_emisor=rut,
        rut_envia=rut_env,
        ambiente=amb,
        dte_tipo=int(dte_tipo),
    )
    if estado == 'ok' and track_id:
        return track_id, 'ok'
    if estado == 'deshabilitado':
        return None, 'STUB_NO_ENVIO'
    return None, estado


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


def enviar_xml_prueba_sii_desde_storage(
    app_root: str,
    *,
    dte_tipo: int = DTE_TIPO_FACTURA_AFECTA,
    folio: int = 1,
    ambiente: Optional[str] = None,
    rut_emisor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sube al SII un XML del set de certificación en storage/dtes/pruebas_sii/
    (p. ej. DTE_33_FOLIO_1.xml del ZIP pruebas_sii_dte_verificacion.zip).
    """
    from services import facturacion_sii_certificacion as cert_sii
    from services import facturacion_sii_soap as sii_soap

    directorio = cert_sii.directorio_pruebas_sii(app_root)
    nombre = cert_sii.nombre_archivo_dte(int(dte_tipo), int(folio))
    ruta = os.path.join(directorio, nombre)
    if not os.path.isfile(ruta):
        return {
            'ok': False,
            'error': 'archivo_no_encontrado',
            'archivo': nombre,
            'ruta': ruta,
        }
    if not sii_soap.soap_habilitado():
        return {'ok': False, 'error': 'soap_deshabilitado', 'archivo': nombre, 'ruta': ruta}

    with open(ruta, 'rb') as fh:
        xml_firmado = fh.read()

    rut = (rut_emisor or os.getenv('EMPRESA_RUT') or '8054120-1').strip()
    rut_env = (os.getenv('SII_RUT_ENVIA') or rut).strip()
    amb = ambiente or os.getenv('SII_AMBIENTE')
    track_id, estado, detalle = sii_soap.enviar_dte_firmado_al_sii(
        xml_firmado,
        rut_emisor=rut,
        rut_envia=rut_env,
        ambiente=amb,
        dte_tipo=int(dte_tipo),
    )
    out: Dict[str, Any] = {
        'ok': estado == 'ok' and bool(track_id),
        'archivo': nombre,
        'ruta': ruta,
        'dte_tipo': int(dte_tipo),
        'folio': int(folio),
        'estado_envio': estado,
        'track_id': track_id,
        'token_estado': detalle.get('token_estado'),
        'upload_status': detalle.get('upload_status'),
        'upload_raw': (detalle.get('upload_raw') or '')[:800],
        'error': detalle.get('error'),
        'ambiente': detalle.get('ambiente'),
    }
    if detalle.get('upload_status') and str(detalle.get('upload_status')) != '0':
        out['upload_nota'] = 'STATUS SII distinto de 0 (7=esquema, 8=firma DTE, 5=no autenticado, etc.)'
    return out


def emitir_prueba_xml(
    dte_tipo: int,
    folio: int = 1,
    *,
    caf_autorizacion_xml: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Usado por la ruta admin: genera XML, TED (si hay CAF), firma y opcional envío SOAP."""
    ctx = construir_contexto_dte_prueba(dte_tipo, folio=folio)
    validar_contexto_antes_firma(ctx)
    xml_raw = generar_xml_dte_prueba_lxml(ctx, caf_autorizacion_xml=caf_autorizacion_xml)
    xml_firma, estado_firma = firmar_xml_dte(xml_raw)
    track_id, estado_envio = enviar_dte_soap(
        xml_firma,
        rut_emisor=ctx.get('rut_emisor'),
        dte_tipo=ctx['dte_tipo'],
    )
    cfg_cert = obtener_config_certificado()
    res = cfg_cert.get('pfx_path_resolved') or ''
    cert_ok = bool((cfg_cert.get('pfx_path') or '').strip() and res and os.path.isfile(res))
    ted_ok = b'<TED' in xml_firma or b'TED version' in xml_firma
    return {
        'ok': True,
        'dte_tipo': ctx['dte_tipo'],
        'folio': ctx['folio'],
        'xml_utf8': xml_firma.decode('utf-8', errors='replace'),
        'xml_valido': validar_xml_bien_formado(xml_firma),
        'ted_timbrado': ted_ok,
        'estado_firma': estado_firma,
        'estado_envio': estado_envio,
        'track_id': track_id,
        'cert_configurado': cert_ok,
        'sii_ambiente': cfg_cert.get('ambiente'),
        'acteco_emisor': ctx.get('acteco_emisor'),
    }


def reintentar_emision_fe_venta(
    db_session: Any,
    venta_id: int,
    venta_model: Any,
    caf_model: Any,
    obtener_config_empresa: Callable[[], Dict[str, str]],
    logger: Any,
    *,
    erp_root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reintenta emisión para venta en PENDIENTE_ENVIO (misma lógica que post-cobro).
    Si no hay folio reservado, asigna CAF; si ya hay nro_documento+caf_id, reutiliza.
    """
    venta = db_session.query(venta_model).filter_by(id=int(venta_id)).first()
    if not venta:
        return {'ok': False, 'motivo': 'venta_no_encontrada'}
    if (getattr(venta, 'dte_estado', None) or '') != DTE_ESTADO_PENDIENTE_ENVIO:
        return {'ok': False, 'motivo': 'estado_no_pendiente', 'dte_estado': getattr(venta, 'dte_estado', None)}
    if not debe_emitir_fe_en_erp(getattr(venta, 'tipo_documento', None)):
        return {
            'ok': False,
            'motivo': 'boleta_emitida_por_multicaja',
            'dte_estado': getattr(venta, 'dte_estado', None),
        }
    dte_tipo = resolver_dte_tipo_por_tipo_documento(getattr(venta, 'tipo_documento', None))
    try:
        with db_session.begin_nested():
            folio = getattr(venta, 'nro_documento', None)
            caf_id = getattr(venta, 'caf_id', None)
            if not folio or not caf_id:
                pair = asignar_folio_disponible(db_session, caf_model, dte_tipo)
                if not pair:
                    raise ValueError('sin_caf_o_folios')
                folio, caf_id = pair
                venta.nro_documento = int(folio)
                venta.caf_id = int(caf_id)
            ctx = construir_contexto_desde_venta(venta, int(folio), dte_tipo, obtener_config_empresa)
            try:
                validar_contexto_antes_firma(ctx)
            except Exception as ex_m:
                from core.domain.shared.iva_chile import ErrorFallaMatematicaDTE

                msg = getattr(ex_m, 'mensaje', None) or str(ex_m)
                if isinstance(ex_m, ErrorFallaMatematicaDTE):
                    raise ValueError('fallo_matematico_dte:%s' % msg) from ex_m
                raise
            caf_xml_b = _caf_autorizacion_bytes(db_session, caf_model, int(caf_id))
            xml_raw = generar_xml_dte_prueba_lxml(ctx, caf_autorizacion_xml=caf_xml_b)
            xml_firma, estado_firma = firmar_xml_dte(xml_raw)
            if (estado_firma or '').startswith('ERROR_FIRMA'):
                raise RuntimeError(estado_firma)
            ambiente = (obtener_config_certificado().get('ambiente') or '').strip()
            _persist_xml_dte_firmado_safe(
                erp_root, ambiente, int(venta.id), int(folio), int(dte_tipo), xml_firma
            )
            track_id, estado_envio = enviar_dte_soap(
                xml_firma,
                ambiente=ambiente,
                rut_emisor=ctx.get('rut_emisor'),
                dte_tipo=dte_tipo,
            )
            venta.dte_tipo = int(dte_tipo)
            if estado_envio == 'ok' and (track_id or '').strip():
                venta.dte_estado = DTE_ESTADO_ENVIADO
                venta.dte_track_id = (track_id or '')[:50]
            else:
                venta.dte_estado = DTE_ESTADO_PENDIENTE_ENVIO
                venta.dte_track_id = None
        return {
            'ok': True,
            'venta_id': venta.id,
            'dte_estado': getattr(venta, 'dte_estado', None),
            'nro_documento': getattr(venta, 'nro_documento', None),
        }
    except Exception as ex:
        db_session.rollback()
        logger.exception('reintentar_emision_fe_venta venta_id=%s', venta_id)
        return {'ok': False, 'motivo': str(ex)[:200]}


def reintentar_envio_dte_venta(venta_id: int) -> Dict[str, Any]:
    """Reservado: usar `reintentar_emision_fe_venta` desde la capa Flask con modelos."""
    _ = venta_id
    return {'ok': False, 'venta_id': venta_id, 'motivo': 'invocar_reintentar_emision_fe_venta_desde_app'}
