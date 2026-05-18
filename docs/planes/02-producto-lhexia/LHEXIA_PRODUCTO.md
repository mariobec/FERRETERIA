# LhexIA ERP — Documento único de producto

**Versión:** 1.0 · **Mayo 2026**  
**Propietario:** Mario Becerra Olea  
**URL:** [www.lhexia.cl](https://www.lhexia.cl)

> **Este es el documento de entrada para todo lo que es producto LhexIA** (visión, roadmap, arquitectura objetivo, agentes, comercial).  
> **No incluye** el detalle operativo día a día de Ferretería Santo Domingo → ver [`../01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md`](../01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md).  
> **Mapa de todos los planes:** [`../00-alineacion/PLAN_INDICE_LHEXIA.md`](../00-alineacion/PLAN_INDICE_LHEXIA.md) · [`../README.md`](../README.md).

---

## 1. Qué es LhexIA ERP

ERP vertical para **ferreterías y retail en Chile**, nacido de un caso real (Santo Domingo) y evolucionado a **producto comercial**.

| Pilar | Significado |
|-------|-------------|
| **Alma SAP** | Procesos robustos, trazabilidad, control de gestión |
| **Cuerpo Python** | Flask, PostgreSQL, Render + Neon |
| **Agentes IA 24/7** | Inventario, riesgos, ventas, orquestación (roadmap) |

**Visión en una frase:** robustez tipo SAP + velocidad Python + agentes que mejoran el negocio del ferretero 24/7.

---

## 2. Historia y posicionamiento

| Etapa | Hecho |
|-------|-------|
| Origen | Cliente ~20 personas, 3 sucursales; abandono SAP; mala experiencia Defontana |
| Decisión | ERP propio predictivo + IA, liderado por consultor SAP BW/HANA/BO |
| Hoy | **LhexIA ERP** como producto; Santo Domingo = cliente #1 y laboratorio |
| Diferenciadores | Multi-tenant (futuro), vertical ferretería, FE SII, agentes IA, arquitectura limpia |

Documentos ampliados: [`product/PLAN_MAESTRO_LHEXIA.md`](product/PLAN_MAESTRO_LHEXIA.md) · [`product/PRODUCT_VISION.md`](product/PRODUCT_VISION.md)

---

## 3. Dos carriles (regla de oro)

| Carril | Objetivo | Plazo | Documento |
|--------|----------|-------|-----------|
| **A — Santo Domingo** | POS + inventario en producción estable | ~2 semanas | [`SANTO_DOMINGO_ENTREGA.md`](SANTO_DOMINGO_ENTREGA.md) |
| **B — Producto LhexIA** | Docs, tenant futuro, agentes, SaaS | Paralelo, sin big-bang | Este documento + §5–8 |

**No mezclar** refactor masivo de `app.py` ni multi-tenant en BD con el go-live operativo del carril A.

---

## 4. Estado técnico del producto (mayo 2026)

| Área | Estado | Notas |
|------|--------|-------|
| Monolito Flask + blueprints | ✅ Producción | `app.py` + `pos`, `caja`, `bodega`, `c360` |
| POS vendedor fullwidth | ✅ Prod | Layout dock, búsqueda 78vh |
| Caja / vales / crédito | ✅ | Tests críticos |
| Stock multi-almacén + kardex | ✅ | Tienda + bodega |
| Inventario enrolamiento / salud | ✅ | Listo para toma física |
| Bodega / despacho / voz | ✅ | Whisper opcional |
| FE SII | 🟡 | Servicios + cola; certificación según cliente |
| `core/` (dominio) | 🟡 | CORE-1.2–1.4 ✅; 1.5 ⏳ |
| Multi-tenant | ❌ | Post SD-1 |
| Agentes negocio (IA-*) | ❌ | Plan documentado; prod post SD-1 |

Mapa técnico vivo: [`ERP_MAESTRO.md`](ERP_MAESTRO.md)  
Optimización monolito: [`planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md`](planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md)

---

## 5. Roadmap producto (eje LX-)

| Fase | Nombre | Contenido | Cuándo |
|------|--------|-----------|--------|
| **LX-0** | Preparación | Docs, `clients/`, reglas Cursor | Paralelo |
| **LX-1** | Core product | `tenant_id`, onboarding, licencias | Post SD-1 |
| **LX-2** | Agentes IA negocio | = eje **IA-*** | 4–6 meses |
| **LX-3** | Comercial SaaS | Landing, pricing, Docker multi-tenant | 6+ meses |

Calendario resumido: [`product/ROADMAP.md`](product/ROADMAP.md)

---

## 6. Agentes IA de negocio (eje IA-)

Operan **en la ferretería** (no en el repo de desarrollo).

| Fase | Contenido |
|------|-----------|
| IA-0 | Prep: `agents/`, tools lectura, logging |
| IA-1 | Risk, Inventory, Sales, Orchestrator + dashboard |
| IA-2 | Purchasing, Retention, Financial, Pricing |
| IA-3 | Autonomía, human-in-the-loop, panel control |

**Plan completo:** [`planes/06-agentes-ia/PLAN_AGENTES_IA_v1.md`](planes/06-agentes-ia/PLAN_AGENTES_IA_v1.md)

---

## 7. Agentes Meta — desarrollo del producto (eje META-)

Apoyan a **Mario + Cursor + Grok** a construir LhexIA.

| Prioridad | Agente | Rol |
|-----------|--------|-----|
| 1–2 | Chief Architect, Code Quality | Arquitectura y review |
| 3–4 | Product Owner, Documentation | Backlog y docs |
| 10 | Orchestrator PM | Coordina y reporta |

**META-1 (3 semanas):** ARCH, QA, DOC, PO, ORCH.  
**Plan completo:** [`planes/07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md`](planes/07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md)

---

## 8. Arquitectura objetivo (12 meses)

```
lhexia/
├── tenant/ · domain/ · application/ · infrastructure/
└── agents/          # negocio 24/7
app.py               # composition root (hoy monolito)
clients/{slug}/      # por ferretería
core/                # refactor en curso
services/            # stock, kardex, venta, …
```

Detalle: [`product/ARCHITECTURE.md`](product/ARCHITECTURE.md) · [`ARQUITECTURA_CAPAS.md`](ARQUITECTURA_CAPAS.md)

---

## 9. Módulos del producto (backlog MOD-)

| ID | Módulo | Documento |
|----|--------|-----------|
| MOD-C360 | Customer 360 | `roadmap_customer_360_ferreteria_2026.md` |
| MOD-FE | Facturación SII | `memory.md` §FE |
| MOD-BODEGA | Bodega premium | `BODEGA_ULTRA_PREMIUM.md` |
| MOD-OBS | Observabilidad | `roadmap_observabilidad_lhexia_2026_2030.md` |

Índice completo MOD-*: [`PLAN_INDICE_LHEXIA.md`](PLAN_INDICE_LHEXIA.md) §8

---

## 10. Estabilidad y calidad (eje TEC- — cerrado)

Plan Grok v2 **cerrado** (mayo 2026): transacciones, audit, servicios, blueprints, salud sistema.

- [`PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`](PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md)
- Flujos críticos: [`FLUJOS_CRITICOS.md`](FLUJOS_CRITICOS.md)
- Tests: ~200 tests, CI en `.github/workflows/tests.yml`

---

## 11. Gobernanza y roles

| Rol | Responsabilidad |
|-----|-----------------|
| **Mario** | Prioridades, piso, “aplícalo” |
| **Cursor** | Código, tests, deploy, docs técnicas |
| **Grok** | UX, IA, revisión externa |
| **Agentes META-*** | Arquitectura, QA, docs (equipo virtual) |

Aprobación antes de implementar: regla `.cursor/rules/aprobacion-antes-de-implementar.mdc`

---

## 12. Documentos hijos (detalle, no duplicar aquí)

| Tema | Archivo |
|------|---------|
| Plan maestro extendido | `product/PLAN_MAESTRO_LHEXIA.md` |
| Visión corta | `product/PRODUCT_VISION.md` |
| Roadmap fechas | `product/ROADMAP.md` |
| Índice todos los ejes | `PLAN_INDICE_LHEXIA.md` |
| Carpeta planes | `planes/README.md` |
| Bitácora sesiones | `memory.md` |
| **Alineación Mario · Grok · Cursor** | **`MEMORY_GROK.md`** |
| Cliente #1 operación | `SANTO_DOMINGO_ENTREGA.md` |

---

*Documento portal — actualizar al cerrar LX-0, LX-1 o al cambiar visión comercial.*
