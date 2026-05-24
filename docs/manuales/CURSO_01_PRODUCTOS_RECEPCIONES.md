# Curso 1 — Productos, proveedores y recepciones

**Duración:** 60–90 minutos  
**Audiencia:** bodeguero, comprador, administrador  
**Prerrequisitos:** usuario con permiso de productos y recepciones

---

## 1. Objetivos de aprendizaje

Al finalizar, el participante podrá:

1. Crear y editar un producto con datos mínimos correctos.
2. Registrar un proveedor usable en recepciones.
3. Crear una recepción, agregar líneas y finalizarla.
4. Verificar que el stock y el Kardex reflejan el ingreso.

---

## 2. Conceptos clave (5 min)

| Concepto | Significado |
|----------|-------------|
| Producto activo | Visible en POS y recepciones |
| Stock | Cantidad disponible para venta |
| Recepción finalizada | Único estado que impacta inventario |
| Kardex | Historial de entradas y salidas |

**Regla de oro:** no vender lo que no está recepcionado (salvo ajustes autorizados).

---

## 3. Módulo Productos (25 min)

### 3.1 Alta manual — paso a paso

1. Menú → **Productos**.
2. Completar:
   - **Nombre** (obligatorio, claro para mostrador)
   - **Código de barra** (si existe; evitar duplicados)
   - **Precio compra** y **precio venta** (nunca dejar en cero)
   - **Stock inicial** (solo si no entrará por recepción)
   - **Categoría / subcategoría** (mejora búsquedas en POS)
   - **Ubicación física** (pasillo/estante — opcional pero útil)
3. Guardar y confirmar mensaje de éxito.
4. Buscar el producto por nombre y por código para validar.

### 3.2 Carga masiva CSV (referencia)

Para go-live con muchos SKUs, usar la guía `GUIA_CARGA_5000_PRODUCTOS.md`.  
Siempre revisar el resumen: creados, actualizados, omitidos, duplicados.

### 3.3 Errores frecuentes

| Error | Acción |
|-------|--------|
| Precio en cero | Editar antes de vender |
| Código duplicado | Unificar productos o corregir código |
| Producto no aparece en POS | Verificar que esté **activo** |

### 3.4 Ejercicio práctico

Crear 2 productos de prueba con categorías distintas. Buscarlos en POS (solo lectura).

---

## 4. Módulo Proveedores (10 min)

1. Menú → **Proveedores**.
2. Crear con nombre y contacto mínimo.
3. Guardar.
4. Verificar que aparece al crear una recepción nueva.

**Buena práctica:** un registro por proveedor real; evitar duplicados por variaciones de nombre.

---

## 5. Módulo Recepciones (30 min)

### 5.1 Crear recepción

1. Menú → **Recepciones** → **Nueva recepción**.
2. Elegir **proveedor** y **tipo de documento** (factura o guía).
3. Guardar encabezado.

### 5.2 Agregar líneas

1. Buscar producto por código o nombre.
2. Ingresar **cantidad física recibida** y **costo unitario**.
3. Confirmar unidad de compra/venta si hay conversión.
4. Repetir por cada ítem del documento.

### 5.3 Finalizar

1. Revisar resumen de líneas (cantidades y totales).
2. Adjuntar documento si el proceso lo exige.
3. **Finalizar recepción** (no dejar en borrador).
4. Ir a **Kardex** → filtrar producto → confirmar movimiento **ENTRADA**.

### 5.4 Recepción en tablet (bodega)

1. Abrir recepción pendiente en tablet.
2. Caminar bodega registrando ítems.
3. Finalizar desde escritorio o tablet según permisos.

### 5.5 Ejercicio práctico

Recepcionar 3 productos reales del proveedor del día. Captura de pantalla del Kardex con las 3 entradas.

---

## 6. Checklist de cierre de sesión

- [ ] Sé crear un producto con precios correctos
- [ ] Sé registrar un proveedor
- [ ] Sé finalizar una recepción
- [ ] Sé verificar entrada en Kardex
- [ ] Sé dónde está la ayuda: `/ayuda#recepciones`

---

## 7. Preguntas para el instructor

1. ¿Qué pasa si finalizo una recepción con cantidad errada?
2. ¿Puedo recepcionar un producto que no existe en el maestro?
3. ¿Cuándo usar enrolamiento con pistola vs recepción?

**Respuestas cortas:** (1) Corregir con ajuste autorizado o nota según política del local; (2) Crear producto primero o usar alta en enrolamiento; (3) Recepción = ingreso mercadería con documento; enrolamiento = códigos de barra y stock inicial en piso.

---

## 8. Enlace en el ERP

Centro de ayuda → pestaña **Bodega / Inventario** → sección **Recepciones de mercadería**  
URL directa: `/ayuda#recepciones`
