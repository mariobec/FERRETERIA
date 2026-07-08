# Plan e-commerce y piloto vitrina — Ferretería Santo Domingo

**Actualizado:** 2026-06-02  
**Estado código:** piloto camino A **cerrado en repo** (vitrina + carrito + PED-WEB + bandeja ERP)  
**Estado operación:** pendiente **OT → QAS → PRD** y UAT en piso (no bloquea SD-1 POS/inventario)  
**Backlog post-piloto:** `PLAN_PENDIENTES_DESARROLLO.md` (Webpay, reserva stock, guía despacho DTE 52, etc.)

**Cliente / marca:** Ferretería Santo Domingo (logo SD, no Sodimac).  
**Catálogo:** Chilemat (`chilemat_vtex_producto`) vinculado a `productos` ERP.

---

## Completado en repo (piloto v0)

| # | Entrega | Ruta / artefacto |
|---|---------|------------------|
| 1 | Vitrina pública (grid, filtros, menú mega, recomendados) | `/tienda/ferreteria-santo-domingo` |
| 2 | Ficha producto + leyenda precio referencial | `/tienda/.../producto/<id>` |
| 3 | Asistente **Maylén** (reglas + Ollama opcional) | `POST /api/tienda/.../asistente` |
| 4 | Carrito (panel + localStorage) | `tienda-vitrina.js`, `carrito_vitrina_shell.html` |
| 5 | Pedido por WhatsApp | `POST .../carrito/whatsapp` |
| 6 | Vale **PED-WEB-######** → venta `Pendiente` (`Maylen-Web`) | `POST .../carrito/vale` → `crear_vale_pedido_web()` |
| 7 | Bandeja operación (SLA, estados prep., anular, CSV, API JSON) | `/ecommerce/pedidos` |
| 8 | Menú ERP + permiso `ecommerce_pedidos` | `app.py` |
| 9 | Tests smoke | `tests/test_tienda_publica.py`, `tests/test_ecommerce_bandeja.py` |

### Flujo operativo

```
Cliente vitrina → carrito → PED-WEB-###### (Pendiente)
    → /ecommerce/pedidos (preparación)
    → Caja vales pendientes VL###### (cobro)
    → Entrega QR / retiro tienda
```

### Regla de datos (acordado 2026-05-27)

| Campo | Fuente | Notas |
|-------|--------|--------|
| Nombre, descripción, imagen, marca, rubro | Chilemat | Solo con `producto_id` ERP |
| Precio mostrado | Chilemat `precio_lista` | Si falta → `precio_venta` ERP |
| Stock / disponibilidad | ERP tienda (`StockPorAlmacen`) | Nunca stock Chilemat |
| Sugeridos | `producto_relacion` | Igual que TV cliente |

Cobro en caja usa precio POS/ERP; la vitrina muestra leyenda de precio referencial.

### Variables de entorno (`.env.example`)

| Variable | Default | Uso |
|----------|---------|-----|
| `VITRINA_TIENDA_HABILITADA` | `1` | Apaga vitrina pública |
| `VITRINA_PEDIDO_WEB_HABILITADO` | `1` | Apaga generación PED-WEB |
| `ECOM_PEDIDO_BLOQUEAR_SIN_STOCK` | `1` | Rechaza vale sin stock tienda |
| `ECOM_PEDIDO_REQUIERE_CAJA` | `0` | Si `1`, exige caja abierta al crear PED-WEB |
| `ECOM_PEDIDO_SLA_MINUTOS` | `10,20,30` | Umbrales bandeja |
| `VITRINA_OLLAMA_*` | off | Maylén con LLM — ver `VITRINA_OLLAMA_PRODUCCION.md` |

---

## Pendiente operación (cerrar piloto en piso)

Checklist UAT — marcar en QAS/PRD:

- [ ] OT código: tag/commit con vitrina + e-commerce → import SAMBOX → sign-off → PRD Render
- [ ] `.env` PRD: `VITRINA_PEDIDO_WEB_HABILITADO=1`, `WHATSAPP_VENTAS`, flags SLA
- [ ] (Opcional) Túnel Ollama: `VITRINA_OLLAMA_ENABLED=1` + `healthz` → `liz_ollama.disponible: true`
- [ ] Curar **80–150 SKU** Chilemat con ficha + stock tienda
- [ ] Recorrido: vitrina → carrito → PED-WEB → bandeja → preparar → caja cobra → QR
- [ ] Capacitar: bandeja ≠ vales POS; folio cliente `PED-WEB-######`, caja `VL######`
- [ ] Métricas 30 días (usar export CSV bandeja + contadores KPI)

**Paquete instalador:** `scripts/crear_instalador_tienda_completo.ps1` → `respaldos/instalador_tienda_*`

---

## Post-piloto (camino B — no SD-1)

- Pago web (Webpay) y confirmación automática
- Reserva / hold de stock al crear PED-WEB (hoy solo validación; descuento al cobrar)
- Guía despacho PDF / DTE 52 — ver `PLAN_PENDIENTES_DESARROLLO.md`
- Marketplace VTEX / seller externo (Chilemat red)

---

## Código principal

`blueprints/tienda_publica.py`, `blueprints/ecommerce.py`, `services/vitrina_tienda_service.py`, `services/ecommerce_pedidos_service.py`, `templates/tienda/`, `templates/ecommerce/`, `static/css/tienda-vitrina.css`, `static/js/tienda-vitrina.js`

### Comandos QA

```bash
pytest tests/test_tienda_publica.py tests/test_ecommerce_bandeja.py -m smoke -q
```

---

## Referencia UX

Layout tipo marketplace (grilla, filtros). **No** logo ni SKU Sodimac/Falabella. Marca **Ferretería Santo Domingo** + catálogo Chilemat homologado ERP.
