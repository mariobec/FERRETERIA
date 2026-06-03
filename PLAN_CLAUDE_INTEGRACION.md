# Integración Claude (Anthropic) — por hacer

**Estado:** documentado · **no implementado**  
**Contexto piloto IA:** Ollama local (Operador + Maylén vitrina) · OpenAI opcional (factura/foto) · Gemini histórico POS Liz (ahora Maylén + Ollama). Ver `memory.md` y `.cursor/rules/ia-piloto-chilemat.mdc`.

---

## ¿Qué quieres integrar? (elegir uno)

| Opción | Dónde | Es cambio en este repo |
|--------|--------|-------------------------|
| **A — Cursor IDE** | Editor Cursor (este chat / Agent) | No — configuración cuenta Cursor |
| **B — ERP LhexIA (API)** | Vitrina Maylén, recepciones IA, etc. | Sí — `services/anthropic_client.py` + env |
| **C — Ambos** | Cursor para desarrollar + API en prod | A + B |

---

## A) Claude en Cursor (desarrollo)

1. Cursor → **Settings** → **Models** (o **API Keys**).
2. Añadir **Anthropic API key** ([console.anthropic.com](https://console.anthropic.com)).
3. En el selector del chat, elegir un modelo Claude (p. ej. Sonnet).
4. El repo no necesita cambios; las reglas en `.cursor/rules/` siguen aplicando.

**Nota:** es independiente del ERP en Render/Neon.

---

## B) Claude en el ERP (recomendación técnica)

### Principio (piloto SD-1)

- **No sustituir** Ollama en PC sucursal (Operador, $0).
- Claude = **capa cloud opcional** cuando Ollama no está o para tareas que requieran mejor razonamiento (texto, no obligatorio visión).

### Cadena de motores propuesta (Maylén vitrina)

```
reglas ERP → Ollama (VITRINA_OLLAMA_*) → Claude (si ANTHROPIC_API_KEY) → respuesta reglas
```

Igual patrón que hoy con `_respuesta_ollama()` en `services/vitrina_tienda_service.py`.

### Archivos a crear (oleada IA-Claude)

| Archivo | Rol |
|---------|-----|
| `services/anthropic_client.py` | `claude_habilitado()`, `generar_chat(system, user, model)` |
| `.env.example` | `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `VITRINA_CLAUDE_ENABLED` |
| `services/vitrina_tienda_service.py` | `_respuesta_claude()` + fallback tras Ollama |
| `tests/test_anthropic_client.py` | Mock HTTP, sin llamar API real |

### Variables de entorno (propuesta)

```env
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=1024
CLAUDE_TIMEOUT_SEC=60

# Maylén vitrina: 1 = intentar Claude si Ollama falla o no responde
VITRINA_CLAUDE_ENABLED=0
```

**Render/PRD:** activar solo tras prueba QAS; costo por token (presupuesto Mario).

### Alcance OUT (primera oleada)

- Reemplazar OpenAI en factura PDF (mantener `OPENAI_API_KEY` hasta decisión).
- CrewAI / agentes meta.
- POS vendedor (Gemini legacy) — no tocar SD-1.

### Criterios de aceptación

- Sin `ANTHROPIC_API_KEY`: ERP igual que hoy (503 o solo reglas/Ollama).
- Con key en DEV: chat Maylén devuelve `motor: claude` en JSON cuando Ollama off.
- `pytest tests/test_anthropic_client.py -q` verde.
- No bloquear checkout ni POS.

### Transporte PRD

Seguir [`PLAN_TRANSPORTE_RESPALDO_PRD.md`](PLAN_TRANSPORTE_RESPALDO_PRD.md) — OT-Código, tag checkpoint, key solo en Render Environment (nunca en git).

---

## Coste orientativo

- Claude Sonnet: pago por uso (Anthropic console).
- Comparar con Gemini/OpenAI ya presupuestados en memoria piloto (~$0–15/mes Liz).

---

## Decisión Mario

- [ ] **A** — Solo Cursor (ya con esta guía)
- [ ] **B** — API en ERP (Maylén fallback)
- [ ] **C** — Ambos
- [ ] **Aplícalo B** en rama `feature/claude-vitrina` (pedir explícitamente al agente)
