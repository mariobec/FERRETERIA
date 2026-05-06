# Manual operador: Enrolamiento de inventario y códigos

Guía para uso diario del módulo **Enrolamiento inventario** y del vínculo de **código de barras** en **Recepciones** (factura o guía de despacho).

---

## 1. Qué resuelve el módulo

| Concepto | Dónde se guarda | Quién lo define |
|----------|-----------------|-----------------|
| Código **Chilemat** (o referencia de proveedor) | `codigo_chilemat` | Maestro / importación |
| Código **interno** (ej. FERRE-0001) | `codigo_interno` | El sistema (automático al vincular o al asignar barras en recepción) |
| Código que **lee la pistola** (EAN del producto) | `codigo_barra` | Usted al pistolar en enrolamiento o en recepción |

**Regla simple:** la pistola siempre alimenta **`codigo_barra`**. El interno es el “DNI interno” del ferretero; el Chilemat es la referencia del catálogo/proveedor.

---

## 2. Permisos y acceso

- Menú lateral: **Enrolamiento inventario** (visible si su rol tiene el permiso **Enrolamiento inventario** o **Admin inventario**, o si es administrador del sistema).
- Si no ve el menú, un administrador debe asignar el permiso **Enrolamiento inventario** en **Mantenedores → Roles y permisos**.

---

## 3. Pantalla “Enrolamiento en tiempo real”

### 3.1 Antes de escanear

1. Elija **Almacén** (donde debe sumarse el stock inicial al vincular o al dar de alta).
2. Si cambió de turno o quiere contar de cero, use **Nueva sesión** (cada sesión lleva su propio conteo por producto).

### 3.2 Cómo escanear (pistola tipo teclado)

- El cursor queda en un **campo invisible** preparado para la pistola.
- Pistoleé el código y pulse **Enter** (la pistola suele enviar Enter sola).
- No hace falta recargar la página: todo va por **internet (Fetch)**.

### 3.3 Caso A — Producto reconocido

- El código ya está en el sistema (`codigo_barra` o `codigo_interno`).
- Suena un **bip corto de éxito**.
- Se muestra nombre, referencias y el **conteo de la sesión** (+1 por cada lectura correcta del mismo producto).

### 3.4 Caso B — Hay que vincular

- El código **no** existe aún como `codigo_barra`.
- Suena un **doble tono** (atención).
- Se abre el panel inferior: el foco va al **buscador** (nombre, Chilemat, interno o código antiguo).
- Escriba al menos **2 caracteres**; aparecen sugerencias con miniatura si hay `imagen_url`.
- Toque la fila correcta:
  - Indique **Cantidad stock inicial** si corresponde (por defecto 1).
  - El sistema **asigna** el código pistoleado al producto, genera **código interno** si faltaba y registra **entrada** en inventario/Kardex según el almacén elegido.

### 3.5 Caso C — No está en el catálogo

- En el panel de búsqueda use **“No está en el maestro — alta manual”**.
- Suena un tono **más grave** (alta manual).
- Complete **Nombre** (obligatorio), **Precio de venta** (obligatorio), opcional **Precio compra** y **Precio mayoreo**, **Categoría**, opcional **Código Chilemat/referencia**, **Cantidad inicial** y guarde.
- Se crea el producto con **barras** = lo escaneado, **interno** automático, los precios indicados y stock según cantidad.

### 3.6 Abrir con código desde otro lugar

- Si alguien le comparte un enlace con `?codigo=...` al abrir **Enrolamiento**, ese código se **procesa una sola vez** al iniciar la sesión (útil desde **Recepción** cuando hay conflicto).

---

## 4. Recepción (factura o guía): pistola sin duplicar stock

Cuando la mercadería **ya ingresó** por una línea de recepción (cantidades y Kardex con referencia a la recepción):

1. En **Recepciones**, abra la recepción **Pendiente** o **Incompleta**.
2. En **Líneas registradas**, por cada producto use **Pistola**.
3. Pistoleé el código y **Enter** en el modal.
4. **No** se vuelve a sumar stock: solo se guarda el **`codigo_barra`** (y el **interno** si no existía).

### 4.1 Código provisional `INT-…`

- Si el sistema dejó un código tipo **`INT-000123`** (provisional), puede **reemplazarlo** pistoleando el código real **sin** marcar “Forzar”.

### 4.2 Forzar reemplazo

- Si el producto ya tiene **otro** código de barras distinto del que necesita, marque **“Forzar reemplazo…”** y vuelva a pistolar. Úselo solo si está seguro de corregir un error.

### 4.3 Código duplicado u otro conflicto

- Si el mensaje indica que el código **pertenece a otro producto** o hay otro bloqueo, use el enlace **“Abrir módulo Enrolamiento con este código”** (nueva pestaña) para **vincular**, **alta manual** o revisar en **Productos**.

### 4.4 Botón Enrolamiento en la cabecera de la recepción

- Abre el módulo completo en otra pestaña para flujos más largos (búsqueda, altas, etc.).

---

## 5. Buenas prácticas

1. **Recepción primero, pistola después:** registre cantidades del documento; luego asigne barras por línea (así el stock y el documento quedan alineados).
2. **Un código de barras = un producto** en catálogo; no reutilice el mismo EAN en dos SKU distintos.
3. **Proveedor distinto de Chilemat:** el campo “Chilemat” en alta manual sirve igual como **código de referencia** del empaque.
4. Si **no** tiene pistola, puede **pegar** el código en el campo del modal o del enrolamiento y pulsar Enter.

---

## 6. Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| No aparece el menú Enrolamiento | Permisos del rol; o usar usuario admin. |
| “Ejecutá el script SQL…” al abrir Enrolamiento | Administrador debe aplicar `sql/2026_05_06_enrolamiento_inventario.sql` en MySQL. |
| En recepción: “Registre primero la cantidad…” | Debe existir una **línea** con cantidad recibida para ese producto antes de la pistola. |
| Siempre “duplicado” | Ese EAN ya está en otro producto: resolver en Enrolamiento o en **Productos**. |
| Sin sonido | El navegador puede bloquear audio hasta la primera interacción; haga un clic en la página y vuelva a intentar. |

---

## 7. Referencia técnica (para soporte)

- Migración BD: `sql/2026_05_06_enrolamiento_inventario.sql`
- Prefijo interno (opcional): variable de entorno `CODIGO_INTERNO_PREFIX` (por defecto `FERRE`).
- APIs JSON (requieren sesión iniciada):  
  `/api/enrolamiento/sesion`, `procesar_escaneo`, `buscar_maestro`, `vincular`, `alta_manual`  
  `/api/recepcion/asignar_codigo_barras`

---

*Documento alineado al código del ERP a la fecha de generación. Si cambia la interfaz, actualice este manual con las nuevas capturas o textos de botones.*
