# -*- coding: utf-8 -*-
"""
Cliente SII Chile — semilla, token (certificado .pfx) y subida EnvioDTE (Palena / Maullín).

Referencias: CrSeed.jws, GetTokenFromSeed.jws, POST /cgi_dte/UPL/DTEUpload
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

_logger = logging.getLogger(__name__)

HOST_CERTIFICACION = 'https://maullin.sii.cl'
HOST_PRODUCCION = 'https://palena.sii.cl'

NS_SII = 'http://www.sii.cl/SiiDte'
NS_XMLDSIG = 'http://www.w3.org/2000/09/xmldsig#'
C14N_SII = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
SIG_ALG_RSA_SHA1 = 'http://www.w3.org/2000/09/xmldsig#rsa-sha1'
DIGEST_SHA1 = 'http://www.w3.org/2000/09/xmldsig#sha1'

STATUS_UPLOAD_DESC = {
    '0': None,
    '1': 'El Sender no tiene permiso para enviar',
    '2': 'Error en tamaño del archivo',
    '3': 'Archivo cortado',
    '5': 'No está autenticado',
    '6': 'Empresa no autorizada a enviar archivos',
    '7': 'Esquema Invalido',
    '8': 'Firma del Documento',
    '9': 'Sistema Bloqueado',
    '99': 'Error Interno',
}


@dataclass
class ResultadoSemilla:
    ok: bool
    semilla: Optional[str] = None
    estado: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ResultadoToken:
    ok: bool
    token: Optional[str] = None
    estado: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ResultadoUpload:
    ok: bool
    track_id: Optional[str] = None
    status: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None


def normalizar_ambiente(ambiente: Optional[str]) -> str:
    a = (ambiente or os.getenv('SII_AMBIENTE') or 'certificacion').strip().lower()
    if a in ('prod', 'palena', 'produccion', 'production'):
        return 'produccion'
    return 'certificacion'


def url_base_sii(ambiente: Optional[str] = None) -> str:
    return HOST_PRODUCCION if normalizar_ambiente(ambiente) == 'produccion' else HOST_CERTIFICACION


def soap_habilitado() -> bool:
    v = (os.getenv('SII_SOAP_ENABLED') or '').strip().lower()
    return v in ('1', 'true', 'yes', 'si', 'on')


def split_rut(rut: str) -> Tuple[str, str]:
    """Devuelve (cuerpo sin puntos, dígito verificador). Acepta 8.054.120-1 o 8054120-1."""
    s = (rut or '').strip().upper().replace('.', '')
    if '-' not in s:
        raise ValueError('rut_sin_guion')
    cuerpo, dv = s.rsplit('-', 1)
    cuerpo = re.sub(r'\D', '', cuerpo)
    dv = dv.strip().upper()
    if not cuerpo or not dv:
        raise ValueError('rut_invalido')
    return cuerpo, dv


def _localname(el: Any) -> str:
    from lxml import etree

    return etree.QName(el).localname


def _texto_nodo(root: Any, nombre: str) -> Optional[str]:
    for el in root.iter():
        if _localname(el) == nombre and el.text and str(el.text).strip():
            return str(el.text).strip()
    return None


def _parsear_xml_respuesta(raw: Any) -> Any:
    from lxml import etree

    if raw is None:
        raise ValueError('respuesta_vacia')
    if isinstance(raw, (bytes, bytearray)):
        return etree.fromstring(bytes(raw))
    txt = str(raw).strip()
    if not txt:
        raise ValueError('respuesta_vacia')
    return etree.fromstring(txt.encode('utf-8', errors='replace'))


def _get_seed_soap_raw(base: str) -> str:
    """POST SOAP getSeed (evita zeep cuando el WSDL devuelve 503 HTML)."""
    import requests

    url = base + '/DTEWS/CrSeed.jws'
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:def="http://DefaultNamespace">'
        '<soapenv:Header/><soapenv:Body><def:getSeed/></soapenv:Body></soapenv:Envelope>'
    )
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '',
        'User-Agent': 'LhexIA-ERP/1.0',
    }
    resp = requests.post(url, data=envelope.encode('utf-8'), headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.text


def _get_token_soap_raw(base: str, xml_firmado: bytes | str) -> str:
    """
    POST SOAP getToken con XML firmado en ISO-8859-1 (manual SII autenticación v1.9).
    El sobre SOAP va en ISO-8859-1; pszXml en CDATA conserva bytes Latin-1 del DTE auth.
    """
    import requests

    url = base + '/DTEWS/GetTokenFromSeed.jws'
    if isinstance(xml_firmado, (bytes, bytearray)):
        xml_body = bytes(xml_firmado).decode('iso-8859-1', errors='strict')
    else:
        xml_body = str(xml_firmado or '')
    safe_xml = xml_body.replace(']]>', ']]]]><![CDATA[>')
    envelope = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:def="http://DefaultNamespace">'
        '<soapenv:Header/><soapenv:Body>'
        '<def:getToken><pszXml><![CDATA[%s]]></pszXml></def:getToken>'
        '</soapenv:Body></soapenv:Envelope>'
    ) % safe_xml
    payload = envelope.encode('iso-8859-1')
    headers = {
        'Content-Type': 'text/xml; charset=ISO-8859-1',
        'SOAPAction': '',
        'User-Agent': 'LhexIA-ERP/1.0',
    }
    resp = requests.post(url, data=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.text


def obtener_semilla(ambiente: Optional[str] = None) -> ResultadoSemilla:
    """Llama CrSeed.getSeed en Maullín o Palena."""
    base = url_base_sii(ambiente)
    wsdl = base + '/DTEWS/CrSeed.jws?wsdl'
    raw: Any = None
    try:
        from zeep import Client

        client = Client(wsdl)
        raw = client.service.getSeed()
    except Exception as ex_zeep:
        _logger.warning('obtener_semilla zeep falló (%s), reintento SOAP raw: %s', wsdl, ex_zeep)
        try:
            raw = _get_seed_soap_raw(base)
        except Exception as ex_raw:
            _logger.exception('obtener_semilla SII falló (%s)', wsdl)
            return ResultadoSemilla(ok=False, error=f'{type(ex_raw).__name__}:{str(ex_raw)[:300]}')
    try:
        root = _parsear_xml_respuesta(raw)
        estado = _texto_nodo(root, 'ESTADO')
        semilla = _texto_nodo(root, 'SEMILLA')
        ok = (estado or '') == '00' and bool(semilla)
        return ResultadoSemilla(
            ok=ok,
            semilla=semilla,
            estado=estado,
            raw=str(raw)[:2000] if raw is not None else None,
            error=None if ok else 'semilla_no_obtenida',
        )
    except Exception as ex:
        return ResultadoSemilla(ok=False, error=f'{type(ex).__name__}:{str(ex)[:300]}')


def _cargar_clave_certificado_pfx() -> Tuple[Any, Any]:
    """Carga private_key y certificate desde configuración FE."""
    from services import facturacion_electronica_service as fe

    cfg = fe.obtener_config_certificado()
    path = cfg.get('pfx_path_resolved') or fe._resolver_ruta_pfx(cfg.get('pfx_path') or '')
    if not path or not os.path.isfile(path):
        raise FileNotFoundError('pfx_no_configurado')
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(path, 'rb') as fh:
        pfx = fh.read()
    pw_plain = fe._leer_password_pfx_texto_plano(cfg)
    passwords = [pw_plain.encode('utf-8')] if pw_plain else [None, b'']
    last_err: Optional[Exception] = None
    for password in passwords:
        try:
            private_key, certificate, _extra = pkcs12.load_key_and_certificates(pfx, password)
            if private_key is not None and certificate is not None:
                return private_key, certificate
        except ValueError as ex:
            last_err = ex
    if last_err:
        raise last_err
    raise ValueError('pfx_sin_clave_valida')


class _XMLSignerSiiSha1:
    """Firma XML semilla SII: C14N 1.0 (sin comentarios) + RSA-SHA1 + SHA1."""

    @staticmethod
    def _signer():
        from signxml import XMLSigner, methods

        class _Signer(XMLSigner):
            def check_deprecated_methods(self):
                return

        return _Signer(
            method=methods.enveloped,
            signature_algorithm='rsa-sha1',
            digest_algorithm='sha1',
            c14n_algorithm=C14N_SII,
        )

    @classmethod
    def sign(cls, root, *, key, cert):
        return cls._signer().sign(
            root,
            key=key,
            cert=[cert],
            always_add_key_value=True,
        )


def _armar_gettoken_sin_firma(semilla: str):
    """Estructura getToken/item/Semilla exigida por GetTokenFromSeed (manual SII §4.1.3)."""
    from lxml import etree

    root = etree.Element('getToken')
    item = etree.SubElement(root, 'item')
    sem = etree.SubElement(item, 'Semilla')
    sem.text = str(semilla).strip()
    return root


def _serializar_xml_iso8859(root) -> bytes:
    from lxml import etree

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding='ISO-8859-1',
        pretty_print=False,
    )


def firmar_xml_semilla_token(semilla: str) -> bytes:
    """
    Arma y firma el XML getToken para GetTokenFromSeed.

    Estándar SII (manual autenticación v1.9, cap. 8):
    - Canonicalización C14N 1.0 (REC-xml-c14n-20010315, sin comentarios)
    - DigestMethod y SignatureMethod SHA1 / RSA-SHA1
    - KeyInfo con RSAKeyValue (Modulus, Exponent) + X509Certificate
    - Salida ISO-8859-1 (no UTF-8)
    """
    private_key, certificate = _cargar_clave_certificado_pfx()
    root = _armar_gettoken_sin_firma(semilla)
    signed = _XMLSignerSiiSha1.sign(root, key=private_key, cert=certificate)
    _validar_firma_semilla_sii(signed)
    return _serializar_xml_iso8859(signed)


def _validar_firma_semilla_sii(root) -> None:
    """Comprueba algoritmos exigidos por SII antes de enviar a Maullín/Palena."""
    ns = {'ds': NS_XMLDSIG}
    sig = root.find('.//ds:Signature', namespaces=ns)
    if sig is None:
        raise ValueError('firma_semilla_sin_signature')
    c14n = sig.find('.//ds:CanonicalizationMethod', namespaces=ns)
    sig_m = sig.find('.//ds:SignatureMethod', namespaces=ns)
    dig = sig.find('.//ds:DigestMethod', namespaces=ns)
    if (c14n is None or c14n.get('Algorithm') != C14N_SII):
        raise ValueError('firma_semilla_c14n_invalido')
    if sig_m is None or sig_m.get('Algorithm') != SIG_ALG_RSA_SHA1:
        raise ValueError('firma_semilla_signature_method_invalido')
    if dig is None or dig.get('Algorithm') != DIGEST_SHA1:
        raise ValueError('firma_semilla_digest_invalido')
    if sig.find('.//ds:RSAKeyValue', namespaces=ns) is None:
        raise ValueError('firma_semilla_sin_rsakeyvalue')
    ref = sig.find('.//ds:Reference', namespaces=ns)
    if ref is None or (ref.get('URI') or '') != '':
        raise ValueError('firma_semilla_reference_uri_invalido')
    env = sig.find(
        './/ds:Transform[@Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"]',
        namespaces=ns,
    )
    if env is None:
        raise ValueError('firma_semilla_sin_enveloped_transform')


def obtener_token(semilla: str, ambiente: Optional[str] = None) -> ResultadoToken:
    """Firma la semilla y solicita token de sesión al SII."""
    base = url_base_sii(ambiente)
    wsdl = base + '/DTEWS/GetTokenFromSeed.jws?wsdl'
    try:
        xml_firmado = firmar_xml_semilla_token(semilla)
        raw: Any = None
        try:
            raw = _get_token_soap_raw(base, xml_firmado)
        except Exception as ex_raw:
            _logger.warning(
                'obtener_token SOAP raw ISO-8859-1 falló (%s), reintento zeep: %s',
                wsdl,
                ex_raw,
            )
            from zeep import Client

            xml_txt = xml_firmado.decode('iso-8859-1', errors='strict')
            client = Client(wsdl)
            raw = client.service.getToken(xml_txt)
        root = _parsear_xml_respuesta(raw)
        estado = _texto_nodo(root, 'ESTADO')
        token = _texto_nodo(root, 'TOKEN')
        ok = (estado or '') == '00' and bool(token)
        return ResultadoToken(
            ok=ok,
            token=token,
            estado=estado,
            raw=str(raw)[:2000] if raw is not None else None,
            error=None if ok else 'token_no_obtenido',
        )
    except Exception as ex:
        _logger.exception('obtener_token SII falló')
        return ResultadoToken(ok=False, error=f'{type(ex).__name__}:{str(ex)[:300]}')


def conectar_sii(ambiente: Optional[str] = None) -> ResultadoToken:
    """Semilla + token en un paso (diagnóstico de certificado y red)."""
    sem = obtener_semilla(ambiente)
    if not sem.ok or not sem.semilla:
        return ResultadoToken(ok=False, error=sem.error or 'semilla_fallo', estado=sem.estado)
    return obtener_token(sem.semilla, ambiente)


def date_hoy_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _config_resolucion_sii() -> Tuple[str, int]:
    fch = (os.getenv('SII_FCH_RESOLUCION') or date_hoy_iso()).strip()[:10]
    try:
        nro = int((os.getenv('SII_NRO_RESOLUCION') or '0').strip() or '0')
    except ValueError:
        nro = 0
    return fch, nro


def construir_envio_dte(
    dte_xml: bytes,
    *,
    rut_emisor: str,
    rut_envia: Optional[str] = None,
    cantidad_dte: int = 1,
    tipo_dte: int = 39,
) -> bytes:
    """
    Envuelve un DTE firmado en EnvioDTE + Carátula (requerido por DTEUpload).
    """
    from lxml import etree

    root_dte = etree.fromstring(dte_xml)
    nsmap = {None: NS_SII}
    envio = etree.Element('{%s}EnvioDTE' % NS_SII, nsmap=nsmap)
    envio.set('version', '1.0')

    set_dte = etree.SubElement(envio, '{%s}SetDTE' % NS_SII)
    set_dte.set('ID', 'SetDTE-%s' % datetime.now().strftime('%Y%m%d%H%M%S'))

    car = etree.SubElement(set_dte, '{%s}Caratula' % NS_SII)
    car.set('version', '1.0')
    rut_e = (rut_envia or rut_emisor).strip()
    etree.SubElement(car, '{%s}RutEmisor' % NS_SII).text = rut_emisor.strip()
    etree.SubElement(car, '{%s}RutEnvia' % NS_SII).text = rut_e
    fch_res, nro_res = _config_resolucion_sii()
    etree.SubElement(car, '{%s}FchResol' % NS_SII).text = fch_res
    etree.SubElement(car, '{%s}NroResol' % NS_SII).text = str(int(nro_res))
    etree.SubElement(car, '{%s}TmstFirmaEnv' % NS_SII).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    sub = etree.SubElement(car, '{%s}SubTotDTE' % NS_SII)
    etree.SubElement(sub, '{%s}TpoDTE' % NS_SII).text = str(int(tipo_dte))
    etree.SubElement(sub, '{%s}NroDTE' % NS_SII).text = str(int(cantidad_dte))

    if _localname(root_dte) == 'DTE':
        set_dte.append(root_dte)
    else:
        dte_wrap = etree.SubElement(set_dte, '{%s}DTE' % NS_SII)
        dte_wrap.set('version', '1.0')
        for child in list(root_dte):
            dte_wrap.append(child)

    return etree.tostring(
        envio,
        xml_declaration=True,
        encoding='ISO-8859-1',
        pretty_print=True,
    )


def subir_envio_dte(
    envio_xml: bytes,
    token: str,
    *,
    rut_emisor: str,
    rut_envia: Optional[str] = None,
    ambiente: Optional[str] = None,
) -> ResultadoUpload:
    """POST multipart a DTEUpload (mismo flujo que integradores Chile)."""
    import requests

    base = url_base_sii(ambiente)
    rut_env = (rut_envia or rut_emisor).strip()
    try:
        rut_co, dv_co = split_rut(rut_emisor)
        rut_se, dv_se = split_rut(rut_env)
    except ValueError as ex:
        return ResultadoUpload(ok=False, error=str(ex))

    payload = b'<?xml version="1.0" encoding="ISO-8859-1"?>\n' + envio_xml.lstrip()
    files = [
        ('rutSender', (None, rut_se)),
        ('dvSender', (None, dv_se)),
        ('rutCompany', (None, rut_co)),
        ('dvCompany', (None, dv_co)),
        (
            'file',
            ('envio.xml', payload, 'text/xml; charset=ISO-8859-1'),
        ),
    ]
    headers = {
        'Cookie': 'TOKEN=%s' % (token or '').strip(),
        'User-Agent': 'LhexIA-ERP/1.0',
    }
    url = base + '/cgi_dte/UPL/DTEUpload'
    try:
        resp = requests.post(url, files=files, headers=headers, timeout=90)
        raw = resp.text or resp.content.decode('utf-8', errors='replace')
        root = _parsear_xml_respuesta(raw.encode('utf-8'))
        status = _texto_nodo(root, 'STATUS')
        track = _texto_nodo(root, 'TRACKID')
        ok = (status or '') == '0' and bool(track)
        err = None
        if not ok:
            err = STATUS_UPLOAD_DESC.get(status or '', 'upload_rechazado') or 'upload_rechazado'
        return ResultadoUpload(
            ok=ok,
            track_id=track,
            status=status,
            raw=raw[:4000],
            error=err,
        )
    except Exception as ex:
        _logger.exception('subir_envio_dte falló url=%s', url)
        return ResultadoUpload(ok=False, error=f'{type(ex).__name__}:{str(ex)[:300]}')


def enviar_dte_firmado_al_sii(
    xml_firmado: bytes,
    *,
    rut_emisor: str,
    rut_envia: Optional[str] = None,
    ambiente: Optional[str] = None,
    dte_tipo: int = 39,
) -> Tuple[Optional[str], str, Dict[str, Any]]:
    """
    Flujo completo: token + EnvioDTE + upload.
    Retorna (track_id, estado, detalle_dict).
    estado: ok | error_semilla | error_token | error_upload | error_envio | deshabilitado
    """
    detalle: Dict[str, Any] = {'ambiente': normalizar_ambiente(ambiente)}
    if not soap_habilitado():
        return None, 'deshabilitado', detalle

    tok = conectar_sii(ambiente)
    detalle['token_estado'] = tok.estado
    if not tok.ok or not tok.token:
        est = 'error_semilla' if 'semilla' in (tok.error or '') else 'error_token'
        detalle['error'] = tok.error
        return None, est, detalle

    try:
        envio = construir_envio_dte(
            xml_firmado,
            rut_emisor=rut_emisor,
            rut_envia=rut_envia,
            tipo_dte=int(dte_tipo),
        )
    except Exception as ex:
        detalle['error'] = f'envio_dte:{ex}'
        return None, 'error_envio', detalle

    up = subir_envio_dte(
        envio,
        tok.token,
        rut_emisor=rut_emisor,
        rut_envia=rut_envia,
        ambiente=ambiente,
    )
    detalle['upload_status'] = up.status
    detalle['upload_raw'] = (up.raw or '')[:500]
    if up.ok and up.track_id:
        detalle['track_id'] = up.track_id
        return up.track_id, 'ok', detalle
    detalle['error'] = up.error
    return None, 'error_upload', detalle


def diagnostico_sii(ambiente: Optional[str] = None) -> Dict[str, Any]:
    """Solo conectividad semilla+token y estado del .pfx (sin subir DTE)."""
    from services import facturacion_electronica_service as fe

    cfg = fe.obtener_config_certificado()
    path = cfg.get('pfx_path_resolved') or ''
    pfx_ok = bool((cfg.get('pfx_path') or '').strip() and path and os.path.isfile(path))
    amb = normalizar_ambiente(ambiente or cfg.get('ambiente'))
    out: Dict[str, Any] = {
        'soap_habilitado': soap_habilitado(),
        'ambiente': amb,
        'url_base': url_base_sii(amb),
        'pfx_configurado': pfx_ok,
        'pfx_path': (cfg.get('pfx_path') or '')[:120],
    }
    sem = obtener_semilla(amb)
    out['semilla_ok'] = sem.ok
    out['semilla_estado'] = sem.estado
    if not sem.ok:
        out['semilla_error'] = sem.error
        return out
    if not pfx_ok:
        out['token_ok'] = False
        out['token_error'] = 'pfx_no_configurado'
        return out
    tok = obtener_token(sem.semilla or '', amb)
    out['token_ok'] = tok.ok
    out['token_estado'] = tok.estado
    if not tok.ok:
        out['token_error'] = tok.error
        if tok.raw:
            out['token_respuesta'] = tok.raw[:500]
        if tok.estado == '10':
            out['token_nota'] = 'ESTADO 10 = ERROR RETORNO DATOS (XML/firma semilla no aceptada por SII)'
    else:
        out['token_preview'] = (tok.token or '')[:8] + '…' if tok.token else None
    return out
