# Vitácora de trabajo — Reunión Ferretería Santo Domingo

**Tema:** Fidelización por puntos (descuento en caja) + sorteo premio en TV (Experience Wall)  
**Cliente:** Ferretería Santo Domingo  
**Proveedor:** LhexIA ERP · Mario Becerra Olea  
**Estado reunión:** 📅 **Programada** (completar fecha y asistentes al concretar)  
**Fase ERP:** Post **SD-1** (diseño y acuerdo; desarrollo después de POS + inventario estables)  
**Plan técnico de referencia:** [`../02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md`](../02-producto-lhexia/PLAN_FIDELIZACION_Y_PROMO_EXPERIENCE.md)

---

## Datos de la reunión

| Campo | Valor |
|-------|--------|
| **Fecha** | _[DD/MM/AAAA]_ |
| **Hora / lugar** | _[…]_ |
| **Modalidad** | _[Presencial / remota]_ |
| **Asistentes LhexIA** | Mario Becerra Olea · _[otros]_ |
| **Asistentes Santo Domingo** | _[Gerencia / caja / marketing / …]_ |
| **Objetivo** | Acordar reglas de negocio para **LX-FID** (puntos) y **LX-PROMO** (sorteo chocolate en TV) antes de desarrollar |

---

## Agenda sugerida (≈ 45–60 min)

1. Contexto: qué ya tiene el POS hoy (descuento con tarjeta supervisor; TV cliente).
2. **Bloque A — Puntos y descuento en caja** (preguntas §A).
3. **Bloque B — Sorteo «ganaste un chocolate»** en pantalla cliente (preguntas §B).
4. Piloto: sucursal, fechas, quién opera premios en piso.
5. Próximos pasos y responsables.

---

## Contexto para el cliente (1 minuto)

| Hoy en LhexIA | Próximo (si acuerdan) |
|---------------|------------------------|
| Descuento en POS con **tarjeta/PIN de supervisor** (o productos marcados en catálogo) | **Puntos** por compras → la cajera puede aplicar un **%** sin supervisor, hasta un tope |
| **TV cliente** (Experience Wall) muestra carrito e identificación | Mismo TV puede mostrar **«Felicitaciones, ganaste un chocolate»** con un ticket elegido al azar |
| **Saldo a favor** (dinero) ya existe en caja | **No es lo mismo** que puntos; son reglas distintas |

**Importante:** esto **no** reemplaza SD-1 (vale, inventario, descuentos actuales). Se desarrolla cuando el piso confirme que SD-1 está estable.

---

## A. Preguntas — Fidelización por puntos (LX-FID)

_Completar columna **Respuesta SD** durante la reunión._

| # | Pregunta | Propuesta LhexIA (default) | Respuesta Santo Domingo |
|---|----------|----------------------------|-------------------------|
| A1 | ¿Cuándo el cliente **gana** puntos? | Al **cobrar** la venta (estado Pagado), no al emitir el vale | |
| A2 | ¿Quién acumula? | Solo si hay **RUT / cliente identificado** (no «cliente final» anónimo) | |
| A3 | ¿Sobre qué monto se calculan? | Total **pagado** en la venta | |
| A4 | ¿Acumulación por **mes calendario** o saldo que va sumando sin reinicio mensual? | Saldo acumulado con **vencimiento** (ver A6) | |
| A5 | ¿Cuántos puntos por peso? Ej.: **1 punto cada $1.000** | 1 pt / $1.000 CLP (configurable) | |
| A6 | ¿Los puntos **vencen**? ¿En cuántos meses? | 12 meses desde que se ganan | |
| A7 | ¿Las ventas **a crédito** suman puntos? ¿Al emitir vale, al cobrar cuota o al saldar? | Solo al **cobro** (igual que efectivo) | |
| A8 | ¿Cómo se **canjean**? Tabla de tramos: puntos → **% máximo** en esa compra | Ej.: 500 pts → 5 %; 1.000 pts → 10 %; 2.000 pts → 15 % | |
| A9 | ¿Un canje por **venta** o por **línea** de producto? | Por venta (un tope % aplicable según reglas en POS) | |
| A10 | Si el % pedido es **mayor** que el permitido por puntos, ¿se usa **tarjeta supervisor** como hoy? | Sí | |
| A11 | ¿Convive con **productos** ya autorizados en catálogo sin supervisor? | Sí; definir si gana el cliente (más favorable) o la regla más estricta | |
| A12 | ¿Quién en tienda **explica** el programa al cliente? | _[Cajera / vendedor / cartelería]_ | |

### Tabla de canje (borrador para rellenar en reunión)

| Puntos necesarios | % máximo descuento en esa venta | ¿OK SD? |
|-------------------|----------------------------------|---------|
| 500 | 5 % | ☐ |
| 1.000 | 10 % | ☐ |
| 2.000 | 15 % | ☐ |
| _[otro]_ | _[%]_ | ☐ |

---

## B. Preguntas — Sorteo premio TV «chocolate» (LX-PROMO)

_Completar columna **Respuesta SD** durante la reunión._

| # | Pregunta | Propuesta LhexIA (default) | Respuesta Santo Domingo |
|---|----------|----------------------------|-------------------------|
| B1 | ¿Qué **premio** físico se entrega? ¿Siempre chocolate u otro según campaña? | Chocolate (texto configurable en pantalla) | |
| B2 | ¿Texto exacto en la **TV**? | «¡Felicitaciones, [Nombre]! Te has ganado un chocolate por tu compra. Acércate al mostrador con tu vale N° [número].» | |
| B3 | ¿Qué ventas entran al sorteo? | Solo **Pagado**, monto mínimo ej. **$5.000** | |
| B4 | ¿Cada cuánto hay **sorteo**? | 1 ganador cada **N** ventas pagadas (ej. N = 25) **o** cada X minutos con tickets en pool | |
| B5 | ¿Máximo **ganadores por día** por sucursal? | 1 premio activo en pantalla; límite diario a definir | |
| B6 | ¿Un mismo cliente puede ganar **más de una vez** al día / semana? | Máx. **1 premio por cliente por día** | |
| B7 | ¿Participan ventas **sin RUT** (cliente final)? | Solo con **nombre** visible en TV (cliente identificado) | |
| B8 | ¿En qué **sucursal(es)** hay TV Experience Wall piloto? | _[Sucursal 1 / 2 / 3]_ | |
| B9 | ¿Quién **entrega** el chocolate en mostrador? | Cajera; lista de premios pendientes en sistema | |
| B10 | ¿Qué hacer si el ganador **no reclama** el premio? | _[Tiempo límite / vuelve al pool / no aplica]_ | |
| B11 | ¿Mostrar en TV **nombre completo** o solo primer nombre + inicial? | Primer nombre + inicial apellido (privacidad) | |
| B12 | ¿**Sonido** o animación especial en TV? | Opcional (configurable) | |

### Parámetros numéricos (rellenar)

| Parámetro | Valor acordado |
|-----------|----------------|
| Monto mínimo compra (CLP) | |
| Cada N ventas → 1 sorteo (si aplica) | |
| Duración mensaje en TV (segundos) | |

---

## C. Piloto y operación

| Tema | Acuerdo |
|------|---------|
| Sucursal piloto | |
| Fecha inicio piloto (objetivo) | |
| Responsable SD operación | |
| Responsable LhexIA implementación | |
| ¿Capacitación cajeras antes del piloto? | ☐ Sí ☐ No — fecha: |

---

## Acuerdos y decisiones (acta)

_Escribir aquí lo que quede **cerrado** en la reunión._

1. 
2. 
3. 

---

## Pendientes post-reunión

| # | Acción | Responsable | Fecha límite | Estado |
|---|--------|-------------|--------------|--------|
| 1 | Actualizar plan técnico con respuestas §A y §B | LhexIA | | ☐ |
| 2 | Enviar acta firmada / confirmada por correo | SD | | ☐ |
| 3 | Estimar fechas LX-FID / LX-PROMO post SD-1 | LhexIA | | ☐ |
| 4 | | | | ☐ |

---

## Notas libres (durante la reunión)

```
[Espacio para notas, objeciones, ideas adicionales]
```

---

## Historial de esta vitácora

| Fecha | Evento |
|-------|--------|
| 2026-05-19 | Creación vitácora; reunión programada; preguntas desde plan LX-FID / LX-PROMO |
| | Reunión realizada — completar acta |
| | Respuestas volcadas al plan técnico |

---

*Documento de trabajo interno + cliente. No compromete desarrollo hasta cierre SD-1 y confirmación escrita de alcance.*
