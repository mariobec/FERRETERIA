# Plan a desarrollar — E-commerce y piloto vitrina (consulta 2026-05-27)

**Estado:** piloto fase 1 **implementado en repo** (vitrina + menú + asistente) · no bloquea SD-1 · pendiente deploy lhexia.cl  
**Backlog post-piloto:** `PLAN_PENDIENTES_DESARROLLO.md` (guía de despacho, OT/TMS, etc.)  
**Ubicación deseada:** `docs/planes/02-producto-lhexia/PLAN_ECOM_PILOTO_v0.md` (mover cuando docs esté accesible)  
**Cliente / marca:** **Ferretería Santo Domingo** (logo, colores, nombre comercial SD — no Sodimac ni terceros).  
**Catálogo:** productos **Chilemat** vinculados al ERP (`chilemat_vtex_producto` + `productos`).  
**Referencia UX solamente:** layout tipo marketplace (grid, filtros, recomendados) — **sin** copiar logo, textos legales ni SKU de Sodimac/Falabella.

Ver contenido completo en secciones siguientes.

---

## Base actual (~35–40 % ecom B2C)

- `/catalogo` público, ERP catálogo/stock, Chilemat fichas + `producto_relacion`, TV/POS sugeridos.
- Falta: carrito, pago web, reserva stock, pedido automático ERP.

## Piloto recomendado (6–10 semanas, camino A)

1. 80–150 SKU curados con ficha Chilemat.
2. Vitrina web (grid + filtros + recomendados).
3. Carrito → WhatsApp o `PED-WEB-xxx` → caja emite vale.
4. Métricas 30 días; sin Webpay ni publicación Sodimac.

### Regla de datos acordada (consulta 2026-05-27)

| Campo | Fuente | Notas |
|-------|--------|--------|
| Nombre, descripción, imagen, marca, rubro web | **Chilemat** (`chilemat_vtex_producto`) | Solo filas con `producto_id` ERP |
| **Precio mostrado** | **Chilemat** `precio_lista` (oferta VTEX) | Si falta → `precio_venta` ERP |
| **Stock / disponibilidad** | **ERP** (`productos.stock` o tienda vía `StockPorAlmacen`) | Nunca stock Chilemat |
| Sugeridos | `producto_relacion` (sync Chilemat) | Misma lógica que TV cliente |

**Importante:** precio Chilemat es referencia web; cobro en caja sigue precio POS/ERP si difieren (mostrar leyenda en piloto).

## Caminos B/C

- **B:** ecom con pago + stock integrado (4–7 meses).
- **C:** marketplace VTEX / seller Sodimac (partner; post SD-1).

## Sodimac (solo inspiración de pantalla)

- **Sí:** estructura de página (grilla, filtros, orden recomendados).  
- **No:** logo Sodimac, productos Siegen/Thomas/Oster de la captura, ni publicación en sodimac.cl.  
- **Sí en piloto:** marca **Ferretería Santo Domingo** + catálogo **Chilemat** homologado al ERP.

## Código

`blueprints/tienda_publica.py`, `services/vitrina_tienda_service.py`, `templates/tienda/`, `static/css/tienda-vitrina.css`, `static/js/tienda-vitrina.js`, `tests/test_tienda_publica.py`, `producto_relacion`, `sync_relaciones_chilemat_vtex`, `_pos_live_wall_recomendaciones_tv`.

## Vitrina piloto (implementado 2026-05-27/28)

- **URL local:** `/tienda/ferreteria-santo-domingo`
- **Menú:** sidebar raíz fija + franja contextual (máx. 8 subcats + Ver todo)
- **Asistente:** `POST /api/tienda/ferreteria-santo-domingo/asistente` (reglas + Ollama opcional)
