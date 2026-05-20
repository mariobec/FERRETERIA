# ERP LhexIA â€” Documento Maestro

> Sistema ERP integral para ferreterÃ­a. GestiÃ³n de ventas (POS + formulario), caja, inventario multi-almacÃ©n, bodega con despacho por voz (IA), compras, crÃ©ditos, BI, y Customer 360.

**Ãšltima actualizaciÃ³n:** 2026-05-20  
**VersiÃ³n operativa:** v2.0 (cerrado) + **cierre mÃ³dulos v3** + **SD-1** (go-live Santo Domingo)  
**LÃ­neas `app.py`:** ~20.570 (monolito; rutas tambiÃ©n en `blueprints/*`)  
**Paquete `core/`:** ~974 lÃ­neas (venta/cobro/stock post-cobro â€” Clean Architecture ligera)  
**Suite de tests:** ~289 tests (`pytest tests/ --collect-only`)  

**DocumentaciÃ³n complementaria (no duplicar aquÃ­):**

| Tipo | DÃ³nde |
|------|--------|
| Planes producto, SD-1, comercial, agentes | [`docs/planes/README.md`](planes/README.md) |
| Ãndice fases (SD-, POS-, TEC-, CORE-, LX-, IA-, META-) | [`docs/planes/00-alineacion/PLAN_INDICE_LHEXIA.md`](planes/00-alineacion/PLAN_INDICE_LHEXIA.md) |
| Memoria viva sesiones | [`docs/memory.md`](memory.md) |
| Rendimiento BD (~4k SKU, 6 estaciones) | [`docs/planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md`](planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md) |

---

## 1. Stack tecnolÃ³gico

| Componente | TecnologÃ­a |
|---|---|
| Backend | **Python 3.14**, Flask, Flask-SQLAlchemy, Flask-Login |
| BD producciÃ³n | PostgreSQL (Neon/Render) |
| BD desarrollo / QA | **PostgreSQL local** (recomendado; suite `pytest`). Sigue existiendo driver **MySQL (PyMySQL)** para entornos legacy. |
| ORM | SQLAlchemy (modelos en `app.py`) |
| Frontend | Jinja2 + Bootstrap 5 + Font Awesome + CSS propio (`design-system.css`) |
| JS interactivo | Vanilla JS (`pos.js`, timers SLA, etc.) |
| IA | OpenAI Whisper (transcripciÃ³n voz), GPT-4o-mini (parsing comandos bodega), OCR facturas |
| Reportes | pandas + openpyxl (Excel), pdfkit (PDF), QR codes |
| Deploy | Gunicorn en Render (`render.yaml`: plan **standard**, 1 worker Ã— **6 threads**); BD Neon con pooler |
| WhatsApp | API Cloud (cobranza, alertas) |
| Notificaciones | Slack webhooks (alertas operativas) |

### Dependencias (`requirements.txt`)

```
Flask, Flask-SQLAlchemy, Flask-Login, SQLAlchemy, PyMySQL
gunicorn, psycopg2-binary, pandas, openpyxl
qrcode, Pillow, PyMuPDF, pdfkit, requests
```

---

## 2. Arquitectura del repositorio

```
sistema_ventas_limpio/
â”œâ”€â”€ app.py                    # App Flask monolÃ­tica (modelos + rutas + lÃ³gica)
â”œâ”€â”€ init_db.py                # Sync esquema + roles base + admin bootstrap
â”œâ”€â”€ schema_sync.py            # SincronizaciÃ³n modelos â†” BD
â”œâ”€â”€ requirements.txt          # Dependencias Python
â”œâ”€â”€ render.yaml               # Config deploy (gunicorn app:app)
â”œâ”€â”€ memory.md                 # Memoria viva (Cursor: @memory.md); copia en docs/memory.md
â”‚
â”œâ”€â”€ blueprints/               # Registro vÃ­a add_url_rule (no decoradores @route)
â”‚   â”œâ”€â”€ bodega.py             #   ~12 reglas (despacho, plataforma, voz, SLA, TV)
â”‚   â”œâ”€â”€ caja.py               #   ~15 reglas (cobro, cambios, saldos, cierres, limpiar cola)
â”‚   â”œâ”€â”€ pos.py                #   ~22 reglas (POS, command deck, experience wall, live wall, APIs /api/pos/*)
â”‚   â””â”€â”€ c360.py               #   ~10 reglas (Customer 360, IA, ofertas proactivas)
â”‚
â”œâ”€â”€ services/                 # LÃ³gica de negocio extraÃ­da
â”‚   â”œâ”€â”€ stock_service.py      #   Stock multi-almacÃ©n, invariante, reversiÃ³n bodega
â”‚   â”œâ”€â”€ kardex_service.py     #   Movimientos kardex, bitÃ¡coras costo/precio
â”‚   â”œâ”€â”€ venta_service.py      #   transaccion_critica() context manager
â”‚   â”œâ”€â”€ pos_busqueda_service.py      # SemÃ¡foro POS, enriquecimiento bÃºsqueda
â”‚   â”œâ”€â”€ pos_compromiso_entrega_service.py
â”‚   â”œâ”€â”€ whatsapp_service.py   #   WhatsApp Cloud API (cobranza, alertas)
â”‚   â”œâ”€â”€ audit_service.py      #   erp_audit_log (eventos crÃ­ticos)
â”‚   â”œâ”€â”€ unidades_service.py   #   Unidades de medida, factores conversiÃ³n
â”‚   â”œâ”€â”€ c360_service.py       #   Customer 360, predicciÃ³n compra, scoring
â”‚   â”œâ”€â”€ sistema_health_service.py  # GET /api/sistema/salud
â”‚   â”œâ”€â”€ facturacion_electronica_service.py  # FE Chile: XML, firma PKCS#12, post-cobro, cola DTE
â”‚   â”œâ”€â”€ facturacion_caf_service.py          # Parseo e inserciÃ³n CAF (folios SII)
â”‚   â”œâ”€â”€ facturacion_dte_storage.py          # Persistencia XML firmado en storage/dtes/emitidos/
â”‚   â””â”€â”€ facturacion_sii_certificacion.py    # Set de prueba certificaciÃ³n SII (XML casos 33/39/61)
â”‚
â”œâ”€â”€ core/                     # Dominio + casos de uso (CORE-1.x, post TEC-1)
â”‚   â”œâ”€â”€ domain/venta/         #   Entidades, value objects, excepciones
â”‚   â”œâ”€â”€ application/ventas/   #   Emitir/cobrar, post-cobro saldo favor
â”‚   â”œâ”€â”€ application/creditos/
â”‚   â”œâ”€â”€ application/inventario/  # Stock al cobro
â”‚   â””â”€â”€ infrastructure/       #   Repositorios y adapters hacia services/ORM
â”‚
â”œâ”€â”€ templates/                # 89 templates Jinja2
â”‚   â”œâ”€â”€ base.html             #   Layout principal (sidebar dinÃ¡mico por permisos)
â”‚   â”œâ”€â”€ base_tv.html          #   Layout kiosk/TV (auto-refresh 30s)
â”‚   â”œâ”€â”€ base_movil.html       #   Layout mobile
â”‚   â”œâ”€â”€ punto_venta.html      #   POS completo
â”‚   â”œâ”€â”€ caja_pendientes.html  #   Cola de cobro
â”‚   â””â”€â”€ ...                   #   (89 archivos total)
â”‚
â”œâ”€â”€ static/                   # CSS, JS, logos, imÃ¡genes
â”‚   â”œâ”€â”€ design-system.css     #   Sistema de diseÃ±o propio
â”‚   â”œâ”€â”€ pos.js                #   LÃ³gica POS principal
â”‚   â”œâ”€â”€ pos-command-deck.js   #   Command Deck (layout cajero)
â”‚   â”œâ”€â”€ pos-live-wall-*.js    #   Live Wall staff / cliente
â”‚   â””â”€â”€ pos-experience-wall.js
â”‚
â”œâ”€â”€ sql/                      # ~40+ migraciones SQL incrementales
â”‚   â””â”€â”€ 2026_MM_DD_*.sql      #   Incl. 2026_05_21_rendimiento_sd1_postgresql.sql (Ã­ndices POS/caja/bodega)
â”‚
â”œâ”€â”€ scripts/                  # Utilidades, seeds y sync BD
â”‚   â”œâ”€â”€ sync_local_neon_render.py  # Migraciones + copia localâ†’Neon + verificaciÃ³n conteos (`--verify-only`)
â”‚   â”œâ”€â”€ sync_postgres_db.py        #   Tablas, FK, orden topolÃ³gico (usado por el sync)
â”‚   â”œâ”€â”€ seed_demo_data.py          #   Datos demo
â”‚   â””â”€â”€ smoke_alertas_vales_despacho.py
â”‚
â”œâ”€â”€ data/                     # JSON runtime
â”‚   â”œâ”€â”€ empresa_config.json   #   Config empresa (mÃ³dulos, datos fiscales)
â”‚   â””â”€â”€ proveedores_config.json
â”‚
â””â”€â”€ docs/                     # DocumentaciÃ³n tÃ©cnica + planes
    â”œâ”€â”€ ERP_MAESTRO.md        #   â† ESTE DOCUMENTO (mapa tÃ©cnico del sistema)
    â”œâ”€â”€ memory.md             #   Memoria viva Cursor (sincronizada con raÃ­z si aplica)
    â”œâ”€â”€ FLUJOS_CRITICOS.md    #   Secuencias que no romper
    â”œâ”€â”€ MIGRACION_RENDER_NEON.md
    â”œâ”€â”€ CASUISTICAS_PRUEBAS.md
    â””â”€â”€ planes/               #   PlanificaciÃ³n producto / SD-1 / tÃ©cnico (carpetas 00â€“07)
        â”œâ”€â”€ README.md
        â”œâ”€â”€ 00-alineacion/    #   PLAN_INDICE, MEMORY_GROK, ritmo equipo
        â”œâ”€â”€ 01-entrega-santo-domingo/
        â”œâ”€â”€ 02-producto-lhexia/
        â”œâ”€â”€ 03-pos-vendedor/
        â”œâ”€â”€ 04-tecnico/       #   TEC, CORE, ESTADO_OPTIMIZACION_APP, PLAN_RENDIMIENTO_BD_SD1
        â”œâ”€â”€ 05-modulos-backlog/
        â”œâ”€â”€ 06-agentes-ia/
        â””â”€â”€ 07-agentes-meta-desarrollo/
```

> Rutas antiguas en `docs/` raÃ­z (p. ej. `BODEGA_ULTRA_PREMIUM.md`) pueden tener stub **Â«MovidoÂ»** â†’ ver `docs/planes/`.

---

## 3. Modelos de datos (40 tablas)

### NÃºcleo comercial

| Modelo | Tabla | Dominio |
|---|---|---|
| `Venta` | `ventas` | Ventas, vales POS; estados: Abierta â†’ Pendiente â†’ Pagado / Anulada |
| `DetalleVenta` | `detalle_ventas` | LÃ­neas de venta (producto, cantidad, precio, descuento) |
| `VentaCuotaCredito` | `ventas_cuotas_credito` | Plan cuotas 30/60/90 |
| `Cotizacion` | `cotizaciones` | Cotizaciones comerciales |
| `CotizacionDetalle` | `cotizacion_detalles` | LÃ­neas de cotizaciÃ³n |
| `AbonoCredito` | `abonos_credito` | Pagos parciales a cuentas crÃ©dito |

### Caja y pagos

| Modelo | Tabla | Dominio |
|---|---|---|
| `Caja` | `cajas` | Apertura/cierre de caja, arqueo |
| `MovimientoCaja` | `movimiento_cajas` | Ingresos/egresos, cuadratura |
| `CambioOperacion` | `cambio_operaciones` | Devoluciones y cambios |
| `CambioDetalle` | `cambio_detalles` | LÃ­neas de cambio |
| `ClienteSaldoFavor` | `cliente_saldo_favor` | Saldo a favor del cliente |
| `MovimientoSaldoFavor` | `movimiento_saldo_favor` | Historial saldos a favor |

### Inventario y abastecimiento

| Modelo | Tabla | Dominio |
|---|---|---|
| `Producto` | `productos` | Maestro SKU, precios, unidades, ubicaciÃ³n |
| `Almacen` | `almacenes` | Multi-almacÃ©n (tienda, bodega, etc.) |
| `StockPorAlmacen` | `stock_por_almacen` | Stock por SKU por almacÃ©n |
| `CatalogoCategoria` | `catalogo_categorias` | CategorÃ­as jerÃ¡rquicas |
| `CatalogoSubcategoria` | `catalogo_subcategorias` | SubcategorÃ­as nivel 2 |
| `UnidadMedida` | `unidades_medida` | Unidades (kg, mt, un, etc.) |
| `ConversionUnidad` | `conversiones_unidad` | Factores de conversiÃ³n |
| `MovimientoInventario` | `movimientos_inventario` | Kardex (entradas/salidas) |
| `BitacoraCostoCompra` | `bitacora_costos_compra` | Historial costos |
| `BitacoraPrecioVenta` | `bitacora_precios_venta` | Historial precios venta |
| `AuditoriaInventario` | `auditorias_inventario` | Tomas de inventario |
| `DetalleAuditoria` | `detalles_auditoria` | LÃ­neas de auditorÃ­a |

### Compras y recepciones

| Modelo | Tabla | Dominio |
|---|---|---|
| `Proveedor` | `proveedores` | Maestro proveedores |
| `OrdenCompra` | `ordenes_compra` | Ã“rdenes de compra |
| `DetalleOrdenCompra` | `detalle_ordenes_compra` | LÃ­neas OC |
| `RecepcionCompra` | `recepciones_compra` | RecepciÃ³n de mercaderÃ­a |
| `DetalleRecepcion` | `detalles_recepcion` | LÃ­neas recepciÃ³n |

### Clientes y crÃ©dito

| Modelo | Tabla | Dominio |
|---|---|---|
| `Cliente` | `clientes` | Maestro clientes, RUT, crÃ©dito |
| `EnrolamientoTomaSesion` | `enrolamiento_toma_sesiones` | Sesiones de toma fÃ­sica |
| `EnrolamientoTomaLinea` | `enrolamiento_toma_lineas` | LÃ­neas escaneadas |

### Seguridad y auditorÃ­a

| Modelo | Tabla | Dominio |
|---|---|---|
| `Rol` | `roles` | Roles del sistema |
| `Permiso` | `permisos` | CatÃ¡logo de permisos |
| `RolPermiso` | `rol_permisos` | AsignaciÃ³n rol â†” permiso |
| `ErpAuditLog` | `erp_audit_log` | Log de auditorÃ­a (eventos crÃ­ticos) |

### Customer 360 e IA

| Modelo | Tabla | Dominio |
|---|---|---|
| `C360LlamadaSnapshotDia` | `c360_llamadas_snapshot_dia` | Snapshot diario de llamadas |
| `C360ProactivaOferta` | `c360_proactiva_ofertas` | Ofertas proactivas IA |
| `CobranzaRecordatorioWhatsappLog` | `cobranza_recordatorio_wa_log` | Log envÃ­os WA cobranza |
| `ReabastoClienteWaLog` | `reabasto_cliente_wa_log` | Log WA reabastecimiento |

---

## 4. Rutas HTTP (~150+ endpoints, orden de magnitud)

**~100** handlers con `@app.route` / `@app.get|post` en `app.py` + **~59** reglas vÃ­a `add_url_rule` en `blueprints/*` (conteos cambian con el tiempo; ver cÃ³digo).

### 4.1 PÃºblico y landing

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET | `/`, `/index` | Landing page |
| GET | `/healthz` | Health check |
| POST | `/api/landing/lead` | Captura leads |
| GET | `/catalogo` | CatÃ¡logo pÃºblico |
| GET | `/consulta-stock` | Consulta stock pÃºblico |

### 4.2 AutenticaciÃ³n

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET/POST | `/login` | Login (redirige segÃºn perfil) |
| GET | `/logout` | Confirma si caja abierta antes de salir |
| POST | `/logout/forzar` | Logout sin cerrar caja |
| GET/POST | `/cambiar_password` | Cambio contraseÃ±a (forzado si temporal) |

### 4.3 Home y dashboards

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET | `/inicio` | Dashboard principal (KPIs) |
| GET | `/owner-mobile` | Vista ejecutiva mobile-first |
| GET | `/ayuda` | Centro de ayuda |

### 4.4 Punto de venta (POS)

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/punto_venta` | Pantalla POS | `pos_emitir_vale` |
| POST | `/agregar_producto_venta` | Agregar lÃ­nea al carrito | `pos_emitir_vale` |
| POST | `/actualizar_item` | Modificar cantidad/precio | `pos_emitir_vale` |
| POST | `/eliminar_detalle` | Quitar lÃ­nea | `pos_emitir_vale` |
| POST | `/finalizar_venta` | Emitir vale Pendiente | `pos_emitir_vale` |
| GET | `/buscar_producto` | BÃºsqueda por cÃ³digo/nombre | â€” |
| POST | `/pos/usuarios_autorizar_descuento` | Autorizar descuento | `autorizar_descuento_pos` |

**Registro centralizado:** muchas de estas URLs (y APIs `/api/pos/*`, `/pos/command-deck`, `/pos/experience-wall`, ticket vale, despacho, cross-sell, foto producto, etc.) viven en `blueprints/pos.py` â†’ `register_pos_routes()`.

### 4.5 Caja

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/caja/vales_pendientes` | Cola de cobro | `caja_cobrar_vale` |
| POST | `/procesar_cobro_caja` | Cobrar vale | `caja_cobrar_vale` |
| POST | `/caja/vales/<id>/anular` | Anular vale | `anular_vale_caja` |
| GET | `/abrir_caja` | Apertura de caja | `caja_abrir` |
| GET/POST | `/movimiento_caja` | Ingresos/egresos | `caja_movimientos` |
| GET/POST | `/cerrar_caja` | Cierre y cuadratura | `caja_cerrar` |
| GET | `/caja/historial_cierres` | HistÃ³rico cierres | `gestionar_usuarios` |
| GET | `/caja/cambios` | Cambios/devoluciones | `caja_cobrar_vale` |
| GET | `/caja/cambios/historial` | Historial cambios | `caja_cobrar_vale` |
| GET | `/caja/saldos-favor` | Saldos a favor | `caja_cobrar_vale` |

### 4.6 Inventario y productos

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/productos` | CatÃ¡logo productos | `ver_inventario` |
| POST | `/productos/<id>/editar_stock` | Ajuste stock unitario | `admin_inventario` |
| POST | `/productos/stock_masivo` | Ajuste stock masivo | `admin_inventario` |
| POST | `/cargar_productos` | Importar CSV/Excel | `admin_inventario` |
| GET | `/stock/critico` | Stock bajo mÃ­nimo | `ver_inventario` |
| GET | `/kardex` | Movimientos kardex | `ver_inventario` |
| GET | `/consulta-stock` | Consulta rÃ¡pida | â€” (pÃºblico) |
| GET | `/inventario/enrolamiento` | Toma fÃ­sica | `enrolamiento_inventario` |
| GET | `/inventario/salud` | Salud del inventario | `enrolamiento_inventario` |

### 4.7 Bodega

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/bodega/cuadro-mando` | Dashboard bodega (KPIs, SLA) | `bodega_operador` |
| GET | `/bodega/cuadro-mando/tv` | Modo TV/kiosk (auto-refresh) | `bodega_operador` |
| GET | `/bodega/plataforma` | Plataforma operativa retiro | `bodega_operador` |
| GET | `/bodega/vale/<id>` | Detalle vale retiro | `bodega_operador` |
| GET | `/bodega/despachos` | Despacho por voz (IA) | `bodega_operador` |
| POST | `/api/bodega/voice-command` | API transcripciÃ³n + ejecuciÃ³n voz | `bodega_operador` |
| GET | `/bodega/export-dia` | Export CSV del dÃ­a | `bodega_operador` |

### 4.8 Compras y recepciones

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/compras/ordenes` | Lista Ã³rdenes compra | `gestionar_compras` |
| GET/POST | `/compras/ordenes/nueva` | Nueva OC | `gestionar_compras` |
| GET | `/compras/ordenes/<id>/editar` | Editar OC | `gestionar_compras` |
| GET | `/recepciones` | Lista recepciones | `gestionar_compras` |
| GET/POST | `/recepciones/nueva` | Nueva recepciÃ³n | `gestionar_compras` |
| GET | `/recepciones/<id>` | Detalle recepciÃ³n | `gestionar_compras` |
| GET | `/proveedores` | Maestro proveedores | `gestionar_compras` |

### 4.9 CrÃ©ditos y cobranza

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET | `/creditos` | MÃ³dulo crÃ©ditos |
| GET | `/creditos/estado_cuenta/<id>` | Estado de cuenta HTML |
| GET | `/creditos/estado_cuenta/<id>/pdf` | Estado de cuenta PDF |
| POST | `/registrar_abono` | Registrar abono |
| GET | `/ticket_abono/<id>` | Ticket de abono |
| GET | `/cobranza/cuotas` | Cobranza WA cuotas |

### 4.10 Cotizaciones

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET | `/cotizaciones` | Lista cotizaciones |
| GET/POST | `/cotizaciones/nueva` | Nueva cotizaciÃ³n |
| GET | `/cotizaciones/<id>` | Detalle |
| POST | `/cotizaciones/<id>/convertir` | Convertir a venta POS |
| GET | `/cotizaciones/<id>/pdf` | PDF cotizaciÃ³n |

### 4.11 BI y gerencia

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET | `/bi` | BI reportes | `ver_gerencia` |
| GET | `/gerencia/informes-dueno` | Panel ejecutivo | `panel_gerencia` |
| GET | `/gerencia/simulador-margen` | Simulador margen | `panel_gerencia` |
| GET | `/bi/demo/alertas-precio-premium` | Alertas de precio | `panel_gerencia` |
| GET | `/gerencia/c360/ia-dashboard` | Customer 360 IA | `panel_gerencia` |
| GET | `/precios/revision` | RevisiÃ³n precios | `revision_precios` |
| GET | `/bi/export.csv` | Export ventas CSV | â€” |
| GET | `/ia_abastecimiento` | IA sugerencias compra | â€” |

### 4.12 AdministraciÃ³n

| MÃ©todo | Ruta | FunciÃ³n | Permiso |
|---|---|---|---|
| GET/POST | `/admin/empresa` | Datos empresa + mÃ³dulos | `gestionar_usuarios` |
| GET/POST | `/admin/almacenes` | Almacenes | `gestionar_usuarios` |
| GET/POST | `/admin/clientes` | Clientes | `gestionar_usuarios` |
| GET/POST | `/admin/roles-permisos` | Roles y permisos | `gestionar_usuarios` |
| GET/POST | `/admin/unidades` | Unidades medida | `gestionar_usuarios` |
| GET/POST | `/admin/catalogo` | CategorÃ­as | `gestionar_usuarios` |
| GET | `/usuarios` | Lista usuarios | `gestionar_usuarios` |
| GET/POST | `/admin/facturacion/caf` | Carga CAF (folios SII) | `gestionar_usuarios` |
| GET | `/admin/facturacion/cola` | Cola DTE (estados, descarga XML) | `gestionar_usuarios` |
| GET | `/admin/facturacion/dte-xml/<venta_id>` | Descarga XML firmado guardado | `gestionar_usuarios` |
| POST | `/admin/facturacion/reintentar/<venta_id>` | Reintento emisiÃ³n FE (HTML redirect) | `gestionar_usuarios` |
| GET/POST | `/api/admin/facturacion/emitir-prueba` | XML mock / set certificaciÃ³n SII | `gestionar_usuarios` |
| GET | `/api/admin/facturacion/diagnostico-sii` | Semilla + token SII (sin subir DTE) | `gestionar_usuarios` |
| GET/POST | `/api/admin/facturacion/cafs` | API CAF | `gestionar_usuarios` |
| POST | `/api/admin/facturacion/reintentar/<venta_id>` | API reintento FE | `gestionar_usuarios` |

### 4.13 FacturaciÃ³n electrÃ³nica (Chile / SII) â€” Fase 1 operativa ERP

| Componente | Estado | Notas |
|---|---|---|
| Tabla `cafs` + columnas DTE en `ventas` | âœ… | Auto-migraciÃ³n `_asegurar_tabla_cafs_y_columnas_ventas_fe()` |
| Carga CAF (admin) | âœ… | UI + API; rango folios 33/39 |
| Post-cobro FE | âœ… | Tras `procesar_cobro_caja` (no crÃ©dito): folio CAF, XML, firma, estado |
| Persistencia XML | âœ… | `storage/dtes/emitidos/{certificacion\|produccion}/V{id}_T{tipo}_F{folio}.xml` |
| Cola / reintento | âœ… | `PENDIENTE_ENVIO` si SOAP stub; panel cola + API reintento |
| Firma PKCS#12 | âœ… | `SII_CERT_PFX_PATH`, password o `SII_CERT_PFX_PASSWORD_FILE`; signxml 4.x (`cert=[certificate]`) |
| EnvÃ­o SOAP SII real | ðŸŸ¡ | `facturacion_sii_soap.py` (semilla/token/upload Palena/MaullÃ­n); activar `SII_SOAP_ENABLED=1`; falta TED+XSD para `STATUS=0` |
| TED timbre CAF | ðŸŸ¡ | `facturacion_ted_service.py` (RSASK + FRMT); requiere CAF real con RSASK en BD |
| CertificaciÃ³n SII oficial | â³ | Set casos en `storage/dtes/pruebas_sii/` vÃ­a `emitir-prueba?modo=set_certificacion` |

**Variables de entorno:** `SII_CERT_PFX_PATH`, `SII_CERT_PFX_PASSWORD` o `SII_CERT_PFX_PASSWORD_FILE`, `SII_AMBIENTE` (`certificacion` \| `produccion`).

**PolÃ­tica:** el cobro **no se revierte** si falla FE; la venta queda en cola para reintento.

### 4.14 POS Live Wall / Experience Wall (segundo monitor / TV cliente)

| Ruta | FunciÃ³n |
|---|---|
| GET `/pos/live-wall/staff` | Panel cajero/vendedor: KPIs tienda + cola bodega |
| GET `/pos/live-wall/cliente` | TV cliente CFM v2 (layout 50/50 carrito \| recomendaciones) |
| GET `/pos/experience-wall` | Alias TV con `?token=` firmado |
| GET `/api/pos/live-wall/snapshot` | JSON: lÃ­neas, total, `cliente_vitrina`, `recomendaciones`, `vale_emitido` |

**AutenticaciÃ³n snapshot:** sesiÃ³n staff (`session['_user_id']`) o token `itsdangerous` (`pos_live_wall_token_create` / `pos_live_wall_token_create_station`). TTL configurable vÃ­a env.

**Recomendaciones TV (`recomendaciones` en JSON):**

| Campo | DescripciÃ³n |
|-------|-------------|
| `titulo` | Ej. Â«Complementos para su fijaciÃ³nÂ» |
| `subtitulo` | Con `{ancla}` resuelto (Â«los clavosÂ», Â«los tornillosÂ», â€¦) |
| `items[]` | Hasta 4: `id`, `nombre`, `precio`, `imagen_url`, `motivo` |

**Motor backend:** `app.py` â†’ `_pos_live_wall_recomendaciones_tv(venta)`:

- Perfiles: `_POS_TV_PERFIL_FIJACION`, `_OBRA`, `_PINTURA`, `_PVC`, `_MADERA`, `_GENERAL`.
- Contexto: `_pos_tv_contexto_carrito` (familias, ticket bajo/medio, `permite_electrico_caro`).
- Pick producto: `_pos_tv_pick_coherente` (score + tope precio + exclusiÃ³n elÃ©ctricas caras).
- Reglas JSON POS: `data/cross_sell_associations.json` + `_pos_cross_sell_match_rules` (refuerzo obra/PVC/pintura; regla `fijacion_herramientas_manual`).

**Frontend TV:** `static/js/pos-experience-wall.js` (`renderCfmRecommendations`, `recoPaintKey` anti-parpadeo); `static/css/pos-experience-wall-cfm.css` (grid 2Ã—2, tarjetas con imagen/nombre/motivo/precio/botÃ³n). Cache bust en template: `?v=lhexia20260520reco2`.

**Tests:** `tests/test_pos_live_wall.py` (smoke; incluye coherencia clavo sin taladros).

**Admin descuentos (relacionado POS):** GET `/admin/pos-autorizacion-descuentos` â€” tarjeta supervisor LHX-SUP; servicio `services/pos_autorizacion_descuento_service.py`; DDL `sql/2026_05_18_pos_autorizacion_descuento.sql`.

**Cierre caja (2026-05-20):** arqueo solo ventas `Pagado` (`_venta_cuenta_en_cuadre_caja`); `confirmar_cierre.html` anti-autofill email en monto contado.

### 4.15 Caja â€” limpieza cola cierre

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| POST | `/caja/limpiar_cola_cierre` | Admin: anula en lote vales **Pendiente** sin mÃ©todo + borradores **Abierta** de la caja abierta (no borra filas; auditorÃ­a). UI en `confirmar_cierre.html`. |

### 4.16 APIs internas

| MÃ©todo | Ruta | FunciÃ³n |
|---|---|---|
| GET | `/api/sistema/salud` | Health check detallado |
| POST | `/api/ventas/alertas-despachos-pendientes` | Cron alertas vales riesgo |
| GET | `/api/buscar_producto/<codigo>` | BÃºsqueda por cÃ³digo |
| POST | `/api/guardar_conteo_inventario` | Guardar conteo auditorÃ­a |

---

## 5. Sistema de permisos (RBAC v2)

### 5.1 CatÃ¡logo de permisos

```
gestionar_usuarios        admin_inventario          enrolamiento_inventario
panel_gerencia           anular_vale_caja          autorizar_descuento_pos
revision_precios         pos_emitir_vale           caja_cobrar_vale
caja_abrir               caja_movimientos          caja_cerrar
bodega_operador          ver_inventario            ver_gerencia
gestionar_compras        ver_auditoria
```

### 5.2 Perfiles de rol predefinidos

| Rol | Permisos |
|---|---|
| **Vendedor/a** | `pos_emitir_vale` |
| **Cajera/o** | `pos_emitir_vale`, `caja_cobrar_vale`, `caja_abrir`, `caja_movimientos`, `caja_cerrar` |
| **Supervisor / Encargado** | Todo cajera + `anular_vale_caja`, `autorizar_descuento_pos`, `ver_inventario` |
| **Bodeguero/a** | `bodega_operador`, `ver_inventario` |
| **Gerente** | `ver_gerencia`, `panel_gerencia`, `revision_precios`, `ver_inventario`, `gestionar_compras`, `ver_auditoria` |
| **DueÃ±o** | Todo gerente + `gestionar_usuarios` |
| **Admin** | Todos (bypass automÃ¡tico) |

### 5.3 NavegaciÃ³n centralizada (`_NAV_MAP`)

Mapa declarativo en `app.py` que define grupos de menÃº, Ã­tems, permisos requeridos y endpoints activos. La funciÃ³n `_construir_nav_usuario()` filtra en runtime segÃºn permisos del usuario autenticado e inyecta `nav_menu` vÃ­a context_processor. El sidebar de `base.html` itera `nav_menu` (~15 lÃ­neas Jinja).

### 5.4 Capas de control de acceso

```
Capa 1: Empresa    â†’ modulo_activo()         â†’ "Â¿MÃ³dulo habilitado?" (admin_empresa)
Capa 2: Rol        â†’ mapa_por_rol            â†’ "Â¿QuÃ© permisos tiene?" (admin_roles_permisos)
Capa 3: Ruta       â†’ @permisos_required      â†’ "Â¿Puede entrar?" (decorador)
Capa 4: Contexto   â†’ @caja_requerida         â†’ "Â¿Tiene caja abierta?" (decorador)
Capa 5: MenÃº       â†’ _construir_nav_usuario  â†’ "Â¿QuÃ© ve?" (automÃ¡tico)
```

### 5.5 RedirecciÃ³n inteligente al login

```
Admin / DueÃ±o / Gerente  â†’  /owner-mobile      (panel ejecutivo)
Bodeguero (sin caja)     â†’  /bodega/plataforma  (operaciÃ³n bodega)
Cajera / Cajero          â†’  /caja/vales_pendientes (cola cobro)
Vendedor / MesÃ³n         â†’  /punto_venta         (POS directo)
Otro                     â†’  /inicio              (dashboard general)
```

---

## 6. MÃ³dulos activables por empresa

Configurados en **Mantenedores > Datos de empresa** (`/admin/empresa`), almacenados en `data/empresa_config.json`:

| Flag | MÃ³dulo | Controla |
|---|---|---|
| `mod_ventas` | Ventas | POS, cotizaciones, historial ventas |
| `mod_caja` | Caja | Cobro, apertura/cierre, movimientos |
| `mod_inventario` | Inventario | Productos, bodega, compras, recepciones |
| `mod_bi` | BI y anÃ¡lisis | Reportes, revisiÃ³n precios |
| `mod_ia` | IA | Abastecimiento inteligente, OCR facturas |

---

## 7. Flujos de negocio crÃ­ticos

### 7.1 Venta POS (flujo principal)

```
[Vendedor]                    [Cajera]                    [Bodeguero]
    â”‚                             â”‚                            â”‚
    â”œâ”€ Abre POS (/punto_venta)    â”‚                            â”‚
    â”œâ”€ Busca producto (cÃ³digo)    â”‚                            â”‚
    â”œâ”€ Agrega lÃ­neas al carrito   â”‚                            â”‚
    â”œâ”€ Finaliza â†’ vale PENDIENTE  â”‚                            â”‚
    â”‚  (no descuenta stock aÃºn)   â”‚                            â”‚
    â”‚                             â”œâ”€ Ve vale en cola           â”‚
    â”‚                             â”œâ”€ Cobra â†’ estado PAGADO     â”‚
    â”‚                             â”‚  (descuenta stock + kardex) â”‚
    â”‚                             â”‚                            â”œâ”€ Ve en plataforma
    â”‚                             â”‚                            â”œâ”€ Despacha (voz IA)
    â”‚                             â”‚                            â””â”€ Cierra retiro
```

### 7.2 Flujo de cobro (procesar_cobro_caja)

```
1. Valida stock disponible (invariante)
2. Abre transaccion_critica() [savepoint]
3. Actualiza venta â†’ PAGADO
4. Descuenta stock tienda (almacÃ©n)
5. Registra kardex (SALIDA)
6. Registra movimiento caja
7. Si crÃ©dito: actualiza saldo_deudor + cuotas
8. Si saldo a favor: aplica descuento
9. audit_log("cobro_vale_caja")
10. Commit
11. WhatsApp (post-commit, fuera de transacciÃ³n)
```

### 7.3 Bodega â€” Despacho por voz (IA)

```
1. Bodeguero habla al micrÃ³fono
2. OpenAI Whisper â†’ transcripciÃ³n texto
3. GPT-4o-mini â†’ parsing JSON {vale, producto, cantidad}
4. transaccion_critica():
   - Valida vale + producto + stock bodega
   - Actualiza bodega_despacho_json
   - Mueve stock bodega â†’ tienda
   - Kardex SALIDA bodega + ENTRADA tienda
   - Valida invariante
5. Commit
```

### 7.4 Medios de pago

| Medio | Tipo | Descuenta stock |
|---|---|---|
| `Efectivo` | Inmediato | SÃ­, al cobrar |
| `Debito` | Inmediato | SÃ­, al cobrar |
| `TarjetaCredito` | Inmediato (TC bancaria) | SÃ­, al cobrar |
| `Transferencia` | Inmediato | SÃ­, al cobrar |
| `Credito` | Fiado tienda | SÃ­, al cobrar (queda Pendiente) |

### 7.5 SLA Bodega (prioridad inteligente)

Tiempos en minutos para indicadores de color:

| Estado | Normal | AtenciÃ³n | Urgente |
|---|---|---|---|
| PENDIENTE | <5 | 5-10 | >20 |
| EN_PREPARACION | <10 | 10-20 | >40 |
| ENTREGA_PARCIAL | <8 | 8-15 | >30 |
| LISTO_RETIRO | <15 | 15-30 | >60 |

---

## 8. Servicios extraÃ­dos

| Servicio | Responsabilidad |
|---|---|
| `stock_service.py` | Stock multi-almacÃ©n, invariante consumo, reversiÃ³n bodega, disponibilidad POS |
| `kardex_service.py` | Registro movimientos, bitÃ¡coras costo/precio |
| `venta_service.py` | `transaccion_critica()` (savepoint con rollback atÃ³mico) |
| `whatsapp_service.py` | EnvÃ­o mensajes WA Cloud API |
| `audit_service.py` | `_audit_log()` â†’ tabla `erp_audit_log` |
| `unidades_service.py` | Factores conversiÃ³n ventaâ†”stockâ†”compra |
| `c360_service.py` | Motor Customer 360, predicciÃ³n compra, scoring |
| `sistema_health_service.py` | Health check (`/api/sistema/salud`) |
| `facturacion_electronica_service.py` | FE Chile: XML, firma PKCS#12, post-cobro, cola DTE |
| `facturacion_caf_service.py` | CAF SII: parseo e inserciÃ³n de folios |
| `facturacion_dte_storage.py` | Persistencia XML firmado bajo `storage/dtes/emitidos/` |

---

## 9. Blueprints registrados

| Blueprint | Reglas URL (`add_url_rule`) | Dominio |
|---|---|---|
| `blueprints/bodega.py` | ~12 | Plataforma retiro, despacho voz, cuadro mando, SLA, TV, export |
| `blueprints/caja.py` | ~15 | Cobro, anulaciÃ³n, cambios, saldos, cierres, limpiar cola, tickets |
| `blueprints/pos.py` | ~22 | POS, command deck, experience wall, live wall, ticket/despacho, APIs `/api/pos/*` |
| `blueprints/c360.py` | ~10 | Customer 360, dashboard IA, ofertas proactivas |

---

## 10. Migraciones SQL (~39 archivos)

Formato: `sql/YYYY_MM_DD_descripcion.sql`

Principales:
- Stock por almacÃ©n, kardex, recepciones, unidades de medida
- CatÃ¡logo categorÃ­as (2 niveles), productos (ubicaciÃ³n, unidades)
- Clientes (RUT, giro, direcciÃ³n, crÃ©dito), cotizaciones
- Ã“rdenes de compra, ventas (punto retiro, anulaciÃ³n, descuento)
- Caja cuadratura, cambios/saldos a favor
- Bodega retiro plataforma, cobranza WA, cuotas crÃ©dito
- Customer 360 (llamadas, snapshots)
- Vistas SQL: vales riesgo despacho (PostgreSQL + MySQL)

---

## 11. Reglas de negocio invariantes

1. **Invariante de stock:** `consumo_bodega + consumo_tienda â‰¤ consumo_total` por lÃ­nea de venta.
2. **Estados de venta:** Abierta â†’ Pendiente â†’ Pagado / Anulada (inmutable).
3. **Stock se descuenta al COBRAR**, no al emitir vale.
4. **WhatsApp siempre post-commit** (nunca dentro de transacciÃ³n).
5. **Caja obligatoria** para POS y cobro (`@caja_requerida`).
6. **Caja dÃ­a anterior:** se permite cobrar/anular vales sin cerrar, pero no abrir nuevo POS.
7. **Cliente "final"** (RUT `66.666.666-6`) para ventas sin nombre.
8. **CrÃ©dito Ãºnico plan:** `30_60_90` (3 cuotas a 30/60/90 dÃ­as corridos).
9. **AnulaciÃ³n con despacho bodega** requiere permiso especial (`anular_vale_con_despacho_bodega`).
10. **AuditorÃ­a by-default:** todo cambio crÃ­tico registrado en `erp_audit_log`.

---

## 12. ConfiguraciÃ³n y entorno

### Variables de entorno

| Variable | Uso |
|---|---|
| `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI` | ConexiÃ³n BD app (local, Render, etc.) |
| `NEON_DATABASE_URL` | **Solo scripts de sync** (`.env.local`): Postgres Neon; usar host **directo** (sin `-pooler`) para `scripts/sync_local_neon_render.py` |
| `SECRET_KEY` | Flask sessions |
| `OPENAI_API_KEY` | IA (Whisper, GPT, OCR) |
| `EMPRESA_NOMBRE_COMERCIAL` | Nombre por defecto |
| `BOOTSTRAP_ADMIN_*` | Admin inicial en init_db |
| `WHATSAPP_*` / `COBRANZA_*` | Config WA Cloud API |
| `SLACK_WEBHOOK_URL` | Alertas Slack |
| `VALE_DESPACHO_SIN_COBRO_ALERTA_HORAS` | Umbral alertas (default 48h) |
| `SII_CERT_PFX_PATH`, `SII_CERT_PFX_PASSWORD` / `SII_CERT_PFX_PASSWORD_FILE`, `SII_AMBIENTE` | FacturaciÃ³n electrÃ³nica Chile (certificado .pfx y ambiente) |

### Archivos de entorno

```
env_qa.txt      â†’ setdefault (carga si no existe var)
.env.qa         â†’ override
.env.local      â†’ desarrollo local (puede incluir DATABASE_URL + NEON_DATABASE_URL para sync)
```

### SincronizaciÃ³n Postgres local â†’ Neon (datos / QA)

Para **alinear** la base en Neon con la de tu PC (misma app en Render apuntando a esa Neon verÃ¡ los mismos datos tras el sync):

1. En `.env.local`: `DATABASE_URL` = Postgres local; `NEON_DATABASE_URL` = cadena Neon (**host directo**, `sslmode=require`; el pooler suele reservarse para la app en producciÃ³n).
2. **Pausar** servicios que escriban en esa Neon (p. ej. Render) mientras corre el script; si no, los conteos suelen **divergir** tras el `commit`.
3. Desde la raÃ­z del repo:

```bash
python scripts/sync_local_neon_render.py
python scripts/sync_local_neon_render.py --verify-only
```

- El sync aplica migraciones listadas en el script, hace `TRUNCATE` en tablas comunes en destino y copia filas desde local.  
- `--verify-only` solo compara conteos en tablas clave (`TABLAS_CHECK` en el script) y termina con cÃ³digo **1** si difieren.  
- Tras un sync completo, el script **vuelve a verificar** conteos; si fallan, sale con cÃ³digo 1 e imprime sugerencias.  
- En Neon a veces aparece `permission denied ... session_replication_role`: es **esperable** en roles limitados; el flujo continÃºa sin ese bypass.

Detalle operativo: `docs/MIGRACION_RENDER_NEON.md`.

### Arranque local

```bash
python -m pip install -r requirements.txt
python app.py
```

### ProducciÃ³n

```bash
# render.yaml (referencia): plan standard, 1 worker Ã— 6 threads
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 6 --timeout 90
```

**Variables recomendadas (Render):** `DATABASE_URL` con **pooler** Neon; `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=5`, `DB_POOL_TIMEOUT=30`.

**Rendimiento ~4k SKU / 6 estaciones (4 POS + caja + bodega + TV bodega 30s):** ejecutar en Neon `sql/2026_05_21_rendimiento_sd1_postgresql.sql` y seguir [`docs/planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md`](planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md).

---

## 13. Integraciones externas

| IntegraciÃ³n | Uso | Config |
|---|---|---|
| **OpenAI Whisper** | TranscripciÃ³n voz â†’ texto (bodega) | `OPENAI_API_KEY` |
| **OpenAI GPT-4o-mini** | Parsing comandos voz, sugerencias IA | `OPENAI_API_KEY` |
| **OpenAI Vision** | OCR facturas recepciÃ³n | `OPENAI_API_KEY` |
| **WhatsApp Cloud API** | Cobranza cuotas, alertas despacho | `WHATSAPP_*` vars |
| **Slack Webhooks** | Alertas vales riesgo operativo | `SLACK_WEBHOOK_URL` |

---

## 14. Historial de hitos

| Fecha | Hito |
|---|---|
| 2026-05-08 | Memoria `memory.md` + documentaciÃ³n completa por mÃ³dulo |
| 2026-05-08 | Correcciones auditorÃ­a: reversiÃ³n stock, KPIs, ediciÃ³n ventas |
| 2026-05-08 | Caja dÃ­a anterior + cierre bloqueado + cola combined |
| 2026-05-08 | CrÃ©dito cuotas 30/60/90 + medio TarjetaCredito |
| 2026-05-08 | Roadmap Customer 360 documentado |
| 2026-05-08 | Plan v2 Grok: Fase 1A (transacciones atÃ³micas, auditorÃ­a, invariante) |
| 2026-05-08 | Fase 1B: cron alertas vales despacho + Slack + WA |
| 2026-05-08 | Servicios: stock, kardex, venta, whatsapp, audit, unidades, c360 |
| 2026-05-10 | Cierre plan v2.0: blueprints, health, carga masiva con transacciÃ³n |
| 2026-05-11 | Bodega Fase 3: SLA, ranking operador, export CSV, modo TV |
| 2026-05-11 | RBAC v2: `_NAV_MAP`, sidebar dinÃ¡mico, 17 permisos, 7 perfiles rol |
| 2026-05-11 | RedirecciÃ³n inteligente por perfil al login |
| 2026-05-11 | Fix: `grupo['items']` en Jinja2 (colisiÃ³n con `dict.items`) |
| 2026-05-12 | Suite QA v4: 43 tests e2e + rutas HTTP + coverage + CI/CD + guardia anti-prod |
| 2026-05-14 | Customer 360 P0: predicciÃ³n 21d, log predicciones, API resumen |
| 2026-05-15 | FE Fase 1 ERP: CAF, post-cobro, storage XML, cola DTE, firma signxml 4.x, tests FE |
| 2026-05-15 | POS Live Wall staff/cliente + snapshot API |
| 2026-05-15 | Caja: `POST /caja/limpiar_cola_cierre` (anulaciÃ³n masiva admin para desbloquear cierre) |
| 2026-05-16 | **Plan cierre mÃ³dulos v3** documentado (Â§18); ERP maestro + memory actualizados |
| 2026-05-16 | Sync **local â†’ Neon**: `scripts/sync_local_neon_render.py` con `--verify-only`, verificaciÃ³n post-sync (cÃ³digo salida 1 si difieren conteos), trazas con `flush`; Neon **host directo** recomendado para el script |
| 2026-05-17 | ReorganizaciÃ³n **`docs/planes/`** (00â€“07); portales LhexIA + Santo Domingo; planes IA-* y META-* |
| 2026-05-17 | **CORE-1.2â€“1.4** en `core/` (venta/cobro, stock al cobro, post-cobro crÃ©dito/saldo favor) |
| 2026-05-18 | Ritmo equipo async (`EQUIPO_RITMO_ASYNC.md`); POS-4 en `main` |
| 2026-05-21 | **Plan rendimiento BD SD-1**: Ã­ndices `pg_trgm`, `render.yaml` (standard, 6 threads), doc `PLAN_RENDIMIENTO_BD_SD1.md` |
| 2026-05-20 | **TV recomendaciones coherentes** (`4ae0292`): perfiles fijaciÃ³n/obra, cross-sell JSON, tarjetas CFM rediseÃ±adas, tests `test_recomendaciones_tv_solo_clavo_coherente` |
| 2026-05-20 | **Cierre caja**: arqueo solo `Pagado`; anti-autofill monto contado; sidebar scroll `/modulos` |
| 2026-05-20 | **SQL Neon prod**: `apply_sql_neon` â€” autorizaciÃ³n descuentos + Ã­ndices rendimiento SD-1 |

---

## 15. DocumentaciÃ³n relacionada

### TÃ©cnica (este repo, `docs/` raÃ­z)

| Documento | Contenido |
|---|---|
| `docs/ERP_MAESTRO.md` | **Este documento** â€” mapa tÃ©cnico del sistema |
| `docs/memory.md` | Memoria viva entre sesiones (Cursor) |
| `docs/FLUJOS_CRITICOS.md` | Flujos de negocio que no romper |
| `docs/MIGRACION_RENDER_NEON.md` | Deploy Render + Neon, variables, sync datos |
| `docs/CASUISTICAS_PRUEBAS.md` | Matriz QA manual |
| `docs/CASUISTICAS_VENTAS_QA.md` | CatÃ¡logo QA ventaâ†’cajaâ†’entrega (local, sin commit prod aÃºn) |
| `docs/PROMPT_MAESTRO_ERP.md` | Prompt arquitecto (legacy) |

### Planes (`docs/planes/`)

| Documento | Contenido |
|---|---|
| [`planes/README.md`](planes/README.md) | Mapa carpetas 00â€“07 |
| [`planes/00-alineacion/PLAN_INDICE_LHEXIA.md`](planes/00-alineacion/PLAN_INDICE_LHEXIA.md) | Ãndice SD-, POS-, TEC-, CORE-, LX-, IA-, META- |
| [`planes/00-alineacion/MEMORY_GROK.md`](planes/00-alineacion/MEMORY_GROK.md) | Prioridades equipo Mario Â· Grok Â· Cursor |
| [`planes/02-producto-lhexia/LHEXIA_PRODUCTO.md`](planes/02-producto-lhexia/LHEXIA_PRODUCTO.md) | Producto comercial LhexIA |
| [`planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md`](planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md) | Go-live cliente #1 |
| [`planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md`](planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md) | Refactor monolito / TEC / CORE |
| [`planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md`](planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md) | Infra rendimiento ~4k SKU |
| [`planes/04-tecnico/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md`](planes/04-tecnico/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md) | Plan TEC v2 cerrado |
| [`planes/05-modulos-backlog/BODEGA_ULTRA_PREMIUM.md`](planes/05-modulos-backlog/BODEGA_ULTRA_PREMIUM.md) | EspecificaciÃ³n bodega |
| [`planes/05-modulos-backlog/roadmap_customer_360_ferreteria_2026.md`](planes/05-modulos-backlog/roadmap_customer_360_ferreteria_2026.md) | Roadmap C360 |
| [`planes/05-modulos-backlog/manual_operacion_customer_360.md`](planes/05-modulos-backlog/manual_operacion_customer_360.md) | Manual operativo C360 |
| [`planes/06-agentes-ia/PLAN_AGENTES_IA_v1.md`](planes/06-agentes-ia/PLAN_AGENTES_IA_v1.md) | Agentes negocio 24/7 |
| [`planes/07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md`](planes/07-agentes-meta-desarrollo/PLAN_AGENTES_META_v1.md) | Agentes desarrollo producto |

---

## 17. Estrategia de Pruebas Automatizadas

### Suite End-to-End (`tests/test_end_to_end.py`)

| Escenario | Tests | Markers |
|---|---|---|
| T1 Venta completa (happy path) | 5 | smoke, happy_path |
| T2 Venta a crÃ©dito 30/60/90 | 1 | smoke, happy_path |
| T3 Compra y recepciÃ³n OC | 1 | smoke, happy_path |
| T4 Despacho bodega parcial | 1 | smoke, happy_path |
| T5 Invariantes de negocio | 5 | smoke, invariantes |
| T6 RedirecciÃ³n por perfil | 1 | smoke |
| T7 ValidaciÃ³n post-hoc | 1 | smoke, happy_path |
| T8 AnulaciÃ³n de vale (Â±bodega) | 2 | anulacion |
| T9 Stock insuficiente | 1 | edge_case |
| T10 Concurrencia doble cobro | 1 | concurrency, slow |
| T11 Despacho voz completo | 1 | happy_path, bodega |
| T12 Exceder cupo crÃ©dito | 1 | edge_case |
| T13 AnulaciÃ³n despachado | 1 | anulacion |
| T14 Rollback transaccion_critica | 2 | invariantes |
| T15 IVA y redondeos (parametrizado) | 13 | smoke, invariantes |
| T16 Carga ligera (10 ventas ThreadPool) | 1 | load, slow |
| T17 Multi-almacÃ©n (traslados) | 2 | happy_path, bodega |
| T18 AuditorÃ­a erp_audit_log | 4 | invariantes, audit |
| **Total** | **43** | |

### Suite de Rutas HTTP (`tests/test_routes.py`)

Pruebas de integraciÃ³n HTTP con Flask test_client. Cubren ~50 endpoints GET/POST sin servidor real.

### Smoke Tests (CI rÃ¡pido)

```bash
pytest tests/ -m smoke -q --tb=no    # ~77 tests con marker smoke (ver pytest --collect-only)
```

### Coverage

| MÃ©trica | Valor actual | Meta 2-3 semanas |
|---|---|---|
| `app.py` | 17% | 35-45% |
| `services/` | 29% promedio | 50%+ |
| **Comando** | `pytest tests/ --cov=app --cov=services --cov-report=term-missing` | |

### CI/CD

- **GitHub Actions**: `.github/workflows/tests.yml`
  - PR/push: smoke tests + coverage
  - Push a main: suite completa + reporte HTML + artefactos
- **Reporte HTML**: `pytest tests/ --html=docs/test_report_v4.html --self-contained-html`

### Datos de DemostraciÃ³n

```bash
python scripts/seed_demo_data.py          # 8 clientes, 25 ventas, 2 OC
python scripts/seed_demo_data.py --clean   # limpia datos DEMO
```

### ProtecciÃ³n de BD ProducciÃ³n

- `tests/conftest.py` incluye guardia `_verificar_no_es_produccion()`
- Bloquea ejecuciÃ³n si `DATABASE_URL` contiene hosts cloud conocidos (neon.tech, render.com, etc.)
- Override: `ALLOW_TESTS_ON_REMOTE=1` (bajo responsabilidad del operador)
- RecomendaciÃ³n: crear `.env.qa` con `DATABASE_URL` apuntando a BD local o de QA dedicada

### Archivos clave

| Archivo | PropÃ³sito |
|---|---|
| `tests/conftest.py` | Fixtures, helpers, guardia anti-prod |
| `tests/test_end_to_end.py` | 43 tests e2e (T1-T18) |
| `tests/test_routes.py` | Tests HTTP rutas crÃ­ticas |
| `scripts/seed_demo_data.py` | Generador datos demo |
| `pytest.ini` | Config pytest + markers |
| `.github/workflows/tests.yml` | CI GitHub Actions |

---

## 16. Backlog pendiente (post v2.0)

- [ ] MÃ©tricas finas: latencia voice-command, errores por endpoint
- [ ] Columna `version` (optimistic locking) en ventas
- [ ] Email alertas (complemento a Slack/WA)
- [ ] MÃ¡s blueprints: BI/gerencia, admin, inventario
- [ ] Customer 360 P1+: CDP, worker llamadas, portal cliente
- [ ] Smart dropzone + OCR mejorado
- [ ] FE: TED real desde CAF + XSD SII + SOAP Zeep producciÃ³n/certificaciÃ³n
- [ ] Portal cliente (autoservicio)

---

## 18. Plan de cierre de mÃ³dulos v3 (operaciÃ³n correcta)

> **Objetivo:** cada mÃ³dulo queda **cerrado** cuando cumple: flujo feliz + errores controlados + permisos + tests smoke/E2E mÃ­nimos + checklist operativo firmado en tienda.

### Leyenda de estado

| SÃ­mbolo | Significado |
|---|---|
| âœ… | Cerrado para operaciÃ³n diaria |
| ðŸŸ¡ | Operativo con deuda tÃ©cnica documentada |
| â³ | En trabajo / no listo para producciÃ³n |

### Prioridad operativa (SD-1)

**Cliente #1:** FerreterÃ­a Santo Domingo â€” 3 sucursales, ~20 personas, ~4.000 SKU.  
**Foco actual:** POS + inventario (toma fÃ­sica) + operaciÃ³n diaria estable. Detalle: [`planes/01-entrega-santo-domingo/`](planes/01-entrega-santo-domingo/).

### Matriz de mÃ³dulos (2026-05-21)

| # | MÃ³dulo | Estado | Criterio de cierre |
|---|---|---|---|
| 1 | Auth / usuarios / RBAC | âœ… | Login, roles, `_NAV_MAP`, tests rutas |
| 2 | POS + vale | âœ… | Abiertaâ†’Pendienteâ†’cobro; live wall; tests E2E T1 |
| 3 | Caja (cobro, cierre, cambios) | âœ… | Cola, anular, cierre cuadratura, limpiar cola admin |
| 4 | Stock / kardex / multi-almacÃ©n | âœ… | Invariante, `transaccion_critica`, tests T5/T17 |
| 5 | Bodega + voz | âœ… | Despacho, SLA, TV, tests bodega |
| 6 | Compras OC + recepciones | ðŸŸ¡ | Requiere migraciones SQL en BD legacy |
| 7 | CrÃ©ditos + abonos | âœ… | Cupo, cuotas 30/60/90, abonos caja |
| 8 | Cotizaciones | âœ… | Convertir a POS, PDF |
| 9 | Productos / precios / inventario UI | âœ… | CRUD, revisiÃ³n precios, enrolamiento |
| 10 | BI / gerencia / observabilidad web | ðŸŸ¡ | Dashboards OK; SEO sync externo stub |
| 11 | Customer 360 | ðŸŸ¡ | P0 en cÃ³digo; P1+ roadmap |
| 12 | FacturaciÃ³n electrÃ³nica SII | ðŸŸ¡ | ERP listo hasta XML+firma+cola; **envÃ­o SII pendiente** |
| 13 | Admin (empresa, almacenes, catÃ¡logo) | âœ… | Incluye enlaces FE (CAF, cola DTE) |
| 14 | PÃºblico / SEO / landing | âœ… | Desplegado; leads JSONL |

### Orden de trabajo recomendado (sprints)

1. **Sprint A â€” OperaciÃ³n tienda (cerrar âœ…):** Caja + POS + stock + bodega â†’ ejecutar checklist Â§18.1 en ferreterÃ­a 1 dÃ­a.
2. **Sprint B â€” Comercial financiero:** CrÃ©ditos + cotizaciones + cierre caja histÃ³rico.
3. **Sprint C â€” Abastecimiento:** OC/recepciones en BD con migraciones aplicadas.
4. **Sprint D â€” FE SII:** CAF reales, certificado, TED+SOAP, certificaciÃ³n MaullÃ­n.
5. **Sprint E â€” C360 + BI:** segÃºn `docs/roadmap_customer_360_ferreteria_2026.md`.

### Â§18.1 Checklist operativo â€” Caja + POS (copiar en cierre de sprint A)

- [ ] Abrir caja con monto inicial correcto.
- [ ] Emitir vale POS â†’ aparece en cola pendientes.
- [ ] Cobrar efectivo + boleta â†’ stock tienda baja, venta `Pagado`.
- [ ] Intentar cerrar con borrador POS abierto â†’ bloqueo; anular borrador o cobrar.
- [ ] Anular vale no cobrado (motivo) â†’ desaparece de bloqueo.
- [ ] Admin: limpiar cola cierre solo para descartes masivos.
- [ ] Cerrar caja: cuadratura efectivo vs teÃ³rico; ticket cierre.
- [ ] Caja dÃ­a anterior: puede cobrar/anular vales exentos sin quedar en callejÃ³n.

### Â§18.2 Checklist â€” FacturaciÃ³n electrÃ³nica (antes de â€œproducciÃ³n SIIâ€)

- [ ] CAF tipo 39 (y 33 si factura) cargado en `/admin/facturacion/caf`.
- [ ] `.pfx` en `instance/certs/` (gitignored) + variables `SII_CERT_*`.
- [ ] Cobro prueba â†’ venta con `nro_documento`, `dte_estado`, XML descargable en cola.
- [ ] `pytest tests/test_facturacion_dte_e2e.py` verde en BD QA.
- [ ] EnvÃ­o SOAP real + aceptaciÃ³n SII (pendiente desarrollo).
- [ ] CertificaciÃ³n set casos SII ejecutado y archivado.

### Â§18.3 Checklist â€” Suite QA (antes de cada release)

```bash
pytest tests/ -m smoke -q --tb=no
pytest tests/test_routes_criticas.py -q
pytest tests/test_facturacion_*.py tests/test_pos_live_wall.py -q
python scripts/sync_local_neon_render.py --verify-only   # opcional: alinear conteos local vs Neon (.env.local)
```

- [ ] Sin `ALLOW_TESTS_ON_REMOTE` salvo BD QA dedicada.
- [ ] CI GitHub Actions verde en `main`.

### Â§18.4 DefiniciÃ³n de â€œmÃ³dulo cerradoâ€

Un mÃ³dulo se considera **cerrado** cuando:

1. Flujos documentados en `docs/FLUJOS_CRITICOS.md` o secciÃ³n de este maestro.
2. Permisos RBAC asignados a perfiles reales (`gerente`, `cajero`, etc.).
3. Al menos un test smoke o E2E que toque el happy path.
4. Checklist Â§18.x firmado por operador o dueÃ±o.
5. Deuda tÃ©cnica â³ listada en Â§16 sin sorpresas.

---

*Ãšltima revisiÃ³n maestra: 2026-05-21 â€” `app.py` ~20.6k lÃ­neas, `core/` ~974 lÃ­neas, ~289 tests; `docs/planes/` como Ã­ndice de planificaciÃ³n; rendimiento SD-1 y deploy 6 threads documentados.*
