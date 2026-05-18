# Revertir — dock relayout + búsqueda alta (POS vendedora)

**Implementado:** 2026-05-25 · cache `20260525a`  
**Tag git (antes del cambio):** `checkpoint/pos-dock-busqueda-alta-pre`

## Qué hace el cambio

1. **Lista de búsqueda** (`#pos-search-suggestions`) más alta hacia abajo (clase `pos-search-suggestions--portal-alta`).
2. **Dock inferior:** zona izquierda vacía (~46%) para no tapar sugerencias; **cliente → crédito → total → Cotizar / Emitir** agrupados a la derecha.

## Revertir en 30 segundos (sin git)

En `templates/punto_venta.html` línea ~3:

```jinja
{% set pos_dock_relayout_busqueda = pos_layout_fullwidth and false %}
```

(o `and true` para volver a activar)

Ctrl+F5 en `/punto_venta`.

## Revertir con git

```bash
git checkout checkpoint/pos-dock-busqueda-alta-pre -- templates/punto_venta.html static/css/pos-premium-layout.css static/js/pos.js
```

(Ajusta archivos si el tag no incluye todos; ver `git show checkpoint/pos-dock-busqueda-alta-pre --stat`)

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `templates/punto_venta.html` | Flag `pos_dock_relayout_busqueda`, clase body, spacer + `#posDockCreditoStrip` |
| `static/css/pos-premium-layout.css` | Bloque `pos-dock-relayout-busqueda` |
| `static/js/pos.js` | `posMontarPanelBusqueda`, `posRenderCreditoCliente` |

## Validación rápida

1. Buscar `est` → lista larga hacia abajo.
2. Dock: total y botones a la derecha; sin bloque grande a la izquierda.
3. Cliente con crédito → barra en dock derecho, no duplicada arriba.
