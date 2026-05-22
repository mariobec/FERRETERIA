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
| **Inventario SD D0–D5 (checklist)** | [`01-entrega-santo-domingo/CHECKLIST_INVENTARIO_SD_D0_D5.md`](01-entrega-santo-domingo/CHECKLIST_INVENTARIO_SD_D0_D5.md) |
| **Importar RCV SII + recepciones** | [`01-entrega-santo-domingo/IMPORTAR_RCV_SII.md`](01-entrega-santo-domingo/IMPORTAR_RCV_SII.md) |
| **Pausa / D1 piloto pistola** | [`01-entrega-santo-domingo/PAUSA_D1_PILOTO_PISTOLA.md`](01-entrega-santo-domingo/PAUSA_D1_PILOTO_PISTOLA.md) |
| **POS offline-first (roadmap)** | [`04-tecnico/ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md`](04-tecnico/ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md) |
| **Casuísticas QA ventas** | [`../CASUISTICAS_VENTAS_QA.md`](../CASUISTICAS_VENTAS_QA.md) |
| **PWA Dueño — validación prod** | [`01-entrega-santo-domingo/OWNER_PWA_VALIDACION_PROD.md`](01-entrega-santo-domingo/OWNER_PWA_VALIDACION_PROD.md) |
| **Biblia Ecosistema LhexIA VERTEX (4 fases)** | [`../arquitectura/LHEXIA_VERTEX_VISION.md`](../arquitectura/LHEXIA_VERTEX_VISION.md) |
| **Tracker sprint VERTEX** | [`../arquitectura/VERTEX_SPRINT_TRACKER.md`](../arquitectura/VERTEX_SPRINT_TRACKER.md) |
| **Cierre SD-1 Fase 1 (checklist)** | [`01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md`](01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md) |
| **ERP multi-sucursal (diseño VERTEX)** | [`../arquitectura/VERTEX_MULTI_SUCURSAL.md`](../arquitectura/VERTEX_MULTI_SUCURSAL.md) |
| **VERTEX Master Core (píldoras / push-pull)** | [`../arquitectura/VERTEX_MASTER_CORE.md`](../arquitectura/VERTEX_MASTER_CORE.md) |

**Bitácora técnica diaria:** [`../memory.md`](../memory.md) — § «Dónde quedamos» (2026-05-22: D0 ✅, D1 lunes).

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
| `ERP_MAESTRO.md` | **Mapa técnico + especificación funcional integral (§0) + planes (§19)** — actualizado 2026-05-22 |
| `FLUJOS_CRITICOS.md` | Secuencias que no romper |
| `MIGRACION_RENDER_NEON.md` | Deploy y Neon |
| `CASUISTICAS_PRUEBAS.md` | QA |
| `memory.md` | Memoria viva Cursor |
| `PROMPT_MAESTRO_ERP.md` | Prompt arquitecto |

---

*Rutas antiguas en `docs/` raíz tienen un stub «Movido» que apunta aquí.*
