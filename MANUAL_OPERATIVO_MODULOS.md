# Manual Operativo por Modulos - ERP Ferreteria

Este documento esta pensado para usuario final (cajero, vendedor, bodega, administrador).
Explica el uso diario por modulo, paso a paso, con validaciones simples para evitar errores.

---

## 1) Flujo operativo recomendado (orden diario)

1. **Abrir Caja** al iniciar turno.
2. **Recepciones** (si llega mercaderia) para subir stock.
3. **Punto de Venta** para armar vales/pedidos.
4. **Vales Pendientes (Caja)** para cobrar.
5. **Kardex** para validar movimientos.
6. **Cerrar Caja** al finalizar turno.
7. **BI Reportes / IA Abastecimiento** para revisar gestion.

---

## 2) Acceso y perfiles

### Login
1. Entrar con correo y clave.
2. Si el sistema pide cambio de clave temporal, actualizarla inmediatamente.
3. Verificar en la barra superior que aparece su nombre de usuario.

### Cierre de sesion
1. Usar siempre el boton **Cerrar Sesion** del menu lateral.
2. Confirmar que vuelve a la pantalla principal (index).

---

## 3) Modulo Inicio

**Objetivo:** panel principal de navegacion interna.

### Paso a paso
1. Desde el menu lateral, hacer clic en **Inicio**.
2. Revisar accesos directos segun su rol.
3. Si un acceso no aparece, solicitar revision de permisos al administrador.

---

## 4) Modulo Productos

**Objetivo:** crear, editar, activar/desactivar y buscar productos.

### A) Alta manual de producto
1. Ir a **Productos**.
2. Completar datos minimos: nombre, codigo barra (si aplica), precio compra, precio venta, stock.
3. Completar categoria/subcategoria para mejorar busquedas.
4. Completar ubicacion fisica (pasillo/estante/nivel) si ya esta definida.
5. Guardar y confirmar mensaje de exito.

### B) Carga masiva por CSV
1. Ir a **Productos** y ubicar seccion de importacion.
2. Descargar plantilla si es necesario.
3. Preparar archivo CSV con columnas del sistema.
4. Subir archivo y ejecutar carga.
5. Revisar resumen final: creados, actualizados, omitidos y duplicados del archivo.

### C) Validaciones clave
- Buscar por nombre, codigo de barra, categoria y subcategoria.
- Confirmar que producto nuevo queda visible y activo.
- Verificar que precios no queden en cero por error.

**Buena practica:** no usar codigos de barra duplicados.

---

## 5) Modulo Proveedores

**Objetivo:** mantener proveedores para recepcion de mercaderia y control de compras.

### Paso a paso
1. Ir a **Proveedores**.
2. Crear proveedor con nombre y datos de contacto.
3. Guardar.
4. Si cambia informacion, usar editar en la misma pantalla.

### Validaciones clave
- El proveedor debe quedar disponible al crear una recepcion.
- Evitar nombres duplicados del mismo proveedor.

---

## 6) Modulo Recepciones (mercaderia)

**Objetivo:** registrar ingreso fisico de mercaderia y actualizar inventario.

### A) Crear nueva recepcion
1. Ir a **Recepciones**.
2. Seleccionar **Nueva Recepcion**.
3. Elegir proveedor y tipo de documento (factura/guia).
4. Guardar encabezado.

### B) Registrar lineas de recepcion
1. Agregar producto por codigo o busqueda.
2. Ingresar cantidad fisica recibida y costo unitario.
3. Confirmar unidad de compra/venta y conversion aplicada.
4. Repetir por cada item.

### C) Finalizar recepcion
1. Revisar resumen de lineas.
2. Adjuntar documento (opcional si proceso lo requiere).
3. Finalizar recepcion.
4. Confirmar que el stock aumenta.

### D) Uso en terreno (tablet)
1. Abrir **Recepciones** en modo tablet.
2. Registrar items caminando en bodega.
3. Confirmar luego en resumen de recepcion.

### Validaciones clave
- No dejar recepciones incompletas sin revisarlas.
- Verificar que cada linea impacte stock.
- Si hay conversiones, revisar que el ingreso al stock base sea coherente.

---

## 7) Modulo Kardex

**Objetivo:** ver historial de movimientos de inventario (entradas y salidas).

### Paso a paso
1. Ir a **Kardex**.
2. Filtrar por producto o tipo de movimiento.
3. Revisar detalle de movimiento, referencia y fecha.

### Que deberia verse
- **ENTRADA** al finalizar recepciones.
- **SALIDA** al cobrar ventas.

### Validaciones clave
- Cada recepcion finalizada debe generar entrada.
- Cada cobro de venta debe generar salida.
- Si no aparece un movimiento, revisar si la operacion se completo correctamente.

---

## 8) Modulo Punto de Venta

**Objetivo:** armar la venta y emitir vale para cobro.

### Paso a paso
1. Ir a **Punto de Venta**.
2. Buscar producto (nombre o codigo) y agregar.
3. Ajustar cantidad y descuento por linea.
4. Revisar subtotal y total.
5. Completar datos de cliente:
   - cliente normal (con RUT), o
   - cliente final (generico).
6. Emitir vale.

### Validaciones clave
- El item debe tener stock disponible.
- Si hay conversion de unidades, revisar el texto de consumo real de stock.
- Si aparece alerta de stock insuficiente, corregir cantidad antes de emitir.

---

## 9) Modulo Vales Pendientes (Caja)

**Objetivo:** cobrar vales emitidos por POS.

### Paso a paso
1. Ir a **Vales Pendientes**.
2. Seleccionar vale.
3. Confirmar medio de pago (efectivo, debito, credito, etc.).
4. Procesar cobro.
5. Verificar que el vale cambia de estado.

### Validaciones clave
- El cobro debe registrar movimiento de caja.
- El stock debe descontarse al procesar cobro.

---

## 10) Modulos de Caja

## 10.1 Abrir Caja
1. Ir a **Abrir Caja**.
2. Ingresar monto inicial.
3. Confirmar apertura.

## 10.2 Movimientos
1. Ir a **Movimientos**.
2. Registrar ingreso o egreso extraordinario.
3. Ingresar motivo y responsable.
4. Guardar.

## 10.3 Cerrar Caja
1. Ir a **Cerrar Caja**.
2. Revisar resumen del turno.
3. Confirmar monto final contado.
4. Ejecutar cierre.

### Validaciones clave
- No operar POS/cobros sin caja abierta.
- Todo movimiento extraordinario debe quedar respaldado con motivo.

---

## 11) Modulo Historial de Ventas

**Objetivo:** consultar ventas anteriores y su estado.

### Paso a paso
1. Ir a **Historial Ventas**.
2. Buscar por fecha/estado/cliente (segun filtros disponibles).
3. Revisar detalle de la venta.

### Validaciones clave
- Confirmar que las ventas cobradas no queden en pendiente.
- Verificar coherencia entre historial y caja.

---

## 12) Modulo Revision de Precios

**Objetivo:** actualizar precios con criterio comercial y trazabilidad.

### Paso a paso
1. Ir a **Revision Precios**.
2. Filtrar productos por categoria/subcategoria/texto.
3. Revisar precio actual, costo, margen y precio sugerido.
4. Ingresar **motivo** de cambio (obligatorio).
5. Aplicar cambio individual o masivo.
6. Revisar bitacora reciente.

### Validaciones clave
- No aplicar cambios masivos sin filtro.
- Siempre registrar motivo claro del ajuste.

---

## 13) Modulo BI Reportes

**Objetivo:** seguimiento de indicadores de negocio.

### Paso a paso
1. Ir a **BI Reportes**.
2. Revisar KPIs principales.
3. Analizar graficos por periodo.
4. Exportar CSV si requiere analisis externo.

---

## 14) Modulo IA Abastecimiento

**Objetivo:** sugerencias para reabastecimiento.

### Paso a paso
1. Ir a **IA Abastecimiento**.
2. Revisar productos sugeridos para compra.
3. Priorizar por riesgo de quiebre o comportamiento de ventas.
4. Usar esta vista como apoyo para decisiones de reposicion.

---

## 15) Modulo Creditos y Abonos

**Objetivo:** administrar cuentas con saldo pendiente y registrar pagos parciales.

### Paso a paso
1. Ir a **Creditos**.
2. Buscar cliente/venta con deuda.
3. Registrar abono.
4. Emitir o revisar ticket de abono.

### Validaciones clave
- El abono debe descontar saldo correctamente.
- Revisar comprobante para respaldo.

---

## 16) Modulos de Administracion (solo admin)

## 16.1 Usuarios
1. Crear usuario con rol.
2. Definir si queda activo/inactivo.
3. Entregar clave temporal.
4. Confirmar que el usuario cambie clave al primer ingreso.

## 16.2 Empresa
1. Editar nombre comercial, razon social y datos de contacto.
2. Guardar.
3. Confirmar reflejo en encabezados del sistema.

## 16.3 Unidades
1. Crear unidades (ej: UN, KG, M, CJ).
2. Configurar conversiones (origen, destino, factor).
3. Validar con un producto real que compra y venta convierten correctamente.

---

## 17) Modulos publicos (sin login)

## 17.1 Catalogo Publico
1. Ir a **Catalogo Publico** desde index.
2. Buscar por nombre/codigo y filtrar por categoria.
3. Revisar disponibilidad.
4. Si corresponde, usar boton de WhatsApp para consulta comercial.

## 17.2 Consulta Rapida Stock
1. Ir a **Consulta Rapida Stock** desde index.
2. Escribir nombre o codigo.
3. Revisar estado de disponibilidad.

**Nota:** segun configuracion, puede mostrarse o no precio y stock exacto.

---

## 18) Cierre operativo diario (checklist rapido)

Antes de cerrar jornada:
- Confirmar que no hay vales pendientes sin gestionar.
- Confirmar que recepciones del dia esten finalizadas.
- Revisar Kardex en movimientos criticos.
- Ejecutar cierre de caja.
- Cerrar sesion.

---

## 19) Errores comunes y accion inmediata

### "Stock insuficiente" en POS
- Ajustar cantidad o quitar item.
- Verificar conversion de unidad del producto.

### Recepcion no impacta Kardex
- Confirmar que la recepcion este finalizada (no solo guardada parcial).
- Revisar que las lineas tengan cantidad valida.

### Usuario no puede entrar
- Revisar si esta inactivo.
- Verificar cambio de clave temporal pendiente.

### Link/menu no visible
- Revisar rol/permisos del usuario.

---

## 20) Sugerencia de capacitacion para cliente final

1. **Sesion 1 (60-90 min):** Productos, Proveedores, Recepciones.
2. **Sesion 2 (60 min):** POS, Caja, Vales Pendientes.
3. **Sesion 3 (45 min):** Kardex, BI, IA Abastecimiento.
4. **Sesion 4 (30 min):** Usuarios, Empresa, Unidades y politicas de seguridad.

Con esto el equipo puede operar de forma autonoma desde el primer ciclo completo:
**producto -> recepcion -> venta -> cobro -> kardex -> reporte**.
