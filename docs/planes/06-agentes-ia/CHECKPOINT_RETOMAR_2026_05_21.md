# Checkpoint desarrollo — retomar 2026-05-21

Documento de continuidad entre sesiones. **Memoria técnica completa:** `docs/memory.md` § *Checkpoint sesión 2026-05-21*.

**Chat Cursor (transcripción):** carpeta `agent-transcripts` → uuid `ea00bfe0-08c5-40c5-a002-e6b877474d7a`.

---

## 1. Qué quedó en producción (`main` → Render)

| Commit | Entregable |
|--------|------------|
| `f10f646` | Tabla `agente_ejecuciones`, Operador v0.1, Control Center |
| `6443b4e` | v0.2: Ollama client, worker enrich, pgvector DDL, manual instalación |
| `de947c0` | Cierre caja **ciego** o **visible** vía config empresa |

---

## 2. Arquitectura agentes (acordada con Gemini + Mario)

```text
Render/Neon  →  scan SQL (v0.1)  →  INSERT alertas texto matemático
PC sucursal  →  enrich Ollama (v0.2)  →  UPDATE cuerpo + tokens  [OPCIONAL]
Gerente      →  /admin/control-center  →  reconocer / cerrar
```

- **Ollama NO es obligatorio hoy.** Con `AGENTE_OLLAMA_ENABLED=0` todo funciona como v0.1.
- Hardware futuro: Core i5, 16 GB RAM, SSD 500 GB, modelo `qwen2.5:7b-instruct-q4_K_M`.
- Manual: `docs/manuales/INSTALACION_OLLAMA_LOCAL.md`.

---

## 3. Archivos clave (mapa rápido)

| Área | Archivos |
|------|----------|
| Persistencia alertas | `services/agente_ejecuciones_service.py` |
| Reglas SQL Operador | `services/agente_operador_service.py` |
| Contexto para LLM | `services/agente_contexto_service.py` |
| HTTP Ollama | `services/ollama_client.py` |
| Control Center UI | `services/control_center_service.py`, `templates/admin/dashboard_madre.html` |
| Modo cierre caja | `services/cierre_caja_config_service.py`, `templates/caja/cerrar_caja.html`, `templates/caja/_resumen_cierre_visible.html` |
| Admin config | `/admin/empresa` → `cierre_caja_modo` |
| SQL | `sql/2026_05_21_agente_ejecuciones.sql`, `sql/2026_05_21_lhexia_vector.sql` |
| Estados | `docs/planes/06-agentes-ia/AGENTE_EJECUCIONES_ESTADOS.md` |
| Tests | `tests/test_agente_operador.py`, `tests/test_agente_operador_v02.py`, `tests/test_cierre_caja_modo.py` |

---

## 4. Cierre de caja — decisión de negocio

- **Default:** `ciego` (Santo Domingo / demo auditores).
- **Opcional:** `visible` — dueño o capacitación ve teórico en `/cerrar_caja`.
- Cambio: **Admin → Datos de empresa → Cierre de caja** (sin tocar Render).
- Alertas Operador guardan `modo_cierre` en `payload_json`; descuadre en modo **visible** → severidad **critical**.

---

## 5. Próximos pasos sugeridos (orden)

1. **SD-1 piso** — POS + inventario (prioridad absoluta).
2. Validar Control Center en prod tras deploy (sin escaneo masivo el primer día).
3. Cuando exista PC en sucursal: Ollama + cron `agente_operador_enrich.py`.
4. Neon: `psql … -f sql/2026_05_21_lhexia_vector.sql`.
5. Agente **Comercial** (HITL + cola) y **Guía** (RAG productos) — después de SD-1.
6. **FE Maullín** — reanudar solo cuando SII cierre folio 77326378627.

---

## 6. Prompt para retomar en Cursor

```
Lee @docs/memory.md (§ Checkpoint 2026-05-21) y @docs/planes/06-agentes-ia/CHECKPOINT_RETOMAR_2026_05_21.md.
Prioridad: SD-1. Agentes v0.1 en prod; v0.2 dormido sin Ollama. Cierre caja: default ciego, configurable en /admin/empresa.
¿Qué seguimos hoy?
```

---

*Creado: 2026-05-21 — Mario / Cursor*
