# Checklist inventario Santo Domingo — D0 a D5

**Cliente:** Ferretería Santo Domingo (1 establecimiento · almacenes Tienda + Bodega)  
**Sistema:** LhexIA ERP — [www.lhexia.cl](https://www.lhexia.cl)  
**Estrategia:** Maestro Chilemat (stock 0) → piloto pistola → facturas Pareto 2026 → enrolamiento físico  
**Fecha referencia:** Mayo 2026  
**Estado 2026-05-22:** **D0 cerrado** (maestro ~4.899 SKU en Neon) · **D1** lunes (`PAUSA_D1_PILOTO_PISTOLA.md`)

---

## Antes de empezar (una sola vez)

| Ítem | Responsable | Hecho |
|------|-------------|-------|
| Usuario con permiso **Enrolamiento inventario** o **Admin inventario** | Admin | ☐ |
| Almacenes **Tienda** y **Bodega** activos (Admin → Almacenes) | Mario | ☐ |
| Tablet + pistola 2D en modo **teclado (HID)** — prueba en enrolamiento | Operador | ☐ |
| Matriz Chilemat en Excel (completar huecos de nombre y `codigo_chilemat`) | Mario | ☐ |
| Backup o ventana sin ventas críticas el día de la **carga masiva** | Mario | ☐ |

**Regla de los 3 códigos (no memorizar más que esto):**

| Código | Quién lo define | En la pistola |
|--------|-----------------|---------------|
| **Chilemat** | Cadena / matriz | No (solo búsqueda) |
| **Barras (EAN)** | Fabricante en el producto | **Sí** — es lo que escaneas |
| **Interno** | LhexIA (`CHM-…` / `FERRE-…`) | A veces en etiqueta propia |

---

## D0 — Homologar y cargar maestro (escritorio, ~4 h) ✅ Cerrado 2026-05-22

**Objetivo:** Catálogo en ERP con **stock = 0**; barras reales se asignan en D2–D4.

**Evidencia:** `CARGA DE DATOS/productos_homologados_sd.csv` (4.913 filas) → `python scripts/cargar_maestro_productos_neon.py --neon` (~4.899 creados, 14 actualizados). Alternativa web: Productos → Carga masiva (fix 5k filas en `main`).

### D0.1 Limpiar matriz Chilemat

1. Columnas mínimas en Excel:
   - `nombre` (obligatorio)
   - `codigo_chilemat` (obligatorio — referencia cadena)
   - `precio_compra` / `precio_venta` (si la matriz los trae)
   - `categoria` / `subcategoria` (opcional)
   - **No** llenar `codigo_barra` salvo que ya tengas el EAN real del envase
2. Quitar filas sin nombre o sin código Chilemat.
3. Guardar como `.xlsx` en PC de control (ej. `matriz_chilemat_sd.xlsx`).

### D0.2 Homologar con script (modo maestro)

En la raíz del proyecto (o copiar solo el script + Excel a la PC):

```bash
python homologar_productos_excel.py --input "matriz_chilemat_sd.xlsx" --output "productos_homologados.csv" --maestro
```

- Revisar consola: columna `codigo_chilemat` mapeada.
- Abrir `productos_homologados.csv`: debe traer `stock` = **0** en todas las filas.
- Filas con `codigo_barra` tipo **`PEND-…`** = provisional; se reemplaza al pistolar en enrolamiento.

Si hay errores → corregir `productos_homologacion_errores.csv` y repetir.

### D0.3 Carga masiva en ERP

1. Ingresar a **Productos** → **Carga masiva y exportación**.
2. Subir `productos_homologados.csv`.
3. Anotar resumen del sistema: creados / actualizados / omitidos.
4. **Productos** → filtrar uno al azar: verificar `codigo_chilemat`, `stock` 0, nombre correcto.

### D0.4 Control rápido

```bash
python scripts/sd1_cierre_preflight.py
```

- Objetivo D0: **productos activos >> 10** y la mayoría con algún identificador.

**Criterio D0 cerrado:** ≥ 80 % del catálogo objetivo cargado con nombre + Chilemat; stock 0 en todo el maestro. **→ Cumplido.**

---

## D1 — Piloto pistola + Caso B (piso, ~1 jornada) ⏸ Lunes

**Runbook:** [`PAUSA_D1_PILOTO_PISTOLA.md`](PAUSA_D1_PILOTO_PISTOLA.md)

**Objetivo:** Medir cuántos productos “no coinciden” y entrenar al operador en **vincular**.

### D1.1 Preparar sesión

1. `/inventario/enrolamiento`
2. Elegir almacén **Tienda** (piloto).
3. **Nueva sesión**.
4. Lista de **50–80 SKU** de alta rotación (tornillos, cemento, pintura, cables, etc.) — anotar `codigo_chilemat` en papel.

### D1.2 Procedimiento por producto

| Paso | Acción |
|------|--------|
| 1 | Pistolar el **EAN del envase** (no el código impreso del portal Chilemat). |
| 2 | **Caso A** (bip corto): producto reconocido → +1 conteo; anotar “OK directo”. |
| 3 | **Caso B** (doble bip): panel abajo → buscar **≥ 2 letras** del nombre o pegar **código Chilemat**. |
| 4 | Tocar la fila correcta en sugerencias → **Cantidad inicial** = 1 (piloto, no inventario real aún) → confirmar vincular. |
| 5 | Verificar que quedó **codigo_barra** = lo pistoleado (ya no `PEND-…`). |

### D1.3 Caso B — instrucción operador (copiar al mural)

> **Si la pistola no encuentra el producto:**  
> 1. No inventes códigos.  
> 2. En el buscador escribe el **nombre** (ej. “clavo 2”) o el **código Chilemat** del listado.  
> 3. Elige la fila que coincide con el **envase en la mano**.  
> 4. Pistola de nuevo solo si te piden confirmar barras.  
> 5. Si no aparece en el maestro → **Alta manual** (Caso C) solo con supervisor.

### D1.4 Métricas al cierre D1

| Métrica | Meta orientativa |
|---------|------------------|
| % Caso A directo | Anotar real |
| % Caso B vincular | Aceptable si búsqueda &lt; 30 s |
| % Caso C alta manual | &lt; 10 % del piloto |

**Criterio D1 cerrado:** Operador domina B; decisión: si &gt; 30 % Caso C → volver a completar nombres en matriz antes de escalar.

---

## D2 — Facturas Pareto 2026 (escritorio + bodega, ~1–2 días)

**Objetivo:** Validar existencia histórica y **precio_compra** en los SKU que más compran (no reemplaza la toma física).

### D2.1 Priorizar (regla 80/20)

1. Reunir facturas / guías **2026** de Chilemat y top 3 proveedores.
2. Ordenar por **monto comprado** (Excel del contador o RCV SII si lo exportan).
3. Trabajar solo el **top 300–500** ítems (no las 4.000 filas).

### D2.0 Import masivo RCV SII (opcional, recomendado antes de PDFs)

```bash
python scripts/apply_sql_neon.py sql/2026_05_22_rcv_sii_recepciones.sql
python scripts/importar_rcv_sii.py --input "compras_rcv_2026.csv" --dry-run
python scripts/importar_rcv_sii.py --input "compras_rcv_2026.csv"
```

Crea recepciones **Pendiente de ítems** (folio + proveedor RUT). Ver `IMPORTAR_RCV_SII.md`.

### D2.2 Flujo en LhexIA (por factura)

1. Abrir recepción borrador RCV o **Compras → Recepciones → Nueva** (proveedor, tipo Factura o Guía).
2. Adjuntar PDF o foto legible.
3. Si hay `OPENAI_API_KEY` en servidor: **Importar líneas desde factura (IA)** → revisar cada match.
4. Confirmar solo líneas con producto correcto en catálogo.
5. **No** usar esta recepción para sumar stock de inventario inicial si la mercadería ya está en piso sin documento — en SD-1 usar recepción sobre todo para **precio y validación de nombre**.

### D2.3 Cuando IA no empareja

- Buscar producto en **Productos** por Chilemat o nombre.
- Corregir nombre en maestro si la factura trae descripción más clara.
- Dejar anotado en lista “pendiente vincular factura” para D3.

**Criterio D2 cerrado:** ≥ 200 líneas Pareto con `precio_compra` actualizado o validado en ERP.

---

## D3 — Enrolamiento Bodega (piso, 1–2 jornadas)

**Objetivo:** Conteo físico real en **Bodega**.

1. `/inventario/enrolamiento` → almacén **Bodega** → **Nueva sesión**.
2. Recorrido por pasillos: pistolar → Caso A suma; Caso B vincular (misma rutina D1).
3. Productos sin etiqueta: búsqueda por nombre → vincular o alta manual con supervisor.
4. Al terminar jornada: no cerrar sesión sin anotar número de sesión en cuaderno.
5. Repetir al día siguiente hasta cubrir bodega.

**Criterio D3:** Sesión bodega cerrada con líneas contadas; supervisor revisa 10 ítems al azar vs piso.

---

## D4 — Enrolamiento Tienda (piso, 1–2 jornadas)

Igual que D3 con almacén **Tienda**.

- Priorizar mostrador y góndolas de alta rotación primero.
- Evitar doble conteo de lo que solo existe en bodega (política: “¿dónde está la caja que vendes?”).

**Criterio D4:** Sesión tienda cerrada; muestra aleatoria 10 ítems OK.

---

## D5 — Cierre, salud y listo para POS (medio día)

| Paso | Acción | Hecho |
|------|--------|-------|
| 1 | `/inventario/salud` — revisar desajustes maestro vs almacenes | ☐ |
| 2 | Corregir deltas graves (ajuste con permiso admin) | ☐ |
| 3 | `python scripts/sd1_cierre_preflight.py` | ☐ |
| 4 | Smoke: un vale TEST o flujo real mínimo POS → caja (si aplica) | ☐ |
| 5 | Capacitar vendedor: POS solo vende lo que tiene stock o política “a pedido” | ☐ |

**Criterio D5 / SD-1 inventario:** Salud sin rojos críticos; enrolamiento tienda + bodega documentado; maestro con barras reales en ítems de rotación.

---

## Referencias rápidas

| Recurso | Ruta |
|---------|------|
| Enrolamiento | `/inventario/enrolamiento` |
| Salud inventario | `/inventario/salud` |
| Carga masiva | **Productos** → Carga CSV |
| Manual operador | `MANUALES DE OPERACIÓN/MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` |
| Homologar matriz | `homologar_productos_excel.py --maestro` |
| Guía 5000 SKU | `GUIA_CARGA_5000_PRODUCTOS.md` |

---

## Contacto y validez

**LhexIA ERP** — Haz rentable tu decisión.  
Checklist operativa SD-1 — válida para la semana de arranque de inventario; ajustar plazos según tamaño real del catálogo cargado en D0.
