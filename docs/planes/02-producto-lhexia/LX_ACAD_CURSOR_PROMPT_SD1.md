# Cursor — Prompt LX-ACAD SD-1 (copiar en Agent)

**Uso:** pegar el bloque «PROMPT» en Cursor **después** de crear checkpoint git.  
**Tickets:** [`LX_ACAD_TICKETS_SD1.md`](LX_ACAD_TICKETS_SD1.md)  
**No implementar todo en un solo PR** — ejecutar **un ticket por iteración** salvo que Mario diga lo contrario.

---

## Antes de codificar (obligatorio)

```bash
git tag checkpoint/lx-acad-0-pre-YYYY-MM-DD
# o: git checkout -b checkpoint/lx-acad-sd1
```

Leer: `docs/planes/02-producto-lhexia/LHEXIA_ACADEMY_MENTOR.md`

---

## PROMPT (copiar desde aquí)

```
Contexto: LhexIA ERP — evolución Academy + Mentor en PISO (Santo Domingo SD-1).
Implementar SOLO la fase acordada LX-ACAD (tickets en docs/planes/02-producto-lhexia/LX_ACAD_TICKETS_SD1.md).
NO ejecutar el prompt masivo "v4 Duolingo" de Grok.

=== PRIORIDAD ABSOLUTA ===
- ¿Bloquea POS, caja o inventario mañana? Si un cambio lo arriesga, detener y reportar.
- Cambios en templates POS/caja/mentor → diff mínimo; mantener partials existentes.
- Producción: respetar guardia tests conftest (_verificar_no_es_produccion).
- Al terminar CADA ticket: pytest tests/test_academy_mentor_api.py tests/test_pos_mentor_academy.py -v (16+ tests verdes).

=== FUERA DE ALCANCE (NO HACER) ===
- Leaderboard, badges públicos, streak global visible entre usuarios
- Reseed masivo "atomic learning" que reemplace todo MANUAL_V2 sin plan de migración
- Simuladores de arqueo/cobro
- RAG / chat LLM / voz
- Tabla user_academy_stats separada, certificados, PWA offline
- micro_quiz_json (post SD-1)
- Refactor masivo estético Duolingo/Notion completo
- Multi-tenant en queries Academy
- Tocar flujos /guardar_venta, /procesar_cobro_caja, stock, caja crítica

=== ARCHIVOS CLAVE (leer primero) ===
- app.py: AcademyArticle, api_mentor_context, api_mentor_log_read, /academy
- blueprints/academy.py, blueprints/pos.py (alias /api/pos/mentor/*)
- services/academy_service.py, academy_bootstrap.py, academy_format.py, vertex_mentor_service.py
- templates/partials/lhexia_mentor_sidebar.html, lhexia_mentor_init.html
- templates/academy_hub.html
- static/js/pos.js, static/js/academy-format.js
- tests/test_academy_mentor_api.py, tests/test_pos_mentor_academy.py

=== TICKET A IMPLEMENTAR (elegir UNO por sesión) ===

--- LX-ACAD-1: Practicar Ahora ---
1. Unificar mapa dedupe_key → practicar_href (rutas reales: /punto_venta, /caja/vales_pendientes, /caja/cambios, /cerrar_caja, /inventario/enrolamiento según artículo).
2. Exponer practicar_href en construir_contexto_mentor_db (articulo_principal, biblioteca, pildora_prioritaria).
3. Botón "Practicar ahora" en sidebar y academy_hub.html.
4. Tests: assert practicar_href en GET /api/mentor/context para /punto_venta y /caja/cambios.

--- LX-ACAD-2: Hub 3 caminos + progreso telemetría ---
1. academy_hub.html: 3 caminos (Vendedor/pos, Cajero/caja, Bodeguero/bodega).
2. academy_service.obtener_progreso_academy_usuario(user_id): ratio artículos con evento mentor en agente_ejecuciones vs total del rol.
3. Barra o texto "X/Y completado" sobrio por camino.
4. Integrar Practicar ahora (ACAD-1).
5. Test GET /academy y test unitario progreso.

--- LX-ACAD-3: Checklist + user_academy_progress ---
1. Modelo UserAcademyProgress + _asegurar_tabla_user_academy_progress() idempotente.
2. sql/2026_05_XX_user_academy_progress.sql referencia.
3. POST /api/mentor/save_step en blueprints/academy.py (mismos permisos que log_read).
4. Pasos con ids step-0..n; persistir completed_steps_json; marcar completed_at al terminar.
5. JS: checkboxes .lhexia-step-check → POST async; restaurar estado al cargar contexto.
6. Tests nuevos save_step + aislamiento por usuario. Mantener 16 tests previos verdes.

--- LX-ACAD-4: Modo Guía Activa + difficulty_level ---
1. Columnas academy_articles: difficulty_level, estimated_time (migración idempotente + seed).
2. Toggle Guía activa / Biblioteca en sidebar (localStorage); comportamiento documentado en LHEXIA_ACADEMY_MENTOR.md.
3. API context: modo_sugerido según detectar_contexto_pantalla.
4. Sin micro_quiz_json.

=== CONVENCIONES ===
- Reutilizar registrar_lectura_academy / vertex_pildora_contract; agente_nombre='mentor'.
- Copy en español Chile, tono profesional ferretería (no "Legend", no cyberpunk).
- INVARIANTE_FINANCIERA: no sugerir cobro en POS.
- Atajos: F2 búsqueda, F8 emitir vale (verificar con tests/POS existentes).

=== ENTREGABLES POR TICKET ===
1. Código + tests
2. Actualizar LHEXIA_ACADEMY_MENTOR.md si hay API/tablas nuevas
3. Resumen: archivos tocados, comando pytest, riesgos piso
4. NO commit salvo que Mario diga "commit" o "aplícalo"

Indica al inicio de tu respuesta qué ticket LX-ACAD-N estás implementando.
```

---

## FIN DEL PROMPT

---

## Variante corta (un solo ticket)

Sustituir la sección `TICKET A IMPLEMENTAR` por una sola línea, por ejemplo:

`Implementar ÚNICAMENTE LX-ACAD-1 según LX_ACAD_TICKETS_SD1.md.`

---

## Después de implementar

```bash
pytest tests/test_academy_mentor_api.py tests/test_pos_mentor_academy.py -v
# si ACAD-3+: pytest tests/test_academy_progress.py -v
```

Validación piso (5 min): POS → expandir Mentor → Practicar ahora; `/academy` muestra 3 caminos.

---

*Versión: 2026-05-23 · Alineado con Cursor + Mario (crítica producto vs Grok v4).*
