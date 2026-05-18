# Memory Grok — Alineación Mario · Grok · Cursor

**Versión:** 1.0 · **Mayo 2026**  
**Repo:** `sistema_ventas_limpio` (LhexIA ERP) · **Prod:** [www.lhexia.cl](https://www.lhexia.cl)

> **Propósito:** Un solo texto corto para que **los tres** partan del mismo contexto.  
> **Grok:** pegar o adjuntar al inicio de cada sesión de diseño/revisión.  
> **Cursor:** leer junto con `memory.md` (detalle técnico del repo).  
> **Mario:** actualizar cuando cambie prioridad o se cierre una fase.

**Mantener sincronizado con:** `docs/memory.md` (bitácora técnica) · actualizar **este archivo** cuando cambien prioridades globales (no cada commit pequeño).

---

## 1. Cómo usar este memory

| Quién | Acción |
|-------|--------|
| **Mario** | Usar **Grok Project** con los 5 archivos fijos → ver [`GROK_PROJECT_SETUP.md`](GROK_PROJECT_SETUP.md). O pegar este archivo al inicio del chat. |
| **Grok** | Tratar esto como **fuente de verdad de prioridades y nomenclatura**. Si contradice el chat, **preguntar a Mario**. No asumir código que no está listado aquí o en los docs enlazados. |
| **Cursor** | Al iniciar sesión: `@docs/planes/00-alineacion/MEMORY_GROK.md` + `@memory.md`. Tras cerrar un hito: Mario pide *«actualiza MEMORY_GROK y memory.md»*. |

---

## 2. Los tres roles

| Rol | Hace | No hace |
|-----|------|---------|
| **Mario** | Prioridades, validación en piso (3 sucursales), «aplícalo», decisiones negocio | — |
| **Grok** | UX POS, arquitectura IA, planes, review de propuestas, redacción producto | No ejecuta en repo; no commit; no inventar APIs/tablas |
| **Cursor** | Código, tests, deploy, docs técnicas; **verifica** propuestas Grok contra repo | No big-bang sin OK de Mario |

**Flujo acordado:** Grok propone → Cursor verifica en código → Mario aprueba alcance → Cursor implementa → actualizar memoria.

---

## 3. Dos documentos únicos (entrada)

| Tema | Archivo en repo |
|------|-----------------|
| **Producto LhexIA** (visión, LX, agentes, SaaS) | `../02-producto-lhexia/LHEXIA_PRODUCTO.md` |
| **Santo Domingo** (SD-1, POS, inventario, deploy) | `../01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md` |
| **Índice prefijos** (SD, POS, TEC, CORE, LX, IA, META) | `../00-alineacion/PLAN_INDICE_LHEXIA.md` |

---

## 4. Prioridad absoluta (mayo 2026)

```
AHORA = SD-1  →  POS + inventario en Ferretería Santo Domingo (~2 semanas)
NO AHORA      →  multi-tenant, mover todo app.py, agentes IA en prod, refactor masivo
```

| Fase | Estado | Nota |
|------|--------|------|
| **SD-1** | 🟡 En curso | Toma inventario + venta diaria |
| POS-1…3 | ✅ Prod | Layout dock aprobado Mario (`5094d5d`) |
| POS-4 | ✅ Código local | F8, búsqueda 2 chars — verificar push |
| TEC-1A…4 | ✅ Cerrado | Transacciones, servicios, blueprints |
| CORE-1.2…1.4 | ✅ | Venta/cobro/stock en `core/` |
| CORE-1.5 | ⏳ | Post SD-1 |
| LX-1 multi-tenant | ⏳ | Post SD-1 |
| IA-* agentes negocio | ⏳ | Plan listo; prod post SD-1 |
| META-* agentes dev | 🟡 META-1 | ARCH, QA, DOC, PO, ORCH (3 sem) |

---

## 5. Nomenclatura (obligatoria)

Evitar «Fase 3» suelta. Usar **prefijo + número**:

| Prefijo | Significado |
|---------|-------------|
| **SD-** | Entrega Santo Domingo (operación) |
| **POS-** | UI pantalla vendedor |
| **TEC-** | Estabilidad monolito v2 (cerrado) |
| **CORE-** | Refactor dominio `core/` |
| **LX-** | Producto comercial LhexIA |
| **IA-** | Agentes IA **en ferretería** (negocio 24/7) |
| **META-** | Agentes IA **para desarrollar** el producto |

**Dos Orchestrator distintos:** `META-ORCH` (proyecto) ≠ `IA-1.4` (reporte ejecutivo ferretería).

---

## 6. Cliente #1 — Santo Domingo (resumen)

- ~20 personas, **3 sucursales**, primer tenant implícito (una Neon, un Render).
- **SD-1.1:** `/inventario/enrolamiento`, `/inventario/salud`, kardex.
- **SD-1.2:** `/punto_venta`, vale → caja → cobro; búsqueda: probar filtro **Catálogo** si Operativo vacío.
- **Cierre SD-1:** conteo por sucursal + ≥1 sucursal flujo vale sin bloqueos críticos.
- Runbook corto piso: `../01-entrega-santo-domingo/CLIENTE_SANTO_DOMINGO.md`

---

## 7. Stack y restricciones técnicas

- **Flask monolito** `app.py` (~20.5k líneas) + `blueprints/` + `services/` + `core/` (~974 líneas).
- **BD:** PostgreSQL (Neon prod, local para pytest).
- **No romper:** invariante stock tienda/bodega; estados venta; `@transaccion_critica` en flujos críticos.
- **Tests:** smoke antes de deploy POS; no tests contra Neon prod sin override.
- **Optimización app:** `../04-tecnico/ESTADO_OPTIMIZACION_APP.md`

---

## 8. Qué pedirle a Grok (alcance útil)

| Sí | Ejemplos |
|----|----------|
| ✅ | Mockups POS, copy UX, revisión plan agentes IA/META, competencia Defontana/SAP B1 |
| ✅ | User stories SD-1, checklist capacitación, pitch LhexIA |
| ✅ | Revisar propuesta Cursor antes de implementar |

| No (sin OK Mario) | Motivo |
|-------------------|--------|
| ❌ | Multi-tenant en BD ahora |
| ❌ | Mover modelos masivos fuera de `app.py` durante toma inventario |
| ❌ | CrewAI en producción antes de SD-1 |
| ❌ | Cambiar flujo caja/stock sin leer `FLUJOS_CRITICOS.md` |

---

## 9. Qué pedirle a Cursor (alcance útil)

| Sí | Ejemplos |
|----|----------|
| ✅ | Hotfix POS, tests, deploy, actualizar docs portal |
| ✅ | CORE-1.5 cuando Mario diga post SD-1 |
| ✅ | Verificar en repo lo que Grok propone |

| Regla | |
|-------|--|
| Aprobación explícita | Sin «aplícalo» / «implementa» → proponer, no commitear |
| Checkpoint git | Cambios UI POS/caja críticos → tag o rama checkpoint |

---

## 10. Planes de agentes (referencia rápida)

| Plan | Archivo |
|------|---------|
| Agentes negocio (Risk, Inventory, Sales…) | `../06-agentes-ia/PLAN_AGENTES_IA_v1.md` |
| Agentes meta (Architect, QA, PO…) | `../07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md` |
| POS UI fases | `../03-pos-vendedor/POS_ALINEACION_CURSOR_GROK.md` |

---

## 11. Visión producto (una frase)

**LhexIA ERP** = alma SAP (control y trazabilidad) + cuerpo Python (Flask/Postgres) + agentes IA 24/7 (roadmap).

---

## 12. Bitácora corta (actualizar al cerrar hitos)

| Fecha | Hito |
|-------|------|
| 2026-05-17 | Docs portal: `LHEXIA_PRODUCTO.md`, `SANTO_DOMINGO_ENTREGA.md`, `MEMORY_GROK.md` |
| 2026-05-17 | Planes IA-* y META-* en `docs/planes/` |
| 2026-05-17 | POS-3 prod `5094d5d`; POS-4 local; SD-1 en curso |
| 2026-05-16 | CORE 1.2–1.4 + TEC v2 cerrado |

*Detalle técnico diario → `docs/memory.md` § sesiones.*

---

## 13. Prompt sugerido para Grok (copiar/pegar)

```
Contexto: proyecto LhexIA ERP (ferretería Chile). Usa como verdad:
1) docs/planes/00-alineacion/MEMORY_GROK.md (prioridades y nomenclatura)
2) docs/planes/02-producto-lhexia/LHEXIA_PRODUCTO.md si es producto/comercial
3) docs/planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md si es operación Santo Domingo

Prioridad HOY: SD-1 (POS + inventario), NO multi-tenant ni agentes en prod.
Responde en español. Si propones código, indica que Cursor debe verificar en repo antes de implementar.
```

---

*Última revisión: 2026-05-17 · Mario / Cursor — Grok debe recibir actualizaciones cuando cambie la fila «Prioridad absoluta».*
