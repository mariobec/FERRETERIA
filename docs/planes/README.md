# Planes LhexIA ERP — Carpeta única de planificación

**Todo el orden de planes vive aquí.** Referencia técnica operativa (ERP, flujos, migración) sigue en `docs/` raíz.

---

## Entradas principales

| Documento | Ruta |
|-----------|------|
| **Índice maestro (prefijos SD, POS, TEC…)** | [`00-alineacion/PLAN_INDICE_LHEXIA.md`](00-alineacion/PLAN_INDICE_LHEXIA.md) |
| **Alineación Mario · Grok · Cursor** | [`00-alineacion/MEMORY_GROK.md`](00-alineacion/MEMORY_GROK.md) |
| **Configurar Grok Project (5 archivos)** | [`00-alineacion/GROK_PROJECT_SETUP.md`](00-alineacion/GROK_PROJECT_SETUP.md) |
| **Ritmo equipo (Daily / Weekly / Sprint)** | [`00-alineacion/EQUIPO_RITMO_ASYNC.md`](00-alineacion/EQUIPO_RITMO_ASYNC.md) |
| **Plantilla documentos cliente** | [`00-alineacion/PLANTILLA_DOCUMENTO_CLIENTE.md`](00-alineacion/PLANTILLA_DOCUMENTO_CLIENTE.md) |
| **Producto LhexIA (portal)** | [`02-producto-lhexia/LHEXIA_PRODUCTO.md`](02-producto-lhexia/LHEXIA_PRODUCTO.md) |
| **Fidelización + sorteo TV (backlog)** | [`02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md`](02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md) |
| **Vitácora reunión SD (puntos + chocolate)** | [`01-entrega-santo-domingo/VITACORA_REUNION_FIDELIZACION_PROMO_SD.md`](01-entrega-santo-domingo/VITACORA_REUNION_FIDELIZACION_PROMO_SD.md) |
| **Santo Domingo entrega (portal)** | [`01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md`](01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md) |
| **POS offline-first (roadmap)** | [`04-tecnico/ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md`](04-tecnico/ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md) |
| **Casuísticas QA ventas** | [`../CASUISTICAS_VENTAS_QA.md`](../CASUISTICAS_VENTAS_QA.md) |

**Bitácora técnica diaria:** [`../memory.md`](../memory.md) — § «Dónde quedamos» = foco SD-1 piso.

---

## Estructura de carpetas

| Carpeta | Prefijo | Contenido |
|---------|---------|-----------|
| [`00-alineacion/`](00-alineacion/) | — | Índice maestro, MEMORY Grok |
| [`01-entrega-santo-domingo/`](01-entrega-santo-domingo/) | **SD-** | Go-live cliente #1, runbook piso |
| [`02-producto-lhexia/`](02-producto-lhexia/) | **LX-** | Visión producto, roadmap, arquitectura objetivo |
| [`03-pos-vendedor/`](03-pos-vendedor/) | **POS-** | UI pantalla vendedor |
| [`04-tecnico/`](04-tecnico/) | **TEC-** / **CORE-** | Estabilidad, `core/`, optimización `app.py` |
| [`05-roadmap_plataforma_madre.md`](05-roadmap_plataforma_madre.md) | **PLAT-** | Roadmap canónico 3 etapas (resiliencia → plataforma → IA) |
| [`05-modulos-backlog/`](05-modulos-backlog/) | **MOD-** | C360, bodega, observabilidad, auditorías |
| [`06-agentes-ia/`](06-agentes-ia/) | **IA-** | Agentes negocio 24/7 (ferretería) |
| [`07-agentes-meta-desarrollo/`](07-agentes-meta-desarrollo/) | **META-** | Agentes para desarrollar LhexIA |

---

## Qué queda en `docs/` (no es plan)

| Archivo | Rol |
|---------|-----|
| `ERP_MAESTRO.md` | **Mapa técnico** del sistema (modelos, rutas, deploy, tests) — actualizado 2026-05-21 |
| `FLUJOS_CRITICOS.md` | Secuencias que no romper |
| `MIGRACION_RENDER_NEON.md` | Deploy y Neon |
| `CASUISTICAS_PRUEBAS.md` | QA |
| `memory.md` | Memoria viva Cursor |
| `PROMPT_MAESTRO_ERP.md` | Prompt arquitecto |

---

*Rutas antiguas en `docs/` raíz tienen un stub «Movido» que apunta aquí.*
