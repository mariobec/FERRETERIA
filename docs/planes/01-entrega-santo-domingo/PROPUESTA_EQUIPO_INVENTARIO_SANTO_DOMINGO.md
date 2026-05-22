# Propuesta de equipamiento — Toma de inventario y enrolamiento

**Cliente:** Ferretería Santo Domingo  
**Proveedor / implementación:** LhexIA ERP · Mario Becerra Olea  
**Fecha:** 21 de mayo de 2026  
**Alcance:** Fase **SD-1** — inventario físico + módulo **Enrolamiento** en [www.lhexia.cl](https://www.lhexia.cl)  
**Vigencia referencial de precios:** mercado Chile, mayo 2026 (sujeto a stock y cotización final del proveedor)

---

## 1. Resumen ejecutivo

Para la **primera toma de inventario** con LhexIA no se requiere comprar otro software de caja (POS comercial tipo retail cerrado). El sistema ya contempla **enrolamiento de inventario** y preparación de catálogo vía navegador web.

Esta propuesta cubre **un puesto de trabajo fijo** (mini PC + pantalla), **una tablet** para operación en pasillo/bodega, **una pistola lectora inalámbrica** (elemento crítico) y periféricos inalámbricos. El equipo queda **reutilizable** en la fase siguiente (puntos de venta y caja).

| Concepto | Monto referencial (CLP) |
|----------|-------------------------|
| **Inversión equipamiento fase inventario** | **$715.000 – $1.195.000** |
| Rango medio orientativo | **~ $950.000** |

*Los montos no incluyen IVA ni instalación eléctrica/red. Facturación según proveedor elegido.*

---

## 2. Objetivo del equipamiento

| Equipo | Rol operativo en LhexIA |
|--------|-------------------------|
| Mini PC + monitor | Mesa de control: altas manuales, categorías, correcciones, sesiones largas |
| Pistola lectora 2D inalámbrica | Escaneo de códigos de barras en enrolamiento (modo teclado, sin software extra) |
| Tablet | Recorrido en pasillo/bodega: `/inventario/enrolamiento` vía Chrome |
| Teclado y mouse inalámbricos | Comodidad en el puesto fijo |

**Operación prevista:** ~4.000 referencias (SKU), **3 sucursales** (almacenes configurados en el ERP). En esta fase se prioriza **una dotación** para arrancar la toma en la sucursal piloto; el resto de puestos POS se cotiza en SD-2.

---

## 3. Recomendaciones técnicas (especificación mínima)

### 3.1 Pistola lectora inalámbrica — **prioridad #1**

| Requisito | Detalle |
|-----------|---------|
| Modo de trabajo | **HID / emulación teclado** (compatible con Chrome y LhexIA sin drivers especiales) |
| Tipos de código | **2D** (QR, Data Matrix) y **1D** (EAN-13, Code 128) |
| Conexión | **2,4 GHz con dongle USB** (recomendado) o Bluetooth con emparejamiento estable |
| Autonomía | Base de carga; jornada completa de inventario |
| Uso | Campo de escaneo en enrolamiento; lectura inmediata del código de barras |

**Referencias de mercado (gama media, duradera):**

- Honeywell Voyager **1472g** (2D, inalámbrico)  
- Zebra **DS2278** (2D, inalámbrico)  

**Alternativa económica:** lector 2D genérico 2,4 GHz con modo HID, compra con garantía local y política de devolución.

**Prueba de aceptación (día 1):** abrir LhexIA → Enrolamiento → enfocar campo de código → escanear producto; el código debe ingresar sin abrir otra aplicación.

---

### 3.2 Mini PC + monitor (puesto fijo)

**Mini PC**

| Componente | Especificación mínima |
|------------|------------------------|
| Procesador | Intel N100 / Core i3 o AMD Ryzen 3 equivalente |
| Memoria RAM | **8 GB** (16 GB deseable si el presupuesto lo permite) |
| Almacenamiento | **SSD 256 GB** |
| Sistema operativo | Windows 11 Home |
| Red | Puerto Ethernet (uso con cable al router) |

**Monitor**

| Componente | Especificación mínima |
|------------|------------------------|
| Tamaño | 21,5" – 24" Full HD (1920×1080) |
| Panel | IPS recomendado |
| Uso | Formularios, catálogo, corrección de líneas de inventario |

Marcas habituales en Chile: Lenovo, HP, Dell; mini PCs Beelink/Ace (validar garantía nacional).

---

### 3.3 Tablet (1 unidad) — enrolamiento en terreno

| Componente | Especificación mínima |
|------------|------------------------|
| Pantalla | 10,5" – 11" |
| Memoria | 4 GB RAM mínimo; **6–8 GB** recomendado |
| Sistema | Android con Chrome actualizado **o** iPad con Safari/Chrome |
| Conectividad | Wi‑Fi estable (ideal banda 5 GHz en local) |
| Accesorios | Funda con protección y correa o soporte de mano |

**Referencias:** Samsung Galaxy Tab A9+ / S9 FE; Lenovo Tab M11; iPad 10.ª generación.

**Requisito de red:** misma red que el mini PC; si la bodega tiene zonas débiles, considerar repetidor Wi‑Fi (no incluido en esta propuesta base).

---

### 3.4 Teclado y mouse inalámbricos

| Ítem | Recomendación |
|------|----------------|
| Kit PC | 1 teclado + 1 mouse inalámbricos con **un solo receptor USB** (ej. Logitech MK270, MK345, Rapoo, Genius) |
| Tablet | Teclado Bluetooth compacto **opcional** en esta fase (la operación principal es táctil + pistola) |

---

### 3.5 Accesorios recomendados (no obligatorios)

| Ítem | Motivo |
|------|--------|
| UPS pequeña (600–900 VA) | Proteger mini PC ante cortes de luz durante carga de datos |
| Cable HDMI | Si el mini PC no incluye cable con el monitor |
| Cable Ethernet Cat6 | Conexión estable al router |

---

## 4. Propuesta económica (valores referenciales CLP)

### 4.1 Dotación base — fase inventario (cantidad sugerida)

| # | Ítem | Cant. | Unitario referencial | Subtotal referencial |
|---|------|-------|----------------------|----------------------|
| 1 | Pistola lectora 2D inalámbrica (HID, base + dongle) | 1 | $120.000 – $220.000 | $120.000 – $220.000 |
| 2 | Mini PC (8 GB RAM, SSD 256 GB, Win 11) | 1 | $250.000 – $380.000 | $250.000 – $380.000 |
| 3 | Monitor 22"–24" Full HD | 1 | $100.000 – $150.000 | $100.000 – $150.000 |
| 4 | Tablet 10"–11" (Android o iPad) + funda básica | 1 | $180.000 – $350.000 | $180.000 – $350.000 |
| 5 | Kit teclado + mouse inalámbrico | 1 | $25.000 – $45.000 | $25.000 – $45.000 |
| 6 | UPS / cables / misceláneos | 1 lote | $40.000 – $80.000 | $40.000 – $80.000 |
| | | | **TOTAL** | **$715.000 – $1.195.000** |

**Propuesta media de trabajo:** **~ $950.000 CLP** (dotación base, gama media, 1 pistola).

---

### 4.2 Opciones adicionales (cotización aparte)

| Ítem | Cant. sugerida | Unitario referencial | Cuándo conviene |
|------|----------------|----------------------|-----------------|
| Segunda pistola lectora 2D | 1 | $120.000 – $220.000 | Dos personas inventariando en paralelo |
| Mini PC + monitor (puesto vendedor) | 1–4 | $350.000 – $500.000 c/u | Fase SD-2 — POS en mostrador |
| Impresora térmica 80 mm + cajón | 1 | $180.000 – $350.000 | Fase SD-2 — caja y tickets |
| Repetidor / access point Wi‑Fi | 1 | $40.000 – $120.000 | Si enrolamiento en tablet falla por señal |

---

### 4.3 Servicios LhexIA (software e infra — recordatorio)

El equipamiento anterior **complementa** el ERP ya en despliegue. La operación en la nube (referencia acordada con implementación):

| Concepto | Orden de magnitud mensual (CLP) |
|----------|----------------------------------|
| Hosting aplicación (Render Standard) | ~$24.000 |
| Base de datos (Neon Launch, horario operación) | ~$20.000 |
| **Referencia infra mensual** | **~$44.000 – $60.000** |

*Detalle técnico: `docs/planes/04-tecnico/PLAN_RENDIMIENTO_BD_SD1.md`. No incluye honorarios de implementación ni capacitación.*

---

## 5. Lo que no se compra en esta fase

- Software POS de terceros (Defontana, Bsale, etc.) — **no requerido**; LhexIA cubre enrolamiento y venta.  
- Impresora fiscal / cajón — fase caja (SD-2).  
- Cuatro equipos completos de vendedora — post inventario.  
- Lectores “solo Bluetooth con app propia” sin modo teclado — **no compatibles** con el flujo web actual.

---

## 6. Plan de implementación en piso (día D0)

| Paso | Responsable | Actividad |
|------|-------------|-----------|
| 1 | LhexIA / TI | Backup de base de datos antes de carga masiva |
| 2 | LhexIA | Verificar almacenes activos (3 sucursales) y permisos `enrolamiento_inventario` |
| 3 | Cliente + LhexIA | Configurar pistola en modo HID; prueba de escaneo en enrolamiento |
| 4 | Cliente | Conectar mini PC por cable de red; tablet en Wi‑Fi |
| 5 | Cliente | Iniciar sesión de toma por almacén según runbook |
| 6 | LhexIA | Soporte remoto primera jornada (recomendado) |

**Runbook operativo:** [`CLIENTE_SANTO_DOMINGO.md`](CLIENTE_SANTO_DOMINGO.md)

---

## 7. Criterios de aceptación del equipamiento

- [ ] Pistola lee códigos EAN del catálogo en enrolamiento (web).  
- [ ] Tablet accede a LhexIA sin cortes en zona de bodega/pasillo.  
- [ ] Mini PC permite altas manuales y correcciones sin reinicios.  
- [ ] Usuario con permiso de inventario puede abrir sesión y cerrar líneas.  

---

## 8. Próximos pasos

1. Cliente confirma **dotación base** u opciones (segunda pistola, UPS, etc.).  
2. Compra en proveedor local con **factura y garantía Chile**.  
3. Fecha de **D0 inventario** acordada con LhexIA.  
4. Tras cierre de inventario: planificar **SD-2** (puestos POS + caja + impresión).

---

## 9. Contacto y validez

| | |
|--|--|
| **Producto** | LhexIA ERP · www.lhexia.cl |
| **Descriptor** | ERP inteligente |
| **Slogan** | Haz rentable tu decisión. |
| **Elaborado por** | Mario Becerra Olea — LhexIA |
| **Validez de cotización hardware** | 30 días desde la fecha del documento |

---

*Documento interno/cliente — Ferretería Santo Domingo. Actualizar montos al recibir cotizaciones formales de distribuidor.*
