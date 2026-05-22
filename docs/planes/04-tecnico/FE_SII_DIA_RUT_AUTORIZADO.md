# FE SII — Día dedicado (RUT ya autorizado)

**Emisor autorizado en portal SII:** `8054120-1` — LUIS GASTON RIVERA PEREZ (captura 2026-05-19).

**Estado LhexIA antes de este día:** XML mock + firma `.pfx` opcional; `enviar_dte_soap()` stub; sin TED real; CAF de laboratorio en tests.

**Objetivo del día:** conectar **Palena** (producción), validar **certificado + token**, cargar **CAF reales**, y dejar checklist para el primer DTE aceptado (TED + esquema XSD en iteración siguiente si el upload rechaza por esquema 7/8).

---

## Orden de trabajo (hoy)

| # | Tarea | Quién | Listo cuando |
|---|--------|--------|----------------|
| 1 | `.pfx` del RUT **8054120-1** en `instance/certs/` (no en git) | Mario / contador | `firmar_xml_dte` → `FIRMADO` |
| 2 | Variables en `.env.local` y Render (ver abajo) | DevOps | Script diagnóstico OK |
| 3 | `SII_SOAP_ENABLED=1` + `SII_AMBIENTE=produccion` | Dev | `diagnostico_sii` → `token_ok: true` |
| 4 | CAF boleta **39** (y factura **33** si aplica) desde portal SII → `/admin/facturacion/caf` | Operación | Folios visibles en admin |
| 5 | `EMPRESA_RUT=8054120-1` y razón social en `data/empresa_config.json` o env | Config | XML muestra RUT correcto |
| 6 | Resolución SII en env: `SII_FCH_RESOLUCION`, `SII_NRO_RESOLUCION` | Contador | Carátula EnvioDTE coherente |
| 7 | Prueba upload (esperable rechazo 7/8 hasta TED) | Dev | Respuesta SII parseada en log |
| 8 | **TED** con CAF real (`facturacion_ted_service.py`) | Dev | XML con `<TED>` + `<FRMT>`; upload `STATUS=0` |

---

## Variables de entorno

```env
EMPRESA_RUT=8054120-1
EMPRESA_RAZON_SOCIAL=LUIS GASTON RIVERA PEREZ

SII_CERT_PFX_PATH=instance/certs/emisor_8054120.pfx
SII_CERT_PFX_PASSWORD_FILE=instance/certs/pfx_password.txt
SII_AMBIENTE=produccion
SII_SOAP_ENABLED=1

# Fecha y número de resolución que aparecen en el portal SII del emisor
SII_FCH_RESOLUCION=2026-05-19
SII_NRO_RESOLUCION=0

# Opcional: RUT persona que envía (representante legal); default = EMPRESA_RUT
# SII_RUT_ENVIA=8054120-1
```

**Maullín** (`SII_AMBIENTE=certificacion`) solo si repiten **set de certificación de software**; con emisor ya autorizado, las boletas reales van a **Palena**.

---

## Comandos locales

```powershell
cd "D:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\.venv\Scripts\activate
python scripts/fe_diagnostico_sii.py
python scripts/verificar_firma_sii_certificacion.py
```

API (admin, permiso `gestionar_usuarios`):

- `GET /api/admin/facturacion/diagnostico-sii?reload_env=1`
- `GET /api/admin/facturacion/emitir-prueba?dte_tipo=39&reload_env=1` (incluye `estado_envio` si SOAP activo)

---

## Qué NO bloquea el cobro

Política ERP: si el SII falla, la venta queda **Pagado** y `dte_estado=PENDIENTE_ENVIO`. Reintento: `/admin/facturacion/cola` o `POST /api/admin/facturacion/reintentar/<venta_id>`.

---

## Códigos de rechazo upload (referencia)

| STATUS | Significado |
|--------|-------------|
| 0 | OK — `TRACKID` asignado |
| 5 | Token inválido o expirado |
| 6 | Empresa no autorizada (RUT/envío) |
| 7 | Esquema inválido (falta TED/namespaces) |
| 8 | Firma del documento |

---

## Archivos tocados en este bloque

- `services/facturacion_sii_soap.py` — semilla, token, EnvioDTE, upload
- `services/facturacion_ted_service.py` — timbrado TED (RSASK del CAF)
- `services/facturacion_electronica_service.py` — `enviar_dte_soap()` real si `SII_SOAP_ENABLED=1`
- `scripts/fe_diagnostico_sii.py`
- `tests/test_facturacion_sii_soap.py`

---

*Última actualización: 2026-05-19 — SD-1 paralelo: no mezclar cambios POS con este carril.*
