# Curso 2 — POS, vales pendientes y caja

**Duración:** 60 minutos  
**Audiencia:** vendedor, cajera  
**Prerrequisitos:** caja abierta, productos con stock

> **Estado:** esqueleto para completar con Gemini o en segunda iteración.  
> Contenido base ya disponible en `/ayuda` (pestañas Vendedor y Cajera).

---

## 1. Objetivos de aprendizaje

1. Abrir caja al inicio del turno.
2. Emitir un vale desde POS.
3. Cobrar el vale en Vales pendientes.
4. Manejar descuentos con autorización de supervisor.
5. Cerrar caja con cuadratura.

---

## 2. Bloque A — Apertura de caja (10 min)

**Pantalla:** Abrir caja  
**Ayuda ERP:** `/ayuda#abrir-caja`

### Pasos

1. Ir a **Abrir caja**.
2. Registrar **monto inicial real** en efectivo.
3. Confirmar apertura.

### Validación

- Sin caja abierta, POS puede bloquearse.
- Si hay caja del día anterior abierta, cerrarla primero.

### Ejercicio

Abrir caja con monto simbólico en ambiente de prueba.

---

## 3. Bloque B — Punto de venta (25 min)

**Pantalla:** Punto de venta  
**Ayuda ERP:** `/ayuda#pos`

### Pasos para emitir vale

1. Buscar producto (nombre o código de barra).
2. Agregar al carrito; ajustar cantidad.
3. Revisar subtotal; aplicar descuento si corresponde.
4. Identificar cliente (RUT) o usar cliente final.
5. **Emitir vale** (no cobra aún — va a cola de caja).

### Alertas importantes

| Alerta | Qué hacer |
|--------|-----------|
| Stock insuficiente | Reducir cantidad o quitar ítem |
| Descuento requiere supervisor | Llamar a autorizado |
| Conversión de unidades | Leer texto de consumo real |

### Ejercicio

Emitir 2 vales: uno con cliente identificado y uno cliente final.

---

## 4. Bloque C — Vales pendientes / cobro (15 min)

**Pantalla:** Vales pendientes  
**Ayuda ERP:** `/ayuda#caja-pendientes`

### Pasos

1. Seleccionar vale de la cola.
2. Elegir medio de pago (efectivo, débito, crédito, etc.).
3. Confirmar cobro.
4. Entregar vuelto si aplica.
5. Imprimir o enviar documento si corresponde.

### Validación post-cobro

- Vale pasa a estado pagado.
- Stock se descuenta (verificar en Kardex si hay duda).
- Movimiento queda en caja del turno.

---

## 5. Bloque D — Movimientos y cierre (10 min)

**Pantallas:** Movimientos de caja, Cerrar caja  
**Ayuda ERP:** `/ayuda#cerrar-caja`

### Movimientos extraordinarios

- **Ingreso:** dinero que entra fuera de venta (ej. cambio adicional).
- **Egreso:** retiro con responsable identificado y motivo.

### Cierre de caja

1. Contar efectivo en gaveta.
2. Registrar montos declarados (efectivo, tarjeta según modo).
3. Revisar diferencia; agregar observación si hay descuadre.
4. Si supera umbral, supervisor autoriza con usuario/clave.

---

## 6. Checklist del participante

- [ ] Abrí caja correctamente
- [ ] Emití un vale en POS
- [ ] Cobré un vale en caja
- [ ] Registré un movimiento con motivo
- [ ] Sé dónde está `/ayuda#pos`

---

## 7. Notas para Gemini (expandir este curso)

Al generar slides o video, incluir:

- Capturas reales de `punto_venta.html` y `caja_pendientes.html`
- Caso de vuelto alto (banner amarillo post-cobro)
- Caso de anulación de vale (solo si cliente no vuelve)
- Flujo cotización → POS si el local usa cotizaciones

**Tono:** español chileno, ferretería, operador de piso, sin jerga técnica de software.
