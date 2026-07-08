# Control de cambio — Producto maestro

| Campo | Valor |
|-------|--------|
| **Documento** | CONTROL_DE_CAMBIO_PRODUCTO_MAESTRO |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-08 |
| **Estado** | Aprobado para operación SD-1 (legacy) |
| **Sistema** | LhexIA ERP — Ferretería Santo Domingo |
| **Paisaje** | DEV → QAS (SAMBOX) → PRD (PRODUCTIVO) |
| **Responsable** | Mario Becerra |
| **Elaborado con** | Cursor / LhexIA |

---

## 1. Resumen ejecutivo

Este documento registra las decisiones sobre **producto maestro**, **códigos duplicados** y el futuro **Smart Units Engine** (motor de presentaciones comerciales).

**Decisión principal (2026-07-08):**

1. **En SD-1 (legacy, go-live):** se mantiene el modelo actual — un producto = una ficha con `codigo_barra` único y alias de escaneo POS. Los duplicados se corrigen operativamente (desactivar + vincular/editar código).
2. **Post go-live / nuevo modelo con Alembic:** se implementará el **Smart Units Engine** — producto maestro + presentaciones comerciales (unidad, caja, rollo, metro, etc.) con inventario siempre en unidad base.

No se desarrolla el motor transversal en el monolito legacy durante Fase -1 / -0.

---

## 2. Problema de negocio

### 2.1 Duplicidad de productos por presentación

Hoy, cuando el mismo ítem se vende como unidad, caja, rollo, metro, etc., el riesgo es crear **varios productos** en catálogo para la misma referencia física. Eso parte el stock, complica la toma de inventario y genera errores en POS y compras.

### 2.2 Código de barras duplicado

Si se da de alta un producto y se asigna un **código de barras que ya existe** en otro producto, el sistema bloquea la operación con error `barras_duplicado` (HTTP 409). Un EAN no puede ser maestro de dos productos distintos.

### 2.3 Limitación del modelo legacy

El ERP actual trata cada `Producto` como una unidad implícita. No existe tabla de presentaciones ni conversión centralizada en inventario/compras. Eso se resolverá en el **nuevo modelo con Alembic**, no en el legacy de go-live.

---

## 3. Comportamiento actual del ERP (legacy SD-1)

### 3.1 Producto maestro hoy

| Concepto | Implementación actual |
|----------|------------------------|
| Identidad del producto | Tabla `productos` (`Producto`) |
| Código pistola (maestro) | `productos.codigo_barra` — **único** en BD |
| Código interno ferretería | `productos.codigo_interno` |
| Referencia Chilemat/proveedor | `productos.codigo_chilemat` |
| Alias escaneo (mismo ítem, otro EAN) | Tabla `producto_codigo_escaneo` |
| Stock | `productos.stock` + `stock_por_almacen` (tienda/bodega) |
| Activo/inactivo | `productos.activo` |

### 3.2 Regla de oro operativa

> **Un código de barras maestro = un solo producto.**  
> Si es el mismo ítem con otro EAN → **vincular alias**, no crear producto nuevo.

### 3.3 No existe “eliminar producto”

El catálogo **no borra** fichas. Se **desactivan** (`activo = false`) para sacarlas del día a día sin perder historial de ventas, kardex ni auditoría.

---

## 4. Procedimiento operativo — código duplicado o producto duplicado

### 4.1 Localizar el conflicto

1. Ir a **Catálogo de productos** (`/productos`).
2. Filtrar por **código de barras** o nombre.
3. Identificar el **producto correcto (maestro)** y el **alta errónea (duplicado)**.

### 4.2 Desactivar el producto duplicado

En `/productos`, fila del producto erróneo:

- Pulsar botón **Off** → queda **inactivo**.
- Ya no aparece en búsquedas normales de POS ni en flujos activos de enrolamiento.

Si el duplicado tenía stock, **trasladar o ajustar** unidades hacia el producto maestro antes o después (columnas tienda/bodega en catálogo, o enrolamiento/kardex según el caso).

### 4.3 Modificar código de barras

En **Catálogo de productos** el código se muestra **solo lectura** (no editable en la grilla).

Para cambiarlo:

1. **Inventario → Enrolamiento** (`/inventario/enrolamiento`).
2. Buscar el producto.
3. **Editar ficha** — cambiar `codigo_barra`, nombre, precios, etc.

Si el EAN está “atrapado” en el producto equivocado:

1. Cambiar el código del producto erróneo (otro EAN o código interno) para **liberar** el EAN.
2. Asignar el EAN al producto maestro correcto (editar ficha o vincular).

### 4.4 Vincular código al maestro (mismo ítem, otro EAN)

No dar alta de producto nuevo. Usar:

| Canal | Acción |
|-------|--------|
| Enrolamiento | **Vincular** al producto maestro |
| POS | Modal “código no registrado” → **Vincular código** |

Esto crea un **alias** en `producto_codigo_escaneo` apuntando al mismo `producto_id`. **No mueve stock**; solo resuelve el escaneo.

### 4.5 Tabla rápida de referencia

| Objetivo | Dónde |
|----------|--------|
| Quitar duplicado del día a día | `/productos` → **Off** |
| Cambiar código de barras maestro | Enrolamiento → **Editar ficha** |
| Mismo ítem, EAN distinto | Enrolamiento **Vincular** o POS **Vincular** |
| Buscar quién tiene un código | `/productos` → filtro por código |

---

## 5. Smart Units Engine — visión futura (post Alembic)

### 5.1 Objetivo

Permitir que un **mismo producto maestro** se comercialice en múltiples **presentaciones** (unidad, caja, paquete, rollo, metro, kilo, litro, etc.) manteniendo **un único inventario en unidad base**.

### 5.2 Arquitectura propuesta (resumen)

**Producto maestro** — identidad del ítem (ej. *Tornillo zincado 2"*).  
**Unidad base** — en la que siempre se controla stock (ej. *unidad*, *metro*).

**ProductPresentation** (entidad nueva):

| Campo | Descripción |
|-------|-------------|
| `product_id` | FK al maestro |
| `nombre` | Ej. “Caja 500 u”, “Rollo 100 m” |
| `unidad` | Etiqueta comercial |
| `factor_conversion` | Cuántas unidades base representa 1 presentación |
| `codigo_barra` | EAN de esa presentación |
| `sku` | SKU comercial |
| `precio_compra` / `precio_venta` / `precio_mayorista` | Por presentación |
| `permite_compra` / `permite_venta` | Flags |
| `es_predeterminada` / `orden_pos` | UX POS |
| `activo` | Vigencia |

**Ejemplo — Cable THHN 2,5 mm**

| Presentación | Factor | Stock afectado al vender 1 |
|--------------|--------|----------------------------|
| Metro | 1 | 1 metro |
| Rollo 100 m | 100 | 100 metros |
| Caja 500 m | 500 | 500 metros |

Inventario almacenado: **12.450 metros** (nunca por presentación).

### 5.3 Servicio central

`UnitConversionService`:

- `ConvertToBase()`
- `ConvertFromBase()`
- `ConvertPresentation()`
- `GetAvailablePresentations()`
- `CalculateRequiredStock()`

Toda conversión pasa por este motor; POS, compras, inventario y catálogo lo consumen.

### 5.4 Integraciones previstas

| Módulo | Comportamiento |
|--------|----------------|
| **Inventario** | Movimientos siempre en unidad base |
| **Compras** | OC en “5 cajas” → convierte a base + costo unitario normalizado |
| **POS** | Escaneo resuelve presentación; descuenta stock en base; selector manual de presentación |
| **Catálogo / e-commerce** | Publica maestro; expone presentaciones comprables |
| **Radar de precios** | Compara ofertas distintas normalizando a unidad base |
| **IA (futuro)** | Estadísticas por presentación (más vendida, comprada, por sucursal/cliente) |

### 5.5 Compatibilidad

Si un producto solo tiene la presentación base (factor = 1), debe comportarse **igual que hoy**.

### 5.6 Decisiones de diseño para Clean

- **No crear `product_unit_conversions` en MVP** si `factor_conversion` lineal basta; evaluar tabla extra solo para conversiones no lineales.
- **Reutilizar/extender** el concepto actual de alias de escaneo (`producto_codigo_escaneo`) para no duplicar motores de resolución de código.
- Definir política de **redondeo** (enteros vs decimales) por tipo de unidad base.
- Migración automática: cada producto legacy recibe presentación default factor=1.

### 5.7 Fases de implementación sugeridas (Clean + Alembic)

| Fase | Alcance | Riesgo |
|------|---------|--------|
| **A** | Tabla presentaciones + conversión + POS (escaneo y selector) | Medio |
| **B** | Compras / OC con conversión y costo normalizado | Medio |
| **C** | Inventario y kardex 100% en unidad base | Alto |
| **D** | Catálogo web, radar precios, analytics IA | Bajo–medio |

---

## 6. Alcance y exclusiones

### 6.1 Incluido en SD-1 (legacy)

- Procedimiento operativo de duplicados (sección 4).
- Mantener `codigo_barra` único + alias POS.
- Correcciones puntuales de bugs críticos en flujo POS/enrolamiento.

### 6.2 Excluido de SD-1 (legacy) — diferido a Clean

- Tablas `product_presentations` / migraciones Alembic.
- `UnitConversionService` transversal.
- Cambios de esquema en `detalle_venta`, `detalle_orden_compra`, `movimiento_inventario`.
- UI de administración de presentaciones en ficha producto.
- APIs REST `/products/{id}/presentations`, `/convert`, etc.
- Arquitectura hexagonal/DDD completa del motor (solo en nuevo repo/modelo).

---

## 7. Referencias técnicas (legacy)

| Área | Ubicación |
|------|-----------|
| Modelo `Producto` | `app.py` — `codigo_barra` unique |
| Alias escaneo | `services/producto_codigo_escaneo_service.py` |
| Enrolamiento vincular / editar | `app.py` — `_enrol_vincular_codigo_barras`, `/api/enrolamiento/editar_ficha` |
| POS vincular | `api_pos_vincular_codigo()` en `app.py` |
| Catálogo listado | `/productos` — `templates/productos.html` |
| Desactivar producto | `POST /toggle_producto/<id>` |
| Manual operador | `MANUALES DE OPERACIÓN/MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` |
| Arquitectura códigos POS | `MANUALES DE OPERACIÓN/POS_CODIGO_ESCANEADO_ARQUITECTURA.md` |

---

## 8. Historial de revisiones

| Versión | Fecha | Autor | Cambio |
|---------|-------|-------|--------|
| 1.0 | 2026-07-08 | Mario / Cursor | Creación: duplicados SD-1 + diferimiento Smart Units Engine a Alembic/Clean |

---

## 9. Próximos pasos

1. **Operación piso:** aplicar procedimiento sección 4 ante duplicados.
2. **Gate Clean:** incluir Smart Units Engine en diseño de modelos Alembic y backlog v2.
3. **Al abrir Clean:** ADR dedicado + migración presentación default factor=1 + tests smoke POS/conversión.

---

*Documento de control de cambio — LhexIA ERP · Producto maestro y Smart Units Engine.*
