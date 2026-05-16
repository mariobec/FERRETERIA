# Memoria del proyecto (ERP ferretería / ventas)

Este archivo es la **memoria viva** del trabajo en el repo. El usuario y el agente lo usan para **recordar contexto entre sesiones**.

**Copia en documentación:** `docs/memory.md` (mismo contenido; mantener sincronizado al actualizar).

## Cómo usarlo

- **Al arrancar una sesión en Cursor:** pedir *“lee memory.md y sigue desde ahí”* o adjuntar `@memory.md`.
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

**Refactor en curso (Clean Architecture ligera):** ver `docs/ARQUITECTURA_CAPAS.md`. **`core/`** Fases **1.2 + 1.3**: estado del vale vía use cases; **stock/kardex al cobro** vía `DescontarStockCobroService` + `AppCobroStockAdapter`. Cuotas, saldo favor, bodega, FE y audit siguen en `app.py`.

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

## Configuración y entorno

| Variable | Uso |
|----------|-----|
| `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI` | BD app (local, Render, etc.) |
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

---

## Dónde quedamos (retomar desde aquí)

**Hecho (Fases 1.2 + 1.3 operativas):**
- Paquete `core/domain/venta/`, `core/application/ventas/`, `core/application/inventario/stock_cobro.py`, repos y adapters (`stock_tienda_validator`, `cobro_stock_adapter`), `core/application/bootstrap.py`.
- **`finalizar_venta`** → `FinalizarVentaUseCase`; **`procesar_cobro_caja`** → `ProcesarCobroUseCase` + `build_descontar_stock_cobro_service()` (preparar líneas fuera del savepoint, aplicar dentro).
- **`tests/conftest.py` `cobrar_venta_efectivo`**: mismo stack que producción (use case + stock service).
- Efectos colaterales **aún en app.py**: alta/edición cliente al finalizar, cuotas crédito + `saldo_deudor`, saldo a favor, flags bodega, `erp_audit_log`, FE post-commit, `MovimientoCaja` en cobro HTTP (si aplica).

**Siguiente paso recomendado (Fase 1.4):**
1. Extraer cuotas crédito + `saldo_deudor` post-cobro a `application/ventas` o `application/creditos`.
2. Opcional: `agregar_producto_venta` / carrito Abierta → dominio (`Venta.agregar_linea` ya existe).
3. Tests unitarios dedicados para `DescontarStockCobroService` (mocks de puertos).

**No hacer aún:** Alembic, multi-tenant, mover modelos ORM fuera de `app.py`.

**Comandos útiles:**
```bash
pytest tests/test_core_domain_venta.py -q
pytest tests/test_end_to_end.py -m "smoke and happy_path" -q --tb=short
```

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

*Última actualización: 2026-05-16 — alineado con `docs/ERP_MAESTRO.md`, sync Neon y estado del repo.*
