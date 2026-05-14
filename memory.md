# Memoria del proyecto (ERP ferretería / ventas)

Este archivo es la **memoria viva** del trabajo en el repo. El usuario y el agente lo usan para **recordar contexto entre sesiones**.

## Cómo usarlo

- **Al arrancar una sesión en Cursor:** pedir *“lee memory.md y sigue desde ahí”* o adjuntar `@memory.md`.
- **Cuando terminemos un bloque de trabajo:** pedir *“actualiza memory.md con lo que hicimos hoy”* para dejar constancia.
- El agente **no inventa** historial: solo documenta lo que consta en el chat o en el código que tocamos.

## Alcance de esta memoria (importante)

- Aquí hay **mapa por módulo, reglas que cruzan el sistema, modelos y lista de rutas**. Para cada función puntual, la **fuente de verdad sigue siendo `app.py`** (≈11k líneas).
- **No sustituye** leer el código cuando hace falta precisión de borde (validaciones raras, mensajes de error, migraciones SQL recientes).

## Qué es este proyecto

- **Stack principal:** Flask, Flask-SQLAlchemy, Flask-Login, PostgreSQL (producción/hosting típico) o MySQL local por defecto si no hay `DATABASE_URL`.
- **Patrón:** núcleo todavía **monolítico** en **`app.py`**, pero ya convive con **blueprints** registrados (`bodega`, `caja`, `pos`, `c360`) y servicios extraídos para dominios críticos.
- **Frontend servidor:** Jinja2 en **`templates/`** (~75 HTML).
- **Estáticos:** **`static/`** (`design-system.css`, Bootstrap local, `pos.js`, logos).
- **Migraciones / DDL:** **`sql/`** (fechas `YYYY_MM_DD_*`).
- **Scripts:** **`scripts/`** (semillas, migraciones auxiliares). Normalizar precios/montos DEMO ya en BD: `python scripts/normalize_demo_data_clp.py`.
- **Datos JSON runtime:** **`data/`** (empresa, proveedores, `landing_leads.jsonl`, `landing_lead_events.jsonl` y otros artefactos runtime).

## Arquitectura del repositorio (carpetas relevantes)

| Ubicación | Rol |
|-----------|-----|
| `app.py` | App Flask, modelos SQLAlchemy, rutas, reglas de negocio principal. |
| `schema_sync.py` | Sincronización esquema modelos vs BD (usado en `init_db`). |
| `init_db.py` | `schema_sync`, roles base, usuario admin opcional `BOOTSTRAP_ADMIN_*`. |
| `requirements.txt` | Dependencias Python. |
| `render.yaml` | Deploy ejemplo: `gunicorn app:app`. |
| `templates/`, `static/` | UI. |
| `sql/`, `scripts/` | DDL incremental y utilidades. |
| `demo_ferreteria/` | Demo empaquetada para cliente. |
| `CARGA DE DATOS/` | CSV masivos. |
| `docs/` | Documentación operativa, roadmap C360 y **roadmap de observabilidad 2026–2030**. |

Copias viejas (`app-28-04-2026.py`, `ventas.*.py`): **operativo = `app.py`**.

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
| `MovimientoInventario` | Movimientos / kardex (según implementación). |
| `BitacoraCostoCompra`, `BitacoraPrecioVenta` | Historial precios/costos. |
| `CambioOperacion`, `CambioDetalle` | Devoluciones/cambios en caja. |
| `ClienteSaldoFavor`, `MovimientoSaldoFavor` | Saldo a favor del cliente. |
| `AuditoriaInventario`, `DetalleAuditoria` | Auditorías/conteos. |
| `AbonoCredito` | Abonos a cuenta crédito. |

---

## Reglas transversales

### Permisos (`permisos_required`, `usuario_tiene_permiso`)

- Roles cuyo nombre normalizado está en `admin`, `administrador`, `superadmin`, `super admin` → **pasan cualquier permiso**.
- Resto: debe existir el permiso en la relación `rol_permisos`.
- Lista orientativa de permisos semilla: `_PERMISOS_SISTEMA_INICIAL` — incluye `gestionar_usuarios`, `admin_inventario`, `enrolamiento_inventario`, `panel_gerencia`, `anular_vale_caja`, `autorizar_descuento_pos`, `revision_precios`, `pos_emitir_vale`, `caja_cobrar_vale`, `caja_abrir`, `caja_movimientos`, `caja_cerrar`.
- **`modulo_activo(n)`:** lee JSON empresa (`mod_*`) para mostrar/ocultar módulos.

### Caja obligatoria (`caja_requerida`)

- Solo aplica si `request.endpoint` está en **`_ENDPOINTS_CAJA_ESTRICTA`**: POS (`punto_venta`, `guardar_venta`, `agregar_producto_venta`, `eliminar_detalle`, `finalizar_venta`, `actualizar_item`, `pos_usuarios_autorizar_descuento`), caja (`caja_pendientes`, `procesar_cobro_caja`, `anular_vale_caja`, `ver_ticket_cobro`), cambios (`caja_cambios`, APIs cambios, `ticket_cambio`, `caja_cambios_historial`), **`registrar_abono`**.
- Si hay caja abierta pero **fecha de apertura anterior al día actual** → por defecto redirige a **cerrar caja** antes de seguir en el POS (**excepto** endpoints en **`_ENDPOINTS_EXENTOS_BLOQUEO_FECHA_CAJA`**: mismos cuatro de cobranza/ticket arriba). Así se puede cobrar o anular vales/borradores que bloquean el cierre sin quedar en un callejón.

### Stock y tienda

- Conversiones venta → stock base con **`_factor_venta_a_stock(producto)`**; disponibilidad con **`stock_disponible_venta_tienda`** y descuento con **`descontar_stock_venta_tienda`** (almacén tienda resuelto por helpers tipo `id_almacen_tienda()`).
- Kardex: **`registrar_movimiento_kardex`** en cobros y ventas directas.

### Cliente sistema “final”

- RUT configurable `POS_RUT_CLIENTE_FINAL` (default `66.666.666-6`) para ventas sin nombre vía **`obtener_o_crear_cliente_final`**.

---

## Lógica por módulo

### 1. Público, landing y catálogo web

- **Rutas:** `/`, `/index`, `/healthz`, `POST /api/landing/lead`, `/catalogo`, `/consulta-stock`, `/sitemap.xml`, `/robots.txt`.
- **SEO / money pages públicas:** `/lhexia-vs-defontana`, `/erp-ferreterias`, `/erp-retail-especializado`, `/alternativa-a-defontana`, `/erp-con-bodega-por-voz`, `/como-reducir-quiebres-de-stock-en-ferreterias`, `/quienes-somos`, `/fundador`.
- **Lógica:** landing premium + cluster SEO ya desplegado en producción; captura leads en JSONL y dispara conversión web first-party. Catálogo/consulta respetan flags tipo **`PUBLICO_MUESTRA_PRECIO`**, **`PUBLICO_MUESTRA_STOCK_EXACTO`** (ver también `render.yaml`). Sitemap/robots se generan dinámicamente desde Flask.

### 2. Autenticación y usuarios

- **Rutas:** `/login`, `/logout`, `/logout/forzar`, `/cambiar_password`, `/usuarios`, toggle estado usuario, `/editar_usuario`, `/eliminar_usuario`.
- **Lógica:** Flask-Login; perfiles `ACTIVO` / `INACTIVO`; forcing cambio clave con perfiles tipo `FORZAR_CLAVE`; sesión guarda `login_at` para UI. **Fix vigente:** si un administrador redefine la contraseña desde `/editar_usuario/<id>`, la cuenta sale de `FORZAR_CLAVE` y queda en `ACTIVO`.

### 3. Home y ayuda

- **Rutas:** `/inicio`, `/ayuda`, `/owner-mobile`.
- **Lógica:** `inicio` concentra navegación según permisos/módulos; `owner-mobile` vista reducida gerencia/móvil.

### 4. Comercial (leads)

- **Rutas:** `/comercial/leads`, `POST .../estado`.
- **Lógica:** gestión de estados de leads capturados desde landing u otros.

### 5. BI, gerencia e informes

- **Rutas:** `/bi`, `/bi/panel-dueno`, `/gerencia/informes-dueno`, demos `/bi/demo/*`, `/gerencia/simulador-margen`, `/gerencia/analitica-web`, `/gerencia/seo-rankings`, exports `bi/export.csv`, `bi/export_vendedores.csv`.
- **Lógica:** además de BI histórico, ahora existe una capa interna de **observabilidad comercial y SEO**: analítica first-party, snapshots SEO locales, funnel ejecutivo, alertas mínimas y taxonomía estable de eventos/CTA. Todo el dashboard consume datos locales ya persistidos, sin llamadas externas en tiempo real.

### 6. IA abastecimiento / sugerencias compra

- **Rutas:** `/ia_abastecimiento`.
- **Lógica:** pantalla de sugerencias (enlace típico con rotación/stock y creación OC multi-línea vía payload JSON a `/compras/ordenes/nueva`).

### 7. Productos, precios, inventario UI

- **Rutas:** `/productos`, APIs subs catálogo, `/precios/revision` (+ aplicar/editar/masivo), filtros `/productos/filtro/<tipo>`, `/stock/critico`, `/inventario/dashboard-premium`, `/inventario/salud`, CRUD masivo (`guardar_producto`, `cargar_productos`, stock masivo, toggle activo), export/plantilla Excel.
- **Lógica:** revisión de precios como workflow aparte; stock crítico y dashboards leen agregaciones; permisos admin inventario para ajustes sensibles (`_usuario_puede_ajustar_stock`).

### 8. Enrolamiento de inventario

- **Rutas:** `/inventario/enrolamiento`, APIs `POST/GET .../api/enrolamiento/*` (sesión, escaneo, maestro, vincular, alta manual, entrada stock, traslado).
- **Lógica:** tomas por sesión/líneas; permiso **`enrolamiento_inventario`** o **`admin_inventario`** según helpers; integración con tablas enrolamiento.

### 9. Proveedores

- **Rutas:** `/proveedores`, guardar/editar/eliminar.
- **Lógica:** maestro proveedor; canales de compra pueden persistirse en JSON **`data/proveedores_config.json`** (`obtener_canales_proveedor`, etc.).

### 10. Ventas — dos flujos distintos (crítico)

| Flujo | Resumen |
|--------|---------|
| **A. POS / vale** | `punto_venta`: venta **`Abierta`** por **caja + usuario** (`_venta_abierta_por_caja_y_usuario`). Se agregan líneas; **`finalizar_venta`** valida stock en tienda, cliente (RUT o cliente final), **punto retiro** obligatorio (`Bodega`/`Tienda`/`Despacho`), deja venta **`Pendiente`**, **sin descontar stock aún**. Cobro en **`procesar_cobro_caja`**: valida stock otra vez; también permite cerrar cobro sobre **`Abierta`** asociada a la **caja abierta** (borrador POS); si pago normal (`≠ Credito`) → **`Pagado`**, vuelto, opcional **saldo a favor**; **descuenta stock** y kardex. Si método **`Credito`** en cobro: sube **`saldo_deudor`**, deja **`Pendiente`**, descuenta stock según bloque actual. Plan de cuotas en **`credito_plan_cuotas`**: solo **`30_60_90`** (tres cuotas a +30/+60/+90 días corridos desde el cobro); opción sin plan = crédito simple. Medios inmediatos incluyen **`Efectivo`**, **`Debito`**, **`TarjetaCredito`** (tarjeta banco; distinto de **`Credito`** = fiado tienda). **`anular_vale_caja`**: **`Pendiente`** sin método, o **`Abierta`** sin método en la caja actual; **no revierte stock** si no estaba cobrado. |
| **B. Venta directa formulario** | **`guardar_venta`** (asociada a pantalla gestión): arma venta en un POST; valida líneas; si **`Credito`** valida **`limite_credito`** y aumenta **`saldo_deudor`** antes de flush; estado **`Pagado`** o **`Pendiente`**; **descuenta stock y kardex en el mismo request** para todas las líneas (incluye venta a crédito en este flujo). Redirect típico a **`mostrar_ventas`**. |

- **Rutas relacionadas:** `/ventas`, `/punto_venta`, `/guardar_venta`, `/agregar_producto_venta`, `/eliminar_detalle`, `/eliminar_venta`, `/finalizar_venta`, `/editar_venta`, `/actualizar_item`, `/pos/usuarios_autorizar_descuento`, `/buscar_producto`, APIs `/api/buscar_producto/<codigo>`.
- **POS:** búsqueda producto por código barra, interno, chilemat; precio efectivo **`precio_efectivo_pos_producto`**; autorización descuentos por usuario con permiso.

### 11. Caja (apertura, arqueo, movimientos, historial)

- **Rutas:** `/abrir_caja`, `/movimiento_caja`, `/cerrar_caja`, `/caja/historial_cierres`, tickets cierre, `/caja/vales_pendientes`, `/procesar_cobro_caja`, `/caja/vale_retiro/<id>` (ticket cobro), `/caja/vales/<id>/anular`.
- **Lógica:** una caja **`Abierta`** a la vez en práctica (última por id); **`cerrar_caja`** bloquea si hay vales **`Pendiente`** sin método en esa caja o ventas **`Abierta`** en esa caja. **`caja_pendientes`** arma **`cola_combined`**: borradores **`Abierta`** de la caja actual + vales **`Pendiente`** sin método (orden práctico: borradores primero). Cierre cuadrado con columnas **`_asegurar_columnas_caja_cuadratura`**; `confirmar_cierre` / `ticket_cierre` desglosa efectivo, débito, **`TarjetaCredito`**, transferencia; **`Credito`** (fiado) informativo; efectivo teórico en gaveta sin incluir medios electrónicos.

### 12. Cambios de productos y saldos a favor

- **Rutas:** `/caja/cambios`, APIs `/api/cambios/*`, tickets e historial `/caja/cambios/historial`, `/caja/saldos-favor`.
- **Lógica:** operaciones `CambioOperacion`/`CambioDetalle`; saldos **`ClienteSaldoFavor`** / movimientos.

### 13. Admin maestro

- **Rutas:** `/admin/empresa`, `/admin/almacenes`, `/admin/clientes`, `/admin/roles-permisos`, `/admin/unidades`, `/admin/catalogo`.
- **Lógica:** empresa desde JSON/config; almacenes activos/códigos tienda-bodega; clientes y créditos admin; roles ↔ permisos; unidades/conversiones; catálogo jerárquico categoría/subcategoría y asignación masiva de productos (**`_sincronizar_producto_desde_subcatalogo`**).

### 14. Auditorías y kardex

- **Rutas:** `/ver_auditorias`, `/finalizar_auditoria/<id>`, APIs conteo/recepción inventario, `/kardex`.
- **Lógica:** auditorías inventario y movimientos consultables por producto/fecha según implementación en `app.py`.

### 15. Órdenes de compra

- **Rutas:** `/compras/ordenes`, nueva, editar `<oid>`, seguimiento rápido POST.
- **Lógica:** si **`_tablas_orden_compra_existen()`** falso → redirige con aviso **migración `sql/2026_05_03_ordenes_compra.sql`**. OC con líneas, estados válidos `_OC_ESTADOS_VALIDOS`, seguimiento embebido en observaciones vía **`_registrar_seguimiento_oc`**. Sugerencia proveedor IA por histórico OC. Duplicado rechazado: mismo `(proveedor_id, numero)`.

### 16. Recepciones de compra

- **Rutas:** lista, tablet móvil, `nueva`, `detalle`, APIs iniciar/resumen, reporte **`/recepciones/costos`**, IA factura **`.../ia-factura/analizar|aplicar`**, documento/etiquetas, `ver_documento`, `descargar_pdf`.
- **Lógica:** creación recepción con proveedor + tipo doc Factura/Guía + número; vínculo opcional **`orden_compra_id`** si proveedor coincide; líneas vía **`_aplicar_linea_recepcion`** (stock, costos, alertas margen); finalización puede generar códigos **`INT-{id}`** y redirect a etiquetas; IA con **`OPENAI_API_KEY`**, PDF/pages **`IA_FACTURA_PDF_PAGINAS`**.

### 17. Créditos y cobranza

- **Rutas:** `/creditos`, estado cuenta HTML/PDF/boucher, **`POST /registrar_abono`**, `/ticket_abono/<id>`.
- **Lógica:** límites y saldos en `Cliente`; abonos registran **`AbonoCredito`**; integración con caja según permisos.

### 18. Cotizaciones

- **Rutas:** lista, `nueva`, `detalle`, `editar`, `contacto`, `estado`, `pdf`, `whatsapp`, **`convertir`** → POS, APIs buscar productos/clientes.
- **Lógica:** cotización con snapshot cliente; **`cotizacion_convertir_venta`** crea **`Venta` Abierta**, copia líneas, marca cotización **`Convertida`** y **`venta_id`**; enlaza/crea **`Cliente`** desde snapshot si falta; valida stock y advierte faltantes **antes de emitir vale** en POS.

### 19. Observabilidad web y SEO interno (implementado mayo 2026)

- **Rutas públicas / ingestión:** `POST /api/analytics/track`, `POST /api/landing/lead`, `POST /api/observabilidad/cron-diario`.
- **Rutas internas:** `/gerencia/analitica-web`, `/gerencia/seo-rankings`, `POST /gerencia/seo-rankings/snapshot`, `POST /gerencia/seo-rankings/keyword-metric`.
- **Persistencia principal:** `WebAnalyticsVisitor`, `WebAnalyticsSession`, `WebAnalyticsPageView`, `WebAnalyticsEvent`, `WebAnalyticsConversion`, `ControlTraficoInterno`, `TelemetriaHistoricaAgregada`, `SeoKeywordTarget`, `SeoKeywordDailyMetric`, `SeoPageDailySnapshot`, `SeoSiteDailySnapshot`.
- **Lógica:** tracking first-party con `session_id` Liz válido, taxonomía estable de eventos/CTA, retención/purga de telemetría, cron seguro de observabilidad, funnel ejecutivo `visita -> CTA -> WhatsApp -> lead`, alertas comerciales mínimas y alertas SEO ejecutivas. La sync con Search Console quedó aislada y solo como proceso asíncrono/stub.

### 20. Roadmap — Customer 360 + módulo clientes (plan 2026, pendiente de código)

- **Documento detallado:** `docs/roadmap_customer_360_ferreteria_2026.md` (fuente de verdad del plan por fases).
- **Resumen:** P0 urgente = ficha **Customer 360** en Flask, motor **etapa de proyecto** (clasificación obra gruesa / instalaciones / acabados), **fecha estimada siguiente compra** (~21 días), **score de puntualidad** y regla **>90 %** solo para **sugerencias** de crédito proactivo (no automático), **log de predicciones** medible vs ventas. P1 = CDP ligero, timeline, dashboard ferretero predictivo. P2 = Smart dropzone + OCR simulado/real y abonos prellenados. P2b = **worker/cron** “llamadas recomendadas”. P3 = portal cliente, IA asistida.
- **Stack acordado en roadmap:** priorizar **monolito Flask/Jinja**; React+TS+Tailwind solo si se decide micro-frontend para dropzone.
- **Para retomar con el asistente:** *«Lee `memory.md` y `docs/roadmap_customer_360_ferreteria_2026.md`; sigue el roadmap Customer 360 desde la fase que indique.»*

---

## Índice de rutas HTTP (`app.py`, 132 entradas)

Referencias `L####` = línea aproximada en `app.py` para ubicar la vista rápido.

| Línea | Ruta |
|-------|------|
| 2354–2362 | `/`, `/index`, `/healthz` |
| 2367 | `POST /api/landing/lead` |
| 2378, 2413 | `/comercial/leads`, `POST .../estado` |
| 2434, 2473 | `/catalogo`, `/consulta-stock` |
| 2502, 2768 | `/inicio`, `/owner-mobile` |
| 2872, 3583–3615 | `/bi`, `/bi/panel-dueno`, `/gerencia/informes-dueno`, demos BI, `/gerencia/simulador-margen` |
| 3764, 3784 | `/ayuda`, `/ia_abastecimiento` |
| 3881, 3928 | `/bi/export.csv`, `/bi/export_vendedores.csv` |
| 4062–5481 | `/productos/*`, `/precios/revision/*`, stock/inventario/enrolamiento APIs y páginas, proveedores, `guardar_*`, Excel |
| 5606–7511 | `/ventas`, POS, caja vales/cambios/APIs, `buscar_producto` |
| 7594–8033 | `/abrir_caja`, `/movimiento_caja`, `/cerrar_caja`, historial cierres |
| 8051–8718 | usuarios, login/logout, `/admin/*` |
| 8964–9418 | `/api/buscar_producto`, auditorías, `/kardex` |
| 9545–10309 | `/compras/ordenes/*`, `/recepciones/*`, APIs recepciones, documentos PDF |
| 10491–10640 | `/creditos/*`, `/registrar_abono`, `/ticket_abono` |
| 10758–11334 | `/cotizaciones/*`, APIs cotizaciones |

---

## Configuración y entorno

- **Archivos env:** `env_qa.txt` (setdefault), `.env.qa` (override), `.env.local` (local, setdefault).
- **URI BD:** `SQLALCHEMY_DATABASE_URI` → `DATABASE_URL` → default MySQL local si vacío.
- **Postgres:** normalización a `postgresql+psycopg2://`; UTF-8 client encoding por problema Windows/libpq en español.

## Arranque local

- `python -m pip install -r requirements.txt`
- `python app.py`

### Dependencias frecuentes

- **`psycopg2-binary`** si usas PostgreSQL.

### Entorno

- En esta máquina: **Python 3.14** Windows; con otro Python/venv reinstalar deps.

### Producción

- **`render.yaml`:** `gunicorn app:app`, vars `SECRET_KEY`, flags catálogo público.

---

## Historial (actualizar cuando haya hitos)

| Fecha       | Qué pasó |
|------------|----------|
| 2026-05-08 | Diagnóstico: `ModuleNotFoundError: psycopg2` → instalar `psycopg2-binary`. |
| 2026-05-08 | Memoria de arquitectura y uso de `memory.md`. |
| 2026-05-08 | Documentación por **módulo** de lógica de negocio + **132 rutas** + modelos + transversales (permisos/caja/stock/venta dual). |
| 2026-05-08 | Correcciones tras auditoría: reversión inventario/cliente al **eliminar venta** (permisos admin/anular); KPI **monto en vuelo** solo vales sin método de pago; **guardar_venta** alinea redirects y permisos con POS/caja/admin; **editar_venta** bloquea Pagado/crédito; KPI **ventas_hoy** (inicio / owner-mobile / gráfico 7d) excluye `Abierta`; artículos rotados en historial **acotados al filtro** del listado. |
| 2026-05-08 | Al eliminar venta **Pagada** (no crédito), **egreso en `movimiento_caja`** sobre la misma `caja_id` por el neto cobrado fuera de saldo a favor; efectivo usa ticket (`monto_recibido - vuelto`). Sin egreso si monto neto es 0 o falta `caja_id`. |
| 2026-05-08 | **Caja día anterior + cierre bloqueado:** `_ENDPOINTS_EXENTOS_BLOQUEO_FECHA_CAJA` permite `caja_pendientes`, `procesar_cobro_caja`, `anular_vale_caja`, `ver_ticket_cobro` aunque la caja sea de otro día (evita callejón). **`cola_combined`** lista borradores POS **`Abierta`** de la caja + vales pendientes; **`procesar_cobro_caja`** / **`anular_vale_caja`** soportan esos borradores donde aplica. |
| 2026-05-08 | Crédito en cuotas: único plan **`30_60_90`** (días corridos desde cobro). Medio **`TarjetaCredito`** para cobro inmediato con TC bancaria (UI y totales `total_tarjeta_credito` en cierre/ticket); **`Credito`** sigue siendo cuenta tienda. Cheque: sin medio dedicado aún (documentar política si se agrega). |
| 2026-05-08 | **Roadmap Customer 360** (módulo clientes + predicción obra + OCR + worker llamadas) guardado en **`docs/roadmap_customer_360_ferreteria_2026.md`** y referenciado en esta memoria (§19) para retomar cuando el usuario lo recuerde. |
| 2026-05-08 | **Plan v2 Grok:** Fase 1A revisada y cerrada técnicamente (savepoint en cobro/voz/anular; fix saldo/monto **fuera** de `transaccion_critica()` en `procesar_cobro_caja`; reversión bodega limpia **`bodega_despacho_json`** cuando map vacío en `services/stock_service.py`). Tabla verificación en **`docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`**. |
| 2026-05-08 | **Fase 1B cerrada:** cron **`POST /api/ventas/alertas-despachos-pendientes`** con `dry_run_previews`, Slack opcional, audit **`cron_alertas_vales_despacho`** tras envíos OK; **`sql/README_VISTA_VALES_RIESGO.md`**; **`scripts/smoke_alertas_vales_despacho.py`**. |
| 2026-05-08 | **Servicios / observabilidad:** `services/c360_service.py`, `services/sistema_health_service.py` (`GET /api/sistema/salud`). Blueprint **`blueprints/c360.py`** registrado al final de `app.py`. Auto-columnas **`_asegurar_columnas_ventas_bodega_despacho`** en `before_request` autenticado. |
| 2026-05-10 | **Cierre plan v2.0 Grok:** extracción servicios (stock/kardex/whatsapp/unidades), auditoría UI stock + enrolamiento, `transaccion_critica()` extendida a venta directa / POS / finalizar vale / ajustes stock UI; doc y backlog en **`docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`**. |
| 2026-05-10 | **`POST /cargar_productos`:** bucle de importación CSV/Excel envuelto en `transaccion_critica()`; `_audit_log` evento `carga_masiva_productos_archivo` antes del `commit` (mismo patrón que stock masivo UI). |
| 2026-05-11 | **Bodega Fase 3 completada:** SLA (columnas `bodega_preparacion_cobrado_at` / `bodega_preparacion_cerrado_at`; KPI promedio+max en cuadro de mando; chip SLA por vale), ranking operador (7 días, barras), export CSV del día (`GET /bodega/export-dia`), modo TV/kiosk (`GET /bodega/cuadro-mando/tv` con `base_tv.html`, auto-refresh 30 s). Rediseño estético previo del cuadro de mando. |
| 2026-05-11 | **RBAC v2 — Navegación centralizada por permisos.** `_NAV_MAP` en `app.py`: mapa declarativo de menú (grupos, ítems, permisos, endpoints activos). `_construir_nav_usuario()` filtra por permisos del usuario autenticado; `nav_menu` inyectado vía context_processor. Sidebar de `base.html` reescrito para iterar `nav_menu` (≈15 líneas Jinja vs ~180 anteriores). Nuevos permisos: `ver_inventario`, `ver_gerencia`, `gestionar_compras`. Perfiles: `gerente`, `dueno` en `mapa_por_rol`. Rutas protegidas: `mostrar_productos`, `stock_critico`, `kardex`, `business_intelligence`, `mostrar_proveedores`, `lista_ordenes_compra`, `lista_recepciones`, `editar_stock_producto`, `actualizar_stock_masivo_productos`, `cargar_productos` ahora usan `@permisos_required`. |
| 2026-05-12 | **Sitio público / SEO premium:** landing principal reescrita, páginas institucionales (`quienes-somos`, `fundador`), money pages (`erp-ferreterias`, `erp-retail-especializado`) y cluster editorial/comparativo (`lhexia-vs-defontana`, `alternativa-a-defontana`, `erp-con-bodega-por-voz`, `como-reducir-quiebres-de-stock-en-ferreterias`). `robots.txt` y `sitemap.xml` dinámicos ya operativos en producción. |
| 2026-05-12 | **Observabilidad first-party fase base:** modelos web analytics + SEO monitor, tracker web propio, dashboards internos `gerencia/analitica-web` y `gerencia/seo-rankings`, snapshots SEO locales y captura de conversiones/CTA. |
| 2026-05-13 | **Blindaje observabilidad:** validación estricta de `session_id` Liz en `POST /api/analytics/track`, `control_trafico_interno`, `telemetria_historica_agregada`, `consolidar_y_purgar_telemetria()`, stub asíncrono de Search Console y pruebas críticas verdes. |
| 2026-05-13 | **Profundización observabilidad:** `POST /api/observabilidad/cron-diario`, taxonomía estable de eventos/CTA, embudo ejecutivo `visita -> CTA -> WhatsApp -> lead`, alertas gerenciales mínimas en analítica/SEO, roadmap `docs/roadmap_observabilidad_lhexia_2026_2030.md` y despliegue confirmado en Render. |
| 2026-05-14 | **Facturación electrónica — diagnóstico de certificación:** existe base **Fase 1** (`services/facturacion_electronica_service.py`, ruta admin `GET/POST /api/admin/facturacion/emitir-prueba`, migración `sql/2026_05_12_facturacion_electronica_fase1.sql`). En esta máquina el `.pfx` sí existe en `instance/certs/emisor.pfx` y `SII_AMBIENTE=certificacion`, pero la firma falla con **`Invalid password or PKCS12 data`**; la clave hoy entra por `SII_CERT_PFX_PASSWORD` (4 caracteres) y debe revisarse como **clave de exportación del `.pfx`** o pasar a `SII_CERT_PFX_PASSWORD_FILE`. Además, tabla **`cafs`** está vacía (`33/39/61 = 0`) y el envío SOAP al SII sigue en **stub** (`enviar_dte_soap`). Mientras se consigue la clave correcta, continuar otros frentes sin bloquear caja/POS. |
| 2026-05-14 | **Customer 360 P0 — avance real en código:** se agregó auditoría **`cliente_prediccion_log`** (modelo en `app.py` + migración `sql/2026_05_14_cliente_prediccion_log.sql` + auto-ensure), el motor ahora guarda **`fecha_estimada_siguiente_compra`** y **`ultima_compra_clasificada`** (regla default 21 días vía `C360_SIGUIENTE_COMPRA_DIAS`), calcula **`elegible_credito_proactivo`** / motivo de no elegibilidad y evita duplicar logs idénticos el mismo día. La ficha `admin_cliente_c360.html` ahora muestra próxima compra estimada, elegibilidad de crédito y **compras recientes**. Cobertura mínima agregada en `tests/test_customer_360.py` (2 tests verdes). |
| 2026-05-14 | **Customer 360 P0.1 — backend resumen/API:** se añadió resumen 90 días en `services/c360_service.py` (`c360_resumen_actividad_cliente`) con última compra, ventas 90d, ticket promedio, frecuencia media, saldo/límite/cupo y familias compradas por `Producto.categoria`; también `c360_predicciones_recientes_cliente`. Nueva API protegida **`GET /api/c360/clientes/<id>/resumen`** (opción `?recalcular=1`) expone `cliente`, `perfil`, `resumen`, `compras_recientes` y `predicciones_recientes`. La ficha `admin_cliente_c360.html` ahora incorpora bloque **“Actividad 90 días”**. Tests ampliados a **3 verdes** en `tests/test_customer_360.py`. |

---

## Plan consolidado v2.0 — **cierre (mayo 2026)**

El documento **`docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`** quedó **cerrado para alcance v2.0**. Última entrega de código alineada a fila 1.4 del plan: **`transaccion_critica()`** en `guardar_venta`, POS (`agregar_producto_venta`, `eliminar_detalle`, `actualizar_item`), `finalizar_venta`, ajustes stock desde catálogo (unitario + masivo) y **`cargar_productos`** (carga masiva catálogo).

**Backlog post-v2:** métricas Fase 4 finas, otras rutas masivas no inventariadas, `version` optimistic locking, más blueprints — ver sección *Backlog post-v2* en el plan.

**Referencias:** `docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`, `docs/FLUJOS_CRITICOS.md`, blueprints `bodega` / `caja` / `pos` / `c360`, `docs/roadmap_observabilidad_lhexia_2026_2030.md`.

---

*Última actualización del contenido estructural: 2026-05-14 (diagnóstico FE certificación pendiente de clave `.pfx`).*
