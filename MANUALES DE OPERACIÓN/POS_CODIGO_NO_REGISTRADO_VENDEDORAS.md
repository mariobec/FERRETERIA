# Manual vendedora: Código escaneado no registrado (Punto de venta)

Procedimiento en **Punto de venta** cuando la pistola lee un código que el sistema **no reconoce**. Complementa el manual de **Enrolamiento inventario** (conteo y alta en bodega/tienda).

| Campo | Valor |
|-------|--------|
| **Módulo** | Punto de venta (`/punto_venta`) |
| **Permiso** | Emitir vale (`pos_emitir_vale`) |
| **Audiencia** | Vendedoras y mostrador |
| **Versión doc** | 1.0 — 2026-06-02 |
| **Estado funcional** | Vincular operativo — ver sección 8 |

---

## 1. Regla de oro (léala una vez)

> **Un producto físico = una ficha en el sistema = un solo stock.**  
> Los códigos de barras son **etiquetas** para encontrar ese producto, no productos distintos.

| Acción | ¿Duplica stock? | ¿Cuándo usarla? |
|--------|-----------------|-----------------|
| **Vincular código** (mismo producto, otro sticker) | **No** | Ya vendemos el ítem con otro código o el fabricante cambió el EAN (botón verde en POS) |
| **Alta rápida** (producto nuevo) | **Sí** (solo lo que trajo / ve en mostrador) | Referencia nueva que nunca entró al catálogo |
| **Buscar por nombre** | No (solo elige ítem existente) | No está segura del código o solo sabe el nombre |

**No cree un producto nuevo** si en realidad es el mismo tornillo, pintura o cable que ya está en el catálogo con otro código.

---

## 2. Cuándo aparece el aviso «Código no registrado»

1. En el campo **«Escanea código o escribe nombre / SKU…»** (o pistola en ese campo), lee un código.
2. El sistema busca en catálogo (incluye variantes habituales de EAN: ceros, empaque, etc.).
3. Si **no** hay coincidencia, se abre el cuadro **Código no registrado** con el número escaneado.
4. **La venta sigue abierta** — puede cerrar el cuadro y seguir armando el vale.

---

## 3. Decisión en 10 segundos (árbol simple)

```
¿El producto ya lo vendemos con otro código o nombre?
│
├─ SÍ, es el mismo artículo ──► VINCULAR código a producto existente
│
├─ NO, es referencia nueva en mostrador ──► ALTA RÁPIDA
│
└─ NO ESTOY SEGURA ──► BUSCAR POR NOMBRE (o preguntar a bodega/encargado)
```

---

## 4. Los tres caminos (procedimiento)

### 4.1 Alta rápida — producto **nuevo** en mostrador

**Use cuando:** trajo mercadería nueva, etiqueta de fabricante distinta y **no existe** en el catálogo (ni por nombre similar).

**Pasos:**

1. En el cuadro **Código no registrado**, pulse **«Alta rápida y agregar al vale»**.
2. Complete:
   - **Código de barras** — ya viene del escaneo (no lo cambie salvo error de pistola).
   - **Nombre** — claro para cliente y bodega (obligatorio).
   - **Precio venta** — precio mostrador SD (obligatorio).
   - **Stock tienda** — cuántas unidades está vendiendo **ahora** (por defecto 1).
3. Pulse **«Guardar y agregar»**.
4. El ítem queda en el vale y en catálogo; el stock en **tienda** sube según la cantidad indicada.

**Importante:**

- Esto **sí** crea ficha nueva y **sí** mueve stock en tienda.
- Después, bodega/admin puede completar categoría, foto y precio en **Carga precios piloto** si falta algo.

---

### 4.2 Vincular código — **mismo** producto, otro número de barras

**Use cuando:**

- El fabricante cambió el EAN o trae caja con otro código.
- La etiqueta está mal impresa pero el producto es el que ya vendemos.
- Pistoleó un código parecido al del catálogo (vea la lista **«¿Quiso decir?»**).

**Pasos:**

1. En el cuadro **Código no registrado**, pulse **«Mismo producto — vincular código»** (botón verde).
2. Busque el producto correcto (nombre, código interno o el que ya conocen).
3. Revise en pantalla: nombre, stock en tienda, precio.
4. Confirme el mensaje: *«El código [escaneado] quedará ligado a este producto. No duplica stock.»*
5. Si el producto **no tiene precio SD**, complete el campo **Precio venta SD** (el sistema puede sugerir el precio lista del catálogo si existe).
6. Pulse **«Vincular y agregar al vale»**.

**Atajo:** si aparece **«¿Quiso decir?»** con un candidato claro, pulse **«Vincular código aquí y agregar»** (si falta precio SD, abre el cuadro para indicarlo).

**Importante:**

- **No** indique stock extra al vincular — el stock sigue en la ficha que ya existía.
- La próxima vez que pistolee **este** código, el sistema lo reconocerá solo.

---

### 4.3 Buscar por nombre — duda o código muy erróneo

**Use cuando:** no sabe si es nuevo o existente, o el código no sirve.

**Pasos:**

1. Pulse **«Buscar por nombre en catálogo»** (o cierre el cuadro y escriba en el buscador).
2. Escriba al menos **2 letras** del nombre o parte del código conocido.
3. Use flechas **↑ ↓** y **Enter** para agregar al vale.
4. Si encuentra el producto, **no** use alta rápida para ese mismo artículo.

---

## 5. Lista «¿Quiso decir?»

Si el código escaneado es **parecido** a uno del catálogo, el sistema muestra sugerencias.

| Qué hacer | Criterio |
|-----------|----------|
| Agregar sugerencia al vale | Es claramente el mismo producto (mismo nombre / familia) |
| Vincular en lugar de alta rápida | El código escaneado es distinto al SKU maestro pero es el mismo ítem |
| Ignorar y usar alta rápida | Ninguna sugerencia coincide — es producto nuevo |

---

## 6. Casuísticas frecuentes en ferretería

| Situación | Camino correcto | Error típico |
|-----------|-----------------|--------------|
| Mismo tornillo, nuevo EAN del proveedor | Vincular | Alta rápida → stock duplicado |
| Producto de promoción nunca cargado | Alta rápida | Buscar sin dar de alta |
| Código ilegible / pistola leyó mal | Buscar por nombre; re-escanear | Vincular al producto equivocado |
| Cliente trae muestra sin etiqueta | Buscar por nombre | Inventar código |
| Ya existe con código `PEND-…` | Vincular al producto PEND o pedir a bodega enrolamiento | Segunda ficha |
| Sin stock en tienda pero hay en catálogo | Agregar al vale; puede salir **a pedido** (otro cuadro) | Alta rápida duplicada |

---

## 7. Qué pasa con el stock (resumen para piso)

| Momento | Stock en sistema |
|---------|------------------|
| Venta normal (código conocido) | Descuenta tienda/bodega según retiro del vale |
| **Vincular** código | Sin movimiento; solo «aprende» el nuevo código |
| **Alta rápida** | Suma en **tienda** la cantidad que puso la vendedora |
| Toma física / enrolamiento | Cuenta siempre el **mismo** producto, con cualquier código ya vinculado |

---

## 8. Estado en sistema (LhexIA ERP)

Para coordinación con capacitación y TI.

| Función | Estado |
|---------|--------|
| Cuadro **Código no registrado** | Operativo |
| **Alta rápida** y agregar al vale | Operativo |
| **Buscar por nombre** | Operativo |
| Sugerencias **¿Quiso decir?** | Operativo |
| Botón **Mismo producto — vincular código** | **Operativo** |
| API `POST /api/pos/vincular-codigo` | **Operativo** |
| Reporte diario altas y vínculos POS | Planificado (panel del día) |

---

## 9. Si el cuadro no responde al clic

1. Cierre con **X** o **Esc**.
2. Recargue la página con **Ctrl+Shift+R** (una vez).
3. Haga clic en el campo de escaneo y vuelva a intentar.
4. Si persiste, avise a soporte/TI — no repita alta rápida del mismo código.

---

## 10. Relación con otros módulos

| Módulo | Diferencia |
|--------|------------|
| **Enrolamiento inventario** | Conteo y vínculo en **bodega/tienda** por sesión; no reemplaza el vale POS |
| **Recepción compras** | Pistola en factura **no duplica** stock ya recibido |
| **Carga precios piloto** | Completar precio SD y datos maestro después de alta rápida |
| **Caja** | El vale emitido en POS se cobra en caja; el POS no recauda dinero |

---

## 11. Contacto y mejora del procedimiento

- Dudas de **mismo producto vs. nuevo**: encargado de mostrador o bodega.
- Dudas de **precio**: **Precios** (piloto) o supervisor.
- Propuestas de texto en pantalla: registrar en bitácora SD-1 para ajustar botones y mensajes.

**Hoja para imprimir (árbol de decisión):** `POS_ARBOL_DECISION_CODIGO_IMPRESION.html` — abrir con Chrome/Edge → Ctrl+P → A4.

**Documentos relacionados**

- `MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` — enrolamiento y casos A/B/C en bodega.
- `POS_CODIGO_ESCANEADO_ARQUITECTURA.md` — diseño técnico (equipo desarrollo / dueño).

---

*LhexIA ERP · Ferretería Santo Domingo · SD-1*
