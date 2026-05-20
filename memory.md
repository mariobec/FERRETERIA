# Memoria del proyecto (ERP ferretería / ventas)

Este archivo es la **memoria viva** del trabajo en el repo. El usuario y el agente lo usan para **recordar contexto entre sesiones**.

**Copia canónica (detalle completo):** `docs/memory.md` — mantener sincronizado al actualizar. Este archivo = índice + «Dónde quedamos» breve.

**Planes:** `docs/planes/README.md` · **Memory Grok:** `docs/planes/00-alineacion/MEMORY_GROK.md` · **Backlog post SD-1 (puntos + sorteo TV):** `docs/planes/02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md`

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
| 2026-05-20 | **POS pantalla vendedora (WIP local):** semáforo, filtros, compromiso entrega, layout sin sidebar, tarjetas carrito, `/pos` acceso directo. **Análisis rediseño profundo guardado abajo — pendiente aprobación usuario.** |

---

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

## Dónde quedamos (retomar desde aquí)

**Canónico:** detalle completo en **`docs/memory.md`** § «Dónde quedamos» y § «Live Wall / Experience Wall — TV cliente».

**PRIORIDAD (2026-05-20):** validar TV cliente en piso (recomendaciones + tarjetas nuevas). Cache TV **Ctrl+F5** `lhexia20260520reco2`.

**En producción (`4ae0292`):** recomendaciones TV coherentes; tarjetas CFM; cierre caja solo `Pagado`; sidebar scroll; tarjeta supervisor; SQL Neon autorización + rendimiento.

**Pendiente local:** carrito v3 chips (`20260519c`) si no en `main`; QA casuísticas sin commit.

**En `main` ya:** layout `5094d5d`, POS-4 `309f02f`, Live Wall TV `4ae0292`.

---

## Plan de cierre de módulos v3 (mayo 2026)

**Fuente de verdad:** `docs/ERP_MAESTRO.md` **§18** (matriz, sprints A–E, checklists POS/caja/FE/QA).

| Prioridad | Foco |
|-----------|------|
| Sprint A | POS + Caja + Stock + Bodega (validar checklist §18.1 en tienda) |
| Sprint D | FE SII 🟡 — envío SOAP real pendiente |
| Sprint E | C360 + BI según roadmaps en `docs/` |

**Definición “módulo cerrado”:** flujo documentado + RBAC + test smoke/E2E mínimo + checklist §18.x firmado + deuda en §16 del maestro sin sorpresas.

---

## Referencias rápidas

| Documento | Contenido |
|-----------|-----------|
| `docs/ERP_MAESTRO.md` | Documento maestro completo |
| `docs/FLUJOS_CRITICOS.md` | Diagramas Mermaid |
| `docs/MIGRACION_RENDER_NEON.md` | Deploy + sync datos |
| `docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md` | Plan v2 cerrado |
| `docs/roadmap_customer_360_ferreteria_2026.md` | C360 por fases |

---

---

## POS — Dock fijo 3 zonas + carrito AJAX (sesión 2026-05-16)

**Problema:** barra azul saltaba al agregar productos (vendedor).

**Hecho en local:** layout 3 zonas (`pos-vendedor-stage`), dock `pos-checkout-dock--stage` fijo abajo, `GET /api/pos/carrito-html`, `pos.js` sin reload en vendedor. Cache `20260521f`.

**Archivos:** `punto_venta.html`, `pos-premium-layout.css`, `pos.js`, `app.py`, `blueprints/pos.py`.

**Mañana:** Ctrl+F5, probar escaneo, commit si OK. Detalle completo en `docs/memory.md` (misma sección).

**Git:** `main` ahead 2; cambios sin commit al cierre del día.

---

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

*Última actualización: 2026-05-20 — Sincronizado con `docs/memory.md` (TV prod `4ae0292`).*
