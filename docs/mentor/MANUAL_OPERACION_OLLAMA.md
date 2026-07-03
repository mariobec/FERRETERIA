# Manual operativo LhexIA — base Ollama / Mentor Coach

> Versión KB: **2026-06-04** · Producto: LhexIA ERP · Ferretería Santo Domingo

Documento fuente para **Ollama** y el **Mentor Coach** en `/academy`.
No editar el Markdown a mano: regenerar con `python scripts/export_mentor_kb_md.py`.

---

## Invariantes de negocio

- **inv_financiera:** El POS jamás recauda dinero real. Todo cobro (efectivo, tarjeta, crédito) se cierra únicamente en la estación de Caja.
- **inv_stock_tienda:** El POS descuenta stock solo del almacén marcado como Tienda / Mostrador. Bodega es reserva interna.
- **inv_codigo_pistola:** La pistola alimenta codigo_barra. Vincular en enrolamiento crea alias; no pisa el código maestro del producto.

---

## Procedimientos por módulo

### Punto de venta (mostrador) (`pos`)
- Ruta base: `/punto_venta`

#### Emitir vale pendiente de cobro
1. Abrir caja del turno (si no está abierta, el sistema redirige a Abrir caja).
2. Ir a Punto de venta (/punto_venta).
3. F2 o clic en buscador; escanear código o escribir nombre parcial.
4. Elegir filtro Operativo (vendible hoy), Tienda (stock mostrador) o Catálogo (todo con precio).
5. Revisar semáforo: verde = OK, amarillo = confirmar, rojo = no prometer entrega inmediata.
6. Agregar líneas con cantidad correcta y unidad de medida.
7. Identificar cliente o usar cliente final del sistema.
8. Pulsar Emitir vale (F8). El vale queda Pendiente — NO cobrar en POS.
9. Entregar ticket al cliente para fila de caja.

**Errores frecuentes:**
- Cobrar en POS: incorrecto; usar Caja → Vales pendientes.
- Ignorar semáforo rojo: genera reclamos.
- Producto sin precio POS (precio_venta_sd): no es vendible hasta corregir en maestro o enrolador.

#### Usar filtros de búsqueda POS
1. Operativo: productos vendibles hoy (stock tienda + precio POS).
2. Tienda: solo SKU con stock en almacén mostrador.
3. Catálogo: maestro completo con precio, aunque no haya stock.

### Caja registradora (`caja`)
- Ruta base: `/caja/vales_pendientes`

#### Abrir caja (inicio de turno)
1. Menú Caja → Abrir caja (/abrir_caja).
2. Contar físicamente billetes y monedas del fondo (sencillo).
3. Ingresar saldo inicial en CLP.
4. Confirmar Iniciar jornada.
5. Verificar que POS y Vales pendientes queden habilitados.

#### Cobrar vale emitido en POS
1. Ir a Vales pendientes (/caja/vales_pendientes).
2. Escanear código del vale (VL######) o buscar por folio.
3. Verificar ítems, totales e IVA incluido.
4. Elegir medio de pago: efectivo, tarjeta, transferencia o crédito (si aplica).
5. Confirmar cobro; el vale pasa a Pagado.
6. Entregar comprobante al cliente.

#### Cobrar pedido web (Maylén / tienda online)
1. Pedido PED-WEB###### puede estar Pagado (Webpay) o Pendiente (pagar en tienda).
2. Si Pendiente: cobrar en caja como vale normal.
3. Si Pagado Webpay: aparece en bandeja e-commerce (/ecommerce/pedidos) para preparación.
4. Bodega prepara; cliente retira con QR.

#### Movimiento extraordinario de caja
1. Caja → Movimientos (/movimiento_caja).
2. Elegir Ingreso o Egreso.
3. Concepto claro y verificable.
4. En Egreso: responsable del retiro es obligatorio.
5. Guardar y verificar en historial del turno.

#### Cerrar caja — arqueo ciego
1. Resolver vales pendientes o documentar excepción.
2. Separar efectivo, vouchers y otros medios.
3. Caja → Cerrar caja (/cerrar_caja).
4. Ingresar montos declarados sin ver teórico primero.
5. Si hay descuadre: observación obligatoria y escalar.
6. Confirmar cierre según política de la tienda.

### Bodega e inventario (`bodega`)
- Ruta base: `/inventario/enrolamiento`

#### Enrolamiento — sesión y escaneo
1. Ir a Enrolamiento inventario (/inventario/enrolamiento).
2. Elegir almacén de la toma (Tienda = venta POS; Bodega = reserva).
3. Pulsar Nueva sesión.
4. Pistoleá código; Enter envía automático.
5. Caso A reconocido: revisar ficha y pulsar Sumar para confirmar cantidad.
6. Caso B código nuevo: buscar en maestro y Vincular (crea alias).
7. Caso C no está en maestro: Alta manual con nombre y precio venta.

#### Enrolador en tablet + pistola BCST
1. Tablet y PC servidor en la misma WiFi.
2. Abrir http://IP_SERVIDOR:5000/login e iniciar sesión.
3. Ir a /inventario/enrolamiento/tablet o escanear QR en /bodega/enrolador.
4. Agregar a pantalla de inicio (acceso directo, sin APK).
5. Emparejar pistola Bluetooth en modo teclado (HID).
6. Tocar recuadro de escaneo visible en tablet y pistoleá.

#### Salud del inventario
1. Ir a Inventario → Salud (/inventario/salud).
2. Revisar desajuste maestro vs suma depósitos.
3. Segunda tabla: tienda en cero y bodega con stock → candidatos a traslado.
4. Exportar CSV si hace falta trabajar en Excel.
5. Corregir con traslado, ajuste autorizado o nuevo conteo.

#### Recepción — pistola sin duplicar stock
1. Abrir recepción Pendiente o Incompleta.
2. En líneas registradas usar botón Pistola por producto.
3. Pistoleá código en modal — NO suma stock extra, solo guarda codigo_barra.
4. Si hay código provisional INT-..., puede reemplazarse pistoleando el real.

### Tienda online y pedidos web (`ecommerce`)
- Ruta base: `/ecommerce/pedidos`

#### Bandeja pedidos web Maylén
1. Menú E-commerce → Pedidos web (/ecommerce/pedidos).
2. Filtrar Pagado + pendiente preparación.
3. Preparar ítems; marcar listo para retiro.
4. Cliente retira con QR; caja ya cobró o Webpay pagó automático.

---

## Preguntas y respuestas (FAQ)

### ¿Cómo emitir un vale en el POS?
- **Módulo:** pos · **Ruta:** `/punto_venta`

En Punto de venta agregá productos, revisá semáforos y precio POS, identificá cliente y pulsá Emitir vale (F8). El vale queda Pendiente para cobro en caja. Nunca cobres en el POS.

**Pasos:**
1. Abrir /punto_venta
2. Buscar o escanear producto (F2)
3. Revisar semáforo y precio SD
4. Emitir vale F8
5. Cliente va a caja con el ticket

*También preguntan:* emitir vale, vender sin cobrar, mandar a caja, F8 vale, vale pendiente

### ¿Puedo cobrar en el punto de venta?
- **Módulo:** pos · **Ruta:** `/caja/vales_pendientes`

No. Invariante financiera: el POS solo emite vales pendientes. Todo cobro real se hace en Caja → Vales pendientes.

**Pasos:**
1. Emitir vale en POS
2. Derivar cliente a caja
3. Cajero cobra en /caja/vales_pendientes

*También preguntan:* cobrar en pos, recaudar mostrador, efectivo pos

### ¿Qué significan los semáforos de stock en el POS?
- **Módulo:** pos · **Ruta:** `/punto_venta`

Verde: stock suficiente en tienda — entrega inmediata OK. Amarillo: stock bajo o parcial — confirmá con el cliente. Rojo/sin stock: no prometas entrega inmediata; ofrecé pedido o alternativa.

**Pasos:**
1. Filtro Operativo muestra semáforo
2. Verde = vendible hoy
3. Rojo = no prometer

*También preguntan:* semáforo verde, semáforo rojo, semáforo amarillo, stock operativo

### ¿Cuál filtro de búsqueda uso: Operativo, Tienda o Catálogo?
- **Módulo:** pos · **Ruta:** `/punto_venta`

Operativo = lo vendible hoy (stock tienda + precio POS). Tienda = solo con stock en mostrador. Catálogo = todo el maestro con precio aunque no haya stock. Para vender rápido usá Operativo.

**Pasos:**
1. F2 foco búsqueda
2. Elegir filtro en barra
3. Operativo para venta del día

*También preguntan:* filtro operativo, filtro tienda, filtro catalogo, buscar producto pos

### El POS dice sin precio o no deja vender un producto
- **Módulo:** pos · **Ruta:** `/inventario/enrolamiento`

El POS usa precio_venta_sd (precio POS Santo Domingo). Si falta o stock tienda es cero, no es vendible. Corregí en enrolador o maestro de productos: asignar precio SD y stock en almacén Tienda.

**Pasos:**
1. Ver pill Vendible en POS en enrolador
2. Sumar stock en Tienda
3. Asignar precio_venta_sd

*También preguntan:* sin precio pos, precio venta sd, producto no vendible

### ¿Cómo abro la caja al iniciar el turno?
- **Módulo:** caja · **Ruta:** `/abrir_caja`

Menú Caja → Abrir caja. Contá el efectivo físico en gaveta, ingresá el monto en CLP y confirmá Iniciar jornada. Sin caja abierta el POS puede bloquearse.

**Pasos:**
1. /abrir_caja
2. Contar gaveta
3. Ingresar saldo inicial
4. Iniciar jornada

*También preguntan:* abrir caja, inicio turno, saldo inicial, fondo caja

### ¿Cómo cobro un vale del vendedor?
- **Módulo:** caja · **Ruta:** `/caja/vales_pendientes`

Ir a Vales pendientes, escanear código VL###### o buscar folio, verificar total y elegir medio de pago. Confirmar cobro — pasa a Pagado.

**Pasos:**
1. /caja/vales_pendientes
2. Escanear vale
3. Medio de pago
4. Confirmar

*También preguntan:* cobrar vale, vales pendientes, VL, escanear vale caja

### ¿Cómo cierro la caja con arqueo ciego?
- **Módulo:** caja · **Ruta:** `/cerrar_caja`

Resolvé vales pendientes, separá medios de pago, andá a Cerrar caja. Declarás montos sin ver el teórico primero. Si hay diferencia, observación obligatoria y escalá a supervisor.

**Pasos:**
1. /cerrar_caja
2. Declarar efectivo y vouchers
3. Revisar diferencia
4. Confirmar cierre

*También preguntan:* cerrar caja, arqueo ciego, PLAT, descuadre caja

### ¿Cómo registro un retiro de efectivo de caja?
- **Módulo:** caja · **Ruta:** `/movimiento_caja`

Caja → Movimientos. Elegí Ingreso o Egreso, concepto claro, monto en CLP. En Egreso el responsable del retiro es obligatorio. No uses esto para anular vales.

**Pasos:**
1. /movimiento_caja
2. Ingreso o Egreso
3. Concepto + monto
4. Responsable si egreso

*También preguntan:* movimiento caja, egreso caja, retiro efectivo, ingreso caja

### ¿Cómo hago una devolución o cambio?
- **Módulo:** caja · **Ruta:** `/caja/cambios`

Usá el módulo Caja → Cambios y devoluciones (/caja/cambios). Seguí el flujo autorizado por supervisión. No anules vales con movimientos de caja.

**Pasos:**
1. /caja/cambios
2. Identificar venta original
3. Flujo devolución autorizado

*También preguntan:* devolucion, cambio producto, nota credito caja

### ¿Qué es el Caso A, B y C en enrolamiento?
- **Módulo:** bodega · **Ruta:** `/inventario/enrolamiento`

Caso A: código reconocido (maestro o alias) — revisá y Sumá cantidad. Caso B: código nuevo — buscá producto y Vinculá (alias, no pisa maestro). Caso C: no está en maestro — Alta manual con nombre y precio.

**Pasos:**
1. Nueva sesión + almacén
2. Escanear
3. A=Sumar, B=Vincular, C=Alta manual

*También preguntan:* caso a b c, codigo nuevo, vincular codigo, alta manual enrol

### ¿Cómo uso el enrolador en tablet con pistola?
- **Módulo:** bodega · **Ruta:** `/bodega/enrolador`

Misma WiFi que el servidor. Login en http://IP:5000, luego /inventario/enrolamiento/tablet o QR en /bodega/enrolador. Emparejá pistola Bluetooth HID, tocá campo de escaneo y pistoleá.

**Pasos:**
1. Login LAN
2. Tablet mode o QR
3. Bluetooth pistola
4. Nueva sesión y escanear

*También preguntan:* tablet bodega, pistola BCST, QR enrolador, wifi enrolamiento

### ¿En qué almacén sumo stock para que venda el POS?
- **Módulo:** bodega · **Ruta:** `/inventario/enrolamiento`

El POS descuenta solo almacén Tienda / Mostrador. Stock en Bodega no vende en caja hasta traslado Bodega → Tienda (modo avanzado en enrolador o plataforma bodega).

**Pasos:**
1. Sesión enrolador en Tienda
2. O traslado Bodega→Tienda
3. Ver pill Vendible en POS

*También preguntan:* almacen tienda, stock mostrador, bodega vs tienda

### ¿Cómo reviso desajustes de inventario?
- **Módulo:** bodega · **Ruta:** `/inventario/salud`

Inventario → Salud del inventario. Compara stock maestro vs suma depósitos. Segunda tabla lista SKU con tienda en cero y bodega con stock para traslado.

**Pasos:**
1. /inventario/salud
2. Filtrar o exportar CSV
3. Traslado o ajuste autorizado

*También preguntan:* salud inventario, maestro vs depositos, desajuste stock

### ¿Pistola en recepción suma stock dos veces?
- **Módulo:** bodega · **Ruta:** `/recepciones`

No. Si la mercadería ya ingresó por línea de recepción, el botón Pistola solo guarda codigo_barra (y genera interno si falta). No duplica kardex.

**Pasos:**
1. Recepción pendiente
2. Líneas → Pistola
3. Escanear sin re-ingresar cantidad

*También preguntan:* recepcion pistola, codigo recepcion, INT provisional

### ¿Cómo atiendo un pedido de la tienda online Maylén?
- **Módulo:** ecommerce · **Ruta:** `/ecommerce/pedidos`

Pagar en tienda: vale PED-WEB Pendiente → cobrar en caja. Webpay: ya Pagado → bandeja /ecommerce/pedidos para preparar. Retiro con QR tras preparación.

**Pasos:**
1. Identificar PED-WEB
2. Cobrar si Pendiente
3. Bandeja e-commerce si Pagado
4. Preparar y retiro

*También preguntan:* pedido web, PED-WEB, maylen, tienda online cobro

### ¿Dónde está la capacitación paso a paso?
- **Módulo:** general · **Ruta:** `/academy`

Menú Capacitación LhexIA → /academy. Tres rutas por rol. En POS y caja usá el botón violeta Mentor para guías en pantalla. Preguntale al Mentor Coach en Academy con lenguaje natural.

**Pasos:**
1. /academy
2. Elegir ruta por rol
3. Guía interactiva o Mentor en piso

*También preguntan:* manual, academy, mentor, capacitacion, ayuda erp

### No veo un menú o pantalla — ¿qué hago?
- **Módulo:** general · **Ruta:** `/login`

Cada pantalla requiere permiso RBAC. Pedí al administrador revisar Mantenedores → Roles y permisos. Permisos clave: pos_emitir_vale, caja_cobrar_vale, enrolamiento_inventario, bodega_operador.

**Pasos:**
1. Confirmar login correcto
2. Solicitar permiso al admin
3. Cerrar sesión y re-entrar

*También preguntan:* sin permiso, no aparece menu, acceso denegado

### Atajos de teclado esenciales en POS
- **Módulo:** pos · **Ruta:** `/punto_venta`

F2 = foco búsqueda/escáner. F8 = emitir vale pendiente. Esc = cerrar modal. El Mentor violeta lista atajos según pantalla.

**Pasos:**
1. F2 buscar
2. F8 emitir vale
3. Esc cancelar

*También preguntan:* F2 F8, atajos pos, teclado pos

### ¿Qué hago si la caja del día anterior quedó abierta?
- **Módulo:** caja · **Ruta:** `/cerrar_caja`

Un supervisor o cajero autorizado debe cerrar la caja anterior antes de abrir turno nuevo. El Mentor en /cerrar_caja guía el arqueo. No abras dos turnos en la misma estación.

**Pasos:**
1. Identificar caja abierta
2. Cerrar con arqueo
3. Abrir caja nuevo turno

*También preguntan:* caja dia anterior, caja no cerrada, bloqueo pos caja

### Vinculé un código — ¿por qué no cambió el código maestro?
- **Módulo:** bodega · **Ruta:** `/inventario/enrolamiento`

Es correcto: vincular crea alias de escaneo (como POS). El codigo_barra maestro no se sobrescribe. Re-escaneá y debe resolver Caso A por alias.

**Pasos:**
1. Vincular en Caso B
2. Re-escaneaar
3. Caso A con alias activo

*También preguntan:* alias codigo, vincular no pisa, codigo barras duplicado

### ¿Dónde veo el historial de movimientos de un producto?
- **Módulo:** inventario · **Ruta:** `/kardex`

Menú Inventario → Kardex (/kardex). Filtrá por producto, fecha o tipo de movimiento. Cada Sumar en enrolador y cada venta registran kardex.

**Pasos:**
1. /kardex
2. Buscar producto
3. Revisar entradas/salidas

*También preguntan:* kardex, trazabilidad stock, movimientos inventario

### ¿Cómo escaneo con pistola en el POS?
- **Módulo:** pos · **Ruta:** `/punto_venta`

El foco debe estar en el buscador (F2). Pistoleá — la pistola en modo teclado escribe el código y envía Enter. El producto se agrega si está vendible.

**Pasos:**
1. F2 foco
2. Pistoleá
3. Enter automático
4. Revisar línea

*También preguntan:* pistola pos, codigo barras pos, escaner pos

### ¿Cómo cobro con tarjeta un pedido Webpay?
- **Módulo:** caja · **Ruta:** `/ecommerce/pedidos`

Si el cliente pagó Webpay en tienda online, la venta ya está Pagada. No cobres de nuevo en caja. Prepará desde bandeja e-commerce. Si quedó Pendiente (pagar en tienda), cobrá como vale normal.

**Pasos:**
1. Ver estado PED-WEB
2. Pagado Webpay → preparar
3. Pendiente → cobrar caja

*También preguntan:* webpay, tarjeta online, pedido pagado web

### Producto inactivo — ¿por qué aparece en enrolador?
- **Módulo:** bodega · **Ruta:** `/inventario/enrolamiento`

El enrolador puede resolver códigos de productos inactivos con advertencia. No aparecen en POS hasta reactivarlos en maestro de productos.

**Pasos:**
1. Ver aviso INACTIVO en ficha
2. Reactivar en Productos si corresponde

*También preguntan:* producto inactivo, no vende pos inactivo
