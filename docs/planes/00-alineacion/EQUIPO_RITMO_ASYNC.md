# Ritmo de equipo — Mario · Grok · Cursor (modelo híbrido)

**Origen:** Propuesta Grok · **Aprobado por:** Mario  
**Versión:** 1.0 · Mayo 2026  
**Relacionado:** `MEMORY_GROK.md`, `PLAN_INDICE_LHEXIA.md`

Equipo pequeño, trabajo **asíncrono**. Tres canales, una prioridad: **SD-1**.

---

## Roles en el ritmo

| Quién | Daily — qué aporta |
|-------|-------------------|
| **Mario** | Prioridades del día, validación negocio/piso, bloqueos con cliente |
| **Grok** | Propuestas, revisiones, planificación, user stories |
| **Cursor** | Avances técnicos vía Mario (al cerrar sesión Cursor, Mario pega resumen o pide actualizar `memory.md`) |

**Nota Cursor:** no responde solo en Grok; Mario trae el extracto del chat Cursor al Daily o pide *«actualiza memory.md»*.

---

## 1. Daily Update (diario · ~5 min)

Cada uno postea **un bloque por día** (Grok Project, WhatsApp interno, o copia en `memory.md` § Daily).

### Plantilla

```markdown
## Daily — YYYY-MM-DD

**Ayer logré:**
- 

**Hoy voy a:**
- 

**Bloqueos / Necesito ayuda con:**
- 

**Notas importantes:** (deploy, piso, decisión pendiente)
- 

**Eje:** SD- / POS- / META- / otro: ___
```

### Reglas

- Máximo **3 ítems** en «Hoy voy a» (realista).
- Si hay bloqueo >24 h en SD-1, **Mario decide**: posponer, hotfix Cursor, o cambio en piso.
- No usar Daily para refactor LX-/IA- sin OK explícito.

---

## 2. Weekly Planning (domingo o lunes)

**Duración:** 20–30 min (async: cada uno lee y comenta por escrito).

### Agenda

1. ¿Cerramos algo de SD-1 esta semana? (criterios en `SANTO_DOMINGO_ENTREGA.md`)
2. Top **3 tareas** semana con prefijo (SD-1.1, POS-4, etc.)
3. ¿Actualizar `MEMORY_GROK.md` §4 prioridad o §12 bitácora?
4. Riesgos: inventario, POS, deploy, personal sucursal

### Plantilla

```markdown
## Weekly — Semana YYYY-MM-DD

**Logros semana anterior:**
- 

**Top 3 esta semana:**
1. [SD-/POS-/…] 
2. 
3. 

**Fuera de alcance esta semana:**
- 

**Decisión Mario:**
- 
```

---

## 3. Sprint Review (cada 14 días)

**Objetivo:** demo / validación **SD-1** desde ojo Ferretería Santo Domingo.

### Agenda

| # | Tema |
|---|------|
| 1 | Demo flujo: inventario y/o vale → caja (sucursal piloto) |
| 2 | Checklist cierre SD-1: qué falta |
| 3 | Feedback piso (Mario) |
| 4 | Próximo sprint 14 días: solo SD-2 o seguir SD-1 |

### Salida

- Actualizar `PLAN_INDICE` §1 estado SD-*
- Entrada en `memory.md` con fecha del review

---

## Calendario sugerido (SD-1)

| Ritual | Frecuencia | Día sugerido |
|--------|------------|--------------|
| Daily | Diario | Mañana (antes de piso) |
| Weekly | Semanal | Lunes |
| Sprint Review | 14 días | Viernes (cierre quincena) |

---

## Dónde queda registrado

| Ritual | Canal rápido | Registro permanente |
|--------|--------------|-------------------|
| Daily | Grok Project / WhatsApp | `memory.md` (opcional, fin de día) |
| Weekly | Grok + comentario Mario | `memory.md` + §12 `MEMORY_GROK` si cambia prioridad |
| Sprint Review | Videollamada o notas Mario | `PLAN_INDICE` + `SANTO_DOMINGO_ENTREGA` |

---

## Primera acción

**Hoy:** Mario postea el primer Daily en Grok (o acá en Cursor) usando la plantilla §1.

---

*Modelo híbrido — ajustar tras cerrar SD-1 si el equipo crece.*
