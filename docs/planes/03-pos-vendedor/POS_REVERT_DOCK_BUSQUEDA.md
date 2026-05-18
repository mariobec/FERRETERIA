# Revertir — dock relayout + búsqueda alta (POS vendedora)

**Implementado:** 2026-05-25 · cache `20260525e`  
**Commit:** `5094d5d` — `feat(pos): búsqueda alta 78vh y dock vendedor reorganizado`  
**Tag git (antes del relayout dock):** `checkpoint/pos-dock-busqueda-alta-pre`

## Qué hace el cambio

1. **Panel de búsqueda** (`#pos-search-suggestions` en portal): altura hasta **`min(78vh, calc(100vh - 6rem))`**, scroll vertical, tarjetas compactas.
2. **Columna izquierda:** RUT/TV + buscador hero; zona inferior del viewport libre para que el portal no quede tapado.
3. **Dock (franja azul derecha ~58%):**
   - **Fila identidad:** nombre completo + RUT + Cambiar.
   - **Debajo:** barra de crédito (`#posDockCreditoStrip`).
   - **A la derecha:** total a emitir + Cotizar + Emitir vale.
4. **Flag Jinja:** `pos_dock_relayout_busqueda` en `punto_venta.html` (~línea 3) activa clase body `pos-dock-relayout-busqueda`.

## Revertir en 30 segundos (sin git)

En `templates/punto_venta.html` línea ~3:

```jinja
{% set pos_dock_relayout_busqueda = pos_layout_fullwidth and false %}
```

Ctrl+F5 en `/punto_venta` (forzar recarga de CSS/JS si hace falta: cache `20260525e` o borrar query antigua).

## Revertir con git

Solo el bloque POS (sin tocar el resto del commit):

```bash
git checkout checkpoint/pos-dock-busqueda-alta-pre -- \
  templates/punto_venta.html \
  templates/pos/includes/premium_cart_cards.html \
  templates/pos/includes/unified_search_vendedor.html \
  static/css/pos-premium-layout.css \
  static/js/pos.js
```

Volver al commit anterior completo:

```bash
git revert 5094d5d --no-edit
```

## Archivos del feature

| Archivo | Cambio |
|---------|--------|
| `templates/punto_venta.html` | Flag, body class, HTML dock `pos-dock-zone-left` + `pos-dock-zone-right` |
| `templates/pos/includes/unified_search_vendedor.html` | Hero búsqueda Fase 1 |
| `templates/pos/includes/premium_cart_cards.html` | Carrito v3, chips stock/retiro |
| `static/css/pos-premium-layout.css` | Grid altura, portal 78vh, dock relayout |
| `static/js/pos.js` | Portal, `posRenderCreditoCliente` (dock), retiro línea |
| `app.py` | Stock bodega al agregar, `stock_bodega` en carrito, APIs POS |
| `blueprints/pos.py` | Rutas `carrito-html`, `retiro-linea`, etc. |

## Validación rápida

1. Buscar `est` (3+ letras) → lista larga con borde azul, muchas filas visibles.
2. Dock: nombre en franja azul (no caja blanca a la izquierda); crédito debajo del nombre.
3. Total y botones pegados a la derecha.
4. Producto solo bodega: agrega al vale; chip puede mostrar `0 T / N B`.

## Documentación relacionada

- `../03-pos-vendedor/POS_ALINEACION_CURSOR_GROK.md` — §13 estado final
- `../03-pos-vendedor/POS_PANTALLA_VENDEDORA_AUDITORIA.md` — mapa técnico
- `docs/memory.md` — bitácora sesión POS
