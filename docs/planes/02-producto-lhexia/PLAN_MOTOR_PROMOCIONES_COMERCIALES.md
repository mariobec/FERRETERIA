# ADR + Plan — Motor de Promociones Comerciales (retail)

**ID:** LX-PROMO-COM (no confundir con **LX-PROMO** = sorteo Experience Wall)  
**Estado:** Diseño aprobado para backlog — **no implementar en SD-1 / Fase -1** sin OK explícito de piso  
**Fecha:** 2026-07-11  
**Product Owner:** Mario Becerra Olea  
**Contexto:** Casuística POS (precio lista intacto; beneficio al pie de ticket/boleta). Diferencia vs editar precio_unitario o solo % de línea.

**Relacionados:**
- Fidelización / sorteo TV: [PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md](./PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md) (**LX-FID**, **LX-PROMO**)
- Backlog: docs/governance/PRODUCT_BACKLOG.md → **P-008**
- Regla go-live: idea no P0 → backlog; checkpoint git antes de tocar POS/ticket

---

## 1. Decisión (ADR)

### Contexto

El retail (Jumbo, Walmart, Falabella, Easy) **no altera el precio de lista** del SKU en la línea. El carrito se calcula a precio normal y un **motor** aplica reglas; el beneficio aparece como renglón(es) de **PROMOCIONES / DESCUENTOS** al final del ticket y de la boleta.

Hoy LhexIA POS solo permite **descuento % por línea** (y autorización supervisor). Eso no cubre limpio: 2x1, 2ª al 50%, pack, escala por cantidad, ni auditoría «cuánto regalé por promo X».

### Decisión

Construir un **Motor de Promociones Comerciales** basado en reglas, no un «módulo de ofertas» que muta precios de catálogo.

1. **Precio de lista** permanece en DetalleVenta.precio_unitario.
2. El motor corre al cambiar el carrito (qty/ítem) y al emitir/cobrar.
3. Los beneficios se persisten en enta_promocion (+ detalle opcional por línea).
4. UI ticket / vale / boleta / dock POS muestran: Subtotal → Promociones → Total.
5. IVA Chile se recalcula sobre el **total comercial post-promo** (misma política residual de desglosar_iva / bruto cobrado).

### Consecuencias

- (+) Ticket claro, auditable, reportable; compatible con estilo Walmart.
- (+) Combina tipos de promo con prioridades/exclusiones.
- (−) Impacto en POS, caja, boleta, cotización (decidir scope); requiere feature flag.
- (−) No es hotfix SD-1: trabajo post inventario/POS estable, con checkpoint git.

### Alternativas rechazadas (para el núcleo)

| Alternativa | Motivo de rechazo |
|-------------|-------------------|
| Bajar precio_unitario en la línea | Pierde traza de promo; distorsiona margen y reportes |
| Solo % manual | No modela 2x1 / pack / escala |
| Precio especial fijo en ficha SKU | Mezcla lista con campaña; vigencia y exclusión difíciles |

---

## 2. Menú producto (propuesto)

`
Ventas y mostrador
 └── Comercial
      ├── Listas de precios          (tarifas; ya hay semilla mayoreo/cliente)
      ├── Promociones                ← este plan (MVP)
      ├── Simulador de carrito       (MVP-2)
      ├── Cupones                    (v2)
      ├── Club / clientes frecuentes (solapa con LX-FID)
      └── Tarjetas regalo            (v2 / Clean)
`

**Nombre UI:** «Promociones comerciales» (evitar «Ofertas» sueltas).

---

## 3. Contrato visual ticket / boleta

`
Tornillo hexagonal M6     2 × \.000          \.000
Martillo                  1 × \.990           \.990
----------------------------------------------
Subtotal                                     \.990
PROMOCIONES
  2x1 Tornillo M6                             -\.000
----------------------------------------------
TOTAL                                        \.990
`

Misma estructura en:
- Dock POS («Total a emitir»)
- Vale / ticket térmico
- Boleta / PDF (si aplica FE)
- Caja al cobrar

**Regla:** el cliente siempre ve precio lista en la línea; el ahorro tiene **nombre de promoción**.

---

## 4. Modelo de datos (borrador)

### promocion

| Campo | Nota |
|-------|------|
| id, nombre, codigo | Identificable en ticket |
| tipo | enum lógico: NXM, SEGUNDO_PCT, PACK, ESCALA_QTY, MARCA_PCT, CATEGORIA_PCT, CLIENTE_PCT, … |
| prioridad | Entero; menor número = se evalúa primero (definir convención) |
| vigencia_desde / hasta | Inclusive |
| activo | bool |
| exclusiva | Si true, no combina con otras del mismo grupo |
| sucursal_id | NULL = todas (multi-sucursal post SD-1) |
| notas | Texto interno |

### promocion_condicion

Producto, marca, categoría, cantidad_min/max, cliente/grupo, día/hora (fase 2).  
Una promo puede tener N condiciones (AND por defecto; OR documentado si se usa).

### promocion_beneficio

tipo: PORCENTAJE | MONTO | PRECIO_FIJO_PACK | GRATIS | SEGUNDO_PCT | NXM  
+ parámetros JSON (
, m, pct, 	ramos, sku_pack[], …).

### enta_promocion

| Campo | Nota |
|-------|------|
| venta_id, promocion_id | FK |
| etiqueta_ticket | Texto mostrado («2x1 Tornillos») |
| monto_descuento | CLP entero ≥ 0 |
| snapshot_json | Regla aplicada (reconstruir boleta años después) |

### enta_promocion_linea (opcional MVP-1.1)

Imputa el descuento a detalle_venta_id(s) para reportes por SKU.

---

## 5. Motor de cálculo

`
Carrito (líneas a precio lista)
        │
        ▼
Filtrar promos vigentes + activas + scope
        │
        ▼
Ordenar por prioridad
        │
        ▼
Aplicar / saltar según exclusiones
        │
        ▼
Generar venta_promocion[] + total comercial
        │
        ▼
desglosar_iva(total) · UI · persistir
`

**Principios:**
- Idempotente: recalcular borra/reemplaza aplicaciones de la venta abierta.
- No mutar precio_unitario.
- Descuento de línea % supervisor **convive** con motor: definir orden (propuesta: primero % línea ya guardado en subtotal de línea; motor sobre subtotales netos de línea — **decidir en LX-PROMO-COM-0**).
- Feature flag: motor_promociones_activo=0 hasta piloto.

---

## 6. Tipologías MVP vs v2

### MVP-1 (piso ferretería)

1. **N×M** — 2x1, lleve 3 pague 2  
2. **2ª unidad X%** — el más barato al 50%  
3. **Escala por cantidad** — tramos 1–4 / 5–9 / 10+ (beneficio vía renglón, no cambio de lista)

### MVP-2

4. Pack / combo (SKU A+B+C a precio fijo o %)  
5. Marca / categoría %  
6. Prioridad + exclusión formal + simulador admin  
7. Reportes: monto regalado por promo, ventas influenciadas

### v2 / Clean

8. Horario, cupones, gift card  
9. Cliente constructor % (si no va en lista de precios)  
10. Motor de reglas libre (SI…ENTONCES…)  
11. IA: sugerir promos por patrones (stock / co-compra) — **después** de historial enta_promocion

---

## 7. Pantallas admin (MVP)

1. Listado promociones (filtro vigencia/activo)  
2. Alta/edición: tipo + condiciones + beneficio + prioridad  
3. Vista previa: «Simular carrito» (SKU + qty → desglose)  
4. (MVP-2) Dashboard: top promos por \$ descontado / tickets

Permisos sugeridos: promociones_admin, lectura para jefatura; POS solo consume motor.

---

## 8. Impacto técnico (archivos / flujos)

| Área | Impacto |
|------|---------|
| Servicio nuevo | services/promociones_service.py (evaluar, aplicar, snapshot) |
| Persistencia | Tablas arriba; migración controlada (script SQL documentado si Fase -1 restringe Alembic) |
| POS | Recalc al actualizar ítem / emitir vale; dock muestra renglones promo |
| Ticket / boleta | Templates: bloque PROMOCIONES |
| Caja | Cobro usa total post-promo (_monto_cobro_venta_ui / bruto comercial) |
| Cotizaciones | ¿Mismo motor? Propuesta: sí en MVP-2 |
| Tests | Smoke: 2x1 en carrito; ticket; total caja; flag off = comportamiento actual |

**Checkpoint git:** checkpoint/pos-promociones-YYYY-MM-DD antes del primer PR que toque POS/ticket.

---

## 9. Fases de entrega

| Fase | Entregable | Criterio de aceptación |
|------|------------|------------------------|
| **LX-PROMO-COM-0** | Este ADR + reglas de convivencia con dto % y IVA | Mario OK |
| **LX-PROMO-COM-1** | Tablas + servicio + 2x1 / 2ª 50% / escala | Tests unitarios motor |
| **LX-PROMO-COM-2** | Integración POS + ticket + boleta + flag | UAT: líneas a lista + renglón promo |
| **LX-PROMO-COM-3** | Admin catálogo promos | Operación crea 2x1 sin deploy |
| **LX-PROMO-COM-4** | Pack + marca/categoría + reportes | Pilot Chilemat / SD |
| **LX-PROMO-COM-IA** | Sugerencias automáticas | Post historial ≥ N semanas |

**Estimación orientativa:** COM-1…2 ≈ 2–3 semanas post SD-1; COM-3 ≈ +1 semana; COM-4 ≈ +1–2.

---

## 10. Casuística ejemplo

Producto lista **\.000**; campaña retail (2x1, pack «2 por \», o 2ª al %).

- Líneas: 2 × \.000 = \.000 (precio lista).  
- Renglón promo según regla (ej. 2x1 → -\.000).  
- Total = subtotal − promos.  
- **No** se edita el precio en ficha salvo beneficio PRECIO_FIJO_PACK sobre el conjunto.

---

## 11. Qué no hacer ahora

- No abrir Cupones / Gift / IA en el mismo sprint que el MVP.  
- No mezclar con **LX-PROMO** (sorteo chocolate en TV).  
- No implementar en Legacy durante bloqueo SD-1 / Fase -1 salvo acuerdo explícito «P0 comercial».

---

## 12. Checklist antes de código

- [ ] SD-1 estable en piso  
- [ ] Confirmar orden: dto % línea vs motor  
- [ ] Confirmar IVA post-promo (bruto comercial)  
- [ ] Feature flag + checkpoint git  
- [ ] Scope boleta electrónica / DTE (descuento global SII)  
- [ ] Piloto: 5–10 SKU con 2x1 real de ferretería  

---

*Documento de producto LhexIA — Motor retail de promociones. Actualizar estado en PRODUCT_BACKLOG P-008 al pasar de Backlog → En diseño → En desarrollo.*
