# Plan de capacitación — LhexIA ERP (ferretería)

Plan de **4 sesiones presenciales o remotas** para dejar al equipo operando de forma autónoma desde el primer ciclo completo.

## Objetivo general

Al terminar las 4 sesiones, cada rol debe poder ejecutar sin supervisión:

- Alta y mantención de productos
- Recepción de mercadería con impacto en stock
- Emisión de vales en POS y cobro en caja
- Consulta de Kardex y lectura básica de reportes
- (Admin) usuarios, permisos y datos de empresa

## Sesiones

### Sesión 1 — Productos, proveedores y recepciones (60–90 min)

**Participantes:** bodeguero, encargado de compras, administrador.  
**Material:** [CURSO_01_PRODUCTOS_RECEPCIONES.md](CURSO_01_PRODUCTOS_RECEPCIONES.md)

| Bloque | Min | Contenido |
|--------|-----|-----------|
| Apertura | 10 | Login, permisos, orden del día operativo |
| Productos | 25 | Alta manual, búsqueda, categorías, validaciones |
| Proveedores | 10 | Alta y edición |
| Recepciones | 30 | Crear, líneas, finalizar, verificar Kardex |
| Cierre | 10 | Checklist + preguntas |

**Práctica obligatoria:** recepcionar 3 productos reales y confirmar entrada en Kardex.

---

### Sesión 2 — POS, vales y caja (60 min)

**Participantes:** vendedor, cajera.  
**Material:** [CURSO_02_POS_CAJA.md](CURSO_02_POS_CAJA.md)

| Bloque | Min | Contenido |
|--------|-----|-----------|
| Apertura de caja | 10 | Monto inicial, bloqueo si hay caja anterior |
| POS | 25 | Buscar, cantidades, descuentos, emitir vale |
| Vales pendientes | 15 | Cobro, medios de pago, vuelto |
| Cierre parcial | 10 | Movimientos extraordinarios |

**Práctica obligatoria:** ciclo completo vale → cobro → ticket.

---

### Sesión 3 — Kardex, stock crítico e IA abastecimiento (45 min)

**Participantes:** bodeguero, supervisor, dueño.  
**Material:** [CURSO_03_KARDEX_BI.md](CURSO_03_KARDEX_BI.md) *(pendiente redacción)*

| Bloque | Min | Contenido |
|--------|-----|-----------|
| Kardex | 15 | Filtros, entradas/salidas, auditoría |
| Stock crítico | 10 | Umbral, reposición |
| BI reportes | 10 | KPIs diarios, export CSV |
| IA abastecimiento | 10 | Sugerencias de compra |

---

### Sesión 4 — Administración y seguridad (30 min)

**Participantes:** administrador, dueño.  
**Material:** [CURSO_04_ADMIN_SEGURIDAD.md](CURSO_04_ADMIN_SEGURIDAD.md) *(pendiente redacción)*

| Bloque | Min | Contenido |
|--------|-----|-----------|
| Usuarios y roles | 15 | Crear usuario, permisos mínimos |
| Empresa y unidades | 10 | Datos emisor, conversiones |
| Políticas | 5 | Claves, cierre sesión, quién autoriza descuentos |

---

## Sesión especial — Enrolamiento con pistola (45 min, opcional D0–D5)

**Cuándo:** durante carga inicial de inventario (Santo Domingo).  
**Material:** `MANUALES DE OPERACIÓN/MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` + sección Enrolamiento en `/ayuda#enrolamiento`.

**Práctica obligatoria:** vincular 10 códigos nuevos + 5 altas manuales.

---

## Evaluación por rol

| Rol | Debe demostrar |
|-----|----------------|
| Vendedor | Emitir vale con cliente, manejar alerta de stock |
| Cajera | Cobrar vale, registrar vuelto, abrir/cerrar caja |
| Bodega | Recepcionar, consultar Kardex, enrolar con pistola |
| Admin | Crear usuario, asignar permiso, revisar BI |

## Materiales de apoyo en el ERP

- Centro de ayuda: `/ayuda`
- Pestaña **Capacitación** con checklist por sesión
- Enlaces `?` en pantallas críticas

## Calendario sugerido (Santo Domingo)

| Día | Sesión |
|-----|--------|
| D-2 | Sesión 4 (admin) + Sesión 1 (bodega) |
| D-1 | Enrolamiento pistola + recepciones piloto |
| D0 | Sesión 2 (POS/caja) en piso con supervisión |
| D+3 | Sesión 3 (Kardex/BI) + repaso errores comunes |
