# Roadmap — Módulo Clientes + Customer 360 (Ferretería LhexIA ERP)

**Versión:** 1.0 · **Fecha referencia:** mayo 2026  
**Stack actual del ERP:** Python / Flask / SQLAlchemy / Jinja2 / Bootstrap (no hay SPA React hoy).  
**Nota de arquitectura:** El prompt original pide React + TypeScript + Tailwind; este roadmap **prioriza entregar valor en el monolito Flask** y deja **React como fase opcional** (Canvas embebido, micro-frontend o pantalla aparte) para no bloquear el negocio.

---

## Leyenda de prioridad

| Etiqueta | Significado |
|----------|-------------|
| **P0 — Urgente** | Customer 360 mínimo viable + reglas de negocio acordadas; base para predicción y crédito. |
| **P1** | Mejora fuerte de UX y datos; impacto operativo inmediato. |
| **P2** | Diferenciación “premium” / IA / OCR / workers nocturnos. |
| **P3** | Escala, portal cliente, integraciones pesadas. |

---

## Fase P0 — Urgente: núcleo “Customer 360” (sin React obligatorio)

**Objetivo:** Una **ficha cliente 360** dentro del ERP que una inventario reciente + crédito + ventas en una sola vista accionable.

### P0.1 — Modelo de datos y vistas (backend)

- Tabla o vista materializable **`cliente_actividad_resumen`** (o consultas parametrizadas): última compra, frecuencia 90 días, categorías agregadas por familia de producto, `saldo_deudor`, `limite_credito`, estado crédito.
- Tabla **`cliente_prediccion_log`** (auditoría): timestamp, tipo_recomendación, payload JSON, usuario/sistema, **resultado** (`ignorada` | `aplicada_limite` | `venta_asociada_id` null) para medir conversión.
- Endpoint(s) JSON bajo prefijo `/api/clientes/...` o `/api/c360/...` con mismos permisos que mantenedores / créditos según rol.

### P0.2 — Motor “analizar etapa de proyecto” (lógica ferretería)

Implementar en **Python** (equivalente a `analizarEtapaProyecto(comprasRecientes)` del prompt):

1. **Clasificación de líneas de venta** según producto → categoría de obra:
   - `OBRA_GRUESA` | `INSTALACIONES` | `ACABADOS`  
   (mapeo vía `categoria` / `subcategoria` del catálogo o tabla de reglas configurable `producto_categoria_obra`).
2. **Regla mayoritaria:** si el peso (monto o cantidad de SKUs) de `OBRA_GRUESA` supera umbral configurable → etapa detectada = obra gruesa.
3. **Trigger “extensión proactiva de crédito” (solo sugerencia, no automático):**
   - Calcular **`fecha_estimada_siguiente_compra`** = última compra clasificada + **21 días** (configurable).
   - Guardar fila en `cliente_prediccion_log` tipo `EXTENSION_CREDITO_SUGERIDA` con monto/etapa/score requerido (ver P0.3).
4. **Documentación interna:** umbrales y definiciones de categorías versionadas (para no “magia negra” en tribunal interno).

### P0.3 — Score de puntualidad (> 90 % para crédito proactivo)

- Definición explícita v1 (ejemplo, ajustable):
  - % de cuotas / documentos pagados **a tiempo** en ventana rolling 12 meses.
  - Penalizaciones por mora > N días.
- Función `score_puntualidad_cliente(cliente_id) -> float 0..100`.
- **Regla de negocio:** bandera `elegible_credito_proactivo = score > 90` **y** estado crédito activo **y** sin listas negras internas.
- Todo crédito proactivo es **recomendación**; aprobación humana (jefe) o flujo futuro.

### P0.4 — UI en Flask (Jinja)

- Nueva ruta **`/clientes/<id>/360`** o pestaña “360” desde listado Clientes.
- Secciones:
  - Resumen crédito + link a cartola / cobranza.
  - “**Etapa de proyecto detectada**” + próxima fecha sugerida.
  - Lista corta últimas compras con iconos por categoría obra.
  - Bloque **“Oportunidades de crédito”** (solo si score > umbral): texto + botón “Registrar nota” / “Ajustar límite” (futuro).

**Criterio de cierre P0:** Un vendedor o dueño abre un cliente y entiende en **< 30 s** si conviene acercarse por siguiente fase de obra y si el cliente es puntual.

---

## Fase P1 — Premium operativo (2025–2026 tendencias “CDP ligero”)

- Etiquetas cliente + consentimiento canal (WhatsApp / llamada).
- Timeline de eventos (ventas, abonos, cambios límite).
- Búsqueda unificada (RUT flexible, teléfono parcial).
- **Dashboard “Ferretero predictivo”** (versión 1) en página dedicada o widget en 360:
  - Lista **clientes por pasar de obra gruesa → instalaciones/acabados** (según motor P0.2).
  - **Barra “salud de proyecto”** v1: `crédito_usado / crédito_estimado_obra` donde “estimado” sale de heurística (reglas por m² o ticket promedio histórico del segmento) hasta tener modelo mejor.

---

## Fase P2 — Prompt original: UI “Smart Dropzone” + OCR simulado

**Alineación con stack:**  
- **Opción A (recomendada MVP):** Componente en Jinja + JS (`react-dropzone` no aplica sin React): usar **`<input type="file">` + drag-and-drop nativo** + estado de carga animado; llamada a endpoint **`POST /api/abonos/ocr-simulado`** que devuelve JSON `{ monto, fecha_vencimiento, rut }` con **mock** fijo o reglas demo.
- **Opción B:** Micro-front **React + TS + Tailwind** solo para el dropzone (build estático servido por Flask) si el equipo quiere el stack del prompt literal.

### P2.1 — Contrato OCR (futuro Textract / Vision)

- Mismo JSON schema para intercambiar con AWS/Google más adelante.
- Cola **opcional** (tabla `ocr_jobs`) si el volumen crece.

### P2.2 — Poblar formulario de abonos

- Al confirmar extracción: prellenar formulario existente de abono con validación humana obligatoria (checkbox “Verifiqué datos”).

---

## Fase P2b — Worker nocturno (“Pro-Tip” del arquitecto)

- **Script / job** (cron Windows o systemd Linux) que llame a:
  - `POST /api/interno/llamadas-recomendadas/generar` con `Authorization: Bearer` (mismo patrón que `dispatch-cloud` de cobranza), **o**
  - comando `python -m scripts.generar_llamadas_recomendadas`.
- Salida: tabla **`llamadas_recomendadas_dia`** o JSON para imprimir: cliente, motivo (“probable paso a acabados”), score, teléfono, vendedor sugerido.
- Métricas: join con `cliente_prediccion_log` para **tasa conversión recomendación → venta**.

---

## Fase P3 — Escala y confianza

- Portal cliente mínimo (token mágico) para ver cartola.
- IA generativa **solo asistida** (borrador mensaje cobranza / visita), siempre con revisión.
- Refinar modelo de “gasto estimado restante” con histórico real por zona/comuna.

---

## Matriz resumen (qué del prompt → dónde)

| Idea del prompt | Implementación en este ERP |
|-----------------|----------------------------|
| `analizarEtapaProyecto` | Función Python + reglas categoría producto |
| Extensión crédito + 21 días | Campo calculado + log predicción + UI sugerencia |
| Smart Dropzone + OCR | JS + endpoint mock → proveedor real en P2 |
| Dashboard oportunidades | Vista Flask + consultas agregadas |
| Score puntualidad > 90 % | Función score + bandera elegibilidad |
| Log predicciones → ventas | Tabla `cliente_prediccion_log` + resultado |
| React + TS + Tailwind | Opcional; MVP en Jinja |
| Worker nocturno llamadas | Cron + endpoint interno o script |

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Categorías mal mapeadas | Reglas editables + revisión humana en v1 |
| Crédito “automático” mal entendido | Solo **sugerencias** y auditoría |
| OCR errores en abonos | Confirmación obligatoria + no auto-post |
| Complejidad React | No bloquear P0; SPA después si aporta |

---

## Próximo paso sugerido para Cursor / desarrollo

1. Implementar **P0.2 + P0.3 + P0.4** en Flask (sin OCR).  
2. Añadir **P2b** mínimo (lista diaria mock o real).  
3. Iterar **P2** OCR simulado en el flujo de abonos.

---

*Documento vivo: actualizar fechas y fases al cerrar cada hito.*
