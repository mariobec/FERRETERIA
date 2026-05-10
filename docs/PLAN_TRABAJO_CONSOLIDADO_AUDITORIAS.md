# Plan de trabajo consolidado (Grok + Gemini + Copilot)

> **Referencia actualizada (10/10, Grok mayo 2026):** [PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md](./PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md) — decisiones cerradas, fases 1A–4 y checklist de pruebas.

**Objetivo:** cerrar riesgos de negocio e inventario **antes** del refactor estructural grande; modularizar **por etapas** sin romper POS, caja, permisos ni anti–doble descuento Tienda/Bodega.

**Principios (no negociables):**

- Preservar invariante: `consumo_bodega_acumulado + consumo_tienda_al_cobrar ≤ consumo_total` por línea.
- No cambiar semántica de `ventas.estado` (Abierta / Pendiente / Pagado / Anulada) ni romper `@permisos_required` / `@caja_requerida`.
- WhatsApp Cloud **fuera** de la transacción SQL: **solo después** de `commit` exitoso de stock+kardex+venta (o cola dedicada).
- Cambios en stock/caja: difs pequeños, revisables, con pruebas manuales checklist.

---

## Decisiones pendientes (definir antes o durante Fase 1A)

1. **Vale despachado en bodega y sin cobro tras X horas:** ¿solo **alerta** (UI/email/log) o **acción automática** (ej. recordatorio WA al cliente / flag en pantalla caja)? Evitar auto-anulación con reversión de stock **sin** política explícita de negocio.
2. **Anulación con despacho bodega:** ¿`anular_vale_caja` + reversión automática para todos, o **solo** con permiso `gestionar_usuarios` (o permiso nuevo `anular_vale_con_despacho_bodega`)?

---

## Fase 1A — Estabilidad inmediata (máxima prioridad)

| # | Entrega | Origen | Acción concreta |
|---|---------|--------|------------------|
| 1.1 | **`audit_log` (o `auditoria_movimientos`)** | Grok, Copilot | Migración SQL MySQL + Postgres; modelo SQLAlchemy; helper `_audit_log(...)`; escritura en: cobro caja, despacho voz, anulación vale, ajustes stock críticos (mínimo viable). |
| 1.2 | **`_revertir_stock_bodega_por_anulacion(venta)`** (nombre final a acordar) | Grok, Copilot | Si `bodega_despacho_json` tiene consumo > 0: **ENTRADA** en bodega por cada línea afectada, kardex, limpiar `bodega_despacho_json` / `bodega_despacho_estado`, refrescar `productos.stock`. Idempotente donde sea posible. |
| 1.3 | **Integrar reversión en `anular_vale_caja`** | Grok, Copilot | Antes de marcar `Anulada`: si hay despacho bodega, llamar reversión **en la misma transacción** que el resto de efectos de anulación; si falla, rollback + mensaje claro. |
| 1.4 | **Transacciones BD en flujos críticos** | Grok, Copilot | `procesar_cobro_caja`: un solo bloque try/commit con rollback global en error; sin commits parciales en medio. `_bodega_voice_ejecutar`: mismo criterio; **mover envío WA después del commit** (o registrar intento fallido en `audit_log`). |
| 1.5 | **Validación de invariante** antes de persistir despacho | Copilot | Función única que valide límites por `detalle_id` antes de sumar a JSON y descontar bodega. |
| 1.6 | **UI caja** | Grok | En `caja_pendientes` (o detalle): badge “Despacho bodega” + tooltip de riesgo si se anula sin permiso / con reversión. |

**Criterio de hecho Fase 1A:** anular un vale con `bodega_despacho_json` no vacío deja inventario coherente y deja fila(s) en `audit_log`.

---

## Fase 1B — Política “vale despachado sin cobro”

| # | Entrega | Origen | Acción |
|---|---------|--------|--------|
| 1.7 | **Columna opcional** `ventas.bodega_despacho_ultimo_at` (TIMESTAMP) o derivado de `audit_log` | Grok | Actualizar al cada despacho voz exitoso. |
| 1.8 | **Worker / endpoint cron** (Bearer, mismo patrón que C360/cobranza) | Grok | Env `VALE_DESPACHO_SIN_COBRO_ALERTA_HORAS` (default conservador). Listar vales `Pendiente` + `metodo_pago` vacío + despacho no null + antigüedad > umbral → log + opcional WA interno / flag (según decisión 1). |

**Criterio de hecho:** operación puede **ver** vales en riesgo sin depender de SQL manual.

---

## Fase 2 — Servicios sin cambiar rutas (extracción segura)

| # | Entrega | Origen | Acción |
|---|---------|--------|--------|
| 2.1 | **`services/stock_service.py`** | Gemini, Copilot | Mover (copiar primero, delegar desde `app.py`): anti–doble descuento, `_venta_consumo_ya_despachado_bodega`, helpers de validación, reversión bodega. |
| 2.2 | **`services/kardex_service.py`** | Copilot | Wrapper delgado sobre `registrar_movimiento_kardex` + reglas de referencia. |
| 2.3 | **`services/whatsapp_outbound.py`** | Gemini, Copilot | Centralizar `_whatsapp_cloud_send_text` + normalización teléfono; post-commit desde despacho/cobranza. |
| 2.4 | **`services/ia_governance.py`** (opcional nombre) | Copilot | Timeouts, límites de cantidad por comando voz, registro prompt/respuesta en `audit_log` o tabla `ia_comando_log` si el volumen lo exige. |

**Criterio de hecho:** `app.py` delega en servicios; tests manuales siguen verdes; líneas netas en `app.py` bajan de a poco.

---

## Fase 3 — Blueprints (un dominio a la vez)

| # | Entrega | Origen | Acción |
|---|---------|--------|--------|
| 3.1 | **`blueprints/bodega.py`** | Gemini | Registrar `/bodega/despachos` y `/api/bodega/voice-command` reutilizando funciones ya extraídas a `services/`. |
| 3.2 | Repetir patrón para **caja** o **c360** solo cuando Fase 2 esté estable | Gemini | Evitar mover todo en un solo PR. |

---

## Fase 4 — Colas y async (solo si hay dolor medible)

| # | Entrega | Origen | Acción |
|---|---------|--------|--------|
| 4.1 | Cola ligera (RQ/Celery) **o** worker HTTP existente ampliado | Gemini | Para WA masivo, C360 batch, reabasto — **después** de medir timeouts y carga. |

---

## Fase 5 — Backlog arquitectura / producto (2027+, no bloquea producción)

- Modelos on-edge, picking asistido, BIM, smart contracts: **roadmap comercial**, no sprint actual.
- Migración motor **Postgres** por JSON: evaluar cuando las consultas analíticas sobre JSON lo exijan.

---

## Checklist manual mínimo (tras cada PR de Fase 1A)

1. Vale sin despacho: cobrar → stock tienda correcto.  
2. Vale con despacho parcial bodega: cobrar → solo remanente en tienda.  
3. Vale con despacho: anular → bodega restaurada, JSON limpio, kardex coherente.  
4. Voz: fallo simulado post-commit de WA → stock no se revierte por error de WA.  
5. Permisos: usuario sin permiso no ejecuta anulación con reversión si la política lo exige.

---

## Orden sugerido de implementación en Cursor

1. Migración `audit_log` + helper + 2–3 escrituras piloto.  
2. Reversión bodega + integración `anular_vale_caja` + transacción.  
3. Reordenar WA en voice-command + transacción cobro.  
4. UI caja + env + worker alerta (1B).  
5. Iniciar Fase 2 con `stock_service` únicamente.

---

*Documento vivo: actualizar al cerrar cada fase y al tomar decisiones 1–2.*
