# Memoria del proyecto (ERP ferretería / ventas)

Este archivo es la **memoria viva** del trabajo en el repo. El usuario y el agente lo usan para **recordar contexto entre sesiones**.

**Copia en documentación:** `docs/memory.md` (mismo contenido; mantener sincronizado al actualizar).

**Carpeta planes:** `docs/planes/README.md` — toda la planificación ordenada por carpetas `00`–`07`.  
**Alineación Mario · Grok · Cursor:** `docs/planes/00-alineacion/MEMORY_GROK.md` — brief compartido. Actualizar junto con este archivo cuando cambie la prioridad global.

## Cómo usarlo

- **Al arrancar una sesión en Cursor:** `@docs/MEMORY_GROK.md` + `@memory.md` (o *“lee memory.md y sigue desde ahí”*).
- **Al arrancar sesión con Grok:** pegar `docs/MEMORY_GROK.md` o el prompt del §13 de ese archivo.
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
| 2026-05-22 | **Inventario SD D0–D5:** `homologar_productos_excel.py --maestro` (`codigo_chilemat`, `PEND-*`, stock 0); checklist `CHECKLIST_INVENTARIO_SD_D0_D5.md`. |
| 2026-05-22 | **Operación empresa:** Admin → Empresa — un local vs red (`operacion_un_local`, `operacion_sucursales_red_n`); `empresa_operacion_service.py`; Guardián lee JSON. Docs: SD ≠ 3 sucursales en piso. |
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
| 2026-05-19 | **POS carrito v3 UX (sesión Cursor):** chips stock unificados `X T / Y B`; chips fuera del precio; descuento rápido 5/10/15/20 + Enter; menú dto hacia arriba + z-index. Ver § «POS carrito v3 — chips y descuento UX». Cache `20260519c`. **Local sin commit.** |
| 2026-05-19 | **Revisión memory.md:** `docs/memory.md` = canónico; raíz desactualizada; prioridad «dock 3 zonas» ya superseded por `5094d5d`. |

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

#### Fase A — Un solo buscador (máximo impacto visual, ~1 sesión)

- Unificar `#posBarcodeWedge` + `#posBuscarManual` en **un solo hero** `#posBusquedaUnificada` (solo si `pos_layout_fullwidth`).
- Comportamiento: pistoleo y texto en el mismo input; **F2** focus; dropdown semáforo debajo (`#pos-search-suggestions` sin mover lógica JS).
- Retirar labels duplicados, caja “BÚSQUEDA MANUAL” morada, segundo `form-control` grande.
- Mantener filtros Operativo/Tienda/Catálogo como **pills** compactos en la misma barra (no segundo panel).

**Archivos:** `punto_venta.html` (rama vendedor), `pos-premium-layout.css`, ajustes menores `pos.js` (focus F2 al input unificado; wedge sigue llamando misma API).

#### Fase B — Carrito “desmaterializado” v2 (~1 sesión)

- Renombrar contenedor a `#contenedor-carrito` (`pos-cart-list` alias).
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

**Prioridad código (post validación piso 2026-05-21):** **SD-1 checklist piso firmado** ✅ · siguiente operativo: **un establecimiento** — enrolamiento por **almacenes** (Tienda + Bodega) + capacitación POS/caja (SD-1.3). **Multi-sucursal** = opción Admin → Empresa (`operacion_un_local`) + CRUD sucursales SD-2, no “3 locales” en SD. **PWA Guardián** en prod. **PLAT-1.2** offline solo si hay dolor de red. **FE Maullín congelado** (Form. 3230).

### Carril activo — SD-1 piso (operación + QA manual)

| Orden | Qué | Evidencia / herramienta |
|-------|-----|-------------------------|
| 1 | **Inventario** — enrolamiento + salud | `/inventario/enrolamiento`, `/inventario/salud` |
| 2 | **POS + caja** — flujo vale completo | `docs/CASUISTICAS_VENTAS_QA.md` + `python scripts/seed_ventas_casuisticas_qa.py --clean --con-ventas-ejemplo` |
| 3 | **TV + cierre** — prod ya desplegado | Ctrl+F5 TV cache `lhexia20260520reco2`; arqueo solo `Pagado` |

**Cierre SD-1:** conteo por **almacén** del establecimiento + ≥1 vale → cobro sin bloqueos críticos (`SANTO_DOMINGO_ENTREGA.md`).

### Checklist SD-1 piso — ejecución automática (2026-05-21 sesión Cursor)

| # | Ítem | Automático | Resultado |
|---|------|------------|-----------|
| 1 | Enrolamiento | HTTP pytest | ✅ `test_inventario_enrolamiento` |
| 2 | Salud inventario | HTTP pytest | ✅ `test_inventario_salud` |
| 3 | Seed QA | script | ✅ `--clean --con-ventas-ejemplo` → vales **#2584** (Tienda), **#2585** (Bodega) |
| 4 | CAS-V01…V05 | pytest | ✅ 6/6 + suite completa **11/11** casuísticas |
| 5 | TV + cierre | pytest smoke | ✅ `test_pos_live_wall` 13 pass · `test_cierre_caja_modo` 3/3 |

**Validación piso Mario (2026-05-21):** checklist SD-1 §8 **completo** — enrolamiento, salud, cobro vales **#2584** (Tienda/obra) y **#2585** (Bodega), TV + cierre caja sin bloqueos.

### En repo `main` local (commits recientes — 2026-05-20/21)

| Commit | Contenido |
|--------|-----------|
| `4ae0292` | **Prod referencia** — TV recomendaciones, tarjetas CFM, cierre caja, cross-sell |
| `79220c9` | Casuísticas QA TEST-CAS (11 tests smoke) |
| `d9a9594` | Política IVA `desglosar_iva_clp`, PrcItem SII, `FALLO_MATEMATICO` |
| `dbe03ed` | **TEC-OFFLINE Fase 0** — ADR, contrato API v1, `iva-chile.js`, tag `checkpoint/offline-design-2026-05-20` |

**TV/caja en prod (`4ae0292`):** validar recomendaciones + cierre; anti-autofill monto contado.

**SQL Neon aplicado:** `2026_05_18_pos_autorizacion_descuento.sql`, `2026_05_21_rendimiento_sd1_postgresql.sql`.

### En pausa (no atacar código)

| Tema | Motivo |
|------|--------|
| **FE Maullín** | Form. 3230 folio **77326378627** — *Recepcionada* (§ FE abajo). Sin `emitir-prueba` ni reintentos background. |
| **TEC-OFFLINE F1+** | Fase 0 diseño lista; implementar tras SD-1 o caja piloto offline |
| **FE SOAP/TED sin commit** | Archivos locales `??` — commit en rama aparte cuando retome FE |

### Pendiente local (sin commit, no mezclar con SD-1)

Scaffold `adapters/`/`domain/`, logos 3D, scripts FE diagnóstico, `facturacion_sii_soap.py` / TED.

### Backlog post SD-1

Fotos placeholder TV; `PLAN_RENDIMIENTO_BD_SD1` índices; Fase 4 cuadratura DTE panel; fidelización TV (`PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md`).

**No hacer aún:** Alembic masivo, multi-tenant en queries prod, refactor big-bang `app.py`.

**Comandos útiles (SD-1):**
```bash
python scripts/seed_ventas_casuisticas_qa.py --clean --con-ventas-ejemplo
pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -q
pytest tests/test_pos_live_wall.py -m smoke -q
pytest tests/test_iva_chile.py tests/test_iva_chile_js_parity.py -q
python scripts/apply_sql_neon.py sql/ARCHIVO.sql
```

**Planes offline:** `docs/planes/04-tecnico/ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md`, `ADR_OFFLINE_FIRST.md`.

---

## Plan de cierre de módulos v3 (mayo 2026)

**Fuente de verdad:** `docs/ERP_MAESTRO.md` **§18** (matriz, sprints A–E, checklists POS/caja/FE/QA).

| Prioridad | Foco |
|-----------|------|
| Sprint A | POS + Caja + Stock + Bodega (validar checklist §18.1 en tienda) |
| Sprint D | FE SII ⏸ — código listo; esperar **timbraje SII** + prueba manual Track ID |
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

**Problema:** la barra azul (`pos-checkout-dock`) “saltaba” al agregar productos en pantalla vendedora.

**Causas identificadas:**
- `window.location.reload()` tras escanear/alta rápida en `pos.js`.
- Dock dentro de `pos-premium-col--cart` con grid `1fr auto` (no fijo al viewport).
- `position: sticky` en CSS inline de `punto_venta.html`.
- Clase `pos-ui-settling` ocultaba el dock 1–2 frames al cargar.

**Implementado (local, sin commit/push al cierre del día):**

| Zona | Contenido |
|------|-----------|
| 1 — Izquierda | RUT, crédito, búsqueda unificada, historial (`pos-premium-col--tools`, scroll propio) |
| 2 — Derecha | Carrito tarjetas (`#posCartHost` / `premium_cart_cards.html`, scroll solo ahí) |
| 3 — Abajo | Dock azul fijo ancho completo (`pos-checkout-dock--stage`), **fuera** de la columna carrito, dentro de `pos-vendedor-stage` |

**Archivos tocados:**
- `templates/punto_venta.html` — wrapper `pos-vendedor-stage`, dock después de `pos-premium-shell`, `id="posCartHost"`, cache `20260521f`.
- `static/css/pos-premium-layout.css` — layout `100vh`, flex 3 zonas, dock `--stage` fijo.
- `static/js/pos.js` — `posRefrescarCarritoVendedor()`, `posBindCartLineHandlers()`, sin reload en vendedor si AJAX OK.
- `app.py` + `blueprints/pos.py` — `GET /api/pos/carrito-html` → `api_pos_carrito_html`.

**Otro trabajo en la misma rama (sesiones previas, sin push):** créditos en POS (chrome Cartola/Boucher), fixes login/sesión (`SESSION_COOKIE_SECURE`, `remember=True`), `render.yaml`, tests crédito en `test_routes_criticas.py`.

**Pendiente mañana (validación Mario):**
1. Ctrl+F5 en `/punto_venta` o `/pos` como vendedor.
2. Agregar 3–5 productos: dock quieto, solo scroll en carrito.
3. Si falla AJAX carrito → fallback reload (revisar consola red `/api/pos/carrito-html`).
4. Decidir **commit + tag** y si push a Render.

**Checkpoint git sugerido al commitear:**
```bash
git tag checkpoint/pos-dock-3zonas-2026-05-16
```

**Estado git al 2026-05-16:** `main` ahead 2 commits de `origin/main`; muchos archivos modificados sin commit (incl. dock 3 zonas).

---

## POS vendedora — PAUSA para retomar (2026-05-17) — HISTÓRICO

> **Supersedido (2026-05-25):** Fase 3 cerrada y validada — ver sección «Relayout dock + búsqueda alta» y `docs/POS_ALINEACION_CURSOR_GROK.md` §13.

**Mensaje Mario (cierre sesión):** *“No es lo que te pedí”* — revisará al regreso. **No commitear** hasta que valide layout y alcance.

**Conversación:** transcript Cursor `2bee32c7-0747-4320-9f77-33b17db4c0d0` (chat POS vendedora / mockup Paint).

### Qué pidió Mario (mockup con recuadros verdes — captura 2026-05-17)

Referencia visual: `assets/.../Captura_de_pantalla_2026-05-17_133426-401f5c61-1532-485d-be15-15ebf9a271c3.png`

1. **Buscador ancho arriba** — franja superior que cruza casi todo el ancho (no solo columna izquierda estrecha).
2. **Abajo, dos columnas alineadas:**
   - **Izquierda:** tarjeta cliente (RUT, crédito) + asistente de búsqueda / resultados, **misma columna**, bien alineados.
   - **Derecha:** carrito + dock (total, emitir vale).
3. **Retiro por línea** — que no se sienta “brusco” al cambiar el `<select>`.
4. **Stock coherente** — búsqueda muestra tienda/bodega; al agregar no debe decir “sin stock” si solo hay en bodega; chip carrito no debe mostrar solo `0 UNIDAD` cuando hay bodega.

**Importante:** La implementación del agente **no cumplió** la intención visual de Mario; hay que **releer el mockup con él** antes de más CSS/HTML.

### Qué se implementó en esta sesión (local, sin commit pedido)

| Tema | Archivos | Notas |
|------|----------|--------|
| Layout “Fase 3” intentada | `punto_venta.html`, `pos-premium-layout.css` | `{% include unified_search %}` movido a `.pos-vendedor-search-stage` **arriba** del grid — Mario: **no es lo pedido** |
| Stock bodega al agregar | `app.py` `_pos_puede_sumar_unidad` | Si tienda no alcanza pero bodega sí → permite agregar |
| Chip stock carrito | `premium_cart_cards.html`, `stock_bodega` en `_pos_pagina_context` | Formato `0 T / N B` si solo bodega |
| Retiro suave | `pos.js`, CSS | Clase `pos-retiro-select--saving` (sin `disabled`) |
| Portal búsqueda | `pos.js` `posMontarPanelBusqueda` | Ancho desde `.pos-vendedor-search-stage` |
| Cache bust | `punto_venta.html` | `20260524a` |

**Tags git existentes (sesiones anteriores):** `checkpoint/pos-busqueda-hero-2026-05-17`, `checkpoint/pos-carrito-v3-2026-05-17`.

**Doc vivo:** `docs/POS_ALINEACION_CURSOR_GROK.md`, `docs/POS_PANTALLA_VENDEDORA_AUDITORIA.md`.

### Fases acordadas (estado)

| Fase | Estado |
|------|--------|
| 1 — Hero búsqueda | ✅ (Mario aprobó antes) |
| 2 — Carrito v3 | ✅ (pendiente validación Mario) |
| 3 — Layout mockup Paint | ✅ Validado 2026-05-25 (`5094d5d`) |
| 4 — Pulido F8/toasts | ✅ 2026-05-17 · cache `20260525f` |

### Bugs / temas técnicos ya identificados (retomar)

- `_pos_puede_sumar_unidad` solo tienda → **parche bodega aplicado** (verificar en UI).
- Retiro: API `POST /api/pos/retiro-linea` + delegación en `pos.js` — funciona pero UX afinar.
- Seed pruebas semáforo: `python scripts/seed_pos_semaforo_pruebas.py` + `pruebas/pos_semaforo/productos.json` (no ejecutado en sesión).

### Primer paso al regreso

1. Mario abre POS con **Ctrl+F5** (`20260524a`) y explica **qué difiere** del mockup (captura verde).
2. Acordar layout exacto (¿buscador solo arriba vs también en columna izq.? ¿portal de sugerencias?).
3. Solo entonces ajustar `punto_venta.html` + CSS; opcional checkpoint `checkpoint/pos-layout-mockup-YYYY-MM-DD`.
4. Validar stock bodega + retiro con productos `POS-SEM-*`.

---

### Retomo 2026-05-17 (Cursor)

**Hipótesis del error anterior:** se movió el buscador a `.pos-vendedor-search-stage` **arriba del grid**; el mockup Paint agrupa **cliente + búsqueda en la misma columna izquierda** (más ancha), no una franja superior separada.

**Cambio aplicado (cache `20260524b`):**
- Búsqueda de vuelta en `pos-premium-col--tools` (debajo tarjeta RUT/TV).
- Grid vendedora: **46% / 54%** (antes 38/62).
- Portal de sugerencias anclado otra vez a columna tools.
- Se mantienen parches stock bodega + retiro suave.

**Validar con Mario:** Ctrl+F5, comparar con captura verde.

---

### Relayout dock + búsqueda alta (2026-05-25) — CERRADO ✅

- **Iteraciones:** dock izquierda con nombre → total a la derecha → nombre+crédito dentro del bloque azul (aprobado).
- **Grok:** CSS `78vh` panel, grid `calc(100vh - 11.5rem)`, dock compacto.
- **Mario:** «excelente!!» — layout Fase 3 validado.
- **Commit:** `5094d5d` en `main` (12 archivos POS + docs).
- **Cache:** `20260525e` · **Revert:** `docs/POS_REVERT_DOCK_BUSQUEDA.md`.
- **Detalle técnico:** `docs/POS_ALINEACION_CURSOR_GROK.md` §13.

---

---

## Daily equipo — 2026-05-18

### Bloque único (copiar a Grok)

```markdown
## Daily — 2026-05-18

**Ayer logré:**
- Grok Project LhexIA: prompt único + confirmación 5 bullets alineada
- Repo: carpeta `docs/planes/` (00–07), portales producto/SD, MEMORY_GROK
- Commits en `main`: `309f02f` (planes + POS-4 + core post-cobro), `c423864` (Grok Project), `30aa8c6` (ritmo async + GROK_PROMPT_UNICO)
- Modelo Daily / Weekly / Sprint 14d adoptado (EQUIPO_RITMO_ASYNC.md)

**Hoy voy a:**
- [SD-1.1] Mario: validar 3 almacenes + permisos `enrolamiento_inventario`; backup Neon; iniciar `/inventario/enrolamiento`
- [SD-1.2] Mario: piloto POS en sucursal — Ctrl+F5, búsqueda 2+ letras, filtro **Catálogo** si Operativo vacío, vale → caja
- [Cursor] Disponible hotfix SD-1; smoke tests si Mario pide «corre pytest smoke»
- [Grok] Checklist operativo D0 inventario o user stories POS piso (si Mario lo pide en Project)

**Bloqueos / Necesito ayuda con:**
- **Operación (Mario):** confirmar IDs/nombres de 3 almacenes activos y usuarios con permiso enrolamiento
- **Piso:** primera toma inventario y primer vale completo aún por validar (criterio cierre SD-1)
- **Técnico menor:** `render.yaml` + `scripts/sync_local_neon_render.py` con cambios locales sin commit (no bloquea SD-1)

**Notas importantes:**
- **POS-4** ya en producción vía `main` (`309f02f`): cache `20260525f`, búsqueda ≥2 chars, F8 `posEmitirValeAtajo`
- Deploy Render: auto-deploy en push — verificar www.lhexia.cl tras Ctrl+F5 en caja
- No iniciar LX-1 / IA prod / refactor masivo hasta cerrar SD-1

**Eje:** SD-1
```

---

### Detalle por rol (repo)

**Mario**
- **Ayer:** Grok Project OK; documentación planes en GitHub.
- **Hoy:** SD-1.1 inventario + SD-1.2 POS piso (ver checklist `CLIENTE_SANTO_DOMINGO.md`).
- **Bloqueos:** almacenes/permisos en operación; validación flujo real en sucursal.

**Cursor**
- **Ayer/logrado:** `docs/planes/`; commits `309f02f`, `c423864`, `30aa8c6` pusheados; POS-4 en `main`.
- **Hoy (completado sesión):** Daily documentado; pendiente SD-1 = hotfix bajo demanda, pytest smoke bajo pedido.
- **Sin commit pendiente crítico** para SD-1. Local sin commitear: `render.yaml`, `sync_local_neon_render.py` (sync Neon).

**Grok**
- Ritmo async documentado; apoyo planificación/checklists SD-1 en Project.

**Estado técnico rápido (Cursor)**

| Ítem | Estado |
|------|--------|
| POS-4 en `main` | ✅ `309f02f` (`20260525f`, búsqueda 2+, F8) |
| Inventario enrolamiento/salud | ✅ código listo — operación SD-1.1 |
| Tests smoke | No corridos hoy — ejecutar antes de hotfix si hay duda |
| `main` vs origin | ✅ al día (`30aa8c6`) |

**Eje:** SD-1

---

## Índice de planes (2026-05-17)

**Planes:** `docs/planes/README.md`  
**Alineación 3:** `docs/planes/00-alineacion/MEMORY_GROK.md`  
**Producto:** `docs/planes/02-producto-lhexia/LHEXIA_PRODUCTO.md`  
**Santo Domingo:** `docs/planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md`  
**Índice:** `docs/planes/00-alineacion/PLAN_INDICE_LHEXIA.md`

**Agentes IA negocio (2026-05-17):** `docs/planes/06-agentes-ia/PLAN_AGENTES_IA_v1.md` — IA-0…IA-3 (ferretería 24/7). Prod post SD-1.

**Agentes Meta desarrollo (2026-05-17):** `docs/planes/07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md` — META-1 MVP: ARCH, QA, DOC, PO, ORCH (3 semanas).

**Ritmo async (2026-05-18):** `docs/planes/00-alineacion/EQUIPO_RITMO_ASYNC.md` — Daily / Weekly / Sprint 14d (Mario · Grok · Cursor).

**Optimización app.py (2026-05-17):** Vista única en `docs/planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md` — TEC-1A…4 ✅, CORE-1.2…1.4 ✅, CORE-1.5 ⏳, `app.py` ~20.5k líneas, `core/` ~974 líneas.

| Prioridad | Fase | Estado |
|-----------|------|--------|
| **Ahora** | **SD-1** Santo Domingo POS + inventario | 🟡 En curso |
| Cerrado | POS-1…4 UI vendedor | ✅ POS-4 en `main` (`309f02f`) — validar piso |
| Cerrado | TEC-1A…4 estabilidad v2 | ✅ |
| Paralelo | LX-0 producto (docs) | 🟡 |
| Después | LX-1 multi-tenant | ⏳ |

- **Regla Cursor:** `.cursor/rules/lhexia-producto.mdc`

---

### POS vendedor — plan operativo CERRADO (Fases 1–4) 2026-05-17

- Fase 4: F8 `posEmitirValeAtajo`, búsqueda 2+ letras, meta filtro stock, cache `20260525f`.
- Doc: `docs/POS_ALINEACION_CURSOR_GROK.md` §14.

---

---

## POS — Autorización de descuentos (sesión chat 2026-05-18, transcript `2bee32c7-0747-4320-9f77-33b17db4c0d0`)

**Estado:** en **`main`/producción** (servicio + SQL Neon aplicado 2026-05-20). Impresión tarjeta vía iframe en `admin_pos_autorizacion.html` + `static/css/pos-supervisor-card.css` (commit `4ae0292`). Tests: `pytest tests/test_pos_autorizacion_descuento.py` → 4 passed.

### Reglas de negocio acordadas

1. **Todo descuento > 0** en POS exige autorización de **supervisor** (tarjeta código `LHX-SUP-…` + **PIN 4 dígitos** si % > umbral empresa, default **20%**).
2. **Excepción:** productos marcados en catálogo como **preautorizados** (`pos_descuento_preautorizado` + tope `pos_descuento_preautorizado_pct`) — sin tarjeta hasta ese tope.
3. **Futuro (no implementado):** autorización por **comportamiento del cliente** (historial compras/pagos). Flag config `pos_descuento_autorizacion_por_cliente: "0"` en `_config_empresa_default()`.
4. El permiso `autorizar_descuento_pos` identifica **quién puede autorizar** (tarjeta/PIN), **no** exime al vendedor en caja (incl. usuario Admin — fix sesión 2026-05-18).

### Archivos clave

| Archivo | Rol |
|---------|-----|
| `services/pos_autorizacion_descuento_service.py` | Token tarjeta, PIN, umbral, `requiere_autorizacion_supervisor_pos`, `detalle_descuento_autorizacion_valida`, producto preauth |
| `sql/2026_05_18_pos_autorizacion_descuento.sql` | DDL: pin usuario, tabla tarjetas, columnas detalle_ventas, columnas productos preauth |
| `app.py` | Modelos `UsuarioTarjetaAutorizacion`, columnas `DetalleVenta`/`Producto`; `_validar_autorizacion_descuento_pos`, `actualizar_item`, `finalizar_venta` (bloqueo si descuento sin traza), ruta `/admin/pos-autorizacion-descuentos` |
| `templates/admin_pos_autorizacion.html` | Umbral %, supervisores (PIN/tarjeta), buscar producto preautorizado |
| `templates/punto_venta.html` | Modal `#modalAutorizarDescuentoPos`; `descuento_libre: false` en config POS |
| `static/js/pos.js` | Modal al cambiar % (blur/`change`) o ✓; bloqueo emitir vale; `posHayDescuentosSinGuardarOAutorizar` |
| `templates/ticket_vale.html` | Línea: `Dto X% · Aut: Nombre` si hay supervisor |
| `tests/test_pos_autorizacion_descuento.py` | Smoke tarjeta+PIN + reglas preauth |

### Flujo operativo (local)

1. Admin → **POS autorización descuentos** (`/admin/pos-autorizacion-descuentos`): generar tarjeta (código una vez + JsBarcode), PIN 4 dígitos, umbral %.
2. En POS vendedor: poner **Dto %** → salir del campo o **✓** → modal tarjeta (+ PIN si > umbral) → guardar línea.
3. **Emitir vale** solo si cada línea con descuento tiene traza en BD (`descuento_autorizado_metodo`: `tarjeta`, `tarjeta_pin`, `password`, o `producto_preautorizado`).
4. **Ctrl+F5** tras cambios en `pos.js`.

### UX stock en carrito (misma sesión)

- Mensaje carrito vendedor: **«Excede stock en tienda»** o **«Excede stock en bodega»** según retiro por línea (`posLimiteStockLinea` en `pos.js`; `data-stock-bodega` en tarjetas). **Bug corregido:** retiro **Bodega** ya no compara contra stock tienda (0 T / 3 B dejaba emitir en gris). `actualizar_item` valida bodega si retiro=Bodega.
- Líneas **a pedido** no aplican validación de stock mostrador.

### Problemas detectados y corregidos en chat

| Síntoma | Causa | Fix |
|---------|--------|-----|
| No pedía clave/PIN | Admin tenía bypass por `autorizar_descuento_pos` / `descuento_libre: true` | Siempre pedir tarjeta en POS; `descuento_libre: false` |
| Emitía vale igual | `finalizar_venta` no validaba autorización; descuento solo en pantalla | Validación servidor + bloqueo JS al emitir |
| Modal solo al ✓ | Descuento no persistía al salir del campo | `change` en `.descuento-input` abre flujo autorización |

### Pendiente / no mezclar en SD-1

- Validar en piso tarjeta impresa y flujo PIN con supervisores reales.
- Hub POS → pantalla vendedora (`_pos_url_destino`, `?layout=vendedor`) — verificar en sucursal.

### Comandos útiles

```bash
pytest tests/test_pos_autorizacion_descuento.py -q
python app.py   # local + Ctrl+F5 en /punto_venta?layout=vendedor
```

---

## POS carrito v3 — chips stock y descuento UX (sesión 2026-05-19)

**Estado:** implementado en **local**; sin commit/push al cierre de sesión. **Cache bust:** `pos-cart-premium-20260519c` / `pos-premium-layout-20260519c` en `punto_venta.html`.

### Chips en cada línea del carrito (congruencia)

Cada tarjeta muestra **dos badges** distintos:

| Badge | Ejemplo | Significado |
|-------|---------|-------------|
| Verde/amarillo con cajita | `200 T / 0 B` | Stock **Tienda (T)** / **Bodega (B)** en unidades de venta |
| Amarillo texto | `TIENDA`, `BODEGA` | **Punto de retiro** de la línea (`punto_retiro_linea`) |

**Antes (confuso):** si había stock en tienda → `200 CAJA`; si solo bodega → `0 T / 3 B`. Mezclaba unidad de venta con códigos de almacén.

**Ahora:** siempre `X T / Y B`. Tooltip: tienda, bodega y unidad (`CAJA`, etc.). Clase `pos-cart-card__chip--stock-bodega` si tienda=0 y bodega>0.

**Layout:** `.pos-cart-card__status-corner` pasó de `position:absolute` (esquina tarjeta, tapaba el **$**) a la columna **`pos-cart-card__commerce`**, arriba de cantidad/precio.

### Menú descuento % (UX vendedor)

| Mejora | Detalle |
|--------|---------|
| Botones rápidos | **5 · 10 · 15 · 20** en panel `⋯` — aplican % y disparan guardado (+ modal supervisor si aplica) |
| Foco | Al abrir `⋯`, foco en input y **select all**; si 0 % el campo va vacío con `placeholder="0"` |
| Enter | Guarda línea (equivale a ✓); cierra menú si guardó OK |
| Superposición | Panel abre **hacia arriba** (`bottom: calc(100% + …)`); tarjeta abierta `pos-cart-card--dto-open` + `z-index: 40` para no quedar bajo la línea de abajo |

### Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `templates/pos/includes/premium_cart_cards.html` | Chips T/B; panel dto con quick buttons |
| `static/css/pos-premium-layout.css` | Chips en commerce; `.pos-dto-quick*`; z-index menú abierto |
| `static/js/pos.js` | `posFocusDescuentoInput`, `posCerrarMenuDto`, `posAplicarDescuentoRapido`; Enter; clase `--dto-open`; `actualizarItem` retorna bool |
| `templates/punto_venta.html` | Query cache `20260519c` |

### Validación sugerida

1. Ctrl+F5 `/punto_venta` o `/pos` rol vendedor.
2. Dos productos: uno con stock tienda, otro solo bodega — verificar chips `T/B` + retiro.
3. Abrir `⋯` en línea del medio del carrito — botones 5–20 clicables sin tapar producto de abajo.
4. Descuento > umbral → modal tarjeta/PIN; emitir vale bloqueado si falta autorización.

### Relación con autorización descuentos (2026-05-18)

Los botones rápidos llaman `posIntentarGuardarLineaConAutorizacionDesc` — misma regla: todo dto > 0 exige supervisor salvo producto preautorizado. Ver § «POS — Autorización de descuentos» arriba.

---

---

## Live Wall / Experience Wall — TV cliente (sesión 2026-05-19 / 2026-05-20)

**Estado:** en **`main`/producción** — commit `4ae0292` (2026-05-20). Prod: [www.lhexia.cl](https://www.lhexia.cl).

### Rutas y archivos

| Ruta / archivo | Rol |
|----------------|-----|
| GET `/pos/live-wall/cliente`, `/pos/experience-wall?token=` | HTML TV (CFM v2) |
| GET `/api/pos/live-wall/snapshot` | JSON carrito + `recomendaciones` + `cliente_vitrina` |
| `templates/pos_live_wall_cliente.html` | Layout 50/50 carrito \| recomendaciones |
| `static/js/pos-experience-wall.js` | Poll snapshot, `renderCfmRecommendations`, anti-parpadeo (`lastRecoPaintKey`) |
| `static/css/pos-experience-wall-cfm.css` | Grid 2×2 tarjetas, tipografía TV |
| `app.py` | `_pos_live_wall_recomendaciones_tv`, perfiles `_POS_TV_PERFIL_*`, helpers scoring |
| `data/cross_sell_associations.json` | Reglas POS vendedor + coherencia obra/fijación |
| `tests/test_pos_live_wall.py` | 17 tests smoke (incl. `test_recomendaciones_tv_solo_clavo_coherente`) |

### Lógica de recomendaciones (TV)

1. **Perfil** según carrito: `fijacion` (clavos, tornillos, escuadras…), `obra_pesada`, `pintura`, `pvc`, `madera`, `general`.
2. **Exclusión** herramientas eléctricas caras (`taladro`, `rotomartill`, `amoladora`, …) salvo obra pesada o ticket alto con materiales construcción.
3. **Tope precio** por ítem según ticket (bajo &lt; $28k → complementos económicos).
4. **Motivos cortos** con ancla dinámica (`los clavos`, `los tornillos`, …).
5. **Cross-sell JSON** solo refuerza perfiles obra/pintura/PVC (no pisa fijación).
6. Regla `obra_arena_herramientas`: triggers `saco cement`, `bolsa cement` — **no** activa con «bolsa 1kg» de clavos.

### UI tarjetas (2026-05-20)

- Estructura: imagen → nombre (18–20px bold) → motivo (italic gris) → pie precio `#22c55e` + botón «Pida en mostrador».
- Hover: `scale(1.05)` + glow verde.
- Cache assets TV: `?v=lhexia20260520reco2`.

### Cierre de caja (misma entrega prod)

- `_venta_cuenta_en_cuadre_caja()`: solo estado **`Pagado`** suma al arqueo.
- `confirmar_cierre.html`: campo efectivo `type=tel`, `autocomplete=transaction-amount`, rechazo si monto contiene `@`.

### Sidebar menú

- `design-system.css`: scroll en `.app-sidebar-nav`, `align-self: flex-start` en sidebar.

### Deploy y SQL (2026-05-20)

```bash
git push origin main   # Render auto-deploy
python scripts/apply_sql_neon.py sql/2026_05_18_pos_autorizacion_descuento.sql
python scripts/apply_sql_neon.py sql/2026_05_21_rendimiento_sd1_postgresql.sql
```

---

## FE Maullín — pausa SII (sesión 2026-05-20, cierre jornada)

**Emisor:** RUT `8054120-1` — LUIS GASTON RIVERA PEREZ. **Dev solo certificación:** `SII_AMBIENTE=certificacion`, host `maullin.sii.cl`.

### Bloqueo administrativo SII (no es bug LhexIA)

- Portal SII → *Estado mis peticiones administrativas* → folio **77326378627**.
- Materia: **Solicitud de folios electrónicos y Timbraje Dctos**.
- Estado al 20/05/2026: **Recepcionada** (18/05/2026). **Esperar cierre/aprobación** antes de CAF oficiales y certificación formal.

### Hecho en código (backend listo)

| Pieza | Detalle |
|-------|---------|
| Firma semilla/token | `services/facturacion_sii_soap.py` — C14N `REC-xml-c14n-20010315`, SHA1, RSA-SHA1, `always_add_key_value`, salida **ISO-8859-1**, SOAP getToken en ISO-8859-1 |
| Acteco ferretería | `475200` en factura 33 (set + API) |
| Set certificación | `verificar_firma_sii_certificacion.py` → ZIP `storage/dtes/pruebas_sii/pruebas_sii_dte_verificacion.zip` (39/33/61 FIRMADO; 39+33 TIMBRADO) |
| CAF laboratorio | `fe_setup_caf_certificacion_maullin.py --bd` (no sustituye CAF SII) |
| API emitir prueba | `emitir-prueba` con `caf_id`, `reservar_folio=1`, folio 2 correlativo OK |
| API envío SII | **`GET /api/admin/facturacion/enviar-prueba-sii?dte_tipo=33&folio=1&reload_env=1`** → sube `DTE_33_FOLIO_1.xml` |
| Diagnóstico | `diagnostico-sii`, scripts `fe_diagnostico_sii.py`, `fe_diagnostico_sii_reintentos.py` |
| Red Maullín | 503 intermitente en CrSeed/GetToken; firma **no** rechazada con estado 10 en últimos ciclos — **no** ejecutar reintentos en background (DoS) |

### Retomar FE (manual, cuando SII habilite timbraje)

1. Confirmar petición **77326378627** cerrada/aprobada en portal SII.
2. Timbraje + descarga CAF oficiales Maullín → cargar en `/admin/facturacion/caf`.
3. `GET /api/admin/facturacion/diagnostico-sii?reload_env=1` → `token_estado: "00"`.
4. `GET /api/admin/facturacion/enviar-prueba-sii?dte_tipo=33&folio=1&reload_env=1` → capturar **Track ID**.
5. Si `token_estado: "10"` estable → revisar Transforms en `Reference` (signxml añade C14N extra además de enveloped).

**Doc:** `docs/planes/04-tecnico/FE_CERTIFICACION_MAULLIN.md`, `FE_SII_DIA_RUT_AUTORIZADO.md`.

---

---

## Checkpoint sesión 2026-05-21 — Agentes IA + caja opcional (retomar mañana)

**Transcripción Cursor (chat completo):** `agent-transcripts/ea00bfe0-08c5-40c5-a002-e6b877474d7a/ea00bfe0-08c5-40c5-a002-e6b877474d7a.jsonl`  
**Resumen ejecutivo:** `docs/planes/06-agentes-ia/CHECKPOINT_RETOMAR_2026_05_21.md`

### Commits en `main` (pushed a `origin`)

| SHA | Mensaje |
|-----|---------|
| `f10f646` | `feat(agentes): tabla agente_ejecuciones y Operador v0.1 en Control Center` |
| `6443b4e` | `feat(agentes): v0.2 Ollama worker local, contexto y pgvector` |
| `de947c0` | `feat(caja): cierre opcional ciego/visible en config empresa` |

**Prod:** Render auto-deploy desde `main` → [www.lhexia.cl](https://www.lhexia.cl)

### LhexIA Operador — estado

| Versión | Qué hace | ¿Requiere Ollama? |
|---------|----------|-------------------|
| **v0.1** | Reglas SQL: vales `Pendiente` > N h, cajas cerradas con descuadre | No |
| **v0.2** | Worker PC sucursal enriquece `cuerpo` vía Ollama (batch 5–10) | **Opcional** — `AGENTE_OLLAMA_ENABLED=0` en Render |

**Rutas:** `GET /admin/control-center`, `POST /admin/agente-operador/escanear`  
**Scripts:** `scripts/agente_operador_scan.py`, `scripts/agente_operador_enrich.py` (solo PC i5 16GB)  
**Tabla:** `agente_ejecuciones` — migración `sql/2026_05_21_agente_ejecuciones.sql`  
**Docs:** `docs/planes/06-agentes-ia/AGENTE_EJECUCIONES_ESTADOS.md`, `docs/manuales/INSTALACION_OLLAMA_LOCAL.md`  
**Vectorial (fase siguiente):** `sql/2026_05_21_lhexia_vector.sql` → `lhexia_vector_chunks` (pgvector; indexar productos después)

**Orden agentes acordado (4 IAs asesoría):** 1 Operador → 2 Comercial → 3 Guía → 4 Pulso Marca (congelado post-SD-1).  
**Consolidación:** `docs/planes/06-agentes-ia/CONSOLIDACION_4_AGENTES_ASESORIA.md`

**Env agentes (Render = Ollama OFF):**

```env
AGENTE_OLLAMA_ENABLED=0
AGENTE_VALE_HORAS_UMBRAL=3
AGENTE_CIERRE_DIF_UMBRAL_CLP=5000
# PC sucursal cuando exista hardware:
# AGENTE_OLLAMA_ENABLED=1
# OLLAMA_BASE_URL=http://127.0.0.1:11434
# OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
```

**Cuidado prod:** primer «Escanear ahora» masivo puede crear muchas alertas si hay vales `Pendiente` históricos — escanear en horario bajo o cerrar lote viejo.

### Cierre de caja — modo opcional (nuevo)

| Modo | Config | Pantalla `/cerrar_caja` |
|------|--------|-------------------------|
| **ciego** (default) | `cierre_caja_modo: ciego` en empresa | Sin teórico (PLAT-1.1) |
| **visible** | Admin → Datos de empresa → Modo visible | Resumen + efectivo esperado en gaveta |

**Servicio:** `services/cierre_caja_config_service.py`  
**Override env:** `CIERRE_CAJA_MODO=ciego|visible`  
**Persistencia cierre:** `caja.modo_cierre_arqueo` → `payload_json.modo_cierre` en alertas Operador  
**Tests:** `tests/test_cierre_caja_modo.py`, `tests/test_agente_operador*.py` (13 tests agentes+caja modo)

### Pendiente / no bloquea SD-1

- [ ] Instalar Ollama en PC sucursal (i5 16GB) + cron `agente_operador_enrich.py` — **después** de estabilizar piso
- [ ] Ejecutar en Neon: `sql/2026_05_21_lhexia_vector.sql` (pgvector)
- [ ] Switch UI futuro en admin si se quiere más visible que radios en `/admin/empresa`
- [ ] Agente Comercial (HITL) y Guía (RAG) — post SD-1
- [ ] FE Maullín — **congelado** hasta folio SII 77326378627 (ver § FE abajo)
- [ ] Cambios locales **sin commit:** `data/empresa_config.json`, `docs/ERP_MAESTRO.md`, FE certificación, etc.

### Retomar mañana (comandos)

```bash
# Tests smoke agentes + caja
pytest tests/test_agente_operador.py tests/test_agente_operador_v02.py tests/test_cierre_caja_modo.py -q

# Validar Control Center local
# http://127.0.0.1:5000/admin/control-center

# Cambiar modo cierre (admin)
# http://127.0.0.1:5000/admin/empresa
```

**En Cursor:** `@docs/memory.md` + `@docs/planes/06-agentes-ia/CHECKPOINT_RETOMAR_2026_05_21.md` + *«sigue desde el checkpoint 2026-05-21»*.

---

## PWA Dueño v0.1–v0.2 (2026-05-21)

**Objetivo:** control “un vistazo y un toque” en móvil para el dueño (SD-1), sin FastAPI ni segundo backend.

| Pieza | Ubicación |
|-------|-----------|
| API semáforo | `GET /api/v1/owner/dashboard` — `blueprints/owner_api.py`, `services/owner_dashboard_service.py` |
| Vista PWA | `GET /owner-mobile` — `templates/owner_mobile.html` (sidebar oculto, tarjetas grandes) |
| Front poll | `static/owner-pwa/owner-dashboard.js` — cada 45 s `?nocache=1` |
| Manifest / SW | `GET /owner-pwa/manifest.webmanifest`, `GET /owner-pwa/sw.js` |
| Fuente alertas | `agente_ejecuciones` (Operador) + descuadres caja (`control_center_service`) + SKU &lt; 5 |

**Permisos:** `panel_gerencia`, `ver_gerencia`, `gestionar_usuarios` (admin bypass).

**Env:**

```env
OWNER_SUPERVISOR_TELEFONO=+569XXXXXXXX   # botón Llamar supervisor (tel:)
OWNER_PWA_SUCURSAL_LABEL=Santo Domingo   # texto tarjeta inventario
```

**Operación un local vs red:** Admin → **Datos de empresa** → *Un establecimiento* (default SD) o *Red multi-sucursal* → `operacion_un_local` / `operacion_sucursales_red_n` en `empresa_config.json`. Guardián: `services/empresa_operacion_service.py` (env `OWNER_GUARDIAN_*` solo override).

**Tests smoke:** `pytest tests/test_owner_dashboard_api.py -m smoke -q`

**Instalar en teléfono:** Chrome → `/owner-mobile` → “Añadir a pantalla de inicio” (usa manifest).

**Validación prod completa:** `docs/planes/01-entrega-santo-domingo/OWNER_PWA_VALIDACION_PROD.md` — manifest/SW/API 401 OK en www.lhexia.cl (2026-05-21).

**Pendiente SD-2:** micrófono / voz; token API sin cookie si se requiere app nativa.

---

---

## Sesión 2026-05-21 — VERTEX Centro de Mandos + animaciones + Agente Mentor (chat Cursor)

**Transcripción:** `agent-transcripts/bc4d8ea6-60b4-441b-bbaf-b5a8fb5551a9`  
**Documento maestro ampliado:** `docs/ERP_MAESTRO.md` §19.6.1, rutas §4.3, changelog 2026-05-21.

### Contexto de la sesión

Mario validó el **Centro de Mandos Global** (`/owner/vertex-control?scope=global_maestro`) en www.lhexia.cl. Feedback iterativo:

1. Mapa cognitivo “otro nivel” visualmente ✅ tras varias rondas de animación.
2. Problema inicial: **solo el icono central se movía**; circuitos y anillos estáticos.
3. Causa raíz: código con fix **sin push a `origin/main`** + animaciones SVG (SMIL/WAAPI) poco fiables en Windows/Edge.
4. Producto: faltaba el **Agente Mentor** (asesoría cajera/vendedora — ej. cómo hacer nota de crédito).

### PWA Guardián (trabajo previo misma línea de producto)

| Pieza | Detalle |
|-------|---------|
| Ruta | `/owner-mobile` — renombrado producto **Guardián** (no “Dueño”) |
| Manifest | `name`/`short_name` Guardián, `background_color` `#0b0f19` |
| Iconos | `scripts/build_guardian_pwa_icons.py` → `static/owner-pwa/icon-*.png` desde `lhexia-core-reveal-square.png` |
| Splash | `templates/partials/pwa_splash.html` + `static/css/pwa-splash.css` |
| Caja móvil | `templates/caja_pendientes.html` — header columna, botones 2×2 |
| **Operativa** | Tras deploy: **desinstalar PWA vieja** y reinstalar para icono/splash nuevos |

### Centro de Mandos VERTEX — arquitectura

| Capa | Archivos |
|------|----------|
| Ruta + permiso | `blueprints/owner_api.py` — `@permisos_required('gestionar_usuarios')`, `usuario_es_vertex_maestro()` |
| Shell HTML | `templates/owner_vertex_control.html` — stage neural, HUB HTML, SVG `#vertexNeuralSvg`, riles glass |
| API | `GET /api/v1/owner/dashboard?scope=global_maestro` |
| Servicio | `services/vertex_control_center_service.py` — `_cliente_santo_domingo_live`, `_clientes_mock`, `_grafo_agentes`, `_feed_preview_global` |
| Píldoras | `services/vertex_pildora_contract.py` — `build_pildora`, `asegurar_pildoras_demo_red`, tenants `santo_domingo`, `sodimac_piloto`, `easy_demo` |
| Front | `static/owner-pwa/vertex-control.js`, `vertex-control.css` — cache **`vertex-neural-6`** |

**Layout mapa:** HUB `(400,262)` · clientes en slots TL/TR/BR · paths PCB ortogonales · 3 líneas energía por arista (rail + track + energy).

### Animaciones — evolución técnica (importante para retomar)

| Versión cache | Enfoque | Resultado en piso |
|---------------|---------|-------------------|
| neural-2 / 3 | SMIL `<animate stroke-dashoffset>` | Casi nada visible |
| neural-4 | Web Animations API en paths SVG | Usuario: “nada” (sin deploy + WAAPI débil en SVG) |
| **neural-5 / 6** | **CSS `@keyframes`** `.vertex-dash-anim` + anillos `rotate` + arco `conic-gradient` en `.vertex-hub-vault::before` | ✅ Aprobado “maravilloso” |

**Reglas fijadas:**

- No setear `stroke-dashoffset` inline en JS.
- Clase `vertex-neural-live` en SVG (también en template por defecto).
- `wireEnergyPaths()` solo añade clases + dots en `requestAnimationFrame`.
- `@media (prefers-reduced-motion: reduce)` en VERTEX: duraciones más largas, no `animation: none` global.
- Quitar `contain: layout style` del stage (podía interferir).

**Commits (orden):** `40dd867` red neuronal · `06a7020` SMIL · `a8f9e38` WAAPI · `fc1d58b` CSS neural-5 · `e9d7af6` Mentor · push a `main` obligatorio antes de validar prod.

### Agente Mentor (`vertex_mentor`) — 2026-05-21 tarde

**Producto:** mismo rol que **LhexIA Guía** (Agente 3 en `docs/planes/06-agentes-ia/CONSOLIDACION_4_AGENTES_ASESORIA.md`) — guía procesos para cajera/vendedora, no supervisión ni stock.

| Implementado hoy | Pendiente (post SD-1) |
|------------------|----------------------|
| Nodo grafo violeta, leyenda, pill módulo | Chat / panel en POS |
| Tarjeta glass riel izquierdo (icono `fa-graduation-cap`) | RAG `ERP_MAESTRO` + `CASUISTICAS_VENTAS_QA` |
| SD live: `mentor` en `agentes_activos` + `vertex_mentor` en módulos | Botón “Pedir ayuda al Mentor” en caja/POS |
| Píldora demo NC → `/caja/cambios` | Métricas consultas reales |

**Demo píldoras:** `mentor_guia_nota_credito` (SD), `mentor_capacitacion` (Sodimac). Test: `test_pildora_mentor_demo_red`.

### Enlaces útiles operación

| Vista | URL |
|-------|-----|
| Guardián (un cliente) | `/owner-mobile` |
| VERTEX maestro | `/owner/vertex-control` |
| Control operativo SD | `/admin/control-center` |
| API maestro | `/api/v1/owner/dashboard?scope=global_maestro` |

### Validación

```bash
pytest tests/test_owner_dashboard_api.py -q
# shell: vertex-neural-6 en HTML; grafo con nodo mentor
```

Prod: Ctrl+Shift+R; verificar deploy Render tras cada push.

### Próximo paso sugerido (no implementado)

- **Mentor en POS:** FAB o enlace contextual “¿Cómo hago una nota de crédito?” → wizard o RAG.
- Checkpoint git antes de UI POS: `checkpoint/vertex-mentor-pos-YYYY-MM-DD` (regla `.cursor/rules/punto-restauracion-cambios-drasticos.mdc`).

**Eje:** SD-1 + PLAT Etapa 2 visual; IA Mentor completo post SD-1.

---

*Última actualización: 2026-05-21 — VERTEX Centro de Mandos (red neuronal neural-6), Agente Mentor, PWA Guardián; memoria sincronizada con `ERP_MAESTRO.md` §19.6.1. Prioridad: SD-1 piso + validar Mentor en deploy.*
