# POS pantalla vendedora — documento para auditoría de código

**Fecha de referencia:** 2026-05-16  
**Ruta:** `GET /punto_venta` (cuando `pos_layout_fullwidth` está activo)  
**Cache bust actual:** `20260522d` en `punto_venta.html` (`pos.js` y `pos-premium-layout.css`)

Este documento describe qué hace la página POS vendedor, qué archivos intervienen, flujos HTTP/JS y problemas conocidos. Está pensado para que **otro agente o revisor** audite el código sin depender del historial del chat.

---

## 1. Objetivo de la pantalla

Pantalla de armado de vale para el vendedor:

1. **Buscar/agregar productos** (código de barras o texto).
2. **Editar el carrito** (cantidad, descuento, retiro por línea).
3. **Identificar cliente** y ver cupo crédito.
4. **Emitir vale** desde el dock inferior.

Layout en **3 zonas**:

| Zona | Contenedor HTML | Contenido |
|------|-----------------|-----------|
| Izquierda | `.pos-premium-col--tools` | Buscador unificado, identificación cliente, historial |
| Derecha | `.pos-premium-col--cart` → `#posCartHost` | Carrito tarjetas v2 |
| Abajo | `#posCheckoutDock` | Total, cliente, botón emitir |

Clases de body relevantes: `pos-layout-fullwidth`, `pos-pantalla-vendedora`.

---

## 2. Mapa de archivos (prioridad para auditoría)

### Templates

| Archivo | Rol |
|---------|-----|
| `templates/punto_venta.html` | Página principal; layout vendedor; `#pos-config` JSON; dock; cache bust |
| `templates/pos/includes/unified_search_vendedor.html` | Input `#posBuscarManual`, panel `#pos-search-suggestions` |
| `templates/pos/includes/premium_cart_cards.html` | Carrito v2: tarjetas, `.pos-retiro-select`, cantidades, eliminar |

### JavaScript

| Archivo | Rol |
|---------|-----|
| `static/js/pos.js` | Toda la lógica cliente: búsqueda, carrito AJAX, retiro, cliente, emisión |

### CSS

| Archivo | Rol |
|---------|-----|
| `static/css/pos-premium-layout.css` | Grid 2 columnas, dock vendedor, carrito v2, panel búsqueda portal |
| `static/css/design-system.css` | Estilos base `.pos-search-card`, `.pos-search-suggestions` |

### Backend (Flask)

| Archivo | Rol |
|---------|-----|
| `app.py` | Rutas POS, APIs `/api/pos/*`, `actualizar_item`, `buscar_producto`, contexto página |
| `blueprints/pos.py` | Registro de rutas POS y wrappers de permisos |
| `services/stock_service.py` | Stock por línea / retiro efectivo (`_consumo_tienda_linea`, etc.) |
| `data/empresa_config.json` | Flag `pos_retiro_por_linea` |

### Tests relacionados (referencia)

- `tests/test_pos_ticket_despacho.py`
- `tests/test_routes_criticas.py` (rutas POS si aplica)

---

## 3. Configuración JS (`#pos-config`)

En `punto_venta.html` hay un `<script type="application/json" id="pos-config">` leído por `readPosConfig()` en `pos.js`.

Campos importantes:

```json
{
  "pos_retiro_por_linea": true|false,
  "descuento_libre": true|false,
  "urls": {
    "buscar_producto": "/buscar_producto",
    "agregar_producto": "/agregar_producto_venta",
    "actualizar_item": "/actualizar_item",
    "escanear_agregar": "/api/pos/escanear-agregar",
    "carrito_html": "/api/pos/carrito-html",
    "retiro_linea": "/api/pos/retiro-linea",
    "vincular_cliente": "/api/pos/vincular-cliente",
    ...
  }
}
```

**Auditar:** que `retiro_linea` exista y que `pos_retiro_por_linea` coincida con la config de empresa (`_pos_retiro_por_linea_empresa()` en `app.py`).

---

## 4. Estructura HTML (vendedor fullwidth)

```
.container-fluid.pos-vendedor-page
  header.pos-vendedor-chrome
  div.pos-vendedor-body                    ← flex columna
    div.pos-premium-shell
      div.pos-premium-grid                 ← grid tools | cart
        div.pos-premium-col--tools
          include unified_search_vendedor.html
          ...
        div.pos-premium-col--cart
          div.pos-sale-card
            div#posCartHost.card-body
              include premium_cart_cards.html
              → #contenedor-carrito.pos-cart-list
    footer#posCheckoutDock.pos-checkout-dock--vendedor
```

**Nota layout:** el dock va **dentro** de `pos-vendedor-body`, no `position: fixed` global (evita franja blanca y solapamiento).

---

## 5. Flujo: asistente de precios (búsqueda)

### Archivos

- Template: `unified_search_vendedor.html` → `#posBuscarManual`, `#pos-search-suggestions`
- JS: `pos.js` → `initPosManualSearch(buscarUrl)`

### Secuencia

1. Usuario escribe ≥3 caracteres en `#posBuscarManual`.
2. `ejecutarBusqueda(term)` → `GET buscar_producto?q=...&origen=pos&enriquecido=1&filtro_pos=operativo|tienda|catalogo`.
3. Respuesta esperada: `{ "results": [ { producto_id, nombre, codigo, precio, stock_tienda, stock_bodega, semaforo, badges, ... } ] }`.
4. `renderItems(items)` genera HTML de `.pos-search-card` (grid 3 columnas en `design-system.css`).
5. Clic en tarjeta o Enter → `seleccionarItem()` → `posEscanearYAgregar(producto_id)`.
6. `POST /api/pos/escanear-agregar` (JSON) → agrega línea al vale abierto de la caja.
7. Éxito → `posRefrescarCarritoVendedor()` sin reload de página.

### Funciones JS clave

| Función | Propósito |
|---------|-----------|
| `initPosManualSearch` | Inicializa input, debounce, teclado ↑↓, panel |
| `renderItems` | Pinta tarjetas en `#pos-search-suggestions` |
| `posMontarPanelBusqueda` | Mueve panel a `document.body` + `position:fixed` (ancho ≥300px) |
| `posDesmontarPanelBusqueda` | Devuelve panel al DOM original al cerrar |
| `posEscanearYAgregar` | POST escanear-agregar |
| `posRetiroSugeridoDesdeItem` | Sugiere Tienda/Bodega según stock al agregar |

### Bug histórico (búsqueda)

**Síntoma:** nombres de producto mostrados como **letras apiladas verticalmente** (una letra por línea).

**Causa probable:** panel de sugerencias en columna izquierda demasiado estrecha o posicionamiento inline sin `position:fixed` efectivo (clase `--floating` sin reglas CSS).

**Corrección aplicada (20260522d):**

- `posMontarPanelBusqueda` / `pos-search-suggestions--portal` en `pos-premium-layout.css`.
- Panel montado en `body` con ancho calculado desde `getBoundingClientRect()` del input.

### Backend búsqueda

- `app.py` → `buscar_producto()` (~línea 14048).
- Usa `services/pos_busqueda_service.py` para filtro operativo/tienda/catálogo.

---

## 6. Flujo: carrito (sin recargar página)

### Template carrito

`premium_cart_cards.html`:

- Cada línea: `<article class="pos-cart-card pos-cart-card--v2" id="pos_row_{detalle_id}">`
- Cantidad: `.cantidad-input`, botones `.btn-ajustar-cantidad`
- Retiro (si flag empresa): `<select class="pos-retiro-select" data-detalle-id="...">`
- Eliminar: form `.pos-cart-card__delete-form`

### Refresco AJAX

| Paso | Función | HTTP |
|------|---------|------|
| Recargar HTML carrito | `posRefrescarCarritoVendedor()` | `GET /api/pos/carrito-html` |
| Backend | `api_pos_carrito_html()` | Renderiza `premium_cart_cards.html` → JSON `{ ok, html, venta_total, items_count }` |
| Tras refresh | `wirePosCartV2()`, `posBindCartLineHandlers()` | Re-enlaza eventos |

### Persistir cantidad/descuento

- `posPersistirLineaAjax(detalleId, urlActualizarItem, opts)`
- `POST /actualizar_item` con `FormData`: `actualizar`, `cantidad_*`, `descuento_*`, `pos_ajax=1`
- Respuesta JSON: `{ ok, venta_total, items_count, mensaje? }`

### Eliminar línea

- `posEliminarLineaCarrito(form)` → `POST` al action del form con `pos_ajax=1`

### UI carrito v2

- `wirePosCartV2()`: clic en tarjeta activa línea; **ignora** clics en `.pos-retiro-select`, inputs, toolbar (`.closest(...)`).

---

## 7. Flujo: retiro por línea

### Activación

- Config empresa: `pos_retiro_por_linea` = `"1"` en `data/empresa_config.json` o admin empresa.
- Python: `_pos_retiro_por_linea_empresa()` en `app.py`.
- Si desactivado, el `<select>` no se renderiza en `premium_cart_cards.html`.

### Valores permitidos

`Tienda` | `Bodega` | `Despacho` (columna `detalle_ventas.punto_retiro_linea`).

### Frontend (actual)

| Función | Comportamiento |
|---------|----------------|
| `posBindRetiroLineaHandlers()` | Listener global `change` en `document` (una sola vez) |
| `posActualizarRetiroLinea(detalleId, valor, url)` | POST JSON a `/api/pos/retiro-linea` si URL contiene esa ruta; si no, fallback `actualizar_item` + `solo_retiro_linea` |
| `posUrlRetiroLinea(cfg)` | Lee `cfg.urls.retiro_linea` |
| `mousedown` capture | `stopPropagation` en `.pos-retiro-select` para no interferir con foco de tarjeta |

**Body JSON esperado:**

```json
{
  "detalle_id": 123,
  "punto_retiro_linea": "Bodega"
}
```

**Respuesta OK:**

```json
{
  "ok": true,
  "punto_retiro_linea": "Bodega",
  "venta_total": 661900,
  "items_count": 5
}
```

### Backend

- `app.py` → `api_pos_retiro_linea()` (~línea 12001)
- Ruta: `blueprints/pos.py` → `POST /api/pos/retiro-linea`, wrapper `_wrap_pos_api_emitir` (permiso `pos_emitir_vale`, login)

**Validaciones servidor:**

- Permiso `pos_emitir_vale`
- `_pos_retiro_por_linea_empresa()` activo
- Detalle existe, venta `estado == 'Abierta'`
- `detalle.venta.caja_id == caja_activa.id`

### Ruta legacy (alternativa)

`POST /actualizar_item` con:

- `actualizar={detalle_id}`
- `solo_retiro_linea=1`
- `punto_retiro_linea=Tienda|Bodega|Despacho`
- `pos_ajax=1`

Función helper: `_json_tras_actualizar_item_pos` (si se usa esta vía).

### Stock / negocio (referencia)

| Momento | Comportamiento stock |
|---------|---------------------|
| Emitir vale | Valida disponibilidad; **no** descuenta stock |
| Cobrar en caja | Descuenta tienda en líneas Tienda/Despacho |
| Línea Bodega | Validación bodega al cobro; descuento en retiro bodega |
| QR ticket despacho | Solo lectura |

Revisar: `services/stock_service.py` → `_punto_retiro_efectivo_linea`, `_consumo_tienda_linea`.

---

## 8. Flujo: dock y emisión de vale

- HTML: `#posCheckoutDock` en `punto_venta.html`
- CSS: `.pos-checkout-dock--vendedor` en `pos-premium-layout.css` (`position: relative`, `flex-shrink: 0`)
- JS: `actualizarTotalesVisuales()`, `actualizarEstadoEmisionVale()`, `posAsegurarDockVisible()`
- Emisión: form/modal existente hacia rutas de guardar/finalizar venta (revisar handlers al final de `pos.js` y forms en template)

---

## 9. APIs POS registradas (`blueprints/pos.py`)

Relevantes para pantalla vendedora:

| Método | Ruta | Handler `app.py` |
|--------|------|------------------|
| GET | `/api/pos/carrito-html` | `api_pos_carrito_html` |
| POST | `/api/pos/retiro-linea` | `api_pos_retiro_linea` |
| POST | `/api/pos/escanear-agregar` | `api_pos_escanear_agregar` |
| POST | `/api/pos/vincular-cliente` | `api_pos_vincular_cliente` |
| GET | `/api/pos/vales-hoy` | `api_pos_vales_hoy` |

Rutas clásicas (form POST):

| Método | Ruta | Notas |
|--------|------|-------|
| GET/POST | `/punto_venta` | Render página |
| POST | `/agregar_producto_venta` | Alta por form (legacy) |
| POST | `/actualizar_item` | Cantidad, descuento, retiro legacy |

---

## 10. Inicialización al cargar la página

En `pos.js`, al `DOMContentLoaded` (bloque principal ~línea 2900+):

1. `readPosConfig()` → `cfg`, `u = cfg.urls`
2. `initPosManualSearch(u.buscar_producto)` si existe `#posBuscarManual`
3. `posBindCartLineHandlers(u, descLibre)` → cantidad, descuento, retiro
4. `wirePosCartV2()` → foco tarjetas
5. Cliente: `initPosClienteUiFromConfig`, botones TV/RUT
6. Delegado global submit para `.pos-cart-card__delete-form`

Tras cada `posRefrescarCarritoVendedor()`:

- Reemplaza `innerHTML` de `#posCartHost`
- Reset `dataset.posCartV2Wired` en `#contenedor-carrito`
- Vuelve a llamar `wirePosCartV2()`, `posBindCartLineHandlers()`, `posBindRetiroLineaHandlers()`

---

## 11. Problemas conocidos / puntos de auditoría

### A. Búsqueda — panel estrecho

- [ ] Verificar que `posMontarPanelBusqueda` se llama en cada `syncPanelBusquedaVisible` / `renderItems`
- [ ] Verificar CSS `.pos-search-suggestions--portal` (min-width 300px)
- [ ] Confirmar que al cerrar panel se llama `posDesmontarPanelBusqueda` (panel vuelve al form)

### B. Retiro por línea — sin POST en servidor

- [ ] En DevTools → Network: al cambiar `<select>` debe aparecer `POST /api/pos/retiro-linea` 200
- [ ] Confirmar `pos_retiro_por_linea: true` en `#pos-config`
- [ ] Confirmar selects presentes en HTML (`premium_cart_cards.html`)
- [ ] Revisar que ningún overlay/z-index tape el select (dock, modales)
- [ ] `overflow: hidden` en `.pos-premium-col--cart` no debe impedir interacción con `<select>` nativo

### C. Dock alto / contenido cortado

- [ ] Revisar cadena flex: `app-main` → `pos-vendedor-page` → `pos-vendedor-body` → grid
- [ ] Altura dock: variables CSS `--pos-dock-height` si existen
- [ ] `#contenedor-carrito` debe tener `overflow-y: auto` y `min-height: 0`

### D. Código fragmentado

- [ ] Estilos inline en `punto_venta.html` (<style> bloque grande) vs `pos-premium-layout.css`
- [ ] Duplicidad retiro: API nueva vs `actualizar_item` + `solo_retiro_linea`
- [ ] Cache bust: forzar Ctrl+F5 si el navegador sirve `pos.js` antiguo (`20260521h` etc.)

### E. Permisos y caja

- APIs emitir requieren `pos_emitir_vale` + caja abierta según endpoint
- `@caja_requerida` en algunas rutas clásicas; APIs en `_wrap_pos_api_emitir` solo login + permiso

---

## 12. Plan de prueba manual (checklist)

1. Abrir `/punto_venta` con caja abierta y permiso vendedor.
2. **Ctrl+F5** (cache `20260522d`).
3. Buscar producto (≥3 letras): tarjetas legibles, nombre horizontal.
4. Agregar producto: carrito se actualiza sin reload completo.
5. Cambiar cantidad +/-: `POST /actualizar_item` con `pos_ajax=1`.
6. Cambiar retiro Tienda/Bodega/Despacho: `POST /api/pos/retiro-linea` JSON 200.
7. Recargar página: retiro persistido en BD (`detalle_ventas.punto_retiro_linea`).
8. Emitir vale: flujo completo según reglas de negocio.

Comandos útiles:

```bash
# Tests smoke POS (si aplica)
pytest tests/ -m smoke -q --tb=no

# Buscar referencias retiro
rg "pos-retiro-select|api_pos_retiro_linea|pos_retiro_por_linea" .
```

---

## 13. Cambios recientes (para diff / git)

Archivos modificados en el arreglo UI POS vendedor:

- `templates/punto_venta.html` — URL `retiro_linea` en config, cache `20260522d`
- `templates/pos/includes/premium_cart_cards.html` — select retiro sin `onchange="submit"`
- `static/js/pos.js` — portal búsqueda, API retiro, carrito AJAX
- `static/css/pos-premium-layout.css` — portal, retiro select, layout grid
- `app.py` — `api_pos_retiro_linea()`, ajustes stock por línea al emitir
- `blueprints/pos.py` — registro `/api/pos/retiro-linea`

Tag checkpoint sugerido (si existe en repo): `checkpoint/pos-dock-3zonas-2026-05-16`

---

## 14. Referencias rápidas de líneas (aproximadas)

> Los números pueden variar si el archivo creció; usar `rg`/IDE para ubicar exacto.

| Símbolo | Archivo | Ubicación aprox. |
|---------|---------|------------------|
| `api_pos_retiro_linea` | `app.py` | ~12001 |
| `api_pos_carrito_html` | `app.py` | ~11973 |
| `api_pos_escanear_agregar` | `app.py` | ~12037 |
| `buscar_producto` | `app.py` | ~14048 |
| `initPosManualSearch` | `static/js/pos.js` | ~620 |
| `posMontarPanelBusqueda` | `static/js/pos.js` | ~273 |
| `posBindRetiroLineaHandlers` | `static/js/pos.js` | ~395 |
| `posActualizarRetiroLinea` | `static/js/pos.js` | ~510 |
| `posRefrescarCarritoVendedor` | `static/js/pos.js` | ~545 |
| `wirePosCartV2` | `static/js/pos.js` | ~580 |
| Registro rutas POS | `blueprints/pos.py` | `register_pos_routes` |

---

## 15. Preguntas para el agente auditor

1. ¿Hay race conditions entre `posCartPersistBusy` y `posActualizarRetiroLinea` (select `disabled`)?
2. ¿El panel portal de búsqueda deja fugas DOM si el usuario navega sin cerrar sugerencias?
3. ¿`api_pos_retiro_linea` debe exigir `@caja_requerida` explícitamente?
4. ¿Conviene unificar todo en `/api/pos/linea` (cantidad + retiro + descuento) en lugar de `actualizar_item`?
5. ¿Los tests E2E cubren cambio de retiro y búsqueda en pantalla vendedora?

---

*Fin del documento de auditoría.*
