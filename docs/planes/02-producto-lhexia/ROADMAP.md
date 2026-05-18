# LhexIA ERP — Roadmap (producto LX)

> **Plan operativo inmediato (Santo Domingo):** fase **SD-1** en `../00-alineacion/PLAN_INDICE_LHEXIA.md` y `../01-entrega-santo-domingo/CLIENTE_SANTO_DOMINGO.md`.  
> Este archivo resume **producto comercial (LX-*)** y fechas largas.

**Actualizado:** 2026-05-17  

## Ahora → 2 semanas (CRÍTICO — Santo Domingo = SD-1)

**Meta:** Prototipo en prueba — **POS + inventario** operables en piso.

### Inventario (toma física)

| # | Tarea | Ruta / artefacto | Estado repo |
|---|--------|------------------|-------------|
| I1 | Validar 3 almacenes/sucursales activos | Admin → Almacenes | Verificar en Neon |
| I2 | Permisos enrolamiento a encargados | `enrolamiento_inventario` | Existe RBAC |
| I3 | Sesión de conteo por sucursal | `/inventario/enrolamiento` | ✅ Implementado |
| I4 | Export desajustes pre/post | `/inventario/salud?export=desajuste` | ✅ |
| I5 | Cierre y kardex de ajustes | Auditoría móvil / ajuste automático | ✅ |
| I6 | Runbook 1 página para piso | `CLIENTE_SANTO_DOMINGO.md` | Este sprint |

### POS

| # | Tarea | Estado |
|---|--------|--------|
| P1 | Layout vendedor en producción | ✅ `5094d5d` |
| P2 | Búsqueda manual confiable | 🟡 Validar en piso; hotfix si vacío |
| P3 | Retiro tienda/bodega + stock coherente | ✅ |
| P4 | Vale → caja → cobro piloto | Probar en sucursal 1 |
| P5 | Capacitación F2 / filtros Operativo vs Catálogo | Operación |

### Infra

| # | Tarea |
|---|--------|
| D1 | Backup Neon antes de masivos ajustes stock |
| D2 | Ctrl+F5 / cache POS tras cada deploy |
| D3 | Smoke tests en `main` antes de push |

---

## 3–6 semanas (estabilización + producto liviano)

- Cerrar hallazgos toma inventario
- Caja y cierre diario en las 3 sucursales
- Fase 0 producto: `tenants` tabla + docs (sin cambiar comportamiento)
- Primer agente (detección anomalías vales) en **modo lectura**

---

## 2–4 meses (Fase 1 producto)

- Multi-tenant MVP
- Onboarding wizard nueva ferretería
- Licencias / planes
- Dashboard ejecutivo

---

## 4–6 meses (Fase 2 — Agentes = eje **IA-***)

**Plan completo:** `../06-agentes-ia/PLAN_AGENTES_IA_v1.md`

| Mes | Fases IA | Agentes |
|-----|----------|---------|
| 1 | IA-0 + IA-1.1–1.2 | Prep, Risk & Vales, Inventory Optimizer |
| 2 | IA-1.3–1.4 | Sales Analyst, Orchestrator + Dashboard |
| 3 | IA-2.1–2.2 | Purchasing, Customer Retention |
| 4 | IA-2.3–2.4 + IA-3 | Financial, Pricing, sistema autónomo |

- CrewAI + LangGraph + tools ERP seguros
- Groq + Claude · Celery + Redis · WhatsApp alertas

---

## 6+ meses (Fase 3 — Comercial)

- Landing + demo
- Contratos / pricing SaaS
- Templates Docker + Render multi-tenant

---

## Calendario visual (simplificado)

```
May 2026     [████████████████] Sprint SD: POS + Inventario
Jun 2026     [████░░░░░░░░░░░░] Estabilización + Fase 0 producto
Jul-Ago      [░░░░████████░░░░] Fase 1 multi-tenant
Sep-Dic      [░░░░░░░░████████] IA-1…3 Agentes (ver PLAN_AGENTES_IA_v1)
```

*SD = Santo Domingo*
