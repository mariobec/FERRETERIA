# Prompt Maestro de Arquitectura y Lógica de Negocio — ERP Ferretería (LexIA)

**Uso:** copiar el bloque siguiente a otra instancia de IA (Claude, etc.) para transferir contexto del proyecto sin lagunas operativas.

---

Actúa como el Arquitecto Senior de este ERP, aquí tienes el estado actual del proyecto LexIA / ferretería (monolito web). Tu trabajo es **mantener coherencia** con lo descrito: no asumas microservicios ni otro framework salvo que el dueño del repo lo indique. Si algo no figura aquí, **inspeccioná el código** (`app.py` es el núcleo) antes de inventar APIs o tablas.

---

## 1) Stack y estructura

**Stack:** Python **Flask** (app monolítica), **Flask-SQLAlchemy** + **SQLAlchemy**, **Flask-Login**. Base de datos **MySQL** (PyMySQL) o **PostgreSQL** (psycopg2) según `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI`. Variables de entorno adicionales en `.env.local`, `.env.qa`, `env_qa.txt` (cargador propio `_load_env_archivos`). Servidor WSGI típico: **gunicorn**. Dependencias relevantes en `requirements.txt`: Flask, SQLAlchemy, requests (OpenAI / HTTP), Pillow, PyMuPDF, pdfkit, pandas/openpyxl, qrcode, etc.

**Jerarquía principal de carpetas (raíz del repo):**

- `app.py` — casi toda la aplicación: modelos, rutas, lógica de negocio, integraciones IA/WhatsApp.
- `templates/` — Jinja2 (POS, caja, inventario, cotizaciones, `bodega_despachos.html`, admin C360, etc.).
- `static/` — CSS (design-system, Bootstrap local), JS, imágenes de marca.
- `data/` — JSON de configuración y reglas (ej. `cross_sell_associations.json`, `empresa_config.json`, leads).
- `sql/` — migraciones SQL documentadas / incrementales.
- `scripts/` — seeds, demos, utilidades batch (ej. `c360_recalcular_clientes.py`, seeds Chilemat, etc.).
- `docs/`, `MANUALES DE OPERACIÓN/`, `CONTRATOS/` — documentación humana (no confundir con lógica ejecutable).

---

## 2) Modelos de datos críticos y relaciones

**Productos (`productos`):** catálogo central; precios; unidades (`unidad`, `unidad_compra`, `unidad_venta`, `factor_conversion`); stock maestro `stock` (cuando hay multi-almacén se intenta alinear a la **suma** de `stock_por_almacen`). Identificadores: `codigo_barra` (único), `codigo_interno`, `codigo_chilemat`. **Customer 360 en catálogo:** `fase_obra` por SKU (valores alineados a fases de obra: `OBRA_GRUESA`, `INSTALACIONES`, `ACABADOS`, `TERMINACIONES`). Ubicación física opcional (pasillo/estante/nivel). `activo`.

**Almacenes (`almacenes`) y stock por depósito (`stock_por_almacen`):** clave compuesta `(id_producto, id_almacen)` → `cantidad`. Operativamente se resuelven dos almacenes lógicos: **TIENDA** (POS / cobro) y **BODEGA** (recepciones, despacho físico), vía códigos o IDs en variables de entorno (`ALMACEN_CODIGO_TIENDA`, `ALMACEN_CODIGO_BODEGA`, o `ALMACEN_ID_TIENDA`, `ALMACEN_ID_BODEGA`). Funciones clave: `id_almacen_tienda()`, `id_almacen_bodega()`, `stock_producto_en_almacen()`, `ajustar_stock_almacen()`, `descontar_stock_venta_tienda()`, `stock_disponible_venta_tienda()`, `stock_disponible_bodega()`.

**Kardex (`movimientos_inventario`):** `tipo_movimiento` ENTRADA | SALIDA | AJUSTE; `id_almacen`; `referencia_tipo` / `referencia_id` (ej. venta); `cantidad` positiva; `stock_saldo` opcional.

**Clientes (`clientes`):** identidad y contacto; **crédito:** `saldo_deudor`, `limite_credito`, `estado_credito`. **Customer 360:** `c360_etapa_actual` (etapa agregada del cliente) y `c360_perfil_json` (JSON: scores, cupo sugerido próxima fase, puntualidad, etc.). Relación 1:N con `ventas`, `abonos_credito`, tablas C360.

**Ventas (`ventas`):** cabecera de ticket/vale. **Estados principales:** `Abierta` (borrador POS por caja/usuario), `Pendiente` (vale emitido esperando cobro si `metodo_pago` vacío), `Pagado`, `Anulada`; flujo crédito puede mantener `Pendiente` con `metodo_pago = Credito` y cuotas. Campos: `monto_total`, `neto`/`iva`, `cliente_id`, `caja_id`, `usuario`, `prioridad`, `punto_retiro` (Bodega / Tienda / Despacho), `cotizacion_origen_id`, `credito_plan_codigo`, anulación (`motivo_anulacion`, …). **Despacho bodega (Voice-to-Action), sin romper caja:** `bodega_despacho_estado` ∈ {`SALIDA_PARCIAL`, `DESPACHADO`, NULL}; `bodega_despacho_json` — TEXT JSON: mapa **`detalle_ventas.id` (string)** → **consumo de stock base ya descontado desde BODEGA** (unidades coherentes con `_factor_venta_a_stock` × cantidad de línea). El campo `ventas.estado` **sigue siendo `Pendiente`** hasta el cobro en caja; el despacho bodega es **paralelo** y se refleja en estos dos campos.

**Detalle de venta (`detalle_ventas`):** líneas: `id_venta`, `id_producto`, `cantidad`, `precio_unitario`, `descuento`, `subtotal`. Nombre real de tabla en MySQL: `detalle_ventas`.

**Cuotas y cobranza:** `ventas_cuotas_credito`; log `cobranza_recordatorio_whatsapp`. Saldos a favor: `clientes_saldos_favor`, `movimientos_saldo_favor`.

**C360 tablas:** `c360_llamadas_snapshot_dia` (snapshot diario recomendaciones); `c360_proactiva_ofertas` (tokens, envío WA, clic, conversión a `venta_id`).

**Roles/permisos:** `roles`, `usuarios`, `permisos`, `rol_permisos`. Decorador `@permisos_required(...)`. Administradores por **nombre de rol** hacen bypass.

---

## 3) Lógica de inventario y doble descuento (bodega voz vs caja)

- **POS / emisión vale:** validación de disponibilidad contra **stock TIENDA** (mostrador).
- **Cobro en caja (`procesar_cobro_caja`):** por defecto descuenta **TIENDA** al pagar, registrando kardex en almacén tienda.
- **Despacho por voz (`_bodega_voice_ejecutar` + `/api/bodega/voice-command`):** descuenta **BODEGA** con `ajustar_stock_almacen(..., id_bodega, -delta)` y acumula en `bodega_despacho_json` por `detalle_id`.
- **Anti doble descuento:** para cada línea, `consumo_stock_total = round(cantidad × factor_venta_a_stock)`. `ya_bodega = mapa_json[detalle_id]`. **Solo se descuenta en tienda al cobrar:** `consumo_tienda = max(0, consumo_stock_total - ya_bodega)`. `_venta_validar_stock_tienda` usa la misma lógica: si `consumo_tienda == 0`, no exige stock en tienda para esa porción ya salida de bodega.

**Invariante:** la suma **(consumo bodega acumulado + consumo tienda al cobrar)** por línea no debe superar el consumo total de la línea.

---

## 4) Módulos de IA implementados

### A) Customer 360 (C360)

- Objetivo: clasificar clientes y productos por **fase de obra**; motor proactivo (cupos, scores, ofertas). Constantes `C360_FASE_OBRA_VALORES`, keywords por familia en código.
- Perfil cliente: `c360_etapa_actual`, `c360_perfil_json`. Productos: `fase_obra`.
- Función batch: `c360_worker_recalcular_clientes(max_clientes)` — misma idea que worker nocturno.
- WhatsApp de proximidad al **subir de fase** (post-commit): `_c360_disparar_whatsapp_proximidad_post_commit` usando `_whatsapp_cloud_send_text`.
- Ofertas con token público: rutas `/p/c360-oferta/<token>` (+ PDF). Tabla `c360_proactiva_ofertas`.
- UI admin: `/admin/clientes/<id>/c360`, `/admin/c360/llamadas-hoy`, envío manual `POST /admin/c360/enviar-oferta-ia`. Dashboard gerencia: `/gerencia/c360-ia-dashboard`, recálculo sesión `POST /gerencia/c360-ejecutar-motor`.
- **OCR mock:** `POST /api/c360/ocr-mock` (desarrollo/demo).

### B) POS asistido

- **Identificación por foto:** `POST /api/pos/identificar-producto-foto` — visión OpenAI (requiere `OPENAI_API_KEY`); devuelve candidatos de SKU; confirmación humana en flujo UI.
- **Cross-sell:** reglas en `data/cross_sell_associations.json` (incluye `rule_id` estable). Sugerencias vía lógica en `app.py`; API `GET /api/pos/cross-sell-sugerencias`, rechazo `POST /api/pos/cross-sell-reject`. **Memoria de rechazo:** sesión Flask `pos_cross_sell_rejected_rules` (y scope por vale); al emitir vale / vaciar carrito / borrar venta abierta se limpia con `_pos_cross_sell_clear_session_nueva_venta_pos()` para no ser intrusivo en la venta siguiente.

### C) Voice-to-Action (bodega)

- Vista: `GET /bodega/despachos` (permiso `bodega_operador`), template `bodega_despachos.html`.
- Audio: `POST /api/bodega/voice-command` — **Whisper** transcribe; **GPT-4o-mini** devuelve JSON (`accion`, `producto`, `cantidad`, `numero_vale`). Acciones: `descontar`, `marcar_despacho`, `verificar_stock`.
- Ejecución `descontar`/`marcar_despacho`: localiza vale `Pendiente` + `metodo_pago` vacío, matchea línea por nombre de producto, descuenta **bodega**, actualiza JSON + `bodega_despacho_estado`, kardex, opcional WhatsApp al cliente (mensaje de salida de mercadería).

---

## 5) Flujos de API y workers

### APIs REST bajo `/api/` (subset frecuente)

`POST /api/landing/lead` · enrolamiento (`/api/enrolamiento/*`) · cambios POS (`/api/cambios/*`) · recepciones (`/api/registrar_item_recepcion`, `/api/recepciones/*`) · inventario (`/api/guardar_conteo_inventario`) · **C360** `POST /api/c360/worker-noche`, `POST /api/c360/ocr-mock` · **bodega** `POST /api/bodega/voice-command` · **créditos/cobranza** `GET /api/creditos/cobranza/sugerencias`, `POST /api/creditos/cobranza/dispatch-cloud`, `GET /api/creditos/buscar_deudores` · **POS IA** `GET /api/pos/cross-sell-sugerencias`, `POST /api/pos/cross-sell-reject`, `POST /api/pos/identificar-producto-foto` · **WhatsApp / automatización** `POST /api/wa/consulta-stock` (Bearer `WA_CONSULTA_STOCK_SECRET` o fallback según doc), `POST /api/ventas/reabasto-dispatch-wa` (secreto `REABASTO_WA_CRON_SECRET` o fallback) · cotizaciones `GET /api/cotizaciones/buscar_*` · `GET /api/buscar_producto/<codigo>`.

### Workers / cron (HTTP POST con Bearer compartido)

- `POST /api/c360/worker-noche` — secreto `C360_CRON_SECRET` (o fallback documentado en código); ejecuta `c360_worker_recalcular_clientes`.
- `POST /api/creditos/cobranza/dispatch-cloud` — `COBRANZA_DISPATCH_CRON_SECRET`; envío recordatorios cuotas vía Cloud API.
- `POST /api/ventas/reabasto-dispatch-wa` — reabasto preventivo por WhatsApp.

### Función central WhatsApp Cloud

`_whatsapp_cloud_send_text(to_e164_digits, body)` — requiere `WHATSAPP_CLOUD_ACCESS_TOKEN`, `WHATSAPP_CLOUD_PHONE_NUMBER_ID`, opcional `WHATSAPP_CLOUD_API_VERSION`. Normalización Chile: `_telefono_whatsapp_chile_digits`. Otros usos de WA: C360 proximidad, despacho bodega voz, cotizaciones (rutas HTML que construyen enlaces/mensajes), cobranza UI, etc.

### Scripts offline (ejemplos en `scripts/`)

`c360_recalcular_clientes.py`, seeds, `cobranza_dispatch_cron.example.ps1`, `c360_worker_noche.example.sh` — plantillas para schedulers externos.

---

## 6) Reglas de negocio, seguridad y permisos

- **Caja estricta:** decorador `@caja_requerida` — lista `_ENDPOINTS_CAJA_ESTRICTA` exige caja abierta para POS y cobro; excepciones para evitar callejón con cierre.
- **Permisos representativos:** `pos_emitir_vale`, `caja_cobrar_vale`, `caja_abrir`, `caja_movimientos`, `caja_cerrar`, `gestionar_usuarios`, `admin_inventario`, `enrolamiento_inventario`, `bodega_operador`, `anular_vale_caja`, etc. Catálogo inicial `_PERMISOS_SISTEMA_INICIAL`; seed `_seed_permisos_catalogo_si_vacio()` y mapeo por nombre de rol en `_seed_permisos_roles_operativos()` (incluye **bodeguero/bodeguera** → `bodega_operador`).
- **Vales pendientes de cobro:** típicamente `estado == 'Pendiente'` y `metodo_pago` NULL/vacío (alineado con pantalla caja).
- **Stock:** no vender en POS sin stock tienda; no despachar voz sin stock bodega suficiente; cobro valida solo el remanente en tienda.
- **IA externa:** no loguear `OPENAI_API_KEY`; fallos degradados con mensajes UI.
- **WhatsApp:** respetar políticas Meta (plantillas fuera de ventana 24h, opt-in donde aplique).

---

## 7) Instrucción final para la otra IA

Cuando modifiques el sistema: (1) **preservá invariantes de stock** tienda/bodega/cobro; (2) **no rompas** estados de `ventas` ni la cola de caja; (3) **documentá** nuevas env vars y rutas API; (4) preferí **migraciones SQL** en `sql/` + `_asegurar_columnas_*` para compatibilidad legacy MySQL/Postgres; (5) antes de refactor grande, **grep** en `app.py` por tabla o endpoint afectado.

---

*Documento generado para transferencia de contexto entre instancias de IA / equipo técnico. Ruta en disco: `docs/PROMPT_MAESTRO_ERP.md`.*
