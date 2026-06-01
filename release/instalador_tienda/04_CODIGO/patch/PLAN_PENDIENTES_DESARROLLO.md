# Plan de pendientes a desarrollar (post piloto SD-1)

**Actualizado:** 2026-05-29  
**Regla:** no bloquear piloto Santo Domingo (POS + inventario + vitrina). Items aquí = **después de sign-off QAS** o cuando el ERP esté estable en piso.

**Foco actual:** piloto SAMBOX / operación diaria — ver `respaldos/transporte/` y commit vitrina.

---

## Bugs piloto (corregir en DEV → OT QAS → PRD)

| # | Problema | Estado | Archivos |
|---|----------|--------|----------|
| 1 | TV no muestra productos al seleccionar/agregar en POS | **Corregido 2026-05-29** | `app.py`, `pos-experience-wall.js`, `pos.js` |
| 2 | Vales pendientes sin recordatorio ni limpieza por tiempo | **Corregido 2026-05-29** | `services/caja_vale_sla_service.py`, `app.py`, `caja_pendientes.html`, `blueprints/caja.py` |
| 3 | TV idle “Acérquese” sin cámara — modo vitrina Chilemat | **Corregido 2026-05-29** | `services/pos_tv_vitrina_service.py`, `pos-experience-wall.js`, `pos_live_wall_cliente.html` |

### 3. Modo vitrina TV (catálogo + Chilemat)

**Comportamiento:** carrusel de proyectos Chilemat (relaciones `producto_relacion`), destacados catálogo, slide marca; tras emitir vale ~42 s de gracias y luego vitrina.

**API:** campo `vitrina_attract` en snapshot live wall (cache 5 min).

---

### 2. SLA vales pendientes (10 / 15 / 20 min)

**Comportamiento:** badge a los 10 min, modal cobrar/anular a los 15 min, auto-anulación a los 20 min (solo `Pendiente`, misma caja, sin despacho bodega).

**Config:** `CAJA_VALE_SLA_ALERTAS=10,15`, `CAJA_VALE_SLA_ANULAR=20`, `CAJA_VALE_SLA_MOTIVO_AUTO`.

**API:** `GET /api/caja/vales-pendientes/sla` (polling cada 30 s en cola de cobro).

---

### 1. TV sin líneas al agregar producto

**Síntoma:** Experience Wall queda en pantalla idle o sin carrito al elegir productos en POS.

**Causas:** snapshot con detalles stale; token estación no encontraba vale si usuario/caja no coincidía; overlay ocultaba carrito.

**Fix:** re-query vale+líneas en snapshot, fallback vale Abierta por caja, mostrar carrito si `nItems > 0`, refresh tras escaneo.

---


### Guía de despacho (integración ERP)

**Contexto (consulta 2026-05-29):** hoy el ERP tiene recepción con tipo «Guía de despacho» (entrada proveedor) y despacho operativo POS/bodega (QR, canal `Despacho`), pero **no** emite DTE 52 al SII.

| Etapa | Alcance | Cuándo |
|-------|---------|--------|
| **A — Guía interna PDF** | Imprimir guía desde venta Pagada con líneas `Despacho`: cliente, dirección, ítems, firma, folio interno. Enlace a bodega/QR existente. | Post piloto, bajo riesgo |
| **B — Guía electrónica SII (DTE 52)** | Extender `facturacion_electronica_service`: XML 52, CAF, envío SII, PDF timbrado, referencia opcional a Factura 33 | Tras FE factura 33 estable + definición contador |
| **C — Flujo completo venta + entrega** | POS dirección → bodega prepara → GD al salir → caja boleta/factura referenciada | Post B |

**Ya existe (no rehacer):**

- Compras: `/recepciones/nueva` → tipo documento «Guía de despacho», adjunto, IA líneas.
- Ventas: canal retiro `Despacho`, `/pos/despacho/vale/`, plataforma bodega, voz.

**Decisiones pendientes (1 reunión piso):**

1. ¿Guía de **entrada**, **salida cliente**, o **traslado tienda–bodega**?
2. ¿Documento **SII** o basta **interno** en primera versión?
3. ¿Despacho siempre post-cobro o a veces antes?
4. Boletas siguen en **Multicaja**; facturas/guías en ERP.

**Archivos tocados (estimado):** `app.py` (modelo/rutas), `services/facturacion_electronica_service.py`, templates PDF, permisos bodega/caja, tests smoke documentos.

---

## Prioridad P2 — Infraestructura y transporte

| Item | Descripción |
|------|-------------|
| **Plataforma OT (TMS)** | `ot_publicar` / `ot_recibir` vía git + bandeja nube; panel `/admin/transporte` | Post SD-1 |
| **Multi-sucursal VERTEX** | Tenant, sucursales, stock por local | Post SD-1 |
| **Agentes IA en prod** | CrewAI Guardián/Operador full | Post sign-off piloto |

---

## Prioridad P3 — Producto y e-commerce

Ver `PLAN_ECOM_PILOTO_v0.md`: carrito checkout, Webpay, reserva stock, deploy vitrina prod.

---

## Referencias

- Despacho operativo: `templates/pos/despacho_vale.html`, `bodega_plataforma`
- FE Chile: `services/facturacion_electronica_service.py` (DTE 33/39)
- Recepción guía proveedor: `templates/recepcion_nueva.html`
- Ambientes DEV/QAS/PRD: `.cursor/rules/entornos-desarrollo-sambox-productivo.mdc`
