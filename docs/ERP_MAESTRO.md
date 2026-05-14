# ERP LhexIA — Documento Maestro

> Sistema ERP integral para ferretería. Gestión de ventas (POS + formulario), caja, inventario multi-almacén, bodega con despacho por voz (IA), compras, créditos, BI, y Customer 360.

**Última actualización:** 2026-05-11  
**Versión del plan:** v2.0 (cerrado)  
**Líneas de código `app.py`:** ~16,076  

---

## 1. Stack tecnológico

| Componente | Tecnología |
|---|---|
| Backend | **Python 3.14**, Flask, Flask-SQLAlchemy, Flask-Login |
| BD producción | PostgreSQL (Neon/Render) |
| BD desarrollo | MySQL local (PyMySQL) |
| ORM | SQLAlchemy (modelos en `app.py`) |
| Frontend | Jinja2 + Bootstrap 5 + Font Awesome + CSS propio (`design-system.css`) |
| JS interactivo | Vanilla JS (`pos.js`, timers SLA, etc.) |
| IA | OpenAI Whisper (transcripción voz), GPT-4o-mini (parsing comandos bodega), OCR facturas |
| Reportes | pandas + openpyxl (Excel), pdfkit (PDF), QR codes |
| Deploy | Gunicorn (`render.yaml`), compatible Render/Railway |
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
├── app.py                    # App Flask monolítica (modelos + rutas + lógica)
├── init_db.py                # Sync esquema + roles base + admin bootstrap
├── schema_sync.py            # Sincronización modelos ↔ BD
├── requirements.txt          # Dependencias Python
├── render.yaml               # Config deploy (gunicorn app:app)
├── memory.md                 # Memoria viva del proyecto (contexto entre sesiones)
│
├── blueprints/               # Registro de rutas por dominio
│   ├── bodega.py             #   11 rutas (despacho, plataforma, voz, SLA, TV)
│   ├── caja.py               #   13 rutas (cobro, cambios, saldos, cierres)
│   ├── pos.py                #   10 rutas (punto de venta, finalizar, items)
│   └── c360.py               #    9 rutas (Customer 360, IA, ofertas proactivas)
│
├── services/                 # Lógica de negocio extraída
│   ├── stock_service.py      #   Stock multi-almacén, invariante, reversión bodega
│   ├── kardex_service.py     #   Movimientos kardex, bitácoras costo/precio
│   ├── venta_service.py      #   transaccion_critica() context manager
│   ├── whatsapp_service.py   #   WhatsApp Cloud API (cobranza, alertas)
│   ├── audit_service.py      #   erp_audit_log (eventos críticos)
│   ├── unidades_service.py   #   Unidades de medida, factores conversión
│   ├── c360_service.py       #   Customer 360, predicción compra, scoring
│   └── sistema_health_service.py  # GET /api/sistema/salud
│
├── templates/                # 89 templates Jinja2
│   ├── base.html             #   Layout principal (sidebar dinámico por permisos)
│   ├── base_tv.html          #   Layout kiosk/TV (auto-refresh 30s)
│   ├── base_movil.html       #   Layout mobile
│   ├── punto_venta.html      #   POS completo
│   ├── caja_pendientes.html  #   Cola de cobro
│   └── ...                   #   (89 archivos total)
│
├── static/                   # CSS, JS, logos, imágenes
│   ├── design-system.css     #   Sistema de diseño propio
│   └── pos.js                #   Lógica POS del lado cliente
│
├── sql/                      # 37 migraciones SQL incrementales
│   └── 2026_MM_DD_*.sql      #   Formato fecha para orden cronológico
│
├── scripts/                  # Utilidades y seeds
│   └── smoke_alertas_vales_despacho.py
│
├── data/                     # JSON runtime
│   ├── empresa_config.json   #   Config empresa (módulos, datos fiscales)
│   └── proveedores_config.json
│
└── docs/                     # Documentación
    ├── ERP_MAESTRO.md        #   ← ESTE DOCUMENTO
    ├── FLUJOS_CRITICOS.md    #   Diagramas de flujos de negocio
    ├── BODEGA_ULTRA_PREMIUM.md
    ├── PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md
    ├── roadmap_customer_360_ferreteria_2026.md
    └── manual_operacion_customer_360.md
```

---

## 3. Modelos de datos (40 tablas)

### Núcleo comercial

| Modelo | Tabla | Dominio |
|---|---|---|
| `Venta` | `ventas` | Ventas, vales POS; estados: Abierta → Pendiente → Pagado / Anulada |
| `DetalleVenta` | `detalle_ventas` | Líneas de venta (producto, cantidad, precio, descuento) |
| `VentaCuotaCredito` | `ventas_cuota_credito` | Plan cuotas 30/60/90 |
| `Cotizacion` | `cotizaciones` | Cotizaciones comerciales |
| `CotizacionDetalle` | `cotizacion_detalles` | Líneas de cotización |
| `AbonoCredito` | `abonos_credito` | Pagos parciales a cuentas crédito |

### Caja y pagos

| Modelo | Tabla | Dominio |
|---|---|---|
| `Caja` | `cajas` | Apertura/cierre de caja, arqueo |
| `MovimientoCaja` | `movimiento_cajas` | Ingresos/egresos, cuadratura |
| `CambioOperacion` | `cambio_operaciones` | Devoluciones y cambios |
| `CambioDetalle` | `cambio_detalles` | Líneas de cambio |
| `ClienteSaldoFavor` | `cliente_saldo_favor` | Saldo a favor del cliente |
| `MovimientoSaldoFavor` | `movimiento_saldo_favor` | Historial saldos a favor |

### Inventario y abastecimiento

| Modelo | Tabla | Dominio |
|---|---|---|
| `Producto` | `productos` | Maestro SKU, precios, unidades, ubicación |
| `Almacen` | `almacenes` | Multi-almacén (tienda, bodega, etc.) |
| `StockPorAlmacen` | `stock_por_almacen` | Stock por SKU por almacén |
| `CatalogoCategoria` | `catalogo_categorias` | Categorías jerárquicas |
| `CatalogoSubcategoria` | `catalogo_subcategorias` | Subcategorías nivel 2 |
| `UnidadMedida` | `unidades_medida` | Unidades (kg, mt, un, etc.) |
| `ConversionUnidad` | `conversiones_unidad` | Factores de conversión |
| `MovimientoInventario` | `movimientos_inventario` | Kardex (entradas/salidas) |
| `BitacoraCostoCompra` | `bitacora_costos_compra` | Historial costos |
| `BitacoraPrecioVenta` | `bitacora_precios_venta` | Historial precios venta |
| `AuditoriaInventario` | `auditorias_inventario` | Tomas de inventario |
| `DetalleAuditoria` | `detalles_auditoria` | Líneas de auditoría |

### Compras y recepciones

| Modelo | Tabla | Dominio |
|---|---|---|
| `Proveedor` | `proveedores` | Maestro proveedores |
| `OrdenCompra` | `ordenes_compra` | Órdenes de compra |
| `DetalleOrdenCompra` | `detalle_ordenes_compra` | Líneas OC |
| `RecepcionCompra` | `recepciones_compra` | Recepción de mercadería |
| `DetalleRecepcion` | `detalles_recepcion` | Líneas recepción |

### Clientes y crédito

| Modelo | Tabla | Dominio |
|---|---|---|
| `Cliente` | `clientes` | Maestro clientes, RUT, crédito |
| `EnrolamientoTomaSesion` | `enrolamiento_toma_sesiones` | Sesiones de toma física |
| `EnrolamientoTomaLinea` | `enrolamiento_toma_lineas` | Líneas escaneadas |

### Seguridad y auditoría

| Modelo | Tabla | Dominio |
|---|---|---|
| `Rol` | `roles` | Roles del sistema |
| `Permiso` | `permisos` | Catálogo de permisos |
| `RolPermiso` | `rol_permisos` | Asignación rol ↔ permiso |
| `ErpAuditLog` | `erp_audit_log` | Log de auditoría (eventos críticos) |

### Customer 360 e IA

| Modelo | Tabla | Dominio |
|---|---|---|
| `C360LlamadaSnapshotDia` | `c360_llamadas_snapshot_dia` | Snapshot diario de llamadas |
| `C360ProactivaOferta` | `c360_proactiva_ofertas` | Ofertas proactivas IA |
| `CobranzaRecordatorioWhatsappLog` | `cobranza_recordatorio_wa_log` | Log envíos WA cobranza |
| `ReabastoClienteWaLog` | `reabasto_cliente_wa_log` | Log WA reabastecimiento |

---

## 4. Rutas HTTP (~143 endpoints)

**100 rutas** definidas con `@app.route` en `app.py` + **43 rutas** registradas via blueprints.

### 4.1 Público y landing

| Método | Ruta | Función |
|---|---|---|
| GET | `/`, `/index` | Landing page |
| GET | `/healthz` | Health check |
| POST | `/api/landing/lead` | Captura leads |
| GET | `/catalogo` | Catálogo público |
| GET | `/consulta-stock` | Consulta stock público |

### 4.2 Autenticación

| Método | Ruta | Función |
|---|---|---|
| GET/POST | `/login` | Login (redirige según perfil) |
| GET | `/logout` | Confirma si caja abierta antes de salir |
| POST | `/logout/forzar` | Logout sin cerrar caja |
| GET/POST | `/cambiar_password` | Cambio contraseña (forzado si temporal) |

### 4.3 Home y dashboards

| Método | Ruta | Función |
|---|---|---|
| GET | `/inicio` | Dashboard principal (KPIs) |
| GET | `/owner-mobile` | Vista ejecutiva mobile-first |
| GET | `/ayuda` | Centro de ayuda |

### 4.4 Punto de venta (POS)

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/punto_venta` | Pantalla POS | `pos_emitir_vale` |
| POST | `/agregar_producto_venta` | Agregar línea al carrito | `pos_emitir_vale` |
| POST | `/actualizar_item` | Modificar cantidad/precio | `pos_emitir_vale` |
| POST | `/eliminar_detalle` | Quitar línea | `pos_emitir_vale` |
| POST | `/finalizar_venta` | Emitir vale Pendiente | `pos_emitir_vale` |
| GET | `/buscar_producto` | Búsqueda por código/nombre | — |
| POST | `/pos/usuarios_autorizar_descuento` | Autorizar descuento | `autorizar_descuento_pos` |

### 4.5 Caja

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/caja/vales_pendientes` | Cola de cobro | `caja_cobrar_vale` |
| POST | `/procesar_cobro_caja` | Cobrar vale | `caja_cobrar_vale` |
| POST | `/caja/vales/<id>/anular` | Anular vale | `anular_vale_caja` |
| GET | `/abrir_caja` | Apertura de caja | `caja_abrir` |
| GET/POST | `/movimiento_caja` | Ingresos/egresos | `caja_movimientos` |
| GET/POST | `/cerrar_caja` | Cierre y cuadratura | `caja_cerrar` |
| GET | `/caja/historial_cierres` | Histórico cierres | `gestionar_usuarios` |
| GET | `/caja/cambios` | Cambios/devoluciones | `caja_cobrar_vale` |
| GET | `/caja/cambios/historial` | Historial cambios | `caja_cobrar_vale` |
| GET | `/caja/saldos-favor` | Saldos a favor | `caja_cobrar_vale` |

### 4.6 Inventario y productos

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/productos` | Catálogo productos | `ver_inventario` |
| POST | `/productos/<id>/editar_stock` | Ajuste stock unitario | `admin_inventario` |
| POST | `/productos/stock_masivo` | Ajuste stock masivo | `admin_inventario` |
| POST | `/cargar_productos` | Importar CSV/Excel | `admin_inventario` |
| GET | `/stock/critico` | Stock bajo mínimo | `ver_inventario` |
| GET | `/kardex` | Movimientos kardex | `ver_inventario` |
| GET | `/consulta-stock` | Consulta rápida | — (público) |
| GET | `/inventario/enrolamiento` | Toma física | `enrolamiento_inventario` |
| GET | `/inventario/salud` | Salud del inventario | `enrolamiento_inventario` |

### 4.7 Bodega

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/bodega/cuadro-mando` | Dashboard bodega (KPIs, SLA) | `bodega_operador` |
| GET | `/bodega/cuadro-mando/tv` | Modo TV/kiosk (auto-refresh) | `bodega_operador` |
| GET | `/bodega/plataforma` | Plataforma operativa retiro | `bodega_operador` |
| GET | `/bodega/vale/<id>` | Detalle vale retiro | `bodega_operador` |
| GET | `/bodega/despachos` | Despacho por voz (IA) | `bodega_operador` |
| POST | `/api/bodega/voice-command` | API transcripción + ejecución voz | `bodega_operador` |
| GET | `/bodega/export-dia` | Export CSV del día | `bodega_operador` |

### 4.8 Compras y recepciones

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/compras/ordenes` | Lista órdenes compra | `gestionar_compras` |
| GET/POST | `/compras/ordenes/nueva` | Nueva OC | `gestionar_compras` |
| GET | `/compras/ordenes/<id>/editar` | Editar OC | `gestionar_compras` |
| GET | `/recepciones` | Lista recepciones | `gestionar_compras` |
| GET/POST | `/recepciones/nueva` | Nueva recepción | `gestionar_compras` |
| GET | `/recepciones/<id>` | Detalle recepción | `gestionar_compras` |
| GET | `/proveedores` | Maestro proveedores | `gestionar_compras` |

### 4.9 Créditos y cobranza

| Método | Ruta | Función |
|---|---|---|
| GET | `/creditos` | Módulo créditos |
| GET | `/creditos/estado_cuenta/<id>` | Estado de cuenta HTML |
| GET | `/creditos/estado_cuenta/<id>/pdf` | Estado de cuenta PDF |
| POST | `/registrar_abono` | Registrar abono |
| GET | `/ticket_abono/<id>` | Ticket de abono |
| GET | `/cobranza/cuotas` | Cobranza WA cuotas |

### 4.10 Cotizaciones

| Método | Ruta | Función |
|---|---|---|
| GET | `/cotizaciones` | Lista cotizaciones |
| GET/POST | `/cotizaciones/nueva` | Nueva cotización |
| GET | `/cotizaciones/<id>` | Detalle |
| POST | `/cotizaciones/<id>/convertir` | Convertir a venta POS |
| GET | `/cotizaciones/<id>/pdf` | PDF cotización |

### 4.11 BI y gerencia

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET | `/bi` | BI reportes | `ver_gerencia` |
| GET | `/gerencia/informes-dueno` | Panel ejecutivo | `panel_gerencia` |
| GET | `/gerencia/simulador-margen` | Simulador margen | `panel_gerencia` |
| GET | `/bi/demo/alertas-precio-premium` | Alertas de precio | `panel_gerencia` |
| GET | `/gerencia/c360/ia-dashboard` | Customer 360 IA | `panel_gerencia` |
| GET | `/precios/revision` | Revisión precios | `revision_precios` |
| GET | `/bi/export.csv` | Export ventas CSV | — |
| GET | `/ia_abastecimiento` | IA sugerencias compra | — |

### 4.12 Administración

| Método | Ruta | Función | Permiso |
|---|---|---|---|
| GET/POST | `/admin/empresa` | Datos empresa + módulos | `gestionar_usuarios` |
| GET/POST | `/admin/almacenes` | Almacenes | `gestionar_usuarios` |
| GET/POST | `/admin/clientes` | Clientes | `gestionar_usuarios` |
| GET/POST | `/admin/roles-permisos` | Roles y permisos | `gestionar_usuarios` |
| GET/POST | `/admin/unidades` | Unidades medida | `gestionar_usuarios` |
| GET/POST | `/admin/catalogo` | Categorías | `gestionar_usuarios` |
| GET | `/usuarios` | Lista usuarios | `gestionar_usuarios` |

### 4.13 APIs internas

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/sistema/salud` | Health check detallado |
| POST | `/api/ventas/alertas-despachos-pendientes` | Cron alertas vales riesgo |
| GET | `/api/buscar_producto/<codigo>` | Búsqueda por código |
| POST | `/api/guardar_conteo_inventario` | Guardar conteo auditoría |

---

## 5. Sistema de permisos (RBAC v2)

### 5.1 Catálogo de permisos

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
| **Dueño** | Todo gerente + `gestionar_usuarios` |
| **Admin** | Todos (bypass automático) |

### 5.3 Navegación centralizada (`_NAV_MAP`)

Mapa declarativo en `app.py` que define grupos de menú, ítems, permisos requeridos y endpoints activos. La función `_construir_nav_usuario()` filtra en runtime según permisos del usuario autenticado e inyecta `nav_menu` vía context_processor. El sidebar de `base.html` itera `nav_menu` (~15 líneas Jinja).

### 5.4 Capas de control de acceso

```
Capa 1: Empresa    → modulo_activo()         → "¿Módulo habilitado?" (admin_empresa)
Capa 2: Rol        → mapa_por_rol            → "¿Qué permisos tiene?" (admin_roles_permisos)
Capa 3: Ruta       → @permisos_required      → "¿Puede entrar?" (decorador)
Capa 4: Contexto   → @caja_requerida         → "¿Tiene caja abierta?" (decorador)
Capa 5: Menú       → _construir_nav_usuario  → "¿Qué ve?" (automático)
```

### 5.5 Redirección inteligente al login

```
Admin / Dueño / Gerente  →  /owner-mobile      (panel ejecutivo)
Bodeguero (sin caja)     →  /bodega/plataforma  (operación bodega)
Cajera / Cajero          →  /caja/vales_pendientes (cola cobro)
Vendedor / Mesón         →  /punto_venta         (POS directo)
Otro                     →  /inicio              (dashboard general)
```

---

## 6. Módulos activables por empresa

Configurados en **Mantenedores > Datos de empresa** (`/admin/empresa`), almacenados en `data/empresa_config.json`:

| Flag | Módulo | Controla |
|---|---|---|
| `mod_ventas` | Ventas | POS, cotizaciones, historial ventas |
| `mod_caja` | Caja | Cobro, apertura/cierre, movimientos |
| `mod_inventario` | Inventario | Productos, bodega, compras, recepciones |
| `mod_bi` | BI y análisis | Reportes, revisión precios |
| `mod_ia` | IA | Abastecimiento inteligente, OCR facturas |

---

## 7. Flujos de negocio críticos

### 7.1 Venta POS (flujo principal)

```
[Vendedor]                    [Cajera]                    [Bodeguero]
    │                             │                            │
    ├─ Abre POS (/punto_venta)    │                            │
    ├─ Busca producto (código)    │                            │
    ├─ Agrega líneas al carrito   │                            │
    ├─ Finaliza → vale PENDIENTE  │                            │
    │  (no descuenta stock aún)   │                            │
    │                             ├─ Ve vale en cola           │
    │                             ├─ Cobra → estado PAGADO     │
    │                             │  (descuenta stock + kardex) │
    │                             │                            ├─ Ve en plataforma
    │                             │                            ├─ Despacha (voz IA)
    │                             │                            └─ Cierra retiro
```

### 7.2 Flujo de cobro (procesar_cobro_caja)

```
1. Valida stock disponible (invariante)
2. Abre transaccion_critica() [savepoint]
3. Actualiza venta → PAGADO
4. Descuenta stock tienda (almacén)
5. Registra kardex (SALIDA)
6. Registra movimiento caja
7. Si crédito: actualiza saldo_deudor + cuotas
8. Si saldo a favor: aplica descuento
9. audit_log("cobro_vale_caja")
10. Commit
11. WhatsApp (post-commit, fuera de transacción)
```

### 7.3 Bodega — Despacho por voz (IA)

```
1. Bodeguero habla al micrófono
2. OpenAI Whisper → transcripción texto
3. GPT-4o-mini → parsing JSON {vale, producto, cantidad}
4. transaccion_critica():
   - Valida vale + producto + stock bodega
   - Actualiza bodega_despacho_json
   - Mueve stock bodega → tienda
   - Kardex SALIDA bodega + ENTRADA tienda
   - Valida invariante
5. Commit
```

### 7.4 Medios de pago

| Medio | Tipo | Descuenta stock |
|---|---|---|
| `Efectivo` | Inmediato | Sí, al cobrar |
| `Debito` | Inmediato | Sí, al cobrar |
| `TarjetaCredito` | Inmediato (TC bancaria) | Sí, al cobrar |
| `Transferencia` | Inmediato | Sí, al cobrar |
| `Credito` | Fiado tienda | Sí, al cobrar (queda Pendiente) |

### 7.5 SLA Bodega (prioridad inteligente)

Tiempos en minutos para indicadores de color:

| Estado | Normal | Atención | Urgente |
|---|---|---|---|
| PENDIENTE | <5 | 5-10 | >20 |
| EN_PREPARACION | <10 | 10-20 | >40 |
| ENTREGA_PARCIAL | <8 | 8-15 | >30 |
| LISTO_RETIRO | <15 | 15-30 | >60 |

---

## 8. Servicios extraídos

| Servicio | Responsabilidad |
|---|---|
| `stock_service.py` | Stock multi-almacén, invariante consumo, reversión bodega, disponibilidad POS |
| `kardex_service.py` | Registro movimientos, bitácoras costo/precio |
| `venta_service.py` | `transaccion_critica()` (savepoint con rollback atómico) |
| `whatsapp_service.py` | Envío mensajes WA Cloud API |
| `audit_service.py` | `_audit_log()` → tabla `erp_audit_log` |
| `unidades_service.py` | Factores conversión venta↔stock↔compra |
| `c360_service.py` | Motor Customer 360, predicción compra, scoring |
| `sistema_health_service.py` | Health check (`/api/sistema/salud`) |

---

## 9. Blueprints registrados

| Blueprint | Rutas | Dominio |
|---|---|---|
| `blueprints/bodega.py` | 11 | Plataforma retiro, despacho voz, cuadro mando, SLA, TV, export |
| `blueprints/caja.py` | 13 | Cobro, anulación, cambios, saldos, cierres, tickets |
| `blueprints/pos.py` | 10 | Punto de venta, carrito, finalizar, búsqueda, descuentos |
| `blueprints/c360.py` | 9 | Customer 360, dashboard IA, ofertas proactivas |

---

## 10. Migraciones SQL (37 archivos)

Formato: `sql/YYYY_MM_DD_descripcion.sql`

Principales:
- Stock por almacén, kardex, recepciones, unidades de medida
- Catálogo categorías (2 niveles), productos (ubicación, unidades)
- Clientes (RUT, giro, dirección, crédito), cotizaciones
- Órdenes de compra, ventas (punto retiro, anulación, descuento)
- Caja cuadratura, cambios/saldos a favor
- Bodega retiro plataforma, cobranza WA, cuotas crédito
- Customer 360 (llamadas, snapshots)
- Vistas SQL: vales riesgo despacho (PostgreSQL + MySQL)

---

## 11. Reglas de negocio invariantes

1. **Invariante de stock:** `consumo_bodega + consumo_tienda ≤ consumo_total` por línea de venta.
2. **Estados de venta:** Abierta → Pendiente → Pagado / Anulada (inmutable).
3. **Stock se descuenta al COBRAR**, no al emitir vale.
4. **WhatsApp siempre post-commit** (nunca dentro de transacción).
5. **Caja obligatoria** para POS y cobro (`@caja_requerida`).
6. **Caja día anterior:** se permite cobrar/anular vales sin cerrar, pero no abrir nuevo POS.
7. **Cliente "final"** (RUT `66.666.666-6`) para ventas sin nombre.
8. **Crédito único plan:** `30_60_90` (3 cuotas a 30/60/90 días corridos).
9. **Anulación con despacho bodega** requiere permiso especial (`anular_vale_con_despacho_bodega`).
10. **Auditoría by-default:** todo cambio crítico registrado en `erp_audit_log`.

---

## 12. Configuración y entorno

### Variables de entorno

| Variable | Uso |
|---|---|
| `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI` | Conexión BD |
| `SECRET_KEY` | Flask sessions |
| `OPENAI_API_KEY` | IA (Whisper, GPT, OCR) |
| `EMPRESA_NOMBRE_COMERCIAL` | Nombre por defecto |
| `BOOTSTRAP_ADMIN_*` | Admin inicial en init_db |
| `WHATSAPP_*` / `COBRANZA_*` | Config WA Cloud API |
| `SLACK_WEBHOOK_URL` | Alertas Slack |
| `VALE_DESPACHO_SIN_COBRO_ALERTA_HORAS` | Umbral alertas (default 48h) |

### Archivos de entorno

```
env_qa.txt      → setdefault (carga si no existe var)
.env.qa         → override
.env.local      → local development
```

### Arranque local

```bash
python -m pip install -r requirements.txt
python app.py
```

### Producción

```bash
gunicorn app:app  # ver render.yaml
```

---

## 13. Integraciones externas

| Integración | Uso | Config |
|---|---|---|
| **OpenAI Whisper** | Transcripción voz → texto (bodega) | `OPENAI_API_KEY` |
| **OpenAI GPT-4o-mini** | Parsing comandos voz, sugerencias IA | `OPENAI_API_KEY` |
| **OpenAI Vision** | OCR facturas recepción | `OPENAI_API_KEY` |
| **WhatsApp Cloud API** | Cobranza cuotas, alertas despacho | `WHATSAPP_*` vars |
| **Slack Webhooks** | Alertas vales riesgo operativo | `SLACK_WEBHOOK_URL` |

---

## 14. Historial de hitos

| Fecha | Hito |
|---|---|
| 2026-05-08 | Memoria `memory.md` + documentación completa por módulo |
| 2026-05-08 | Correcciones auditoría: reversión stock, KPIs, edición ventas |
| 2026-05-08 | Caja día anterior + cierre bloqueado + cola combined |
| 2026-05-08 | Crédito cuotas 30/60/90 + medio TarjetaCredito |
| 2026-05-08 | Roadmap Customer 360 documentado |
| 2026-05-08 | Plan v2 Grok: Fase 1A (transacciones atómicas, auditoría, invariante) |
| 2026-05-08 | Fase 1B: cron alertas vales despacho + Slack + WA |
| 2026-05-08 | Servicios: stock, kardex, venta, whatsapp, audit, unidades, c360 |
| 2026-05-10 | Cierre plan v2.0: blueprints, health, carga masiva con transacción |
| 2026-05-11 | Bodega Fase 3: SLA, ranking operador, export CSV, modo TV |
| 2026-05-11 | RBAC v2: `_NAV_MAP`, sidebar dinámico, 17 permisos, 7 perfiles rol |
| 2026-05-11 | Redirección inteligente por perfil al login |
| 2026-05-11 | Fix: `grupo['items']` en Jinja2 (colisión con `dict.items`) |
| 2026-05-12 | Suite QA v4: 43 tests e2e + rutas HTTP + coverage + CI/CD + guardia anti-prod |

---

## 15. Documentación relacionada

| Documento | Contenido |
|---|---|
| `memory.md` | Memoria viva del proyecto (contexto entre sesiones) |
| `docs/FLUJOS_CRITICOS.md` | Diagramas Mermaid de flujos de negocio |
| `docs/BODEGA_ULTRA_PREMIUM.md` | Especificación módulo bodega (3 fases) |
| `docs/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md` | Plan v2.0 cerrado |
| `docs/roadmap_customer_360_ferreteria_2026.md` | Roadmap C360 por fases |
| `docs/roadmap_observabilidad_lhexia_2026_2030.md` | Roadmap de analítica, SEO y growth intelligence |
| `docs/manual_operacion_customer_360.md` | Manual operativo C360 |

---

## 17. Estrategia de Pruebas Automatizadas

### Suite End-to-End (`tests/test_end_to_end.py`)

| Escenario | Tests | Markers |
|---|---|---|
| T1 Venta completa (happy path) | 5 | smoke, happy_path |
| T2 Venta a crédito 30/60/90 | 1 | smoke, happy_path |
| T3 Compra y recepción OC | 1 | smoke, happy_path |
| T4 Despacho bodega parcial | 1 | smoke, happy_path |
| T5 Invariantes de negocio | 5 | smoke, invariantes |
| T6 Redirección por perfil | 1 | smoke |
| T7 Validación post-hoc | 1 | smoke, happy_path |
| T8 Anulación de vale (±bodega) | 2 | anulacion |
| T9 Stock insuficiente | 1 | edge_case |
| T10 Concurrencia doble cobro | 1 | concurrency, slow |
| T11 Despacho voz completo | 1 | happy_path, bodega |
| T12 Exceder cupo crédito | 1 | edge_case |
| T13 Anulación despachado | 1 | anulacion |
| T14 Rollback transaccion_critica | 2 | invariantes |
| T15 IVA y redondeos (parametrizado) | 13 | smoke, invariantes |
| T16 Carga ligera (10 ventas ThreadPool) | 1 | load, slow |
| T17 Multi-almacén (traslados) | 2 | happy_path, bodega |
| T18 Auditoría erp_audit_log | 4 | invariantes, audit |
| **Total** | **43** | |

### Suite de Rutas HTTP (`tests/test_routes.py`)

Pruebas de integración HTTP con Flask test_client. Cubren ~50 endpoints GET/POST sin servidor real.

### Smoke Tests (CI rápido)

```bash
pytest tests/ -m smoke -q --tb=no    # 27+ tests, < 1s
```

### Coverage

| Métrica | Valor actual | Meta 2-3 semanas |
|---|---|---|
| `app.py` | 17% | 35-45% |
| `services/` | 29% promedio | 50%+ |
| **Comando** | `pytest tests/ --cov=app --cov=services --cov-report=term-missing` | |

### CI/CD

- **GitHub Actions**: `.github/workflows/tests.yml`
  - PR/push: smoke tests + coverage
  - Push a main: suite completa + reporte HTML + artefactos
- **Reporte HTML**: `pytest tests/ --html=docs/test_report_v4.html --self-contained-html`

### Datos de Demostración

```bash
python scripts/seed_demo_data.py          # 8 clientes, 25 ventas, 2 OC
python scripts/seed_demo_data.py --clean   # limpia datos DEMO
```

### Protección de BD Producción

- `tests/conftest.py` incluye guardia `_verificar_no_es_produccion()`
- Bloquea ejecución si `DATABASE_URL` contiene hosts cloud conocidos (neon.tech, render.com, etc.)
- Override: `ALLOW_TESTS_ON_REMOTE=1` (bajo responsabilidad del operador)
- Recomendación: crear `.env.qa` con `DATABASE_URL` apuntando a BD local o de QA dedicada

### Archivos clave

| Archivo | Propósito |
|---|---|
| `tests/conftest.py` | Fixtures, helpers, guardia anti-prod |
| `tests/test_end_to_end.py` | 43 tests e2e (T1-T18) |
| `tests/test_routes.py` | Tests HTTP rutas críticas |
| `scripts/seed_demo_data.py` | Generador datos demo |
| `pytest.ini` | Config pytest + markers |
| `.github/workflows/tests.yml` | CI GitHub Actions |

---

## 16. Backlog pendiente (post v2.0)

- [ ] Métricas finas: latencia voice-command, errores por endpoint
- [ ] Columna `version` (optimistic locking) en ventas
- [ ] Email alertas (complemento a Slack/WA)
- [ ] Más blueprints: BI/gerencia, admin, inventario
- [ ] Customer 360 Fase 1: ficha cliente, predicción compra, scoring
- [ ] Smart dropzone + OCR mejorado
- [ ] Worker cron "llamadas recomendadas"
- [ ] Portal cliente (autoservicio)

---

*Generado automáticamente desde el código fuente y `memory.md` — 2026-05-11*
