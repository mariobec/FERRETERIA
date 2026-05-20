# Master Plan — Resiliencia Operacional y Control Interno (LhexIA)

**Versión:** 1.0  
**Fecha:** 2026-05-20  
**Alcance:** Etapa 1 (Offline-First) + Etapa 2 (Cuadratura y conciliación tributaria)  
**Prerequisitos cerrados:** Política IVA `desglosar_iva_clp` (`d9a9594`), casuísticas QA ventas (`79220c9`), FE Maullín en pausa hasta timbraje SII (Form. 3230 / folio 77326378627).

**Relación SD-1:** No bloquea inventario/enrolamiento en piso; se ejecuta **después** de estabilizar POS+caja actual o en paralelo controlado por sucursal piloto (1 caja).

**Roadmap técnico detallado (4 fases + complejidad):** [`ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md`](ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md)

---

## Resumen ejecutivo

| Etapa | Objetivo | Duración estimada | Hito principal |
|-------|----------|-------------------|----------------|
| **1 — Offline-First** | POS operativo sin internet (modo contingencia + sync) | **5–6 semanas** | Piloto 8 h sin red con 0 pérdida de ventas |
| **2 — Cuadratura y auditoría** | Control interno caja + espejo ERP↔SII | **3–4 semanas** | Cierre mensual sin folios “huérfanos” |

**Duración total secuencial:** ~8–10 semanas calendario (1 dev full-time + QA piso).

---

## Decisiones técnicas (arquitectura)

### Persistencia local — modelo híbrido recomendado

| Capa | Herramienta | Rol |
|------|-------------|-----|
| **POS en navegador** (Chrome en mostrador) | **IndexedDB** + librería **Dexie.js** (o `idb`) | Espejo liviano de productos, cola de ventas `PENDIENTE_SINCRONIZACION`, estado online/offline, comprobante temporal en `localStorage`/PDF cliente |
| **Agente opcional caja** (PC fija Windows) | **SQLite 3** (`sqlite3` / SQLAlchemy local) | Backup de cola, logs de sync, reintentos nocturnos; útil si el navegador se cierra |
| **API central** | Flask + PostgreSQL (Neon) | Fuente de verdad post-sync; sin cambiar multi-tenant aún |
| **Conectividad** | `navigator.onLine` + **heartbeat** `GET /api/health/ping` cada 15–30 s | Conmutación automática de modo |
| **Cálculo tributario offline** | Import vía bundle o réplica JS de reglas desde `core/domain/shared/iva_chile.py` | Misma política `desglosar_iva_clp` (Decimal→enteros en servidor; enteros en cliente con tests de paridad) |

**No usar solo SQLite en navegador** (no nativo). **No depender de Service Worker** en v1 salvo cache estático; la cola de ventas vive en IndexedDB.

### Módulos / archivos a crear o extender

| Área | Nuevos | Modificar |
|------|--------|-----------|
| API offline | `blueprints/offline_sync.py`, `services/offline_catalog_service.py`, `services/offline_reconcile_service.py` | `app.py` (registro blueprint) |
| Modelos | `OfflineVentaPendiente` (opcional en PG para auditoría), migración SQL | `Producto`, `Venta`, `DetalleVenta`, `Caja` |
| POS frontend | `static/js/offline/pos-offline-db.js`, `pos-offline-sync.js`, `pos-connectivity.js` | `static/js/pos.js`, templates `punto_venta.html` |
| Caja / cuadratura | `services/cuadratura_caja_service.py`, `services/conciliacion_dte_service.py` | `cerrar_caja`, `confirmar_cierre.html`, modelos `Caja` |
| Admin | `templates/admin/conciliacion_dte.html` | Rutas admin facturación |
| Tests | `tests/test_offline_sync.py`, `tests/test_cuadratura_caja.py`, `tests/test_conciliacion_dte.py` | `conftest.py` |
| Docs | Este plan | `ERP_MAESTRO.md` § nueva |

---

# ETAPA 1 — Arquitectura Offline-First

**Prefijo plan:** `TEC-OFFLINE-*`  
**Riesgo mitigado:** Caída Render/Neon/ISP — el mostrador sigue vendiendo con stock referencial y precios del espejo.

---

## Fase 1.0 — Diseño y spike (Semana 1)

| ID | Tarea | Entregable |
|----|-------|------------|
| 1.0.1 | ADR persistencia (IndexedDB + contrato API) | `docs/planes/04-tecnico/ADR_OFFLINE_FIRST.md` |
| 1.0.2 | Contrato JSON catálogo espejo + venta offline | Esquema versionado `offline/v1/` |
| 1.0.3 | Paridad JS `desglosar_iva_clp` vs Python | `static/js/offline/iva-chile.js` + tests en `tests/test_iva_chile.py` (paridad) |
| 1.0.4 | Checkpoint git | `git tag checkpoint/offline-design-YYYY-MM-DD` |

**Hito de control H1:** ADR aprobado por Mario; prueba manual Dexie en POS sin backend.

### Criterios de aceptación (Fase 1.0)

- [ ] Documento ADR con límites explícitos (no FE offline en v1; no anulaciones cruzadas complejas).
- [ ] Test automatizado: 10 montos CLP → mismo `(neto, iva, total)` en Python y JS.

---

## Fase 1.1 — Sincronización del maestro local (Semanas 2–3)

| ID | Tarea | Submódulos |
|----|-------|------------|
| 1.1.1 | Endpoint `GET /api/offline/catalogo` (delta + full) | `offline_catalog_service.py`: SKU, `codigo_barra`, nombre corto, `stock` referencial, `precio_venta` bruto CLP, `updated_at` |
| 1.1.2 | Job descarga al abrir turno + timer 60 min | `pos-offline-sync.js` + hook en `abrir_caja` / login POS |
| 1.1.3 | IndexedDB stores: `productos`, `meta_sync` | Dexie schema v1 |
| 1.1.4 | UI indicador “Catálogo local al día” / “Desactualizado” | Banner en `punto_venta.html` |
| 1.1.5 | Límite tamaño (~4k SKU): compresión gzip, paginación | Performance SD-1 |

**Hito de control H2:** Con red, POS carga catálogo en &lt; 30 s; búsqueda por código de barras funciona con API caída (datos ya en IndexedDB).

### Definición de Done (Fase 1.1)

- [ ] Espejo descargado tras abrir caja; refresco automático cada 60 min si hay red.
- [ ] Búsqueda POS offline devuelve producto en &lt; 200 ms (p95 local).
- [ ] Test integración: endpoint catálogo + seed 100 productos → snapshot válido.
- [ ] Smoke CI: `pytest -m offline_catalog -q`.

**Plazo:** fin semana 3.

---

## Fase 1.2 — Conmutación Online ↔ Offline (Semanas 3–4)

| ID | Tarea | Submódulos |
|----|-------|------------|
| 1.2.1 | Heartbeat `GET /api/health/ping` (timeout 3 s) | `pos-connectivity.js` |
| 1.2.2 | Estado global `MODO_ONLINE` \| `MODO_CONTINGENCIA` | Máquina de estados en POS |
| 1.2.3 | Flujo venta offline: escaneo → carrito local → `desglosar_iva_clp` → guardar cola | Store `ventas_pendientes` IndexedDB |
| 1.2.4 | Comprobante temporal (no DTE): número local `OFF-YYYYMMDD-####` | Template ticket + impresión opcional |
| 1.2.5 | Bloqueos UX: no crédito corporativo sin validar cupo online; no FE | Reglas en ADR |
| 1.2.6 | Indicador visual persistente (banner rojo “CONTINGENCIA”) | CSS POS |

**Hito de control H3:** Simulación DevTools offline 2 h: ≥ 20 ventas guardadas localmente sin error.

### Definición de Done (Fase 1.2)

- [ ] Pérdida de ping &lt; 45 s → modo contingencia automático.
- [ ] Recuperación de ping → banner “Sincronizando…” sin bloquear nuevas ventas online.
- [ ] Cada venta offline tiene: timestamp, usuario, caja_id, líneas, montos enteros, UUID local.
- [ ] Casuística documentada en `docs/CASUISTICAS_VENTAS_QA.md` (CAS-OFF01…).

**Plazo:** fin semana 4.

---

## Fase 1.3 — Reconciliación y sync ascendente (Semanas 5–6)

| ID | Tarea | Submódulos |
|----|-------|------------|
| 1.3.1 | `POST /api/offline/ventas/batch` idempotente (`client_uuid`) | `offline_reconcile_service.py` + `transaccion_critica()` |
| 1.3.2 | Orden cronológico por `created_at_local` | Cola servidor |
| 1.3.3 | Conflictos stock: política **servidor gana** en sync; flag `stock_referencial_vs_real` | `stock_service.py`, auditoría |
| 1.3.4 | Post-sync: encolar `post_cobro_emision_fe` si tipo documento requiere DTE y hay red | Cola FE existente |
| 1.3.5 | Panel admin “Ventas recuperadas offline” | Lista + diff |
| 1.3.6 | Reintentos exponenciales + dead letter | Log `erp_audit_log` |

**Hito de control H4:** Día piloto: cortar red 4 h → reconectar → 100 % ventas en Neon en &lt; 15 min; stock coherente salvo alertas documentadas.

### Definición de Done (Etapa 1 completa)

- [ ] 0 ventas perdidas en piloto sucursal (checklist firmado).
- [ ] UUID idempotente: reenvío batch no duplica ventas.
- [ ] Tests: `test_offline_sync.py` (happy path, conflicto stock, batch duplicado).
- [ ] Runbook piso: `docs/planes/01-entrega-santo-domingo/RUNBOOK_OFFLINE_POS.md`.
- [ ] Tag release: `checkpoint/offline-v1-YYYY-MM-DD`.

**Plazo:** fin semana 6.

---

# ETAPA 2 — Cuadratura, Conciliación y Auditoría Interna

**Prefijo plan:** `TEC-CUADRA-*`  
**Dependencia:** Etapa 1 recomendada (cierre caja offline debe cuadrar); panel tributario puede iniciarse en paralelo desde semana 5.

---

## Fase 2.1 — Matriz apertura, arqueo y cierre (Semanas 7–8)

| ID | Tarea | Submódulos |
|----|-------|------------|
| 2.1.1 | Campo `fondo_apertura_clp` (sencillo) obligatorio en `abrir_caja` | Modelo `Caja`, migración SQL |
| 2.1.2 | Pantalla cierre: arqueo **a ciegas** por medio (Efectivo, Transbank, Transferencia) | `confirmar_cierre.html`, `cerrar_caja` |
| 2.1.3 | Cálculo automático `diferencia_caja = efectivo_fisico - efectivo_teorico_erp` | `cuadratura_caja_service.py` |
| 2.1.4 | Teórico ERP solo ventas `Pagado` (regla actual `_venta_cuenta_en_cuadre_caja`) | Sin regresión |
| 2.1.5 | Umbral tolerancia (ej. ±$500) → alerta vs bloqueo | Config empresa |
| 2.1.6 | Informe PDF/Excel cierre por turno | Opcional v1.1 |

**Fórmulas (CLP enteros, Decimal interno):**

```
efectivo_teorico = ventas_efectivo_pagado + fondo_apertura - retiros + movimientos_caja
diferencia       = efectivo_fisico_contado - efectivo_teorico
```

**Hito de control H5:** 5 cierres consecutivos en QA con diferencia cero en escenario controlado.

### Definición de Done (Fase 2.1)

- [ ] No se cierra caja sin fondo apertura y montos físicos ingresados.
- [ ] Diferencia visible en pantalla y guardada en `Caja.diferencia_arqueo`.
- [ ] Tests smoke caja + casuística CAS-C02 extendida.
- [ ] Permiso RBAC: `caja_cerrar`, `caja_ver_diferencia`.

**Plazo:** fin semana 8.

---

## Fase 2.2 — Panel conciliación tributaria ERP ↔ SII (Semanas 9–10)

| ID | Tarea | Submódulos |
|----|-------|------------|
| 2.2.1 | Vista `/admin/conciliacion-dte` | Template + API |
| 2.2.2 | Listado folios: `nro_documento`, `dte_tipo`, `dte_estado`, `dte_track_id`, `monto_total` | Query ventas + CAF |
| 2.2.3 | Semáforo: 🟢 ENVIADO/ACEPTADO con Track ID · 🟡 PENDIENTE_ENVIO · 🔴 FALLO_MATEMATICO / sin folio | `conciliacion_dte_service.py` |
| 2.2.4 | Cruce opcional estado DTE SII (cuando Maullín activo) | Extensión `facturacion_sii_soap.py` |
| 2.2.5 | Export CSV para contador (Form. 29) | Descarga |
| 2.2.6 | Alertas dashboard: conteo discrepancias mes en curso | Widget admin |

**Hito de control H6:** Mes de prueba: 100 % folios clasificados; 0 `FALLO_MATEMATICO` sin ticket de resolución.

### Definición de Done (Etapa 2 completa)

- [ ] Administrador identifica en &lt; 2 min folios problemáticos del mes.
- [ ] Documentación conciliación en `ERP_MAESTRO.md` § control interno.
- [ ] Tests: estados DTE mock + semáforo.
- [ ] Integración con política IVA: folios `FALLO_MATEMATICO` no reenvían hasta corrección manual.
- [ ] Tag: `checkpoint/cuadratura-v1-YYYY-MM-DD`.

**Plazo:** fin semana 10.

---

## Cronograma consolidado (Gantt simplificado)

```
Sem 1    [####] 1.0 Diseño + paridad IVA JS
Sem 2-3  [########] 1.1 Catálogo IndexedDB
Sem 3-4  [########] 1.2 Modo contingencia POS
Sem 5-6  [########] 1.3 Reconciliación batch
Sem 7-8  [########] 2.1 Arqueo ciego caja
Sem 9-10 [########] 2.2 Panel conciliación DTE
```

**Paralelismo permitido:** 2.2 diseño UI en semana 5; FE SII real solo tras timbraje (no bloqueante para 2.2 semáforo local).

---

## Matriz de riesgos y mitigación

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Doble venta al sync | Alto | UUID cliente + idempotencia servidor |
| Stock negativo post-offline | Medio | Servidor gana; alerta kardex |
| Desfase precios espejo vs central | Medio | TTL 60 min + timestamp visible |
| IVA distinto JS vs Python | Alto | Tests paridad; prohibido float |
| FE en contingencia | Alto | Bloquear DTE offline; cola al reconectar |
| Arqueo sin ventas sync | Medio | Cierre bloqueado si hay `PENDIENTE_SINCRONIZACION` |

---

## Criterios globales de aprobación (Go-Live corporativo)

### Etapa 1 — Offline-First

1. Piloto 1 sucursal, 1 caja, 8 h contingencia sin pérdida de datos.
2. Sincronización completa &lt; 15 min tras restablecer red.
3. Suite `pytest -m "offline or smoke"` en verde en CI.
4. Runbook capacitado a cajero y supervisor.

### Etapa 2 — Control interno

1. 5 cierres QA con arqueo ciego y diferencia documentada.
2. Panel conciliación operativo con semáforo para todos los estados `dte_estado`.
3. Procedimiento contador para Form. 29 documentado.
4. Checkpoint git y actualización `docs/memory.md`.

---

## Próximos pasos inmediatos (arranque)

1. Aprobar ADR herramienta (IndexedDB + Dexie en POS).
2. Crear rama `feature/tec-offline-1.0` desde `main` (`d9a9594`).
3. Implementar Fase 1.0 (spike + paridad IVA JS) — **2–3 días**.
4. Mantener FE Maullín en pausa hasta SII Form. 3230 cerrado.

---

*Documento generado para planificación LhexIA ERP — alineado a SD-1, política IVA `core/domain/shared/iva_chile.py` y módulo caja existente.*
