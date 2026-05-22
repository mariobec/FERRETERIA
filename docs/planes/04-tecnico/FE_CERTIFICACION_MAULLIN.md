# FE — Ambiente de certificación Maullín (LhexIA)

Plan reajustado: **desarrollo solo en certificación**; producción (Palena) y coexistencia con facturador gratuito SII quedan para go-live.

## Objetivos

| Fase | Qué |
|------|-----|
| **Ahora (Maullín)** | Boleta 39 + **Factura 33** en código; set de pruebas/simulación; CAF de laboratorio con RSASK |
| **Go-live** | Palena + CAF reales; facturas también desde LhexIA si el SII habilita timbraje 33; facturador gratuito sigue para quien lo use |

## Variables (.env.local — desarrollo)

```env
SII_AMBIENTE=certificacion
SII_SOAP_ENABLED=1
EMPRESA_RUT=8054120-1
EMPRESA_RAZON_SOCIAL=LUIS GASTON RIVERA PEREZ
SII_CERT_PFX_PATH=instance/certs/emisor.pfx
# Resolución ficticia o de certificación:
SII_FCH_RESOLUCION=2026-01-01
SII_NRO_RESOLUCION=0
```

URLs SOAP: **https://maullin.sii.cl** (automático si `SII_AMBIENTE=certificacion`).

---

## Opción A — CAF generados por LhexIA (recomendado para avanzar ya)

No reemplazan el CAF oficial del SII en certificación formal, pero permiten **TED + set de simulación en QA**.

```powershell
py scripts/fe_setup_caf_certificacion_maullin.py
py scripts/fe_setup_caf_certificacion_maullin.py --bd
```

Genera:

- `storage/dtes/caf_certificacion/CAF_cert_33.xml`
- `storage/dtes/caf_certificacion/CAF_cert_39.xml`

Rangos: factura **1–500**, boleta **1–500** (tipo DTE en XML).

Luego:

```powershell
py scripts/verificar_firma_sii_certificacion.py
```

O API:

`GET /api/admin/facturacion/emitir-prueba?modo=set_certificacion&reload_env=1&zip=1`

Los XML del set incluyen **TED timbrado** si `timbrar_con_caf_cert=true` (default).

Prueba factura suelta:

`GET /api/admin/facturacion/emitir-prueba?dte_tipo=33&folio=1&reload_env=1`

(con CAF 33 en BD vía `--bd`).

---

## Opción B — Folios oficiales Maullín (certificación de software)

Cuando el SII exija CAF emitidos por ellos en el **ambiente de certificación**:

1. Postular **certificación de software** en [www.sii.cl](https://www.sii.cl) → Factura electrónica → certificación (no es el mismo flujo que Palena producción).
2. Tras aceptación en ambiente certificación, timbraje en **Maullín** (URL análoga a producción pero host `maullin.sii.cl`).
3. En el combo pueden aparecer **33, 39, 61** según el set asignado.
4. Descargar AUTORIZACION `.xml` con **RSASK** y cargar en `/admin/facturacion/caf`.

Documentación SII: [Portal FE — información técnica](https://www.sii.cl/servicios_online/1041-informacion_tecnica-1324.html).

---

## Factura 33 en LhexIA (código)

| Pieza | Archivo |
|-------|---------|
| Tipo DTE 33 | `facturacion_electronica_service.py` — `DTE_TIPO_FACTURA_AFECTA`, `resolver_dte_tipo_por_tipo_documento('Factura')` |
| XML factura | `generar_xml_dte_prueba_lxml` — Giro, Acteco, receptor extendido |
| Cobro | `tipo_documento=Factura` en caja → emisión 33 + CAF tipo 33 |
| Cert Maullín | `generar_xml_caso2_factura_33`, set certificación |
| CAF lab | `facturacion_caf_certificacion.py` |
| Receptor prueba SII | `55.555.555-5` (`RUT_RECEPTOR_PRUEBA_SII`) en certificación |

En **certificación**, ventas con Factura usan RUT receptor de prueba SII automáticamente.

---

## Coexistencia futura (go-live)

```text
Mismo RUT 8054120-1
├── Facturador gratuito SII  → facturas que sigan ahí
├── LhexIA boleta 39         → CAF 39 Palena
└── LhexIA factura 33        → CAF 33 Palena (cuando SII habilite timbraje 33 en producción)
```

---

## Comandos resumen

```powershell
py scripts/fe_setup_caf_certificacion_maullin.py --bd
py scripts/verificar_firma_sii_certificacion.py
py scripts/fe_diagnostico_sii.py
py scripts/fe_diagnostico_sii_reintentos.py --intentos 5 --pausa 10   # manual; no en background
py -m pytest tests/test_facturacion_ted.py tests/test_facturacion_sii_soap.py -q
```

## Pausa operativa (2026-05-20)

**Esperar habilitación SII** — petición administrativa folio **77326378627** (*Solicitud folios electrónicos y Timbraje*), estado **Recepcionada** para RUT 8054120-1. No bombardear Maullín (503 intermitente; evitar DoS).

**Prueba manual cuando haya ventana + timbraje:**

```http
GET /api/admin/facturacion/diagnostico-sii?reload_env=1
GET /api/admin/facturacion/enviar-prueba-sii?dte_tipo=33&folio=1&reload_env=1
```

---

*2026-05-20 — Plan reajustado tras requerimiento Factura 33 + solo Maullín en dev; backend listo, timbraje SII pendiente.*
