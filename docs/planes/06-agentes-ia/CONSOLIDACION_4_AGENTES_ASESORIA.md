# Consolidación crítica — 4 agentes IA LhexIA (post análisis 5 IAs)

**Fecha:** 2026-05-21  
**Fuente:** `docs/ANALISIS AGENTES DE IA.docx` (Manus 1.6, Grok, Gemini, ChatGPT)  
**Rol:** Asesoría producto — Mario Becerra Olea  
**Estado SD-1:** POS + inventario en piso **antes** de producción masiva de agentes con escritura en BD.

---

## 1. Veredicto ejecutivo (crítico)

Las cuatro IAs **acertaron** en lo esencial:

| Acierto común | Por qué importa |
|---------------|-----------------|
| **Ollama + open source local** | Soberanía de datos ferretero; argumento de venta vs SaaS genérico |
| **No empezar por “chatbot”** | El activo es el ERP + eventos + reglas, no el LLM |
| **HITL** en acciones públicas o financieras | Alineado con Control Center y gate SD-1 |
| **3 prototipos** | Ventas, operación, diferenciador — estructura correcta |

Las cuatro **se equivocaron o exageraron** en algo:

| Error / riesgo | Quién lo empujó más | Juicio |
|----------------|---------------------|--------|
| **13 semanas × 3 agentes completos** antes de validar 1 en piso | Manus | Irreal con SD-1 abierto; quema foco |
| **CrewAI / LangGraph / AutoGen como religión** | Manus, Grok | Framework después del primer agente útil |
| **“No uses CrewAI” vs plan IA-1 CrewAI** | ChatGPT | Contradicción; resolver: **orquestador simple primero**, CrewAI cuando hay 2+ agentes estables |
| **Marketing/scraping/redes sin legal ni SD-1** | Gemini P1–P2 | Posicionamiento sí; **prioridad operativa no** |
| **Lhex Forge / generador de código ERP** | Grok P3 | Brillante para **META-** (desarrollo), **no** primer agente de negocio |
| **Digital Twin™ con clima y OC automática** | ChatGPT P3 | Visión 12–24 meses; **cero datos** multi-año hoy |
| **Event bus + Kafka + FastAPI paralelo al monolito** | ChatGPT | Correcto a mediano plazo; **no** bloquear MVP agente 1 |

**Conclusión:** El mejor “tercero sorpresa” **para vender en 90 días** no es Forge ni Digital Twin: es **telemetría real de Santo Domingo → caso de éxito financiero automático** (Gemini P3), **dentro** del agente operativo o comercial, no como proyecto aparte.

---

## 2. Matriz comparativa de propuestas (resumen)

| IA | Prototipo 1 | Prototipo 2 | Prototipo 3 (“sorpresa”) | Stack favorito |
|----|-------------|-------------|---------------------------|----------------|
| **Manus** | Ventas proactivo C360 | Marca / contenido | Guardián de margen (anomalías) | CrewAI + Ollama |
| **Grok** | Asesor operativo (docs) | Vendedor ferretero (demo) | Lhex Forge (meta-código) | LangGraph + LanceDB + Ollama |
| **Gemini** | Extractor dolores competencia | Landings multi-vertical | Casos de éxito desde BD SD-1 | Ollama + Chroma + Flask hook |
| **ChatGPT** | Vendedor inteligente (web/lead) | **OPERADOR** (supervisor 24/7) | Digital Twin (predicción total) | Event bus + FastAPI + Qdrant + **sin CrewAI** |

**Lo que ya tenías en repo (`PLAN_AGENTES_IA_v1.md`):** Risk Detective, Inventory Optimizer, Sales Analyst, Orchestrator — **más maduro operativamente** que Manus/Gemini, pero **menos narrativa comercial** que Grok/ChatGPT.

---

## 3. Los 4 agentes consolidados (orden de prioridad)

### 🥇 Agente 1 — **LhexIA Operador** (supervisor digital del negocio)

**Prioridad:** Máxima — construir **primero**.

**Fusión de lo mejor:**

| Fuente | Qué se rescata |
|--------|----------------|
| **ChatGPT** | Concepto OPERADOR: eventos, reglas, alertas activas (no chat) |
| **Manus** | Guardián de margen: costos, márgenes, promociones destructivas |
| **Plan IA-1.1** | Risk & Vales Detective: vales > N h, stock negativo, anomalías |
| **Gemini P3** | Reportes de caso de éxito con **datos reales** de `cajas` / arqueo (anonimizados) |
| **ERP hoy** | Control Center, arqueo ciego, cola bodega SLA, `erp_audit_log` |

**Misión en una frase:** Vigila POS, caja, bodega, stock y margen; **detecta pérdida de dinero**; notifica y documenta; genera evidencia para el dueño.

**Entregables MVP (6–8 semanas post SD-1 piso):**

1. Lectura segura ERP (tools solo lectura + umbrales).
2. Alertas diarias: descuadre caja, vales pendientes, quiebres alto margen, SKUs muertos.
3. Resumen ejecutivo 1 página (PDF/WA) — submódulo “caso de éxito SD”.
4. Widget en Control Center (sustituye demo IA genérica).
5. Tabla `agente_ejecuciones` (Etapa 2.1 roadmap).

**Qué NO hacer en v1:** OC automática, Digital Twin, escritura masiva en BD.

**Stack recomendado:** Python en `agents/` + **Ollama** (Llama 3.1 8B / Qwen 2.5 7B) + **reglas SQL** (80%) + LLM (20% redacción) + Chroma/Qdrant opcional para explicaciones. Orquestador: **funciones + cron/Celery**; CrewAI en v2 si hay 3+ sub-roles.

**KPI éxito:** Dueño SD puede citar un número real (“detectamos $X descuadre / Y vales riesgo”) en reunión comercial.

---

### 🥈 Agente 2 — **LhexIA Comercial** (vende LhexIA y activa C360)

**Prioridad:** Alta — en **paralelo liviano** con Agente 1 (solo RAG + demos, sin scraping masivo).

**Fusión:**

| Fuente | Qué se rescata |
|--------|----------------|
| **Grok** | Lhex Vendedor: dolor → flujo ERP → demo |
| **ChatGPT** | Lead scoring, diagnóstico web, ROI simulado |
| **Manus** | C360 proactivo: recompra 21d, mensajes WA **borrador** |
| **Gemini** | Landings por vertical (plantillas, no 50 URLs spam) |

**Misión:** Convierte visitas y base de clientes en **reuniones y pilots**; personaliza discurso ferretero; alimenta www.lhexia.cl con contenido **aprobado (HITL)**.

**MVP:**

- Chat/demo embebido en landing (RAG `ERP_MAESTRO` + planes).
- “Diagnóstico 5 preguntas” → PDF propuesta.
- Cola `pendiente_aprobacion` en Control Center (copy, landings, secuencias WA).
- Integración **solo lectura** C360 existente.

**Qué rechazar en v1:** Envío WA masivo sin humano; scraping agresivo competencia (legal/ética).

**KPI:** Leads calificados / semana; tiempo implementador → primer vale en piso.

---

### 🥉 Agente 3 — **LhexIA Guía** (adopción y soporte operativo)

**Prioridad:** Media — **después** del primer alerta útil del Operador.

**Fusión:**

| Fuente | Qué se rescata |
|--------|----------------|
| **Grok** | Lhex Asesor Operativo: checklists, PLAT-1.1, casuísticas |
| **Manus** | (implícito) reducir curva de aprendizaje |
| **META-DOC** | Mantener docs vivos — **no confundir** con agente negocio |

**Misión:** Responde “cómo cierro caja a ciegas”, “qué permiso necesita el vendedor”, “qué hacer si vale bloqueado” — RAG sobre `ERP_MAESTRO`, `CASUISTICAS_VENTAS_QA`, `FLUJOS_CRITICOS`.

**MVP:** Web interna o WhatsApp interno **solo staff** del cliente; sin acceso a datos de otros tenants (futuro).

**KPI:** Menos tickets Mario / menos errores en capacitación SD-1.3.

---

### 4️⃣ Agente 4 — **LhexIA Pulso de Marca** (contenido y mercado)

**Prioridad:** Baja operativa / alta marketing — **post SD-1**, presupuesto acotado.

**Fusión:**

| Fuente | Qué se rescata |
|--------|----------------|
| **Manus** | Monitoreo sentimiento (acotado) |
| **Gemini** | Extractor dolores competencia → **1 artículo/mes** revisado |
| **Gemini** | Landings por vertical (plantilla, no fábrica SEO grey-hat) |

**Misión:** Posicionar lhexia.cl; contenido técnico ferretero; **todo publicable pasa por HITL**.

**Qué no hacer:** Automatizar 20 landings/día; opinar sin revisión humana sobre competidores nombrados.

---

## 4. Qué descartar o mover de carril

| Propuesta | Decisión | Carril correcto |
|-----------|----------|-----------------|
| **Lhex Forge** (genera código ERP) | ❌ No agente IA-1 negocio | **META-** (`PLAN_AGENTES_META_v1.md`) — Cursor ya lo hace |
| **Digital Twin™** | ⏸ Año 2+ | IA-3 / LX-2 cuando haya histórico multi-sucursal |
| **Inventory Optimizer / Purchasing** | ⏸ Tras Operador estable | IA-1.2 / IA-2.1 existente en plan |
| **Orchestrator “Jefe”** | ✅ Sí, pero **ligero** | Scheduler + resumen; no otro LLM gigante al inicio |
| **Event Bus completo** | 🟡 Fase 1.5 | Tabla `erp_eventos` o triggers; no Kafka día 1 |

---

## 5. Stack técnico único (consenso endurecido)

```
ERP Flask (Neon) ──API lectura/escritura controlada──► agents/
                                                      ├── Ollama (local)
                                                      ├── tools/ (SQL, kardex, caja, C360)
                                                      ├── memory/ (Chroma o Qdrant)
                                                      ├── schedulers/ (Celery + Redis, post-MVP)
                                                      └── HITL → Control Center
```

| Componente | Elección | Notas |
|------------|----------|-------|
| LLM runtime | **Ollama** | Mistral 7B / Llama 3.1 8B para MVP |
| Embeddings | **BGE-M3** o nomic-embed via Ollama | RAG Guía + Comercial |
| Vector DB | **Chroma** (simple) o **Qdrant** (escala) | Uno solo |
| Orquestación v1 | Python + tools + cron | CrewAI cuando Operador + Comercial coexisten |
| Escritura BD | **Prohibida** v1 excepto `agente_ejecuciones` + borradores HITL | Igual plan IA-3 |
| Hardware mínimo | 16 GB RAM, GPU 8 GB VRAM | Manus/Grok coinciden |

---

## 6. Roadmap 90 días (realista con SD-1)

| Semana | Hito | Agente |
|--------|------|--------|
| 0–2 | SD-1 cierre piso; `agente_ejecuciones` DDL; Ollama + 1 tool lectura | Infra |
| 3–5 | Alertas vales + descuadre + resumen WA/PDF | **Operador v0.1** |
| 6–8 | RAG Guía interno + checklist voz | **Guía v0.1** |
| 6–10 | Demo landing + cola HITL Control Center | **Comercial v0.1** |
| 10–12 | 1 caso de éxito SD publicado (datos reales) | Operador + Comercial |
| 12+ | Pulso Marca: 1 landing vertical + 1 artículo competencia | **Pulso v0.1** |

**Gate:** No Celery 24/7 en producción cliente hasta SD-1 firmado.

---

## 7. Alineación con planes existentes

| Documento | Ajuste tras esta consolidación |
|-----------|--------------------------------|
| `PLAN_AGENTES_IA_v1.md` | Renombrar IA-1.1 → subsumido en **Operador**; mantener Inventory/Purchasing como IA-2 |
| `05-roadmap_plataforma_madre.md` | Etapa 2.2 Control Center = casa del **Operador + HITL Comercial** |
| `PLAN_AGENTES_META_v1.md` | **Forge** vive aquí, no en IA- |
| `MEMORY_GROK.md` | Prioridad: Operador MVP > Comercial demo > Guía |

---

## 8. Respuesta a tu pregunta original

**¿Cuál IA “ganó”?**

- **Mejor visión operativa y producto:** **ChatGPT** (OPERADOR + eventos + “trabajador digital”).
- **Mejor sorpresa vendible en 90 días:** **Gemini** (casos de éxito con datos SD-1).
- **Mejor narrativa comercial y open source repo:** **Grok** (vendedor + asesor; Forge va a META-).
- **Mejor plan de proyecto documentado:** **Manus** (fases claras; sobredimensionado en calendario).
- **Peor priorización para hoy:** Gemini P1–P2 solos (marketing antes de operación).

**Los 4 agentes que debes construir (orden):**

1. **LhexIA Operador**  
2. **LhexIA Comercial**  
3. **LhexIA Guía**  
4. **LhexIA Pulso de Marca**

---

*Documento vivo — actualizar al cerrar SD-1 o al elegir stack vectorial definitivo.*
