# Memoria del proyecto (ERP ferretería / ventas)

Este archivo es la **memoria viva** del trabajo en el repo. El usuario y el agente lo usan para **recordar contexto entre sesiones**.

**Copia canónica (detalle completo):** `docs/memory.md` — mantener sincronizado al actualizar. Este archivo = índice + «Dónde quedamos» breve.

**Planes:** `docs/planes/README.md` · **Memory Grok:** `docs/planes/00-alineacion/MEMORY_GROK.md` · **Backlog post SD-1 (puntos + sorteo TV):** `docs/planes/02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md` · **Piloto IA SD/Chilemat:** `docs/planes/06-agentes-ia/MEMORY_PILOTO_IA_SD_CHILEMAT.md`

## Cómo usarlo

- **Cursor:** `@docs/MEMORY_GROK.md` + `@memory.md`
- **Grok:** pegar `docs/MEMORY_GROK.md` o prompt §13 de ese archivo
- **Cuando terminemos un bloque de trabajo:** pedir *“actualiza memory.md con lo que hicimos hoy”* para dejar constancia.
- El agente **no inventa** historial: solo documenta lo que consta en el chat o en el código que tocamos.
- **Transcripción del chat:** Cursor conserva tus conversaciones en la interfaz; aquí **no** se replica el chat palabra por palabra. Esta memoria es el **extracto técnico** entre sesiones/desarrolladores (comandá *“actualiza memory.md”* cuando quieras cerrar el día).
- **Documento maestro (referencia amplia):** `docs/ERP_MAESTRO.md` — arquitectura, rutas, módulos v3, sync Neon, tests.

## Alcance de esta memoria (importante)

- Aquí hay **mapa por módulo, reglas que cruzan el sistema, modelos y operativa reciente**. Para cada función puntual, la **fuente de verdad sigue siendo `app.py`** (~22.3k líneas) y los **blueprints** (`add_url_rule`).
- **No sustituye** leer el código cuando hace falta precisión de borde (validaciones raras, mensajes de error, migraciones SQL recientes).

## Qué es este proyecto

- **Stack principal:** Flask, Flask-SQLAlchemy, Flask-Login, **PostgreSQL** (producción Neon/Render; **local Postgres recomendado para QA** y `pytest`). Driver **MySQL (PyMySQL)** sigue disponible para entornos legacy si no hay `DATABASE_URL` Postgres.
- **Patrón:** núcleo **monolítico** en **`app.py`**, con **blueprints** (`bodega`, `caja`, `pos`, `c360`) que registran rutas vía **`register_*_routes(app)`** + `add_url_rule` (~59 reglas URL en blueprints; el resto en `app.py`).
- **Frontend servidor:** Jinja2 en **`templates/`** (~89 HTML).
- **Estáticos:** **`static/`** (`design-system.css`, Bootstrap local, `pos.js`, `pos-command-deck.js`, `pos-live-wall-*.js`, `pos-experience-wall.js`, logos).
- **Migraciones / DDL:** **`sql/`** (~39 archivos `YYYY_MM_DD_*`).
- **Scripts:** **`scripts/`** — semillas, smoke, **sync local→Neon** (`sync_local_neon_render.py`, `sync_postgres_db.py`), `seed_demo_data.py`, `normalize_demo_data_clp.py`, etc.
- **Datos JSON runtime:** **`data/`** (empresa, proveedores, leads landing JSONL, etc.).
- **Tests:** ~**263** tests recogidos (`pytest tests/ --collect-only`); smoke ~**77** (`-m smoke`).

## Arquitectura del repositorio (carpetas relevantes)

**Refactor en curso (Clean Architecture ligera):** ver `docs/ARQUITECTURA_CAPAS.md`. **`core/`** Fases **1.2–1.4**: use cases venta/cobro; stock/kardex (`DescontarStockCobroService`); **cuotas crédito + saldo_deudor** y **saldo a favor** post-cobro vía servicios en `core/application/creditos` y `ventas/post_cobro_saldo_favor`. Bodega, FE y audit siguen en `app.py`.

| Ubicación | Rol |
|-----------|-----|
| `domain/` | Reglas puras por bounded context (sin Flask/SQLAlchemy). |
| `application/` | Casos de uso + `ports/` (interfaces repos). |
| `infrastructure/` | Persistencia y repos (futura extracción ORM desde app.py). |
| `adapters/web`, `adapters/jobs` | HTTP delgado y cron (convive con `blueprints/`). |
| `config/` | `settings.py` — env centralizado (opt-in). |
| `app.py` | App Flask, modelos SQLAlchemy, gran parte de rutas y reglas de negocio. |
| `blueprints/` | POS (~22 reglas), caja (~15), bodega (~12), c360 (~10) — ver `register_*_routes`. |
| `services/` | stock, kardex, venta (`transaccion_critica`), audit, whatsapp, unidades, c360, health, **facturacion_*** (legacy; migrar gradualmente) |
| `schema_sync.py` | Sincronización esquema modelos vs BD (usado en `init_db`). |
| `init_db.py` | `schema_sync`, roles base, usuario admin opcional `BOOTSTRAP_ADMIN_*`. |
| `requirements.txt` | Dependencias Python. |
| `render.yaml` | Deploy: `gunicorn app:app`. |
| `templates/`, `static/` | UI. |
| `sql/`, `scripts/` | DDL incremental y utilidades (incl. sync Neon). |
| `storage/dtes/` | XML DTE firmados (gitignored en producción típica). |
| `docs/` | **ERP_MAESTRO.md**, **memory.md** (esta copia), MIGRACION_RENDER_NEON, FLUJOS_CRITICOS, roadmaps. |

Copias viejas (`app-28-04-2026.py`, etc.): **operativo = `app.py`**.

---

## Sincronización Postgres local → Neon (QA / pre-producción)

**Scripts:** `scripts/sync_local_neon_render.py` + `scripts/sync_postgres_db.py`  
**Detalle:** `docs/MIGRACION_RENDER_NEON.md` y `docs/ERP_MAESTRO.md` §12.

1. En **`.env.local`** (raíz repo, no en git):  
   - `DATABASE_URL` = Postgres **local** (origen)  
   - `NEON_DATABASE_URL` = Neon **host directo** (sin `-pooler` en el host; `sslmode=require`)
2. **Pausar Render** (u otra app que escriba en la misma Neon) durante el sync; si no, los conteos **divergen** tras el `commit`.
3. Ejecutar desde la raíz:

```bash
python scripts/sync_local_neon_render.py
python scripts/sync_local_neon_render.py --verify-only
```

- Flujo completo: migraciones SQL listadas en el script → `TRUNCATE` tablas comunes en Neon → copia filas desde local → verificación de conteos (`TABLAS_CHECK`).  
- **`--verify-only`:** solo compara conteos; **exit code 1** si local ≠ Neon.  
- Tras sync completo, el script también verifica y falla con código 1 si no cuadra.  
- Warning habitual en Neon: `permission denied ... session_replication_role` — **esperable**; el script continúa sin ese bypass.  
- **Render en producción** puede seguir usando URL **pooler**; el script de sync usa **directo** solo en `NEON_DATABASE_URL`.

**Estado conocido (mayo 2026):** hubo corridas con `sync:ventas:1041` y `sync_completed` pero verificación posterior mostró Neon con menos filas (p. ej. ventas 520 vs 1041) — típico de **escritores concurrentes** en Neon o sync interrumpido; repetir con servicios pausados y `--verify-only` hasta `verificacion_ok`.

---

## Modelos ORM principales (`app.py`)

Tablas/modelos usados como columna vertebral (no exhaustivo de cada campo):

| Modelo | Dominio |
|--------|---------|
| `Almacen`, `StockPorAlmacen` | Multi-almacén (tienda/bodega, stock por SKU). |
| `CatalogoCategoria`, `CatalogoSubcategoria` | Árbol catálogo público/admin. |
| `Producto` | Maestro SKU, precios, unidades de venta, vínculos catálogo. |
| `EnrolamientoTomaSesion`, `EnrolamientoTomaLinea` | Toma física / enrolamiento móvil. |
| `Venta`, `DetalleVenta` | Ventas, vales, líneas; estados Abierta/Pendiente/Pagado/Anulada. |
| `Cotizacion`, `CotizacionDetalle` | Cotizaciones comerciales y conversión a POS. |
| `Caja`, `MovimientoCaja` | Apertura/cierre, arqueo, movimientos. |
| `Proveedor` | Maestro proveedores. |
| `OrdenCompra`, `DetalleOrdenCompra` | OC compras (requiere migración si tablas no existen). |
| `Cliente` | Maestro clientes, crédito (`saldo_deudor`, `limite_credito`). |
| `Rol`, `Permiso`, `RolPermiso` | RBAC. |
| `UnidadMedida`, `ConversionUnidad` | Unidades y conversiones. |
| `RecepcionCompra`, `DetalleRecepcion` | Recepción mercadería vs documento. |
| `MovimientoInventario` | Movimientos / kardex. |
| `BitacoraCostoCompra`, `BitacoraPrecioVenta` | Historial precios/costos. |
| `CambioOperacion`, `CambioDetalle` | Devoluciones/cambios en caja. |
| `ClienteSaldoFavor`, `MovimientoSaldoFavor` | Saldo a favor del cliente. |
| `AuditoriaInventario`, `DetalleAuditoria` | Auditorías/conteos. |
| `AbonoCredito` | Abonos a cuenta crédito. |
| `Caf` | Folios autorizados SII (CAF XML). |
| Columnas FE en `Venta` | `dte_tipo`, `dte_estado`, `dte_track_id`, `caf_id`, `nro_documento` (folio DTE). |
| Web/SEO analytics | `WebAnalytics*`, `Seo*`, `ControlTraficoInterno`, etc. |
| C360 | `C360LlamadaSnapshotDia`, `C360ProactivaOferta`, `cliente_prediccion_log`, etc. |

---

## Reglas transversales

### Permisos (`permisos_required`, `usuario_tiene_permiso`)

- Roles admin/superadmin → **pasan cualquier permiso**.
- Resto: permiso en `rol_permisos`.
- Permisos semilla: `_PERMISOS_SISTEMA_INICIAL` — incluye `gestionar_usuarios`, `admin_inventario`, `enrolamiento_inventario`, `panel_gerencia`, `anular_vale_caja`, `autorizar_descuento_pos`, `revision_precios`, `pos_emitir_vale`, `caja_cobrar_vale`, `caja_abrir`, `caja_movimientos`, `caja_cerrar`, `bodega_operador`, `ver_inventario`, `ver_gerencia`, `gestionar_compras`, `ver_auditoria`.
- **`modulo_activo(n)`:** JSON empresa (`mod_*`).

### Caja obligatoria (`caja_requerida`)

- Endpoints en **`_ENDPOINTS_CAJA_ESTRICTA`**: POS, cobro, anular, cambios, `registrar_abono`, etc.
- Caja de **día anterior** → redirige a cerrar caja salvo **`_ENDPOINTS_EXENTOS_BLOQUEO_FECHA_CAJA`** (cobrar/anular/ticket en cola).

### Stock y tienda

- **`_factor_venta_a_stock`**, **`stock_disponible_venta_tienda`**, **`descontar_stock_venta_tienda`** al cobrar.
- Kardex en cobros; invariante consumo bodega+tienda ≤ total por línea.

### Cliente sistema “final”

- RUT `POS_RUT_CLIENTE_FINAL` (default `66.666.666-6`).

---

## Lógica por módulo (resumen)

### Ventas — dos flujos (crítico)

| Flujo | Resumen |
|--------|---------|
| **A. POS / vale** | `punto_venta` → venta **Abierta**; `finalizar_venta` → **Pendiente** sin descontar stock; **`procesar_cobro_caja`** → **Pagado** + stock + kardex (+ FE post-cobro si aplica). |
| **B. Venta directa** | **`guardar_venta`**: descuenta stock en el mismo request según medio/estado. |

Rutas POS adicionales en **`blueprints/pos.py`**: `/pos/command-deck`, `/pos/experience-wall`, `/pos/live-wall/*`, `/api/pos/*` (cross-sell, vincular cliente, escanear, alta rápida, foto producto, etc.).

### Caja

- Cola **`cola_combined`**, cierre bloqueado por Pendiente/Abierta, **`POST /caja/limpiar_cola_cierre`**, anulación masiva admin.

### Facturación electrónica (SII) — Fase 1 ERP 🟡

- Servicios `facturacion_*`; post-cobro no revierte cobro; cola DTE; firma `.pfx` (signxml 4.x).
- **Pendiente:** TED real, SOAP Zeep, certificación SII producción.

### Bodega, compras, créditos, cotizaciones, C360, observabilidad web

- Sin cambio de reglas de negocio respecto a memoria previa; ver **`docs/ERP_MAESTRO.md`** §4–§7 y módulos §10–§19 del maestro.
- **Customer 360 P0** ya en código (predicción 21d, `cliente_prediccion_log`, API resumen); P1+ en roadmap.

---

## Ambientes (convención del equipo — desde 2026-05-17)

| Ambiente | Dónde corre | Base de datos | Uso |
|----------|-------------|---------------|-----|
| **Desarrollo** | PC local (`python app.py`, IP LAN ej. `192.168.x.x:5000`) | **Postgres local** vía `DATABASE_URL` en `.env.local` | Features, `pytest`, pruebas POS sin tocar usuarios reales. |
| **Productivo** | **Render** (`render.yaml`, Gunicorn, `autoDeployTrigger: commit`) | **Neon** vía `DATABASE_URL` en dashboard Render (host **pooler**) | Operación tienda / URL pública. |

**Reglas operativas:**
- **No** apuntar desarrollo a la misma Neon de productivo salvo prueba puntual acordada (riesgo de datos reales).
- Despliegue a productivo = **`git push`** a la rama que Render sigue (típ. `main`) → build + `preDeployCommand: python init_db.py` + Gunicorn.
- Sync de datos **local → Neon** solo con `scripts/sync_local_neon_render.py` y Render **pausado**; no es necesario para cambios solo de UI/API sin migración SQL.
- Tras deploy en Render: **Ctrl+F5** en `/punto_venta` (cache bust en `pos.js?v=…`).

Detalle deploy: `docs/MIGRACION_RENDER_NEON.md`.

---

## Configuración y entorno

| Variable | Uso |
|----------|-----|
| `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI` | **Local:** Postgres dev. **Render:** Neon productivo (pooler). |
| `NEON_DATABASE_URL` | Solo scripts sync (`.env.local`) |
| `SECRET_KEY`, `OPENAI_API_KEY` | Sesión Flask, IA |
| `SII_CERT_PFX_*`, `SII_AMBIENTE` | Facturación electrónica |
| `WHATSAPP_*`, `SLACK_WEBHOOK_URL` | Integraciones |

**Archivos env:** `env_qa.txt`, `.env.qa`, `.env.local`  
**Postgres:** `postgresql+psycopg2://`; UTF-8 en Windows.

## Arranque local

```bash
python -m pip install -r requirements.txt
python app.py
```

**Producción:** `gunicorn app:app` (`render.yaml`).

## QA rápido

```bash
pytest tests/ -m smoke -q --tb=no
pytest tests/test_routes_criticas.py -q
pytest tests/test_facturacion_*.py tests/test_pos_live_wall.py -q
python scripts/sync_local_neon_render.py --verify-only   # requiere .env.local
```

Guardia anti-prod en `tests/conftest.py` (bloquea hosts cloud salvo `ALLOW_TESTS_ON_REMOTE=1`).

---

## Historial (actualizar cuando haya hitos)

| Fecha       | Qué pasó |
|------------|----------|
| 2026-05-08 | Memoria arquitectura; módulos; venta dual POS vs formulario; caja día anterior; plan v2 Grok. |
| 2026-05-10 | Cierre plan v2.0; servicios extraídos; `transaccion_critica` ampliada. |
| 2026-05-11 | Bodega Fase 3 SLA/TV; RBAC v2 `_NAV_MAP`. |
| 2026-05-12 | SEO/landing; observabilidad first-party; suite QA v4 + CI. |
| 2026-05-14 | FE diagnóstico certificación; Customer 360 P0/P0.1 en código. |
| 2026-05-15 | FE Fase 1 ERP (CAF, cola DTE, XML); POS Live Wall; UX POS/caja (Command Deck, anular lote). |
| 2026-05-16 | **`docs/ERP_MAESTRO.md` actualizado** (~22.3k líneas app, ~263 tests, blueprints, sync Neon, §18 módulos v3). |
| 2026-05-16 | **`scripts/sync_local_neon_render.py`:** `--verify-only`, verificación post-sync (exit 1 si conteos difieren), mensajes de progreso con `flush`, Neon host directo recomendado. |
| 2026-05-16 | **`memory.md` + `docs/memory.md`** sincronizados con maestro y operativa sync. |
| 2026-05-16 | **Estructura capas** `domain/`, `application/`, … + `docs/ARQUITECTURA_CAPAS.md` (sin Alembic). |
| 2026-05-16 | **Fase 1.2** dominio + repo + tests `test_core_domain_venta.py` (8). |
| 2026-05-16 | **Fase 1.2 wiring** `AppStockTiendaValidator`, `bootstrap.py`, `finalizar_venta` → `FinalizarVentaUseCase`, `procesar_cobro_caja` → `ProcesarCobroUseCase`. |
| 2026-05-16 | **Fase 1.3** `DescontarStockCobroService`, `AppCobroStockAdapter`, `procesar_cobro_caja` + `cobrar_venta_efectivo` (conftest) alineados. |
| 2026-05-17 | **Convención ambientes:** desarrollo = local, productivo = Render (+ Neon). |
| 2026-05-17 | **POS asistente búsqueda manual:** commit `8c9535c` — input `#posBuscarManual`, panel tarjetas, `/buscar_producto?enriquecido=1`. **Pendiente `git push` a Render.** |
| 2026-05-24 | **Piloto IA SD→Chilemat:** análisis estrategia (Ollama local + Operador + Guardián + Liz/Gemini); memoria en `docs/planes/06-agentes-ia/MEMORY_PILOTO_IA_SD_CHILEMAT.md` + regla `.cursor/rules/ia-piloto-chilemat.mdc`. Pendiente: decisión prioridad Dueño vs Mostrador e implementación. |
| 2026-05-27 | **Chilemat VTEX en ERP:** explorador, vinculación, **cargas ERP** (`/compras/chilemat/cargas`), reset local 4891 SKU, ficha/imagen API, Radar precios, POS total $0 fix, RCV+CSV en commit `ee2d4fa`. Commits `6c00c08`+`ee2d4fa` sin push. Pendiente: clics ficha carrito POS, token SII ESTADO 10. |


## POS — Pantalla vendedora (rediseño premium) — ANÁLISIS PARA RETOMAR

**Estado:** propuesta evaluada por el agente; **no implementar** el rediseño profundo hasta que Mario confirme alcance al volver.  
**Pedido del usuario (2026-05-20):** dejar diagnóstico y plan en memoria; retomar después.

### ¿Estoy de acuerdo con el diagnóstico “planilla / POS de barrio”?

**Sí, en lo esencial** — con un matiz importante:

| Observación del usuario | Veredicto | Detalle en repo hoy |
|-------------------------|-----------|---------------------|
| Tablas rígidas / Excel | **Parcial** | En rol **vendedor** (`pos_layout_fullwidth`) el carrito **ya no es `<table>`** — usa `templates/pos/includes/premium_cart_cards.html` (tarjetas con borde 4px verde/azul). **Admin** y modo no-vendedor siguen con tabla clásica. |
| Dos buscadores saturan | **Sí, acertado** | Siguen coexistiendo `#posBarcodeWedge` (“Escanear”) y `#posBuscarManual` (“Búsqueda manual”) dentro del mismo `pos-command-card`, más caja morada/kicker, filtros y botón Agregar. Eso explica el “ruido de formulario”. |
| Falta de aire / padding | **Sí** | Columna izquierda muy densa: RUT+TV, card escaneo, card búsqueda, historial, sugerencias. Muchos `card-ds` anidados con bordes Bootstrap. |
| Carrito premium incompleto | **Sí** | Tarjetas mejoran jerarquía pero aún hay `input type=number` visible, `% dto`, hints “Consumo stock”, selects retiro — sensación ERP, no retail premium. |

**Conclusión:** el carrito va por buen camino; el **80% del aspecto “barrio”** viene de la **columna izquierda (doble búsqueda + muchas cards)** y del **dock/totales** aún pegados al layout 2 columnas genérico, no solo del carrito.

### Lo ya hecho en local (sin push completo a Render)

- **Fase 1–2:** semáforo, `a_pedido`, filtros Operativo/Tienda/Catálogo, modal compromiso, `ventas_a_pedido`.
- **Fase 3:** `pos_layout_fullwidth` / `pos-pantalla-vendedora` — oculta sidebar + topbar ERP; chrome `pos-vendedor-chrome`.
- **Carrito tarjetas:** `premium_cart_cards.html` + `pos-premium-layout.css`.
- **Rutas:** `/pos`, `/pos/vendedor` → redirect `punto_venta`.
- **Checkpoints git (tags):**
  - `checkpoint/pos-premium-layout-2026-05-20` → `ed9aede` (antes bloque nuevo)
  - `checkpoint/pos-pre-premium-vendedor-2026-05-20` → `4483019`
  - `checkpoint/pos-premium-vendedor-2026-05-20` → commit `877db19` (filtros + compromiso + layout; previo a tarjetas finales)
- **Revertir layout:** ver `pruebas/pos_semaforo/CHECKLIST.md` sección checkpoints.
- **Bug corregido:** `{% endif %}` faltante en `punto_venta.html` (Jinja2 `endblock` vs `if`) — corregido en sesión 2026-05-20.

**Commits locales `main`:** ~2–3 commits ahead de `origin/main` (4483019, 877db19 + cambios sin commit de tarjetas/CSS).

### Propuesta de rediseño profundo (para aprobar al volver)

**Principio:** cambio **solo presentación** en vendedor — mismos IDs DOM críticos para `pos.js`, mismos POST (`agregar_producto_venta`, `actualizar_item`, `finalizar_venta`). No tocar `blueprints/pos.py` salvo contexto opcional.

#### Fase A — Un solo buscador (máximo impacto visual, ~1 sesión) — **HECHO 2026-05-16**

- Unificar `#posBarcodeWedge` + `#posBuscarManual` en **un solo hero** (`pos-unified-search-hero`, input `#posBuscarManual`; solo si `pos_layout_fullwidth`).
- Include: `templates/pos/includes/unified_search_vendedor.html`. Cache CSS/JS `20260520m` / `20260520h`.
- Comportamiento: pistoleo y texto en el mismo input; **F2** focus; dropdown semáforo debajo (`#pos-search-suggestions` sin mover lógica JS).
- Retirar labels duplicados, caja “BÚSQUEDA MANUAL” morada, segundo `form-control` grande.
- Mantener filtros Operativo/Tienda/Catálogo como **pills** compactos en la misma barra (no segundo panel).

**Archivos:** `punto_venta.html` (rama vendedor), `pos-premium-layout.css`, ajustes menores `pos.js` (focus F2 al input unificado; wedge sigue llamando misma API).

#### Fase B — Carrito “desmaterializado” v2 (~1 sesión) — **HECHO 2026-05-16**

- Renombrar contenedor a `#contenedor-carrito` (`pos-cart-list` alias).
- Cache CSS/JS `20260520n` / `20260520i`.
- Tarjetas: más padding (16–20px), sin bordes grises internos; sombra `0 1px 3px` + `border-radius: 12px`.
- Cantidad: cápsula `−` / número / `+` (ya iniciado); **ocultar spinners** del `input` o sustituir por `span` editable solo con botones + teclado en JS.
- Jerarquía: nombre 1rem/800; meta `SKU | Marca | Unidad` una línea; logística a pedido con ⏳.
- Reducir ruido: dto % en menú “⋯” o línea secundaria colapsada; quitar “Consumo stock” en vendedor o solo en hover.
- **Mantener:** `id="pos_row_{id}"`, `cantidad_{id}`, `subtotal_{id}`, `descuento_{id}`, clases `btn-ajustar-cantidad`, `btn-actualizar-item`.

**Archivos:** `premium_cart_cards.html`, `pos-premium-layout.css`, toques `pos.js` (formatoCLP, sin cambiar cálculos).

#### Fase C — Panel derecho monolítico (~½ sesión)

- Layout 3 zonas en desktop vendedor: **buscador full-width arriba** | **carrito scroll** | **dock fijo** ancho completo de columna derecha.
- “TOTAL A PAGAR” tipografía grande, aislada; botones **full-width** Emitir (F8) y Cotizar (F4); hover suave.
- Opcional: separar cliente RUT en franja fina bajo chrome (no card pesada).

**Archivos:** `punto_venta.html`, `pos-premium-layout.css` (grid `grid-template-columns` o flex columna derecha sticky).

#### Fase D — Pulido (opcional)

- Modo claro premium (actual) vs **modo oscuro** vendedor — decidir con cliente; no mezclar ambos sin guía.
- Command Deck: mismo lenguaje visual o dejar como “modo pro” separado.

### Qué NO hacer en este rediseño

- No reescribir flujo emitir/cobrar/compromiso/backend.
- No eliminar tabla en modo **admin** (solo vendedor).
- No cambiar IDs usados por `actualizarSubtotal`, `validarStockLinea`, `emitirValeBtn`.
- No commit/push a producción sin checkpoint tag y prueba en 1366×768 con rol Vendedor Prueba.

### Criterios de aceptación (checklist al implementar)

1. Rol vendedor: una sola barra de búsqueda visible; F2 y pistoleo OK.
2. Carrito sin `<table>`; borde izquierdo verde/azul por línea.
3. Agregar / +/- cantidad / dto / emitir vale — mismos tests smoke POS.
4. Sin scroll horizontal; descripción legible en 2 líneas max.
5. Ctrl+F5 tras deploy CSS con query `?v=...` bump.

### Decisiones para Mario al volver

1. ¿Aprobamos **Fase A+B+C** completa o solo A+B primero?
2. ¿Modo **claro** (actual design-system) u oscuro para vendedor?
3. ¿Descuento % visible en cada línea o oculto (solo supervisor)?
4. ¿Push a Render tras validar en LAN o más iteración local?

### Orden recomendado de trabajo

```
Checkpoint tag → Fase A (buscador) → validar → Fase B (carrito) → validar → Fase C (dock/grid) → pytest smoke POS → tag nuevo
```

---

## Piloto IA SD → Chilemat — ANÁLISIS PARA RETOMAR (2026-05-24)

**Estado:** estrategia acordada con Mario; **pendiente ejecución** esta noche.  
**Doc canónico:** `docs/planes/06-agentes-ia/MEMORY_PILOTO_IA_SD_CHILEMAT.md`  
**Regla Cursor:** `.cursor/rules/ia-piloto-chilemat.mdc`

**Principio:** no bajar ambición; IA debe **funcionar en piso** para capturar red Chilemat (SD = piloto #1).

### Diagnóstico rápido

| Capa | Realidad hoy | Gap |
|------|--------------|-----|
| Operador | SQL → alertas; Ollama enriquece en worker local | Sin Ollama/cron = no se siente IA |
| Guardián | KPIs + plantillas (`mensaje_ia`) | No muestra alertas Operador enriquecidas |
| Liz | Gemini FC; sin key → regex | POS se siente tonto |
| Ollama | Integrado; **PC sucursal**, no Render | Falta instalar + cron |

### Decisiones estratégicas

- **Licencia grande charo — Ollama $0 + Gemini ~$0–15/mes + OpenAI mini opcional ~$5–25/mes.
- **Ollama:** **SÍ** en PC SD — paso #1 (`qwen2.5:7b-instruct-q4_K_M`, cron scan+enrich cada 10–15 min).
- **Restructurar:** **mínimo** — encender stack; wiring Guardián ↔ alertas Operador; no CrewAI.

### Flujo héroe demo Chilemat

Operador detecta (cron) → Ollama explica → Guardián `/owner-mobile` + Liz en POS (Gemini).

### Fases

| Fase | Qué |
|------|-----|
| 0 | Ollama + cron + GEMINI en Render + alertas en Guardián |
| 1 | Piloto SD 1–2 semanas; ajustar umbrales |
| 2 | Replicar Chilemat (mini PC + Ollama por local) |
| 3 | HITL acciones (WA vale pendiente, aprobación dueño) |

### Inversión piloto

≤ $400 una vez (mini PC) + ≤ $40/mes cloud.

### Pendiente Mario (al retomar)

Prioridad: **(1) Dueño** Guardián+Operador *(recomendado)* | **(2) Mostrador** Liz | **(3) Ambos**.

### Archivos clave

`services/agente_operador_service.py`, `ollama_client.py`, `scripts/agente_operador_scan.py`, `scripts/agente_operador_enrich.py`, `owner_dashboard_service.py`, `/api/demo/chat`, `.env.example` § Operador.

---

## Dónde quedamos (retomar desde aquí)

**Última sesión:** **2026-05-27** — Chilemat VTEX en ERP local, cargas masivas/selectivas, Radar precios, POS ficha/total. Ver § «Sesión 2026-05-27» abajo.

**Git local:** `main` **2 commits** sin push → `6c00c08` (código) + `ee2d4fa` (datos CSV/RCV).

**Mañana (prioridad):**
1. `git push origin main` si Mario confirma.
2. Probar en piso: **Compras → Cargas Chilemat → ERP** (`/compras/chilemat/cargas`), explorador, vincular.
3. **Pendiente POS:** botones link/ficha en carrito premium siguen sin responder (revisar `pointer-events` / overlay `pos-checkout-dock`).
4. FE: token SII **ESTADO 10** sin resolver (`docs/soporte/TOKEN_SII_ESTADO_10_CHECKLIST.md`).

**Canónico histórico:** **`docs/memory.md`** § «Dónde quedamos» (2026-05-22).

**Cierre sesión 2026-05-22:** **D0 maestro Chilemat en Neon** (~4.899 SKU) · **RCV importado** (dedup folio) · **recepciones UI** en prod · **pausa hasta lunes D1** (piloto pistola TIENDA).

---

## Piloto IA SD → Chilemat (2026-05-24) — RETOMAR ESTA NOCHE

**Autorización Mario:** implementar todo el piloto IA; avanzar sin pedir OK en cada paso.  
**Restricción actual:** sin cobertura para pagar OpenAI/Gemini → **Ollama local primero**; Liz/visión cuando haya keys.

**Regla Cursor:** `.cursor/rules/ia-piloto-chilemat.mdc`

### Stack acordado (bajo costo)

| Pieza | Dónde corre | Costo |
|-------|-------------|-------|
| **Operador scan** (SQL) | Render cron `POST /api/agente/operador/dispatch-scan` | $0 |
| **Operador enrich** (texto IA) | PC SD + Ollama | $0 |
| **Guardián** | `/owner-mobile` — feed + mensaje IA | $0 |
| **Liz POS** | Render — requiere `GEMINI_API_KEY` (pendiente pago) | ~$0–15/mes |
| **OpenAI** | factura/foto — pendiente pago | opcional |

### Hecho en repo (2026-05-24, sesión autónoma)

- Cron **`POST /api/agente/operador/dispatch-scan`** (Bearer `AGENTE_OPERADOR_CRON_SECRET` o fallback cobranza).
- Guardián: **feed con `mensaje` + badge «IA local»** si Ollama enriqueció; **`mensaje_ia`** prioriza texto enrich.
- Helper **`cuerpo_alerta_para_ui()`** — oculta bloque `[Base operativa]` en móvil.
- Scripts: `agente_operador_ciclo.py`, `setup_ollama_sd.ps1`, `registrar_tarea_operador_windows.ps1`, `smoke_agente_operador_cron.py`.
- Tests: `tests/test_agente_operador_cron.py`.
- **Prod:** push `16a2dfe` → Render auto-deploy. Tag `checkpoint/ia-operador-prod-2026-05-24`.
- **Perf:** schema ensure al arrancar incluye agente+academy; `before_request` short-circuit ampliado; `render.yaml` `AGENTE_OLLAMA_ENABLED=0`.

### Post-deploy Render (manual dashboard)

- [ ] Confirmar deploy verde (~3–5 min tras push).
- [ ] `DATABASE_URL` usa host **pooler** Neon (`-pooler` en hostname).
- [ ] **No** definir `AGENTE_OPERADOR_SCAN_ON_LOAD=1` en Render.
- [ ] Cron cada 10 min: `POST /api/agente/operador/dispatch-scan` + Bearer (`COBRANZA_DISPATCH_CRON_SECRET` o dedicado).
- [ ] Ctrl+F5 en `/punto_venta` y `/owner-mobile` tras deploy.
- [ ] Neon: si cold start molesta → plan sin auto-suspend (Launch).

### Checklist noche (Mario — Ollama)

1. Instalar [Ollama](https://ollama.com) en PC SD.
2. `powershell -ExecutionPolicy Bypass -File scripts/setup_ollama_sd.ps1`
3. En `.env.local`: `DATABASE_URL` = misma Neon que Render.
4. Probar: `python scripts/agente_operador_ciclo.py`
5. Tarea cada 10 min: `scripts/registrar_tarea_operador_windows.ps1`
6. En Render: cron cada 10 min → `POST /api/agente/operador/dispatch-scan` con Bearer (mismo secreto que cobranza si no hay dedicado).
7. Abrir `/owner-mobile` — hbuilder — ver **Pulso operativo** con texto IA tras enrich.

### Pendiente (sin keys cloud)

- [ ] `GEMINI_API_KEY` en Render → Liz POS
- [ ] `OPENAI_API_KEY` → OCR factura / foto material (opcional demo)
- [ ] Validar 1 semana en piso SD (umbrales vale/descuadre)
- [ ] Paquete replicable Chilemat (mini PC + Ollama por local)

### Decisión original (prioridad)

**Dueño primero** — Guardián + Operador + Ollama (vendible a red Chilemat).

| Siguiente | Doc |
|-----------|-----|
| **D1 lunes** — 50–80 SKU enrolamiento | `docs/planes/01-entrega-santo-domingo/PAUSA_D1_PILOTO_PISTOLA.md` |
| RCV mensual / Pareto D2 | `docs/planes/01-entrega-santo-domingo/IMPORTAR_RCV_SII.md` |
| Checklist D0–D5 | `docs/planes/01-entrega-santo-domingo/CHECKLIST_INVENTARIO_SD_D0_D5.md` |

**No en Neon:** catálogo `SD-PRUEBA-*` (solo QA local). **IA facturas:** propuesta $305k aprobada; activar `OPENAI_API_KEY` en Render al firmar.

**FE Maullín:** CAF 33 id 66 (1–50); venta prueba #3040 `PENDIENTE_ENVIO`; token ESTADO 10 ⏸. **TV/caja prod:** `4ae0292`.

---

## Plan de cierre de módulos v3 (mayo 2026)

**Fuente de verdad:** `docs/ERP_MAESTRO.md` **§18** (matriz, sprints A–E, checklists POS/caja/FE/QA).

| Prioridad | Foco |
|-----------|------|
| Sprint A | POS + Caja + Stock + Bodega (validar checklist §18.1 en tienda) |
| Sprint D | FE **solo Factura (33)** en LhexIA; boletas **Multicaja/Klap** (`EXTERNO_MULTICAJA`). Ver § FE 2026-05-26 abajo |
| Sprint E | C360 + BI según roadmaps en `docs/` |

**Definición “módulo cerrado”:** flujo documentado + RBAC + test smoke/E2E mínimo + checklist §18.x firmado + deuda en §16 del maestro sin sorpresas.

### FE / SII — sesión 2026-05-26 (Santo Domingo)

**Política acordada**
- **Boletas (39):** Multicaja/Klap — LhexIA **no** envía al SII (`SII_FE_SOLO_FACTURA=1`, `EXTERNO_MULTICAJA` en cobro boleta).
- **Facturas (33):** solo LhexIA → CAF + firma `.pfx` + cola `/admin/facturacion/cola`.

**Maullín (certificación) — hecho**
- Emisor DTE **autorizado** (pantalla avance postulación).
- CAF boleta 39 timbrado 11–1010 (`FoliosSII805412039112026526843.xml`) — **no usar en ERP** (boletas por Multicaja).
- CAF factura 33 **reobtención** folios **1–50** (`FoliosSII80541203312026526959.xml`) → BD **caf id 66**, `usado_hasta=0`.
- Software portal: **BOLETA ELECTRONICA MULTICAJA** (coherente con boletas); factura ERP vía software mercado / LhexIA.

**ERP — hecho**
- Scripts: `cargar_caf_real.py`, `recorrelativizar_cola.py`, `archivar_cola_boletas_multicaja.py`, `limpiar_cola_dte_pruebas.py` (`--todo`).
- Cola DTE limpiada (97 ventas prueba); pantalla cola solo facturas 33.
- **Venta prueba #3040:** Factura, folio **1**, `PENDIENTE_ENVIO`, XML `V3040_T33_F1.xml`.

**Bloqueo actual**
- `fe_diagnostico_sii.py`: semilla OK, **token ESTADO 10** (Error Interno) — sin Track ID / sin `ENVIADO`.
- Soporte: `docs/soporte/TOKEN_SII_ESTADO_10_CHECKLIST.md`

**Próximo paso FE**
1. Destrabar token (portal SII / contador / firma getToken).
2. Reintentar venta **#3040** en cola → `ENVIADO` + Track ID.
3. Producción Palena: CAF 33 producción + `SII_AMBIENTE=produccion` (post certificación).

**No mezclar:** CAF de `www.sii.cl` (producción) con Maullín; timbraje nuevo 33 en Maullín si se agotan folios (reobtención o pedir **1** folio si máximo=1).

---

## Referencias rápidas

| Documento | Contenido |
|-----------|-----------|
| `docs/ERP_MAESTRO.md` | Documento maestro completo |
| `docs/FLUJOS_CRITICOS.md` | Diagramas Mermaid |
| `docs/MIGRACION_RENDER_NEON.md` | Deploy + sync datos |
| `docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md` | Plan v2 cerrado |
| `docs/roadmap_customer_360_ferreteria_2026.md` | C360 por fases |
| `docs/soporte/TOKEN_SII_ESTADO_10_CHECKLIST.md` | Token SII ESTADO 10 + reintentos cola |

---

---

## POS — Dock fijo 3 zonas + carrito AJAX (sesión 2026-05-16)

**Problema:** barra azul saltaba al agregar productos (vendedor).

**Hecho en local:** layout 3 zonas (`pos-vendedor-stage`), dock `pos-checkout-dock--stage` fijo abajo, `GET /api/pos/carrito-html`, `pos.js` sin reload en vendedor. Cache `20260521f`.

**Archivos:** `punto_venta.html`, `pos-premium-layout.css`, `pos.js`, `app.py`, `blueprints/pos.py`.

**Mañana:** Ctrl+F5, probar escaneo, commit si OK. Detalle completo en `docs/memory.md` (misma sección).

**Git:** ver sesión 2026-05-27 (commits hechos).

---

## Sesión 2026-05-27 — Chilemat · Radar · POS · datos (detalle)

**Transcripción chat:** `agent-transcripts/7ab37409-1a66-4b15-9680-363fb76eeafe.jsonl`

### Commits (local, sin push al cierre)

| Hash | Mensaje | Contenido |
|------|---------|-----------|
| `6c00c08` | `feat(chilemat-radar-pos): catálogo VTEX, cargas ERP, ficha en carrito y radar precios` | 71 archivos, +11 373 líneas — código, templates, services, tests, docs |
| `ee2d4fa` | `chore(data): CSV carga maestro/Radar y RCV compras SII 2025-2026` | 21 archivos — importación + 17 CSV RCV en `datos_rcv/` |

### Chilemat / catálogo VTEX → ERP

**Objetivo:** operar el universo Chilemat (~4 891 SKU) desde el ERP sin depender solo de scripts CLI.

**Modelos** (`app.py`): `ChilematCategoria`, `ChilematVtexProducto` (+ columnas `imagen_url`, `descripcion_web`, `descripcion_corta`), `producto_relacion` (cross-sell).

**Services nuevos:**
- `services/chilemat_catalogo_service.py` — sync API VTEX (`sync_categorias`, `sync_productos_vtex`, `--solo-faltantes`)
- `services/chilemat_catalogo_ui_service.py` — listados/filtros explorador
- `services/chilemat_vinculacion_service.py` — vincular/desvincular/auto + copiar imagen a `Producto`
- `services/chilemat_ficha_service.py` — ficha desde API VTEX (sin scrape); `imagen_url_para_producto_erp`; APIs carrito/POS/TV/Liz
- `services/chilemat_cargas_service.py` — cargas masivas/selectivas (misma lógica que CLI)
- `services/producto_relacion_service.py` — relaciones manuales + VTEX + histórico ventas

**Blueprint** `blueprints/chilemat_catalogo.py`:

| Ruta | Uso |
|------|-----|
| `/compras/chilemat/explorador` | Explorador visual staging VTEX |
| `/compras/chilemat/vincular` | Vinculación manual/auto ERP ↔ VTEX |
| `/compras/chilemat/cargas` | **Pantalla ERP cargas** (sync, carga, borrado, reset) |
| `/api/compras/chilemat/cargas/ejecutar` | POST JSON (preview / ejecutar) |
| `/api/compras/chilemat/ficha/...` | Ficha producto VTEX o ERP |

**Menú Compras:** Universo Chilemat · Vincular · **Cargas Chilemat → ERP** (atajo BI también).

**Scripts:**
- `scripts/sync_chilemat_catalogo.py`
- `scripts/reset_local_catalogo_a_chilemat.py` — reset total local (taxonomía + TRUNCATE productos + carga)
- `scripts/chilemat_cargas_local.py` — CLI (delega en `chilemat_cargas_service`)
- `scripts/seed_pos_chilemat_ejemplo.py` — demo `DEMO-CHM-BARNIZ`, VTEX `34891`, `producto_id` 2401

**Docs:** `CHILEMAT_CARGAS_LOCAL.md`, `LHEXIA_RADAR_PRECIO_EQUIPO.md` (estrategia radar/reunión equipo).

**Estado BD local post-reset** (`.env.local` → `ferreteria_local`):
- Productos ERP: **4891**
- `chilemat_vtex_producto`: **4891**, todos con `producto_id`
- Categorías ERP: **11**, subcategorías: **240**

**Cargas ERP — acciones:** `sync_staging`, `cargar_productos`, `borrar_productos`, `reset_taxonomia`, `reset_total` (confirmación texto `RESET TOTAL` + permiso admin inventario / gestionar usuarios).

### Radar precios

- `blueprints/precios_radar.py` + templates `precios_radar.html`, `precios_radar_dashboard.html`
- Services: `radar_precios_service.py`, `radar_precios_fetch.py`, `radar_precios_db.py`, `radar_maestro_csv.py`
- Tests: `tests/test_radar_precios.py`
- Sin APIs de pago; Ollama local opcional para enriquecimiento (doc equipo)

### POS / TV / Liz

**Corregido:** total a emitir **$0** con ítems en carrito (`_pos_venta_total_clp`, `pos.js`, `punto_venta.html`, `command_deck.html`).

**Integrado:**
- Miniatura + iconos link/ficha: `templates/pos/includes/cart_line_media.html`, `premium_cart_cards.html`
- `static/js/chilemat_ficha.js` — modal ficha + `bindPosCart` + delegación capture
- Live wall / TV cliente / Liz: imágenes vía `imagen_url_para_producto_erp` y cross-sell `producto_relacion`

**Pendiente conocido:** usuario reportó que **botones link/ficha en carrito POS no responden** tras varios fixes CSS/JS — retomar con DevTools (overlay dock, `z-index`, `pointer-events`).

### Facturación SII (soporte en mismo commit)

- Mejoras `facturacion_sii_soap.py`, `facturacion_electronica_service.py`
- Scripts: `fe_diagnostico_sii.py`, `fe_resolver_facturas.py`, `recorrelativizar_cola.py`, `cargar_caf_real.py`, `limpiar_cola_dte_pruebas.py`, etc.
- `docs/soporte/TOKEN_SII_ESTADO_10_CHECKLIST.md`
- **Bloqueo heredado:** token SII ESTADO 10 — venta prueba #3040 sigue `PENDIENTE_ENVIO`

### Tests añadidos/actualizados

`test_chilemat_cargas`, `test_chilemat_catalogo_explorer`, `test_chilemat_ficha`, `test_chilemat_vinculacion`, `test_match_factura_chilemat`, `test_producto_relacion_cross_sell`, `test_radar_precios`, `test_facturacion_sii_soap`, `test_facturacion_dte_e2e`

```bash
pytest tests/test_chilemat_cargas.py tests/test_chilemat_ficha.py tests/test_chilemat_vinculacion.py -q
```

### Datos (commit `ee2d4fa`)

**`CARGA DE DATOS/`:** `productos_importacion_final.csv` (actualizado), `productos_importacion_maestro_in.csv`, `radar_maestro_acumulado.csv`, `sd_prueba_productos_casuisticas.csv`

**`datos_rcv/`:** RCV compras `8054120-1`, meses `202501`–`202605` (17 CSV) — match facturas / tests.

**No commiteado:** `respaldos/`, logs `fe_*.txt`, `storage/dtes/caf/`, `Lista productos.xlsx`, probes sueltos.

### Utilidades

- `run.py`, `iniciar_servidor.bat`, `iniciar_servidor.ps1`
- `.env.example` — vars Chilemat/radar si aplica

### Estrategia acordada (Mario)

- **SD-1:** priorizar homologación operativa en piso (POS + inventario) antes de multi-tenant o agentes pesados.
- **Chilemat/red:** piloto post SD-1; hoy el foco fue **maestro local alineado a VTEX** + herramientas ERP para cargas selectivas.

---

## POS — Autorización descuentos (2026-05-18)

Detalle: `docs/memory.md` § «POS — Autorización de descuentos». **En prod** + SQL Neon. Tests: `pytest tests/test_pos_autorizacion_descuento.py -q`.

## Live Wall TV — recomendaciones (2026-05-20)

Detalle: `docs/memory.md` § «Live Wall / Experience Wall». Commit `4ae0292`. Tests: `pytest tests/test_pos_live_wall.py -m smoke -q`.

---

## POS carrito v3 — chips + descuento UX (2026-05-19)

**Resumen:** chips **`X T / Y B`** (stock) + **`TIENDA`/`BODEGA`** (retiro); menú **5/10/15/20** %; panel dto sin tapar línea de abajo. Archivos: `premium_cart_cards.html`, `pos-premium-layout.css`, `pos.js`. Cache `20260519c`.

**Detalle:** `docs/memory.md` § «POS carrito v3 — chips stock y descuento UX».

---

*Última actualización: **2026-05-27** — commits `6c00c08` + `ee2d4fa` (Chilemat/Radar/POS/datos). Push pendiente. Transcript: `7ab37409-1a66-4b15-9680-363fb76eeafe`.*
