# Plan de trabajo consolidado v2.0 — ERP LhexIA (10/10)

**Objetivo:** Eliminar los riesgos críticos de negocio e inventario antes de cualquier refactor estructural grande. Modularizar progresivamente sin romper flujos existentes.

**Versión:** 2.0 (mejorada por Grok — mayo 2026)  
**Estado:** **Cerrado para alcance v2.0** (mayo 2026). Lo definido en Fases 1A–3 y el núcleo acordado de Fase 4 está implementado o documentado como backlog explícito más abajo.

### Cierre formal v2.0

| Fase | Cierre |
|------|--------|
| **1A** | Cerrada: criterio de negocio + `transaccion_critica()` también en `guardar_venta`, carrito POS (`agregar_producto_venta`, `eliminar_detalle`, `actualizar_item`), `finalizar_venta`, ajustes stock UI (`editar_stock_producto`, `actualizar_stock_masivo_productos`), carga masiva catálogo (`cargar_productos` CSV/Excel + `_audit_log` `carga_masiva_productos_archivo`). **Backlog menor:** otras rutas masivas legacy si aparecen. |
| **1B** | Cerrada. |
| **2** | Cerrada para la lista de servicios del plan; `app.py` puede seguir reduciéndose en evoluciones posteriores. |
| **3** | Cerrada según blueprints listados. |
| **4** | **Cerrada para alcance v2:** salud (`/api/sistema/salud`), cron + Slack, conteos en salud. Métricas finas (latencia voice-command, errores por endpoint, email) = **backlog v3+**. |

---

## Principios no negociables (invariantes)

1. Preservar invariante de stock: `consumo_bodega_acumulado + consumo_tienda_al_cobrar ≤ consumo_total` por cada línea de `detalle_ventas`.
2. No alterar semántica de `ventas.estado` (Abierta, Pendiente, Pagado, Anulada).
3. Mantener intactos los decoradores `@permisos_required` y `@caja_requerida`.
4. Todos los cambios críticos de stock, caja y kardex dentro de una misma transacción (agrupación coherente con rollback).
5. Envíos de WhatsApp siempre **fuera** de la transacción (post-commit exitoso o en cola).
6. Todo cambio debe ser **revisable** y **reversible** (migraciones, auditoría, difs acotados).

---

## Decisiones estratégicas definidas

| Decisión | Resolución | Responsable |
|----------|------------|-------------|
| Vale despachado sin cobro después de X horas | Alerta + flag visible + recordatorio WA automático (**no** auto-anulación por ahora) | Negocio + técnico |
| Anulación de vale con despacho bodega | Nuevo permiso `anular_vale_con_despacho_bodega` (Admin / Gerente / Supervisor bodega, según mapeo en roles) | Técnico |
| Nivel de granularidad de audit log | Alta (incluye antes/después en cambios críticos) | Técnico |

---

## Fase 1A — Estabilidad inmediata y corrección de riesgos críticos — **cerrada (alcance v2)**

**Prioridad:** máxima  
**Duración estimada:** 5–7 días

| # | Entrega | Detalle | Criterio de aceptación |
|---|---------|---------|------------------------|
| 1.1 | Tabla `erp_audit_log` | Migración / creación en arranque, modelo SQLAlchemy, helper `_audit_log(evento, entidad_tipo, entidad_id, usuario, datos_antes=None, datos_despues=None, ip=None)` | Registros en cobro, despacho voz, anulación y ajustes stock críticos |
| 1.2 | `_revertir_stock_bodega_por_anulacion(venta, usuario)` | Idempotente si JSON vacío; kardex ENTRADA bodega; limpia `bodega_despacho_json`, `bodega_despacho_estado`, `bodega_despacho_ultimo_at`; stock maestro coherente | Ejecutada dos veces no duplica movimientos |
| 1.3 | Integración en `anular_vale_caja` | Si existe despacho → reversión en la misma transacción (savepoint); permiso especial | Anulación deja inventario coherente |
| 1.4 | Transacciones atómicas en flujos críticos | Contexto `transaccion_critica()` + uso en `procesar_cobro_caja`, `_bodega_voice_ejecutar`, anulación y ajustes stock | Sin commit parcial ante error; rollback completo |
| 1.5 | Validación centralizada de invariante | `stock_validar_invariante_venta(venta)` antes de persistencia relevante | Operación rechazada si se viola el invariante |
| 1.6 | Mejoras UI caja | Badge «Despachado en Bodega», tooltip de riesgo, advertencia al anular; bloqueo de anular sin permiso extra | Cajero ve el estado y las reglas |
| 1.7 | Columna `ventas.bodega_despacho_ultimo_at` | Timestamp en cada despacho voz exitoso | Facilita queries y worker |

**Criterio de cierre Fase 1A:** Se puede anular un vale con despacho bodega y el inventario queda coherente, con registro completo en `erp_audit_log`.

### Estado Fase 1A — verificación técnica (revisión código, mayo 2026)

| Requisito plan | Estado | Notas |
|----------------|--------|--------|
| `transaccion_critica()` en `procesar_cobro_caja` | Cumple | Savepoint envuelve mutación venta/stock/kardex + `_audit_log`; validaciones de saldo a favor / monto recibido movidas **fuera** del savepoint (corrige `rollback`+`redirect` dentro del nested, que rompía atomicidad). |
| `transaccion_critica()` en `_bodega_voice_ejecutar` | Cumple | Ruta `POST /api/bodega/voice-command` → `api_bodega_voice_command`. Invariante validado antes de cerrar savepoint; WhatsApp **después** de `commit`. |
| `transaccion_critica()` en `anular_vale_caja` | Cumple | Reversión bodega + marca `Anulada` en mismo savepoint; `_audit_log` y `commit` externos al `with` pero en la misma transacción de sesión. |
| Otros flujos stock/kardex críticos | **Cumple** (ext. mayo 2026) | `transaccion_critica()` en `guardar_venta` (venta directa + stock + kardex + crédito), `agregar_producto_venta`, `eliminar_detalle`, `actualizar_item`, `finalizar_venta` (cliente + vale Pendiente), `editar_stock_producto`, `actualizar_stock_masivo_productos`, `cargar_productos` (bucle de filas; incluye `aplicar_stock_desde_catalogo_a_tienda` cuando el archivo trae columna stock). |
| `_revertir_stock_bodega_por_anulacion` | Cumple | Idempotente si map vacío: **corrige** limpieza de `bodega_despacho_json` cuando no hay cantidades (antes solo limpiaba estado/timestamp). Con datos: ENTRADA kardex por línea, refresco stock, luego `json/estado/ultimo_at` = NULL. |
| `_audit_log` puntos clave | Cumple alcance v2 | Cobro caja, despacho voz, anulación; UI inventario (`ajuste_stock_producto_ui`, `ajuste_stock_masivo_ui`); API enrolamiento (`enrolamiento_*`); carga masiva catálogo (`carga_masiva_productos_archivo`). Otras rutas masivas no inventariadas: **backlog** v3 si aplica. |
| `stock_validar_invariante_venta` | Cumple | Llamado en cobro caja (antes del savepoint) y en despacho voz (dentro, tras actualizar JSON). |
| Permiso `anular_vale_con_despacho_bodega` | Cumple | Backend bloquea si hay despacho y no tiene permiso ni `gestionar_usuarios`. UI deshabilita anular salvo permiso (`caja_pendientes.html`). |
| UI badge despacho | Cumple | Badge «Despachado en Bodega» + tooltip Bootstrap en cola de cobro (`tiene_despacho_bodega`). |

---

## Fase 1B — Política de vales despachados sin cobro — **cerrada (mayo 2026)**

| # | Entrega | Detalle |
|---|---------|---------|
| 1.8 | Worker de alertas | `POST /api/ventas/alertas-despachos-pendientes` con Bearer (`VALE_DESPACHO_ALERTAS_CRON_SECRET` o fallback `COBRANZA_DISPATCH_CRON_SECRET`). `VALE_DESPACHO_SIN_COBRO_ALERTA_HORAS` (default 48). JSON: `dry_run`, `send_wa`, `send_wa_interno`, `notify_slack`, `use_view`, `max`. |
| 1.9 | Vista SQL | Scripts `sql/2026_05_08_vista_vales_riesgo_despacho_postgresql.sql` y `_mysql.sql`. Documentación operativa: `sql/README_VISTA_VALES_RIESGO.md`. |
| 1.10 | Notificaciones | WA cliente (`send_wa`), WA interno (`send_wa_interno` + `VALE_DESPACHO_ALERTA_INTERNA_WA` / `WHATSAPP_VENTAS`), Slack (`notify_slack` + webhooks / `VALES_RIESGO_SLACK_MIN`). |
| — | Dry-run / QA | Con `dry_run: true` se devuelve `dry_run_previews` (textos WA interno y Slack) sin enviar. Script: `scripts/smoke_alertas_vales_despacho.py`. |
| — | Auditoría cron | Si hubo envío exitoso (WA cliente, WA interno o Slack), se registra `erp_audit_log` evento `cron_alertas_vales_despacho` y `commit` dedicado. |

---

## Fase 2 — Extracción de servicios (sin romper rutas) — **cerrada (alcance v2)**

**Orden recomendado:**

1. `services/stock_service.py` (crítico) — **implementado ampliado** (JSON bodega, invariante, reversión, estado despacho; `tablas_inventario_almacen_existen`, resolución TIENDA/BODEGA + códigos + invalidación cache; `stock_producto_en_almacen`, disponibilidad, mapa POS, `stock_ui_producto`, `descontar`/`incrementar`, `venta_validar_stock_tienda`, `ajustar`/`fijar`, `refrescar_stock_total_producto`; `app.py` delega con mismos nombres públicos)  
2. `services/kardex_service.py` — **implementado** (`registrar_movimiento_kardex`, bitácoras costo/precio opcionales; `app.py` delega)  
3. `services/venta_service.py` — **implementado** (`transaccion_critica`)  
4. `services/whatsapp_service.py` — **implementado** (`wa_cloud_config`, `whatsapp_cloud_send_text`, `enviar_texto_cloud`; `app.py` delega)  
5. `services/audit_service.py` — **implementado**  
6. `services/unidades_service.py` — **implementado** (`unidades_disponibles`, `seed_unidades_base`, `factor_compra_a_stock`, `factor_venta_a_stock`; `app.py` delega `_unidades_*` y `_factor_*`)

---

## Fase 3 — Blueprints por dominio — **cerrada (alcance v2)**

**Orden seguro:**

1. `blueprints/bodega.py` — **hecho** (registro de rutas)  
2. `blueprints/caja.py` — **hecho**  
3. `blueprints/pos.py` — **hecho**  
4. `blueprints/c360.py` — **hecho** (rutas `/gerencia/c360*`, `/api/c360/*`, `/admin/.../c360`, landing `/p/c360-oferta/*`; lógica en `services/c360_service.py`).

---

## Fase 4 — Observabilidad y madurez — **cerrada para alcance v2**

- Métricas clave (vales en riesgo, errores de transacción, tiempo de voice-command, etc.). **En v2:** conteo vales riesgo + auditoría 24h en salud. **Backlog v3+:** latencia voice-command, contadores de errores por endpoint.
- Dashboard básico de salud del sistema. **Hecho:** `GET /api/sistema/salud` (`services/sistema_health_service.py`).
- Alertas Slack cuando haya ≥ N vales en riesgo. **Hecho (cron):** `POST /api/ventas/alertas-despachos-pendientes` con JSON `notify_slack: true`, `SLACK_WEBHOOK_URL` o `ERP_SLACK_WEBHOOK_URL`, umbral `VALES_RIESGO_SLACK_MIN` (default 1). Email = backlog.

---

## Checklist de pruebas manuales (obligatoria tras cambios en Fase 1)

- Vale normal → cobro → stock tienda correcto.  
- Vale con despacho parcial → cobro → solo remanente en tienda.  
- Vale con despacho completo → cobro → sin descuento en tienda.  
- Vale con despacho → anulación → bodega restaurada + kardex correcto.  
- Fallo de WhatsApp después de commit → stock **no** se revierte.  
- Intento de anulación sin permiso especial → bloqueado.  
- Violación de invariante → operación rechazada.  

---

## Recomendaciones adicionales (10/10)

- Crear `docs/FLUJOS_CRITICOS.md` con diagramas Mermaid actualizados.  
- Mantener `transaccion_critica()` (o decorador equivalente) como patrón único en mutaciones ligadas.  
- Columna `version` (optimistic locking) en `ventas` y `detalle_ventas` (opcional, recomendado antes de Fase 2 intensa).  
- Mantener `app.py` lo más delegado posible durante la Fase 2.  

---

## Nota de alineación con el repo (mayo 2026)

**Estado implementación — plan v2.0 dado por cerrado:**

- **Fase 1A–1B:** entregadas según criterios de negocio y tabla de verificación; `transaccion_critica()` alineada a fila 1.4 en venta directa, POS (líneas / total / emitir vale), ajustes stock UI y `cargar_productos`. `_audit_log` en carga masiva catálogo; otras rutas masivas no inventariadas → backlog v3 si aplica.
- **Fase 2:** servicios del plan extraídos (`stock_service`, `kardex_service`, `whatsapp_service`, `unidades_service`, etc.) con delegación desde `app.py`.
- **Fase 3:** blueprints `bodega`, `caja`, `pos`, `c360` registrados.
- **Fase 4 (alcance v2):** salud `/api/sistema/salud`, cron alertas + Slack opcional.
- **Documentación:** [FLUJOS_CRITICOS.md](./FLUJOS_CRITICOS.md).

**Backlog post-v2 (no bloquea cierre):** aplicar vista SQL en cada BD operativa; métricas voice-command / errores por endpoint; columna `version` en `ventas`; email alertas; más blueprints BI/gerencia; otras importaciones masivas fuera de `cargar_productos` si se priorizan.

---

## Documento relacionado

- Versión anterior multi-asistente: [PLAN_TRABAJO_CONSOLIDADO_AUDITORIAS.md](./PLAN_TRABAJO_CONSOLIDADO_AUDITORIAS.md) — este archivo **v2.0 Grok** es la referencia operativa prioritaria.
