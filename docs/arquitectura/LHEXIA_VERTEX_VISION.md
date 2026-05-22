# Ecosistema LhexIA VERTEX — Biblia de Arquitectura y Norte Estratégico

**Versión:** 1.1 · **Mayo 2026**  
**Propietario:** Mario Becerra Olea  
**Estado:** Documento oficial — toda decisión de código, BD, API o UI debe alinearse aquí  
**URL producto:** [www.lhexia.cl](https://www.lhexia.cl)

> *«Soluciones en el camino, con el norte claro.»*  
> Cada fase genera caja, valida el producto y deja infraestructura lista para la siguiente.

**Nombre del ecosistema:** **LhexIA VERTEX** (plataforma núcleo + soluciones verticales + agentes).

---

## 1. Las tres capas del ecosistema (regla estructural)

Todo desarrollo futuro respeta esta separación. **No mezclar** responsabilidades entre capas en un mismo commit crítico de piso.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 LhexIA VERTEX (Core SaaS Multi-Cliente)                 │
│  Auth · Tenants · Licencias · Auditoría · Event Bus · API Gateway       │
│  Catálogo de módulos · Billing · Observabilidad · Data contracts        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ provisiona / orquesta
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Solución ERP  │     │ Solución ERP  │     │ Solución ERP  │
│  Ferretería   │     │  Transporte   │     │    Retail     │
│  (SD-1 hoy)   │     │  (fase 2)     │     │  (fase 2)     │
│ POS·Caja·Inv  │     │ Flotas·GPS    │     │ Caja rápida   │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
              ┌───────────────────────────────────┐
              │      LhexIA Agentes (IA Layer)     │
              │  Guardián · Operador · Abastecedor   │
              │  Conectables por API / webhooks      │
              │  HITL · Severidad · Dedupe · Feed    │
              └───────────────────────────────────┘
```

| Capa | Qué es | Qué NO es |
|------|--------|----------|
| **LhexIA VERTEX** | Plataforma madre: identidad, tenant, contratos de datos, catálogo de soluciones | Pantallas de POS ni lógica de arqueo ciego |
| **Soluciones ERP** | Verticales operativos (modelos, flujos, permisos, UI) | Agentes autónomos ni facturación de plataforma |
| **LhexIA Agentes** | Inteligencia transversal: leer eventos, alertar, recomendar, auditar | Fuente de verdad transaccional (la BD del ERP lo es) |

**Referencias:** [`../planes/02-producto-lhexia/LHEXIA_PRODUCTO.md`](../planes/02-producto-lhexia/LHEXIA_PRODUCTO.md) · [`VERTEX_SPRINT_TRACKER.md`](VERTEX_SPRINT_TRACKER.md) · [`GUARDIAN_API_v1.md`](GUARDIAN_API_v1.md)

---

## 2. Plan Maestro — Cuatro fases tácticas

### Fase 1 — El Bastión (Hoy → 2026) · LhexIA Ferretería + Guardián V3.0

| Dimensión | Contenido |
|-----------|-----------|
| **Objetivo** | Consolidar **Ferretería Santo Domingo (SD-1)** como caso de éxito real y blindado |
| **Entregable** | ERP base + POS + **Agente Guardián** (semáforos ×4, arqueos ciegos, feed vivo, matriz de acciones, KPI ventas) |
| **Impacto comercial** | Escudo operativo → red **Chilemat**; narrativa: *menos mermas, control en ruta* |
| **Estado (mayo 2026)** | ✅ Guardián V3 prod. 🟡 **Cierre SD-1** ([checklist](../planes/01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md)). ⏳ V3.1 post sign-off |

**SD-1 = primer tenant lógico de VERTEX** (un establecimiento, sin sucursales; inventario por almacén tienda/bodega). Multi-sucursal = Chilemat / Fase 2.

---

### Fase 2 — Expansión vertical · Hermanos ERP

Clonar estructura transaccional VERTEX → **Transporte** (flotas, GPS, Guardián combustible) y **Retail** (caja rápida).

Paquetes objetivo: `solutions/ferreteria`, `solutions/transporte`, `solutions/retail` bajo VERTEX.

---

### Fase 3 — Desconexión total · IA caballo de Troya

**LhexIA Connect:** agentes por API sobre Defontana, SAP, Softland (solo lectura + alertas).

Vender Guardián standalone → migración a VERTEX completo al año.

---

### Fase 4 — Omnipresencia (Norte 2030)

Zero-UI, voz, visión, gemelos digitales. No bloquea fases 1–3.

---

## 3. Mapa de alineación — Código actual vs. VERTEX

| Componente hoy | Capa | Evolución VERTEX |
|----------------|------|------------------|
| `app.py` + blueprints | Solución Ferretería | `solutions/ferreteria` |
| `owner_dashboard_service` + `owner_api` | Agente Guardián | `agents/guardian` |
| `agente_ejecuciones_service` | Agente Operador | event bus VERTEX |
| `core/domain/venta` | Semilla transaccional VERTEX | patrón Transporte/Retail |
| PWA `/owner-mobile` | UX Guardián | shell multi-vertical |
| Tests smoke 200+ | Calidad Bastión | + contrato API agentes |

**Conclusión:** Backend V3 SD-1 **es el primer caso de éxito global de VERTEX.**

---

## 4. Contratos que no se rompen

1. PostgreSQL ERP = fuente de verdad; agentes leen y alertan.
2. `GET /api/v1/owner/dashboard` — compat `tarjeta_caja` / `tarjeta_inventario`.
3. Permisos gerencia para PWA dueño.
4. Flujos SD-1: POS → Pendiente → cobro Pagado → stock.
5. Nombres: **LhexIA VERTEX** · **LhexIA Ferretería** · **LhexIA Guardián**.

---

## 5. Ecosistema — Catálogo de agentes (VERTEX Catalog)

| Agente | Vertical | Valor |
|--------|----------|-------|
| Guardián | Todos | Semáforos, PWA dueño, consolidado red |
| Operador | Ferretería / Retail | Feed, alertas caja/vale |
| Abastecedor | Ferretería / Retail | Quiebre, OC |
| Auditor flota | Transporte | GPS vs combustible |
| Cobrador | Todos | WhatsApp morosos |

SDK común: `leer_eventos`, `emitir_alerta`, `severidad`, `dedupe_key`, `acciones[]`.

---

## 6. Avance en paralelo (orden acordado)

| Prioridad | Carril | Estado |
|-----------|--------|--------|
| **1** | SD-1: POS, inventario, caja | En curso |
| **2** | Guardián uso diario + UX above-fold | En curso |
| **3** | Docs VERTEX + API Guardián v1 | Este commit |
| **4** | `tenant_id` nullable (diseño) | Semana 2 |
| **5** | LhexIA Connect POC lectura | Post SD-1 |
| **6** | Multi-tenant prod queries | ❌ Post SD-1 |

Tracker vivo: [`VERTEX_SPRINT_TRACKER.md`](VERTEX_SPRINT_TRACKER.md)

---

## 7. KPIs por fase

| Fase | KPI |
|------|-----|
| 1 Bastión | SD-1 5 días sin rollback; Guardián ≥2 opens/día dueño |
| 2 Vertical | 2º vertical piloto + misma API Guardián |
| 3 Troya | 3 clientes solo-agente ERP ajeno; 1 conversión VERTEX |
| 4 2030 | 1 flujo autónomo en prod |

---

## 8. Checklist Cursor (cada feature)

1. ¿Capa VERTEX / Solución / Agente?
2. ¿Bloquea POS o inventario mañana?
3. ¿Smoke test?
4. ¿Checkpoint git si UI POS/caja/PWA?
5. ¿Doc en esta biblia o `GUARDIAN_API_v1`?

---

## 9. Historial

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0 | 2026-05-21 | Plan Maestro 4 fases (nombre Matrix) |
| 1.1 | 2026-05-21 | Renombre oficial → **Ecosistema LhexIA VERTEX** |

---

*LhexIA VERTEX · Mario Becerra Olea · www.lhexia.cl*
