# -*- coding: utf-8 -*-
"""
Cliente SII Chile — semilla, token (certificado .pfx) y subida EnvioDTE (Palena / Maullín).

Referencias: CrSeed.jws, GetTokenFromSeed.jws, POST /cgi_dte/UPL/DTEUpload
"""
from __future__ import annotations

import html
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


def _extraer_xml_interno_soap(raw: Any) -> str:
    """
    SII devuelve RESPUESTA/ESTADO/TOKEN dentro de getTokenReturn o getSeedReturn
    (a menudo escapado como entidad HTML dentro del sobre SOAP).
    """
    if raw is None:
        return ''
    if isinstance(raw, (bytes, bytearray)):
        txt = bytes(raw).decode('utf-8', errors='replace')
    else:
        txt = str(raw).strip()
    if not txt:
        return ''
    if '<' not in txt:
        return txt
    try:
        root = _parsear_xml_respuesta(txt)
    except Exception:
        return txt
    nombres_return = (
        'getTokenReturn',
        'getSeedReturn',
        'getTokenFromSeedReturn',
        'getSeedResponse',
        'getTokenResponse',
    )
    for el in root.iter():
        if _localname(el) in nombres_return:
            inner = (el.text or '').strip()
            if inner:
                return html.unescape(inner)
    return txt


def _parsear_respuesta_sii_negocio(raw: Any) -> Any:
    """Parsea RESPUESTA SII (directa o anidada en sobre SOAP)."""
    inner = _extraer_xml_interno_soap(raw)
    payload = inner if inner else raw
    return _parsear_xml_respuesta(payload)


def _detalle_respuesta_sii(root: Any) -> Dict[str, Optional[str]]:
    """ESTADO, SEMILLA/TOKEN y GLOSA (RESPUESTA plana o SII:RESP_HDR)."""
    estado = _texto_nodo(root, 'ESTADO')
    glosa = _texto_nodo(root, 'GLOSA')
    if not estado:
        for el in root.iter():
            ln = _localname(el)
            if ln == 'ESTADO' and el.text:
                estado = str(el.text).strip()
            elif ln == 'GLOSA' and el.text and not glosa:
                glosa = str(el.text).strip()
    return {
        'estado': estado,
        'semilla': _texto_nodo(root, 'SEMILLA'),
        'token': _texto_nodo(root, 'TOKEN'),
        'glosa': glosa,
    }


def extraer_rut_desde_certificado(certificate: Any) -> Optional[str]:
    """
    RUT del titular del .pfx (formato 8054120-1) desde subject del certificado chileno.
    """
    if certificate is None:
        return None
    candidatos: list[str] = []
    try:
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID, NameOID

        for attr in certificate.subject:
            val = str(getattr(attr, 'value', '') or '').strip().upper()
            if val:
                candidatos.append(val)
            if attr.oid == NameOID.SERIAL_NUMBER:
                candidatos.append(val.replace('RUT', '').strip())
        try:
            san = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            for name in san:
                raw = getattr(name, 'value', None)
                if isinstance(raw, (bytes, bytearray)):
                    txt = bytes(raw).decode('utf-8', errors='ignore').upper()
                    if txt:
                        candidatos.append(txt)
                elif raw is not None:
                    candidatos.append(str(raw).upper())
        except x509.ExtensionNotFound:
            pass
    except Exception:
        pass
    for val in candidatos:
        for m in re.finditer(r'(\d{7,8}-[\dK])', val.replace('.', '')):
            try:
                cuerpo, dv = split_rut(m.group(1))
                return f'{cuerpo}-{dv}'
            except ValueError:
                continue
        m = re.search(r'(\d{1,2}\.?\d{3}\.?\d{3}-[\dK])', val)
        if m:
            try:
                cuerpo, dv = split_rut(m.group(1))
                return f'{cuerpo}-{dv}'
            except ValueError:
                continue
    return None


def auditar_rut_certificado_vs_empresa(rut_empresa: Optional[str] = None) -> Dict[str, Any]:
    """Compara RUT del .pfx con EMPRESA_RUT / configuración ERP."""
    from services import facturacion_electronica_service as fe

    rut_cfg = (rut_empresa or os.getenv('EMPRESA_RUT') or '8054120-1').strip()
    out: Dict[str, Any] = {
        'rut_empresa_config': rut_cfg,
        'rut_certificado': None,
        'rut_coincide': None,
        'error': None,
    }
    try:
        cuerpo_cfg, dv_cfg = split_rut(rut_cfg)
        rut_cfg_norm = f'{cuerpo_cfg}-{dv_cfg}'
        _pk, cert = _cargar_clave_certificado_pfx()
        rut_cert = extraer_rut_desde_certificado(cert)
        out['rut_certificado'] = rut_cert
        if rut_cert:
            cuerpo_c, dv_c = split_rut(rut_cert)
            out['rut_coincide'] = cuerpo_c == cuerpo_cfg and dv_c == dv_cfg
        else:
            out['rut_coincide'] = None
            out['error'] = 'no_se_pudo_leer_rut_del_certificado'
    except Exception as ex:
        out['error'] = f'{type(ex).__name__}:{str(ex)[:200]}'
    return out


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
        root = _parsear_respuesta_sii_negocio(raw)
        det = _detalle_respuesta_sii(root)
        estado = det['estado']
        semilla = det['semilla']
        ok = (estado or '') == '00' and bool(semilla)
        err = None if ok else 'semilla_no_obtenida'
        if not ok and det.get('glosa'):
            err = f'{err}:{det["glosa"]}'
        return ResultadoSemilla(
            ok=ok,
            semilla=semilla,
            estado=estado,
            raw=str(raw)[:8000] if raw is not None else None,
            error=err,
        )
    except Exception as ex:
        return ResultadoSemilla(
            ok=False,
            error=f'{type(ex).__name__}:{str(ex)[:300]}',
            raw=str(raw)[:8000] if raw is not None else None,
        )


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


ENV_ALG_ENVELOPED = 'http://www.w3.org/2000/09/xmldsig#enveloped-signature'


def _normalizar_valor_semilla(semilla: str) -> str:
    """Valor semilla plano: sin espacios, saltos de línea ni caracteres de control."""
    return re.sub(r'\s+', '', str(semilla or '').strip())


def _armar_xml_semilla_sin_firma(semilla_valor: str):
    """
    Estructura XSD Maullín GetTokenFromSeed (manual autenticación v1.9):
    <getToken><item><Semilla>VALOR</Semilla></item></getToken>
    Sin espacios ni saltos de línea entre nodos.
    """
    from lxml import etree

    v = _normalizar_valor_semilla(semilla_valor)
    if not v:
        raise ValueError('semilla_vacia')
    root = etree.Element('getToken')
    item = etree.SubElement(root, 'item')
    sem = etree.SubElement(item, 'Semilla')
    sem.text = v
    return root, v


def _serializar_xml_iso8859(root) -> bytes:
    from lxml import etree

    raw = etree.tostring(
        root,
        xml_declaration=True,
        encoding='ISO-8859-1',
        pretty_print=False,
    )
    # Sin espacios ni saltos de línea entre etiquetas (contenido de texto intacto).
    return re.sub(rb'>\s+<', b'><', raw)


def _xml_semilla_plano_compacto(semilla_valor: str) -> str:
    """Representación compacta esperada por SII (sin firma)."""
    v = _normalizar_valor_semilla(semilla_valor)
    return f'<getToken><item><Semilla>{v}</Semilla></item></getToken>'


class _XMLSignerSiiSha1:
    """Firma XML semilla SII: C14N 1.0 + RSA-SHA1 + enveloped URI=\"\" (manual v1.9)."""

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
        signed = cls._signer().sign(
            root,
            key=key,
            cert=[cert],
            always_add_key_value=True,
            exclude_c14n_transform_element=True,
        )
        _ajustar_transforms_firma_semilla_sii(signed)
        return signed


def firmar_xml_semilla_token(semilla: str) -> bytes:
    """
    Arma y firma el XML de semilla para GetTokenFromSeed (pszXml en SOAP).

    - Documento: <getToken><item><Semilla ID="X">X</Semilla></item></getToken>
    - Reference URI="#X" (nodo Semilla con atributo ID)
    - Un solo Transform: enveloped-signature
    - SignedInfo C14N: REC-xml-c14n-20010315
    - Salida ISO-8859-1
    """
    private_key, certificate = _cargar_clave_certificado_pfx()
    root, semilla_id = _armar_xml_semilla_sin_firma(semilla)
    signed = _XMLSignerSiiSha1.sign(root, key=private_key, cert=certificate)
    _validar_firma_semilla_sii(signed, semilla_id)
    return _serializar_xml_iso8859(signed)


def _ajustar_transforms_firma_semilla_sii(root) -> None:
    """Elimina Transform C14N redundante en Reference; solo enveloped-signature."""
    ns = {'ds': NS_XMLDSIG}
    for ref in root.findall('.//ds:Reference', namespaces=ns):
        transforms = ref.find('ds:Transforms', namespaces=ns)
        if transforms is None:
            continue
        for tr in list(transforms.findall('ds:Transform', namespaces=ns)):
            if (tr.get('Algorithm') or '') != ENV_ALG_ENVELOPED:
                transforms.remove(tr)


def _validar_firma_semilla_sii(root, semilla_id: str) -> None:
    """Comprueba estructura y algoritmos exigidos por SII antes de enviar a Maullín/Palena."""
    from lxml import etree

    ns = {'ds': NS_XMLDSIG}
    sid = _normalizar_valor_semilla(semilla_id)
    uri_esperado = ''

    if etree.QName(root).localname != 'getToken':
        raise ValueError('firma_semilla_raiz_invalida')
    sem = root.find('.//Semilla')
    if sem is None:
        raise ValueError('firma_semilla_sin_nodo_Semilla')
    if (sem.text or '').strip() != sid:
        raise ValueError('firma_semilla_texto_invalido')

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
    if ref is None or (ref.get('URI') or '') != uri_esperado:
        raise ValueError('firma_semilla_reference_uri_invalido')
    env = ref.find(f'.//ds:Transform[@Algorithm="{ENV_ALG_ENVELOPED}"]', namespaces=ns)
    if env is None:
        raise ValueError('firma_semilla_sin_enveloped_transform')
    extra = ref.findall('ds:Transforms/ds:Transform', namespaces=ns)
    if len(extra) != 1:
        raise ValueError('firma_semilla_transforms_invalido')


def obtener_token(semilla: str, ambiente: Optional[str] = None) -> ResultadoToken:
    """Firma la semilla y solicita token de sesión al SII."""
    base = url_base_sii(ambiente)
    wsdl = base + '/DTEWS/GetTokenFromSeed.jws?wsdl'
    raw: Any = None
    try:
        xml_firmado = firmar_xml_semilla_token(semilla)
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
        root = _parsear_respuesta_sii_negocio(raw)
        det = _detalle_respuesta_sii(root)
        estado = det['estado']
        token = det['token']
        ok = (estado or '') == '00' and bool(token)
        err = None if ok else 'token_no_obtenido'
        if not ok:
            if det.get('glosa'):
                err = f'{err}:{det["glosa"]}'
            elif estado and estado != '00':
                err = f'{err}:estado_{estado}'
        return ResultadoToken(
            ok=ok,
            token=token,
            estado=estado,
            raw=str(raw)[:8000] if raw is not None else None,
            error=err,
        )
    except Exception as ex:
        _logger.exception('obtener_token SII falló')
        return ResultadoToken(
            ok=False,
            error=f'{type(ex).__name__}:{str(ex)[:300]}',
            raw=str(raw)[:8000] if raw is not None else None,
        )


def conectar_sii(ambiente: Optional[str] = None) -> ResultadoToken:
    """Semilla + token en un paso (diagnóstico de certificado y red)."""
    sem = obtener_semilla(ambiente)
    if not sem.ok or not sem.semilla:
        return ResultadoToken(ok=False, error=sem.error or 'semilla_fallo', estado=sem.estado)
    return obtener_token(sem.semilla, ambiente)


def date_hoy_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _config_resolucion_sii() -> Tuple[str, int]:
    """Maullín SD: FchResol 2021-03-24 / NroResol 0 (pantalla ad_empresa Maullín)."""
    fch = (os.getenv('SII_FCH_RESOLUCION') or '2021-03-24').strip()[:10]
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
    out.update(auditar_rut_certificado_vs_empresa())
    sem = obtener_semilla(amb)
    out['semilla_ok'] = sem.ok
    out['semilla_estado'] = sem.estado
    if not sem.ok:
        out['semilla_error'] = sem.error
        if sem.raw:
            out['semilla_respuesta_cruda'] = sem.raw
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
            out['token_respuesta_cruda'] = tok.raw
        try:
            xml_env = firmar_xml_semilla_token(sem.semilla or '')
            out['token_xml_firmado_enviado'] = xml_env.decode('iso-8859-1', errors='replace')[:4000]
        except Exception as ex_xml:
            out['token_xml_firmado_error'] = str(ex_xml)[:300]
        if tok.estado == '10':
            out['token_nota'] = (
                'ESTADO 10 = SII rechaza getToken (firma o certificado no habilitado en Maullín). '
                'Revise: certificado vigente, usuario autorizado, software de mercado LhexIA '
                '(no solo Multicaja boletas). Ver scripts/fe_resolver_facturas.py'
            )
        elif tok.estado == '12':
            out['token_nota'] = 'ESTADO 12 = RECHAZO POR RUT CERTIFICADO (titular .pfx distinto al registrado)'
    else:
        out['token_preview'] = (tok.token or '')[:8] + '…' if tok.token else None
    return out
