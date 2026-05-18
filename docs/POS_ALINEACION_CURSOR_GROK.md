# POS vendedora — documento de alineación (Cursor + Grok + producto)

**Propósito:** Un solo lugar donde quedan acuerdos, rechazos, estado de fases y decisiones técnicas.  
**Actualizar este archivo** cada vez que Grok proponga cambios, Cursor implemente, o cambie el criterio de negocio.

**Documentos relacionados:**

- `docs/POS_PANTALLA_VENDEDORA_AUDITORIA.md` — mapa técnico para auditar código
- `memory.md` — bitácora breve del proyecto (opcional)

**Última actualización:** 2026-05-17 (PAUSA — ver §12)  
**Versión cache POS (referencia):** `20260524a` (intento layout; **no validado por Mario**)  
**Estado alineación Grok v2:** ✅ Aceptada con ajustes menores (ver §4.7)  
**Estado Fase 1:** ✅ Aplicada 2026-05-17 · `checkpoint/pos-busqueda-hero-2026-05-17`  
**Estado Fase 2:** ✅ Aplicada 2026-05-17 · `checkpoint/pos-carrito-v3-2026-05-17`  
**Estado Fase 3 (layout mockup):** ⏸ **Pausado** — implementación no coincide con lo pedido (Mario revisará al regreso)

---

## 1. Roles y quién decide qué

| Rol | Responsabilidad | Peso en decisión |
|-----|-----------------|------------------|
| **Producto / Mario** | Prioridad, UX deseada, “sí aplícalo” | Final |
| **Cursor (agente con repo)** | Qué existe en código, riesgo de regresión, implementación | **Primera decisión técnica** (tiene el código) |
| **Grok** | Visión UX, diagnóstico, propuestas HTML/CSS/JS | Propone; no ejecuta en el repo |

**Regla:** Grok propone → Cursor valida contra el repo → Mario aprueba alcance (“aplícalo”) → Cursor implementa → se actualiza este doc.

---

## 2. Visión compartida (acordado)

### Diagnóstico crítico — de acuerdo

- **Búsqueda:** mayor dolor; debe sentirse premium; panel de sugerencias se rompía en ancho estrecho (letras apiladas).
- **Carrito v2:** mejor que tabla, pero denso; spinners y muchos controles inline.
- **Layout 3 zonas:** dock que salta, flex/`min-height: 0`, scrolls en conflicto.
- **Look general:** mucho Bootstrap gris; poca jerarquía; vendedora bajo presión necesita “no pensar”.

### Objetivo norte

Convertir `/punto_venta` con `pos_layout_fullwidth` en experiencia tipo **Square / Lightspeed / Shopify POS**, adaptada a ferretería chilena:

- Stock multi-almacén (tienda / bodega)
- Retiro por línea (Tienda / Bodega / Despacho)
- Cliente y crédito en flujo rápido

### Principio rector

**“Don't make me think”** + velocidad + belleza. Meta de diseño: agregar 5 productos en **&lt;15 s** sin mirar dos veces (validar con pistola + Enter real).

### Orden de fases — de acuerdo

| Fase | Enfoque | Riesgo |
|------|---------|--------|
| **1** | Búsqueda hero (visual + portal estable) | Bajo |
| **2** | Carrito tarjetas premium v3 | Medio |
| **3** | Layout 3 zonas + dock robusto (flex, no `fixed` a la ligera) | Medio-alto |
| **4** | Pulido (animaciones, F8, empty states, modo oscuro opcional) | Bajo |

---

## 3. Hecho importante que Grok debe asumir siempre

En **`pos_layout_fullwidth` (pantalla vendedora)** ya hay **un solo input** de producto:

- Include: `templates/pos/includes/unified_search_vendedor.html`
- ID: `#posBuscarManual`
- JS: `initPosManualSearch()` en `static/js/pos.js`

El **doble input** (`#posBarcodeWedge` + `#posBuscarManual`) solo existe en la rama `{% else %}` de `punto_venta.html` (POS clásico, no fullwidth).

**Fase 1 vendedora = rediseñar el include, no inventar unificación desde cero.**

---

## 4. Fase 1 — búsqueda hero: decisiones explícitas

### 4.1 Propuesta Grok (resumen)

- Pegar HTML hero en `punto_venta.html`
- Nuevo ID `#posBusquedaUnificada`
- Pills con filtro `todos` + operativo + tienda + catálogo
- Panel `#pos-search-suggestions` fuera del form
- Nueva función `initPosBusquedaUnificada()`
- Heurística Enter: `length < 8` = código de barras
- CSS verde `#10b981` + portal 460px

### 4.2 Tabla de veredicto (Cursor / repo)

| Ítem propuesta | Veredicto | Acción correcta |
|----------------|-----------|-----------------|
| HTML en `punto_venta.html` | **Rechazado** | Editar solo `unified_search_vendedor.html` |
| Renombrar a `#posBusquedaUnificada` solo | **Rechazado** | Mantener `#posBuscarManual`; alias opcional en `posInputBusqueda()` |
| Filtro **“Todos”** | **Rechazado** | Solo `operativo` \| `tienda` \| `catalogo` (backend) |
| Panel sugerencias fuera del `<form>` | **Rechazado** | Panel dentro del hero; portal lo mueve a `body` al abrir |
| `initPosBusquedaUnificada()` nueva | **Rechazado** | Extender `initPosManualSearch()` |
| Enter `length < 8` = barcode | **Rechazado** | Mantener `posPareceCodigoBarras()` (sin espacios, ≤60 chars) |
| CSS hero + input grande + pills | **Aceptado** | En `pos-premium-layout.css`, scope vendedora |
| Portal min-width 460px | **Aceptado** | Fusionar con `.pos-search-suggestions--portal` existente |
| Verde #10b981 como marca | **Rechazado** | Tokens ferretería (amarillo/navy en `pos-premium-layout.css`) |
| Botón `#posSearchTrigger` | **Opcional** | No bloqueante |
| Tarjetas sugerencia más premium (imagen, precio grande) | **Aceptado** | `renderItems()` + clase `--premium` |

### 4.3 Contrato HTML/JS que no se rompe en Fase 1

Estos IDs **deben existir** en `unified_search_vendedor.html`:

| ID | Uso en `pos.js` |
|----|-----------------|
| `posBuscarManual` | Input principal, F2, debounce, alineación portal |
| `posFiltroBusqueda` | Hidden: valor `operativo` \| `tienda` \| `catalogo` |
| `posBtnFiltroOperativo` | `wirePosFiltroBusquedaBotones()` |
| `posBtnFiltroTienda` | idem |
| `posBtnFiltroCatalogo` | idem |
| `pos-search-suggestions` | Panel único (`getElementById`) |
| `posBannerApedido` | Confirmación “a pedido” |
| `formAgregarProductoBusqueda` | Submit interceptado |
| `posSeleccionProductoId` | Hidden legacy |

Clases contenedor útiles para JS/CSS:

- `.pos-unified-search-hero` — `posEsBusquedaUnificada()` la detecta
- `.pos-unified-search-card` — card contenedora (se puede aligerar visualmente)

### 4.4 Flujo técnico actual (referencia)

```
Usuario escribe / escanea en #posBuscarManual
  → debounce 280ms, len≥3 → ejecutarBusqueda (interno initPosManualSearch)
  → GET /buscar_producto?enriquecido=1&filtro_pos=...
  → renderItems() → posMontarPanelBusqueda(panel, input)
  → clic / Enter en tarjeta → posEscanearYAgregar()
  → POST /api/pos/escanear-agregar
  → posRefrescarCarritoVendedor() → GET /api/pos/carrito-html
```

**Enter con código:** `posPareceCodigoBarras(q)` → escaneo directo sin abrir lista.

**Portal:** `posMontarPanelBusqueda` / `posDesmontarPanelBusqueda(panel)` — la desmontada **requiere** el nodo panel.

### 4.5 Archivos tocados en Fase 1 (cuando se implemente)

| Archivo | Cambio esperado |
|---------|-----------------|
| `templates/pos/includes/unified_search_vendedor.html` | Hero visual, mismos IDs |
| `static/css/pos-premium-layout.css` | Estilos hero + portal 460px + cards premium |
| `static/js/pos.js` | Mínimo: ancho portal, alias input opcional, renderItems premium |
| `templates/punto_venta.html` | Solo cache bust `?v=20260523a` (no duplicar HTML) |
| `docs/POS_PANTALLA_VENDEDORA_AUDITORIA.md` | Actualizar si cambia algo contractual |

**No tocar en Fase 1:** rama `{% else %}` POS clásico; carrito v3; dock; layout 3 columnas.

### 4.6 Checklist Fase 1 (marcar al implementar)

- [x] Checkpoint git: `checkpoint/pos-busqueda-hero-2026-05-17`
- [x] Hero visual en `unified_search_vendedor.html`
- [x] 3 filtros operativo / tienda / catálogo funcionando (IDs sin cambio)
- [x] Sugerencias legibles, portal min 480px + fix clic fuera con panel en body
- [x] Enter escaneo + Enter en tarjeta (sin cambio de lógica)
- [x] Ctrl+F5 con cache bust `20260523a`
- [x] Sin doble `#pos-search-suggestions` en DOM
- [ ] Tests smoke POS: `pytest tests/ -m smoke -q` (pendiente ejecutar en entorno QA)

**Estado Fase 1:** `IMPLEMENTADA` (2026-05-17) — validar en local con Ctrl+F5.

---

### 4.7 Propuesta Grok v2 (2026-05-17) — corregida y alineada

Grok confirmó lectura de este documento y aceptó las reglas contractuales. Propone Fase 1 en tres archivos: `unified_search_vendedor.html`, `pos-premium-layout.css`, toques mínimos `pos.js`.

**Veredicto Cursor:** ✅ **Aprobada como base**, con los **ajustes obligatorios** del §4.7.1 antes de merge. No pegar el HTML de Grok literal si falta algún ítem del contrato §4.3.

#### 4.7.1 Ajustes obligatorios sobre el HTML de Grok

| Tema | Propuesta Grok | Qué hacer al implementar |
|------|----------------|-------------------------|
| **`<form>`** | No incluye `formAgregarProductoBusqueda` | Mantener `<form id="formAgregarProductoBusqueda" method="POST" action="{{ url_for('agregar_producto_venta') }}">` envolviendo hero + hidden + panel |
| **Banner a pedido** | Ausente | Mantener `<div>` → `<div>` no; mantener `<div>` → `id="posBannerApedido"` |
| **Panel sugerencias** | Sin `d-none` ni ARIA | `class="pos-search-suggestions d-none mt-2"` + `role="listbox"` + `aria-label` |
| **Filtros activos** | Clase CSS `.active` en pills | JS usa `btn-primary` / `btn-outline-secondary` vía `syncPosFiltroBusquedaBotones()` — **no** depender solo de `.active` en CSS; dejar que JS sincronice al cargar |
| **`data-filtro`** | En botones | Opcional (decorativo); la verdad es `#posFiltroBusqueda` + clicks en IDs existentes |
| **Botón Foto** | Ausente | Mantener enlace a `#modalPosFotoSku` (demo SKU por foto) si el modal sigue en `punto_venta.html` |
| **Hint + F2** | Ausente | Recomendado: línea corta “F2 enfoca · ↑↓ sugerencias · Esc cierra” y `<kbd>F2</kbd>` (F2 ya en `pos.js` ~3301) |
| **`autofocus`** | En input | **Evitar** o usar con cuidado: puede pelear con foco post-RUT / pistola; preferir foco programático existente |
| **Input classes** | `pos-search-input-hero` | OK; puede convivir con `pos-unified-search__input` o reemplazar si CSS hero cubre todo |
| **Card exterior** | Grok quita `card card-ds` | OK quitar caja gris; hero `.pos-unified-search-hero` lleva sombra (menos anidación) |
| **Colores CSS** | Bootstrap azul `#0d6efd` | **Cambiar** a tokens ferretería: `--pos-ferre-amarillo`, `--pos-navy-mid` (§4.2) |
| **`.pos-search-card` global** | Hover en todas las cards | Scope `body.pos-pantalla-vendedora` o `.pos-search-suggestions--portal` para no afectar command deck |

#### 4.7.2 HTML de referencia para implementación (fusión Grok + contrato)

*Cursor usará esta estructura al recibir “aplícalo” (no copiar ciego el paste de Grok).*

```html
{# unified_search_vendedor.html — Fase 1 hero #}
<div class="pos-unified-search-card mb-3">
  <form method="POST" action="{{ url_for('agregar_producto_venta') }}" class="m-0" id="formAgregarProductoBusqueda">
    <input type="hidden" name="producto_id" id="posSeleccionProductoId" value="">
    <input type="hidden" id="posFiltroBusqueda" value="operativo" autocomplete="off">

    <div class="pos-unified-search-hero">
      <div class="pos-search-hero__inner">
        <!-- toolbar filtros + foto -->
        <div class="pos-search-hero__toolbar d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <div class="pos-search-filters d-flex gap-2 flex-wrap" role="group" aria-label="Filtro listado POS">
            <button type="button" class="btn btn-sm btn-primary" id="posBtnFiltroOperativo" title="Tienda, bodega y a pedido">Operativo</button>
            <button type="button" class="btn btn-sm btn-outline-secondary" id="posBtnFiltroTienda" title="Solo mostrador">Solo tienda</button>
            <button type="button" class="btn btn-sm btn-outline-secondary" id="posBtnFiltroCatalogo" title="Catálogo completo">Catálogo</button>
          </div>
          <button type="button" class="btn btn-sm btn-link text-secondary py-0" data-bs-toggle="modal" data-bs-target="#modalPosFotoSku">Foto</button>
        </div>

        <label class="visually-hidden" for="posBuscarManual">Buscar o escanear producto</label>
        <div class="input-group input-group-lg pos-search-hero__field">
          <span class="input-group-text bg-white border-end-0"><i class="fas fa-barcode fa-fw"></i></span>
          <input type="text" id="posBuscarManual"
                 class="form-control form-control-lg pos-search-input-hero font-monospace"
                 autocomplete="off" autocorrect="off" spellcheck="false"
                 placeholder="Escanea código o escribe nombre / SKU (3+ letras) — Enter agrega">
          <span class="input-group-text bg-white border-start-0 text-muted"><kbd class="mb-0">F2</kbd></span>
        </div>
        <p class="pos-search-hero__hint mb-0">Pistola y teclado en el mismo campo. Flechas ↑↓ en sugerencias, Esc cierra.</p>

        <div id="posBannerApedido" class="pos-banner-apedido d-none mt-2" role="alert" aria-live="polite"></div>
        <div id="pos-search-suggestions" class="pos-search-suggestions d-none mt-2" role="listbox" aria-label="Sugerencias de productos"></div>
      </div>
    </div>
  </form>
</div>
```

*(Nota: en el repo real usar `<div>` en lugar de `<div>` — aquí se evita confundir con tags HTML.)*

*(Bloque §4.7.2 listo para `unified_search_vendedor.html` al implementar Fase 1.)*

#### 4.7.3 CSS Grok v2 — qué tomar

| Regla Grok | Estado |
|------------|--------|
| `.pos-unified-search-hero` padding/sombra/radius | ✅ Tomar |
| `.pos-search-input-hero` tamaño/focus | ✅ Tomar con colores ferretería en `:focus` |
| `.pos-search-filters button` pills | ✅ Tomar; estado activo vía `.btn-primary` del JS |
| Portal `min-width: 480px` | ✅ Tomar (fusionar bloque existente `--portal`) |
| Hover `.pos-search-card` global | ⚠️ Solo scoped vendedora/portal |

#### 4.7.4 JS — toques mínimos acordados (sin `initPosBusquedaUnificada`)

1. `posMontarPanelBusqueda`: `Math.max(480, rect.width)` en vendedora.
2. `renderItems`: añadir clase `pos-search-card--premium` en cada `<article>` (opcional Fase 1).
3. F2: ya existe listener global; verificar que no se duplique tras cambios.
4. **No** tocar `ejecutarBusqueda`, `posPareceCodigoBarras`, ni crear segunda init.

---

## 5. Fase 2 — Carrito v3 (implementada 2026-05-17)

### Entregado

- `premium_cart_cards.html`: clase `pos-cart-card--v3`, chips esquina (stock / retiro / a pedido), menú ⋯ descuento, botón eliminar grande al hover
- `pos-premium-layout.css`: bloque Fase 2 (padding 20px+, radius 16px, cápsula cantidad grande, empty state)
- `pos.js`: scroll suave al activar línea; chip retiro se actualiza al cambiar select; delete btn en exclusión de clic

### Checklist Fase 2

- [x] Checkpoint `checkpoint/pos-carrito-v3-2026-05-17`
- [x] IDs críticos intactos (`pos_row_*`, `cantidad_*`, `descuento_*`, `pos-retiro-select`)
- [x] Cache bust `20260523b`
- [ ] Validación manual Mario (cantidad, retiro, dto, eliminar)
- [ ] Tests smoke (opcional)

---

## 6. Fases 3–4 — pendientes

### Fase 3 — Layout + dock

- Flex columna con `min-height: 0`; carrito con scroll propio
- Dock al final del flujo; **evitar** `position: fixed` global sin diseño (franja blanca histórica)
- En 1366×768 preferir **2 columnas + dock** antes que 3 columnas apretadas

### Fase 4 — Pulido

- F2 búsqueda, F8 emitir, toasts unificados, empty state carrito
- Modo oscuro: solo si hay tiempo; no mezclar con Fase 1–3

---

## 7. Retiro por línea — alineación negocio (ya en código)

| Momento | Comportamiento |
|---------|----------------|
| Al **agregar** línea | Sugerencia automática: stock tienda → Tienda; solo bodega → Bodega; si no hay → Tienda |
| En **carrito** | Select manual Tienda / Bodega / Despacho por línea (`pos_retiro_por_linea` empresa) |
| Al **emitir** | Valida stock; no descuenta |
| Al **cobrar** | Descuenta según retiro efectivo por línea |

No confundir con “bloquear el select al lugar del producto”: el vendedor **puede cambiar** el retiro después.

---

## 8. Registro de mensajes / iteraciones

Usar esta tabla para no perder el hilo entre agentes.

| Fecha | Autor | Resumen | Decisión |
|-------|-------|---------|----------|
| 2026-05-16 | Grok | Diagnóstico crítico + plan Fases 1–4 + propuesta HTML/JS Fase 1 | Visión aceptada; implementación literal rechazada (ver §4.2) |
| 2026-05-16 | Cursor | Validación contra repo: include ya unificado, IDs, filtros, no duplicar init | Documentado en este archivo |
| 2026-05-16 | Mario | Pedido de documento vivo para alineación Cursor+Grok | Este archivo creado |
| 2026-05-17 | Grok | Lee doc; acepta reglas; envía Fase 1 v2 (hero en include, mismos IDs) | **Aprobada** con §4.7.1 |
| 2026-05-17 | Cursor | Revisión v2: falta form, banner, ARIA, colores ferretería; HTML fusión en §4.7.2 | Listo para “aplícalo” |
| 2026-05-17 | Mario | “aplícalo Fase 1” | Implementado: include hero, CSS, pos.js portal 480px |
| 2026-05-17 | Cursor | Fase 1 aplicada; tag checkpoint; cache 20260523a | Ver §4.6 checklist |
| 2026-05-17 | Mario | “vamos con fase 2” | Fase 2 carrito v3 implementada |
| 2026-05-17 | Cursor | Fase 2: premium_cart_cards v3, CSS, pos.js scroll/retiro chip | cache `20260523b` |
| 2026-05-17 | Mario | Mockup Paint (recuadros verdes): layout buscador + columnas | Ver §12 |
| 2026-05-17 | Cursor | Intento Fase 3 + fix stock bodega + retiro suave | cache `20260524a` — **Mario: no es lo pedido** |
| 2026-05-17 | Mario | Pausa; revisará al regreso | Retomar §12 + `docs/memory.md` |
| | | | |

*(Agregar filas abajo en cada conversación.)*

---

## 9. Respuesta lista para copiar a Grok (versión corta)

> En fullwidth ya tenemos un buscador unificado en `unified_search_vendedor.html` (`#posBuscarManual` + `initPosManualSearch`). No peguemos otro bloque en `punto_venta.html`. No usemos filtro “Todos” (backend solo operativo/tienda/catalogo). No creemos `initPosBusquedaUnificada` en paralelo. Fase 1 = hero visual en el include + CSS premium + portal 460px + mismos IDs. El Enter para pistola sigue con `posPareceCodigoBarras`, no `length < 8`. Colores al design system ferretería, no verde genérico. Cuando Mario diga “aplícalo”, Cursor implementa y actualiza `docs/POS_ALINEACION_CURSOR_GROK.md`.

---

## 10. Cómo actualizar este documento

1. **Nueva propuesta de Grok:** añadir fila en §7 y, si aplica, filas en §4.2 (veredicto).
2. **Implementación hecha:** marcar checklist §4.6, cambiar “Estado Fase N”, anotar cache bust y tag git.
3. **Cambio de criterio de Mario:** párrafo en §2 o nueva subsección con fecha.
4. **Conflicto Cursor vs Grok:** ganar siempre la verificación en repo; documentar el “por qué” en §4.2.

---

## 11. Próximo paso acordado

1. ~~Fase 1~~ ✅ ~~Fase 2~~ ✅ (2026-05-17).
2. **PAUSA (2026-05-17):** Mario validará al regreso; layout Fase 3 **no aprobado**.
3. Al regreso: **§12** — alinear mockup Paint antes de más código.
4. Después: Fase 4 (F8 emitir, toasts, pulido).

---

## 12. PAUSA — retomar conversación (2026-05-17)

**Transcript Cursor:** `agent-transcripts/2bee32c7-0747-4320-9f77-33b17db4c0d0/2bee32c7-0747-4320-9f77-33b17db4c0d0.jsonl`

**Criterio Mario (mockup):**

- Buscador **hero ancho en la franja superior** (no encerrado en columna izquierda estrecha).
- Debajo: **grid 2 columnas** — izquierda = cliente + búsqueda/resultados alineados; derecha = carrito + dock fijo.
- Retiro por línea usable sin UX brusca.
- Stock búsqueda ↔ carrito coherente (tienda/bodega/a pedido).

**Lo que hizo Cursor (y Mario rechazó como “no es lo pedido”):**

- Mover `unified_search_vendedor.html` a `.pos-vendedor-search-stage` encima del grid (`punto_venta.html`).
- Parches: `_pos_puede_sumar_unidad` (bodega), `stock_bodega` en carrito, `pos-retiro-select--saving`.

**Al retomar, preguntar a Mario:**

1. ¿El buscador debe estar **solo arriba** o también visible en la columna izquierda?
2. ¿Panel de sugerencias: portal full-width o dentro de la columna?
3. ¿Revertir el movimiento del include hasta acordar wireframe?

**Bitácora extendida:** `docs/memory.md` → sección “POS vendedora — PAUSA para retomar”.

### Mensaje para Grok (post-revisión Cursor)

> Propuesta v2 aceptada. Al implementar usaremos tu hero + nuestro `<form>`, `#posBannerApedido`, panel con `d-none`+ARIA, botón Foto, hint F2, y colores ferretería (no `#0d6efd`). Los filtros siguen con `btn-primary`/`outline` manejados por `syncPosFiltroBusquedaBotones`. JS: solo ancho portal 480px y clase premium en tarjetas; sin `initPosBusquedaUnificada`. Cuando Mario diga “aplícalo”, Cursor mergea §4.7.2 en el repo.

---

*Documento vivo — no borrar historial de §7; solo agregar filas.*
