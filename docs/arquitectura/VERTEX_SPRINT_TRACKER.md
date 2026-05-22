# VERTEX — Tracker de sprint (vivo)

**Ecosistema:** LhexIA VERTEX · **Cliente #1:** Santo Domingo SD-1  
**Foco actual:** **Cerrar SD-1 (Fase 1 Bastión)** → [`../planes/01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md`](../planes/01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md)

---

## Fase 1 — Cierre SD-1 (PRIORIDAD MÁXIMA)

| ID | Tarea | Responsable | Estado |
|----|-------|-------------|--------|
| **SD-C01** | Enrolamiento **todos los almacenes** (tienda + bodega, 1 local) | Piso | ⏳ |
| **SD-C02** | Vale → cobro retiros faltantes (Bodega/Mixto) | Piso | ⏳ |
| **SD-C03** | Capacitación 2 usuarios × módulo | Piso | ⏳ |
| **SD-C04** | Guardián celular + teléfono supervisor Render | Mario | ⏳ |
| **SD-C05** | Backup Neon pre-ajustes stock | Mario | ⏳ |
| **SD-C06** | Sign-off `SD1_CIERRE_FASE1_VERTEX.md` §G | Mario | ⏳ |

### Tecnología (listo para piso)

| ID | Tarea | Estado |
|----|-------|--------|
| V1-01 | Biblia `LHEXIA_VERTEX_VISION.md` | ✅ |
| V1-02 | Regla Cursor VERTEX | ✅ |
| V1-03 | Guardián UX + mini semáforos | ✅ prod |
| V1-04 | `GUARDIAN_API_v1.md` | ✅ |
| V1-05 | KPI ventas + fecha vale | ✅ prod |
| V1-06 | Landing www visible | ✅ prod |
| V1-07 | Smoke 113 + casuísticas 11 | ✅ 2026-05-21 |
| V1-08 | Script `sd1_cierre_preflight.py` | ✅ |
| V1-09 | Checklist cierre SD1 documento | ✅ |

**SD-1 piloto §8 (2026-05-21):** enrolamiento, salud, vales 2584/2585, TV, caja — ✅ 1 sucursal.

---

## V3.0 — Centro de Mandos Global (andamiaje, paralelo SD-1)

| ID | Tarea | Estado |
|----|-------|--------|
| V3-CC-01 | API `?scope=global_maestro` + clientes live/mock | ✅ |
| V3-CC-02 | UI `/owner/vertex-control` + grafo + feed global | ✅ |
| V3-CC-02b | Doc `VERTEX_MASTER_CORE.md` + píldora v1.0 en BD | ✅ |
| V3-CC-03 | Tenant real multi-BD / filtro por `tenant_id` | ⏳ post SD-1 |

---

## Semana 2 — SOLO tras sign-off SD-1 (multi-sucursal VERTEX)

| ID | Tarea | Capa | Estado |
|----|-------|------|--------|
| V2-01 | SQL `sucursales` + `id_sucursal` nullable + seed SD | VERTEX | ⏳ |
| V2-02 | Admin **Nueva sucursal** + almacenes default | VERTEX | ⏳ |
| V2-03 | Guardián V3.1 filtro por `sucursal_id` | Agente | ⏳ |
| V2-04 | Demo Chilemat (N sucursales, 1 tenant) | Comercial | ⏳ |
| V2-05 | `OWNER_SUPERVISOR_TELEFONO` Render | Ops | ⏳ |

---

## Semana 3–4 (post SD-1)

| Semana | Hitos |
|--------|--------|
| 3 | `agents/guardian` extract · V3.1 sucursal_id · arqueo rutina |
| 4 | RFC LhexIA Connect · Web Push · video caso éxito |

---

*Actualizar al completar cada ítem SD-C0x.*
