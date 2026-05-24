# Manual General — LhexIA ERP

**Sistema de gestión para ferreterías y retail especializado**  
**Versión:** 1.0 · Mayo 2026  
**Audiencia:** cajera, vendedor, bodeguero, supervisor, administrador

---

## Tabla de contenidos

1. [Introducción](#1-introducción)
2. [Acceso al sistema](#2-acceso-al-sistema)
3. [Orden del día operativo](#3-orden-del-día-operativo)
4. [Dónde encontrar ayuda](#4-dónde-encontrar-ayuda)
5. [Módulo Inicio y navegación](#5-módulo-inicio-y-navegación)
6. [Módulo Productos](#6-módulo-productos)
7. [Módulo Proveedores](#7-módulo-proveedores)
8. [Módulo Recepciones](#8-módulo-recepciones)
9. [Módulo Enrolamiento con pistola](#9-módulo-enrolamiento-con-pistola)
10. [Módulo Kardex](#10-módulo-kardex)
11. [Módulo Punto de Venta (POS)](#11-módulo-punto-de-venta-pos)
12. [Módulo Vales Pendientes y Caja](#12-módulo-vales-pendientes-y-caja)
13. [Módulo Historial de Ventas](#13-módulo-historial-de-ventas)
14. [Módulo Cotizaciones](#14-módulo-cotizaciones)
15. [Módulo Créditos y Abonos](#15-módulo-créditos-y-abonos)
16. [Módulo Revisión de Precios](#16-módulo-revisión-de-precios)
17. [Módulo BI Reportes e IA Abastecimiento](#17-módulo-bi-reportes-e-ia-abastecimiento)
18. [Módulo Bodega y despachos](#18-módulo-bodega-y-despachos)
19. [Administración del sistema](#19-administración-del-sistema)
20. [Módulos públicos (sin login)](#20-módulos-públicos-sin-login)
21. [Checklist de cierre diario](#21-checklist-de-cierre-diario)
22. [Errores frecuentes y solución](#22-errores-frecuentes-y-solución)
23. [Plan de capacitación](#23-plan-de-capacitación)
24. [Glosario](#24-glosario)

---

## 1. Introducción

LhexIA ERP es la plataforma que concentra las operaciones diarias de la ferretería: inventario, ventas en mostrador, cobros en caja, compras, reportes y administración de usuarios.

Este manual describe **cómo operar el sistema paso a paso**, sin modificar la configuración técnica del servidor. Está pensado para el equipo de piso y supervisión.

### Ciclo operativo completo

Todo el negocio gira en torno a este flujo:

```
Producto → Recepción → POS (vale) → Caja (cobro) → Kardex → Reporte
```

Si domina este ciclo, puede operar de forma autónoma desde el primer día de uso real.

### Roles habituales

| Rol | Responsabilidad principal |
|-----|---------------------------|
| **Vendedor** | Armar ventas y emitir vales en POS |
| **Cajera** | Cobrar vales, abrir/cerrar caja, vueltos |
| **Bodeguero** | Recepciones, stock, enrolamiento con pistola |
| **Supervisor** | Kardex, stock crítico, reportes, precios |
| **Administrador** | Usuarios, permisos, datos de empresa |

Cada rol ve solo los menús para los que tiene permiso. Si falta un acceso, solicite revisión en **Roles y permisos**.

---

## 2. Acceso al sistema

### 2.1 Iniciar sesión

1. Abra el navegador e ingrese a la dirección del ERP (proporcionada por su administrador).
2. Escriba **correo** y **clave**.
3. Si el sistema pide cambio de clave temporal, actualícela de inmediato.
4. Verifique en la barra superior que aparece su **nombre de usuario**.

### 2.2 Cerrar sesión

1. Use siempre el botón **Cerrar sesión** del menú lateral.
2. Confirme que vuelve a la pantalla de inicio pública.

**Buena práctica:** no deje la sesión abierta en un equipo compartido al terminar el turno.

### 2.3 Cambio de contraseña

Si el sistema lo exige al ingresar, vaya a **Mi cuenta** o siga el aviso en pantalla. Use una clave que recuerde y no la comparta.

---

## 3. Orden del día operativo

Siga esta secuencia para mantener stock, caja e informes alineados:

| Paso | Acción | Quién |
|------|--------|-------|
| 1 | **Abrir caja** con monto inicial real | Cajera |
| 2 | **Recepciones** si llega mercadería | Bodega |
| 3 | **Punto de venta** — emitir vales | Vendedor |
| 4 | **Vales pendientes** — cobrar | Cajera |
| 5 | **Bodega** — despachos si aplica | Bodega |
| 6 | **Kardex** — validar movimientos críticos | Supervisor / Bodega |
| 7 | **Cerrar caja** al finalizar turno | Cajera |
| 8 | **BI / IA abastecimiento** — revisión gerencial | Dueño / Supervisor |

---

## 4. Dónde encontrar ayuda

### Centro de ayuda en el ERP

- Menú lateral → **Ayuda**
- Hub de módulos → tarjeta **Capacitación**
- URL directa: `/ayuda`

Incluye guías por rol, búsqueda de tareas frecuentes, plan de capacitación y tabla de errores comunes.

### Ayuda contextual en pantallas

En POS, caja, enrolamiento y cierre de caja hay un botón **Ayuda** o **Guía** que abre la sección correspondiente del manual en línea.

### Iconos de ayuda (?)

En tableros de gerencia, BI, créditos y otros KPIs, el icono **?** explica qué significa cada indicador al pasar el mouse.

### Este documento

Ubicación en el proyecto: `docs/manuales/MANUAL_GENERAL_ERP.md`  
Puede imprimirse o convertirse a PDF para entregar al equipo.

---

## 5. Módulo Inicio y navegación

**Objetivo:** panel principal con accesos directos según su rol.

### Paso a paso

1. Desde el menú lateral, haga clic en **Panel del día** o **Inicio**.
2. Revise indicadores del día (ventas, stock, créditos) si su rol lo permite.
3. Use los accesos rápidos a módulos frecuentes.
4. Desde **Módulos** (hub) vea todas las áreas del ERP en tarjetas.

### Si no ve un módulo

El menú depende de **permisos por rol**. Solicite al administrador que revise **Roles y permisos** y asigne el acceso necesario.

---

## 6. Módulo Productos

**Objetivo:** crear, editar, activar/desactivar y buscar productos del catálogo.

### 6.1 Alta manual de producto

1. Ir a **Productos**.
2. Completar datos mínimos:
   - **Nombre** (obligatorio)
   - **Código de barra** (si existe; evitar duplicados)
   - **Precio compra** y **precio venta** (nunca dejar en cero)
   - **Stock** inicial (si no entrará por recepción)
   - **Categoría / subcategoría** (mejora búsquedas en POS)
   - **Ubicación física** (pasillo, estante, nivel) si está definida
3. Guardar y confirmar mensaje de éxito.
4. Buscar el producto por nombre y por código para validar.

### 6.2 Carga masiva por CSV

1. Ir a **Productos** → sección de importación.
2. Descargar plantilla si es necesario.
3. Preparar archivo CSV con las columnas del sistema.
4. Subir archivo y ejecutar carga.
5. Revisar resumen: creados, actualizados, omitidos y duplicados.

Para cargas grandes (miles de SKU), consulte también la guía `GUIA_CARGA_5000_PRODUCTOS.md`.

### 6.3 Validaciones clave

- El producto debe quedar **activo** y visible en POS.
- No usar códigos de barra duplicados en productos distintos.
- Verificar que precios no queden en cero por error.
- Buscar por nombre, código, categoría y subcategoría antes de crear duplicados.

---

## 7. Módulo Proveedores

**Objetivo:** mantener el registro de proveedores para recepciones y compras.

### Paso a paso

1. Ir a **Proveedores**.
2. Crear proveedor con nombre y datos de contacto.
3. Guardar.
4. Si cambia información, editar en la misma pantalla.

### Validaciones

- El proveedor debe aparecer al crear una recepción nueva.
- Evitar nombres duplicados del mismo proveedor real.

---

## 8. Módulo Recepciones

**Objetivo:** registrar el ingreso físico de mercadería y actualizar inventario.

### 8.1 Crear recepción

1. Ir a **Recepciones** → **Nueva recepción**.
2. Elegir **proveedor** y **tipo de documento** (factura o guía).
3. Guardar encabezado.

### 8.2 Registrar líneas

1. Agregar producto por código o búsqueda.
2. Ingresar **cantidad física recibida** y **costo unitario**.
3. Confirmar unidad de compra/venta y conversión si aplica.
4. Repetir por cada ítem del documento.

### 8.3 Finalizar recepción

1. Revisar resumen de líneas.
2. Adjuntar documento si el proceso lo requiere.
3. **Finalizar recepción** — solo entonces impacta stock.
4. Ir a **Kardex**, filtrar por producto y confirmar movimiento **ENTRADA**.

### 8.4 Recepción en bodega (tablet)

1. Abrir recepción pendiente en tablet.
2. Registrar ítems caminando la bodega.
3. Finalizar desde resumen cuando esté completa.

### 8.5 Regla de oro

> **Recepción primero, pistola después:** registre cantidades del documento; luego asigne códigos de barra por línea (ver sección Enrolamiento). Así stock y documento quedan alineados.

### Validaciones

- No dejar recepciones incompletas sin revisar.
- Verificar que cada línea impacte stock al finalizar.
- Si hay conversiones de unidad, confirmar que el ingreso al stock base sea coherente.

---

## 9. Módulo Enrolamiento con pistola

**Objetivo:** vincular códigos de barra (EAN) a productos y cargar stock inicial en piso.

Menú: **Enrolamiento inventario** (requiere permiso **Enrolamiento inventario** o **Admin inventario**).

### 9.1 Conceptos de códigos

| Concepto | Descripción | Quién lo define |
|----------|-------------|-----------------|
| **Código de barra** | Lo que lee la pistola (EAN del producto) | Operador al escanear |
| **Código interno** | Identificador interno (ej. FERRE-0001) | El sistema, automático |
| **Código referencia / Chilemat** | Referencia de catálogo o proveedor | Maestro o importación |

**Regla:** la pistola siempre alimenta el **código de barra**. El interno es el identificador propio de la ferretería.

### 9.2 Antes de escanear

1. Elija **Almacén** (donde sumará stock al vincular o crear producto).
2. Use **Nueva sesión** si cambió de turno o quiere reiniciar conteo.
3. Pistolee y pulse **Enter** (la pistola suele enviarlo sola).
4. No recargue la página; el sistema procesa en tiempo real.

### 9.3 Tres casos al escanear

| Caso | Señal | Qué hacer |
|------|-------|-----------|
| **A — Reconocido** | Bip corto de éxito | El código ya existe; suma conteo de sesión |
| **B — Vincular** | Doble tono | Buscar producto en catálogo (mín. 2 caracteres) y asignar el código escaneado |
| **C — Alta manual** | Tono grave | Producto nuevo: completar nombre, categoría y cantidad inicial |

### 9.4 Pistola en recepción (sin duplicar stock)

Cuando la mercadería **ya ingresó** por recepción (cantidades y Kardex registrados):

1. Abrir recepción **Pendiente** o **Incompleta**.
2. En **Líneas registradas**, usar **Pistola** por producto.
3. Escanear código y Enter en el modal.
4. **No** se vuelve a sumar stock: solo se guarda el código de barra real.

**Códigos provisionales `INT-…`:** se reemplazan al pistolar el código real, sin marcar “Forzar”.

**Forzar reemplazo:** solo si debe corregir un código de barra erróneo ya asignado a ese producto.

### 9.5 Buenas prácticas

1. Un código de barra = un producto en catálogo.
2. Sin pistola, puede pegar el código en el campo y pulsar Enter.
3. Si hay conflicto (código duplicado), resolver en Enrolamiento o en **Productos**.

---

## 10. Módulo Kardex

**Objetivo:** ver historial de movimientos de inventario (entradas y salidas).

### Paso a paso

1. Ir a **Kardex**.
2. Filtrar por producto, fecha o tipo de movimiento.
3. Revisar detalle: cantidad, referencia, fecha y usuario.

### Qué debería verse

| Operación | Movimiento en Kardex |
|-----------|----------------------|
| Recepción finalizada | **ENTRADA** |
| Cobro de venta | **SALIDA** |
| Enrolamiento con stock inicial | **ENTRADA** |
| Ajustes autorizados | Según tipo de ajuste |

### Validaciones

- Cada recepción finalizada debe generar entrada.
- Cada cobro de venta debe generar salida.
- Si falta un movimiento, la operación origen probablemente no se completó.

---

## 11. Módulo Punto de Venta (POS)

**Objetivo:** armar la venta y emitir vale para cobro en caja.

### 11.1 Emitir un vale

1. Ir a **Punto de venta**.
2. Buscar producto por **nombre** o **código de barra** y agregar al carrito.
3. Ajustar cantidad; revisar alertas de stock.
4. Aplicar descuento por línea si corresponde (puede requerir supervisor).
5. Identificar cliente:
   - Cliente con **RUT**, o
   - **Cliente final** genérico.
6. **Emitir vale** — el cobro lo realiza caja en Vales pendientes.

### 11.2 Descuentos con autorización

Si el descuento supera el permiso del usuario, el sistema solicita credenciales de **supervisor autorizado** (configurado en POS autorización descuentos).

### 11.3 Cuándo anular un vale

Solo si el cliente **no volverá a pagar**. Registre motivo.  
**No** anule vales ya cobrados — use **Cambios** en caja.

### 11.4 Alerta: stock insuficiente

- Reduzca cantidad o retire el ítem.
- Si el producto usa conversión de unidades (ej. caja → unidad), lea el texto de consumo real de stock.

### 11.5 Venta desde cotización

Desde **Cotizaciones**, convierta a venta. El POS precarga cliente y líneas. Revise precios antes de emitir vale.

### Validaciones

- Debe haber **caja abierta** para operar con normalidad.
- El ítem debe tener stock disponible al emitir (según reglas del local).
- El vale emitido va a cola de **Vales pendientes** hasta que caja cobre.

---

## 12. Módulo Vales Pendientes y Caja

### 12.1 Cobrar vales pendientes

1. Ir a **Vales pendientes**.
2. Seleccionar vale de la cola.
3. Elegir **método de pago** (efectivo, débito, crédito, etc.).
4. Confirmar cobro.
5. Entregar **vuelto** si aplica (el sistema puede mostrar banner de confirmación).
6. Imprimir o enviar documento si corresponde.

**Resultado esperado:** vale pasa a pagado, stock se descuenta, movimiento queda en caja del turno.

### 12.2 Abrir caja

1. Ir a **Abrir caja**.
2. Registrar **monto inicial real** en efectivo.
3. Confirmar apertura.

No inicie ventas ni cobros sin apertura registrada.

### 12.3 Movimientos extraordinarios

1. Ir a **Movimientos**.
2. Registrar **ingreso** o **egreso** fuera de venta normal.
3. En egresos, indicar **responsable** y **motivo**.
4. Guardar.

### 12.4 Cerrar caja

1. Ir a **Cerrar caja**.
2. Contar efectivo en gaveta.
3. Registrar montos declarados (efectivo, tarjeta según modo de la pantalla).
4. Revisar diferencia; agregar observación si hay descuadre.
5. Si la diferencia supera umbral, un supervisor autoriza con usuario y clave.

**Modo cierre a ciegas:** no verá totales teóricos hasta después — cuente físicamente antes de confirmar.

### 12.5 Cambios y devoluciones

Desde **Cambios** procese devoluciones con trazabilidad. Puede generarse saldo a favor según política del local. Registre siempre el motivo.

### Validaciones de caja

- No operar POS/cobros sin caja abierta.
- Si hay **caja del día anterior abierta**, el POS puede bloquearse hasta cerrarla.
- Todo movimiento extraordinario debe quedar respaldado con motivo.

---

## 13. Módulo Historial de Ventas

**Objetivo:** consultar ventas anteriores y su estado.

### Paso a paso

1. Ir a **Historial ventas**.
2. Filtrar por fecha, estado o cliente.
3. Revisar detalle de cada venta.

### Validaciones

- Las ventas cobradas no deben quedar en pendiente.
- Verificar coherencia entre historial y movimientos de caja.

---

## 14. Módulo Cotizaciones

**Objetivo:** preparar presupuestos antes de convertirlos en venta.

### Flujo habitual

1. Crear cotización con cliente y líneas de productos.
2. Revisar precios y vigencia.
3. Convertir a venta cuando el cliente confirme → el POS precarga los datos.

---

## 15. Módulo Créditos y Abonos

**Objetivo:** administrar cuentas con saldo pendiente y registrar pagos parciales.

### Paso a paso

1. Ir a **Créditos**.
2. Buscar cliente o venta con deuda.
3. Registrar **abono**.
4. Emitir o revisar comprobante de abono.

### Validaciones

- El abono debe disminuir el saldo deudor correctamente.
- Conserve comprobante para respaldo.
- Desde caja también puede acceder a abonos según permisos.

---

## 16. Módulo Revisión de Precios

**Objetivo:** actualizar precios con criterio comercial y trazabilidad.

### Paso a paso

1. Ir a **Revisión precios**.
2. Filtrar por categoría, subcategoría o texto.
3. Revisar precio actual, costo, margen y precio sugerido.
4. Ingresar **motivo** de cambio (obligatorio).
5. Aplicar cambio individual o masivo.
6. Revisar bitácora reciente.

### Validaciones

- No aplicar cambios masivos sin filtrar antes.
- Siempre registrar motivo claro del ajuste.
- Preferir hacer cambios fuera de hora punta.

---

## 17. Módulo BI Reportes e IA Abastecimiento

### 17.1 BI Reportes

**Objetivo:** seguimiento de indicadores de negocio.

1. Ir a **BI reportes**.
2. Revisar KPIs: ventas diarias, margen, métodos de pago, top productos.
3. Analizar gráficos por período.
4. Exportar CSV si requiere análisis externo.

### 17.2 IA Abastecimiento

**Objetivo:** sugerencias de reabastecimiento según ventas y stock.

1. Ir a **IA abastecimiento**.
2. Revisar productos sugeridos para compra.
3. Priorizar por riesgo de quiebre o rotación.
4. Usar como **apoyo** a criterio del comprador — no reemplaza decisión humana.

### 17.3 Simulador de margen (gerencia)

Permite simular escenarios de variación de precio, costo y elasticidad sobre ventas históricas. Los iconos **?** en pantalla explican cada indicador.

---

## 18. Módulo Bodega y despachos

Según configuración del local, puede incluir:

- **Cuadro de mando bodega** — cola de retiros y despachos.
- **Plataforma de retiro** — preparación de pedidos.
- **Despacho por voz o QR** — según módulos activos.

Consulte al administrador qué funciones están habilitadas para su ferretería.

---

## 19. Administración del sistema

*Solo usuarios con rol administrador o permisos equivalentes.*

### 19.1 Usuarios

1. Crear usuario con **rol** asignado.
2. Definir estado activo/inactivo.
3. Entregar **clave temporal**.
4. Confirmar cambio obligatorio al primer ingreso.

### 19.2 Roles y permisos

- Asigne solo permisos necesarios por rol (mínimo privilegio).
- Revise accesos al menos una vez al mes.
- Si un operador no ve un menú, ajuste permisos aquí.

### 19.3 Empresa

1. Editar nombre comercial, razón social, RUT emisor y contacto.
2. Guardar.
3. Confirmar reflejo en encabezados e impresiones.

### 19.4 Unidades y conversiones

1. Crear unidades (UN, KG, M, CJ, etc.).
2. Configurar conversiones: origen, destino, factor.
3. Validar con un producto real que compra y venta convierten correctamente.

### 19.5 Mantenedores

Catálogo, almacenes, clientes, POS autorización descuentos, audit log, etc.  
Aplique cambios **fuera de hora punta** y valide con una prueba corta en POS o inventario.

---

## 20. Módulos públicos (sin login)

### Catálogo público

1. Acceder desde la página de inicio del sitio.
2. Buscar por nombre o código; filtrar por categoría.
3. Revisar disponibilidad.
4. Usar botón de WhatsApp para consulta comercial si está disponible.

### Consulta rápida de stock

1. Acceder desde la página de inicio.
2. Escribir nombre o código.
3. Revisar estado de disponibilidad.

*Según configuración, puede mostrarse o no precio y stock exacto.*

---

## 21. Checklist de cierre diario

Antes de terminar la jornada, confirme:

- [ ] No hay vales pendientes sin gestionar (o quedaron justificados)
- [ ] Recepciones del día están **finalizadas**
- [ ] Kardex revisado en movimientos críticos si hubo diferencias
- [ ] **Cierre de caja** ejecutado con cuadratura
- [ ] **Cierre de sesión** en equipos compartidos

---

## 22. Errores frecuentes y solución

| Situación | Qué hacer |
|-----------|-----------|
| **Stock insuficiente en POS** | Ajustar cantidad, quitar ítem o verificar conversión de unidad |
| **Recepción no impacta Kardex** | Confirmar que está **finalizada**, no solo guardada parcial |
| **Caja del día anterior abierta** | Cerrar caja anterior, cuadrar, luego abrir caja nueva |
| **Usuario no puede entrar** | Revisar si está inactivo o debe cambiar clave temporal |
| **Menú o módulo no visible** | Revisar rol y permisos con administrador |
| **No aparece Enrolamiento** | Solicitar permiso **Enrolamiento inventario** |
| **En recepción: registrar cantidad primero** | Debe existir línea con cantidad antes de usar pistola |
| **Código de barra duplicado** | Un EAN no puede estar en dos productos; resolver en Enrolamiento o Productos |
| **Descuento bloqueado en POS** | Llamar supervisor con permiso de autorización |

---

## 23. Plan de capacitación

Programa recomendado de **4 sesiones** para dejar al equipo autónomo:

| Sesión | Duración | Contenido | Participantes |
|--------|----------|-----------|---------------|
| **1** | 60–90 min | Productos, proveedores, recepciones | Bodega + admin |
| **2** | 60 min | POS, vales pendientes, caja | Vendedor + cajera |
| **3** | 45 min | Kardex, stock crítico, BI, IA abastecimiento | Supervisor |
| **4** | 30 min | Usuarios, roles, empresa, seguridad | Administrador |

**Sesión especial (go-live):** enrolamiento con pistola — 45 min durante carga inicial de inventario.

### Evaluación por rol

| Rol | Debe demostrar |
|-----|----------------|
| Vendedor | Emitir vale, manejar alerta de stock |
| Cajera | Cobrar vale, vuelto, abrir/cerrar caja |
| Bodega | Recepcionar, consultar Kardex, enrolar con pistola |
| Admin | Crear usuario, asignar permiso, revisar BI |

Detalle ampliado en `docs/manuales/PLAN_CAPACITACION.md`.

---

## 24. Glosario

| Término | Significado |
|---------|-------------|
| **Vale** | Documento de venta emitido en POS; va a caja para cobro |
| **Kardex** | Historial de entradas y salidas de stock por producto |
| **Recepción** | Registro de ingreso de mercadería con documento (factura/guía) |
| **Enrolamiento** | Proceso de vincular códigos de barra a productos con pistola |
| **POS** | Punto de venta — pantalla del vendedor en mostrador |
| **SKU** | Producto individual en el catálogo |
| **Cuadratura** | Comparación entre efectivo contado y lo registrado en sistema |
| **Cliente final** | Cliente genérico sin RUT identificado |
| **Cierre a ciegas** | Modo de cierre donde el cajero no ve totales teóricos antes de declarar |

---

## Control de versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | Mayo 2026 | Manual general consolidado: módulos operativos, enrolamiento, ayuda en ERP, capacitación |

---

*LhexIA ERP · www.lhexia.cl · Documento para uso interno del cliente. Si la interfaz cambia, actualice las capturas o nombres de botones en revisiones posteriores.*
