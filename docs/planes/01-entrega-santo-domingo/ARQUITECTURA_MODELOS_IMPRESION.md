# LhexIA ERP — Modelos de arquitectura (para impresión)

**Cliente:** Ferretería Santo Domingo · **Producto:** LhexIA (www.lhexia.cl)  
**Fecha referencia:** mayo 2026 · **Estado prod:** nube (Render + Neon)

Documento pensado para **imprimir en A4** (márgenes normales, fuente 10–11 pt).  
Diagramas en texto (ASCII) para que se vean igual en PDF o papel.

---

## 1. Modelo ACTUAL — Operación en la nube (como está hoy)

### 1.1 Vista general

```
┌─ SUCURSAL (Wi‑Fi o cable) ───────────────────────────────────────────────┐
│                                                                          │
│   PC VENDEDORA ──────┐                                                   │
│   (Chrome / Edge)    │                                                   │
│                      │         HTTPS  *** INTERNET OBLIGATORIO ***       │
│   PC CAJA ───────────┼────────────────────────────────────────────┐      │
│                      │                                            │      │
│   TV CLIENTE ────────┘                                            ▼      │
│   (segundo monitor)              https://www.lhexia.cl                   │
│                                  · /punto_venta        → POS vendedor    │
│                                  · /caja/...           → cobro / cierre  │
│                                  · /pos/experience-wall → TV (token)     │
│                                  · /api/pos/live-wall/snapshot           │
│                                                                          │
│   SIN INTERNET EN LA TIENDA → NO HAY POS NI TV (no hay servidor local)   │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Internet
                                      ▼
┌─ NUBE ───────────────────────────────────────────────────────────────────┐
│                                                                          │
│    ┌──────────────────────┐              ┌──────────────────────────┐  │
│    │  RENDER.COM          │   SQL        │  NEON.TECH               │  │
│    │  Servicio web        │◄────────────►│  PostgreSQL              │  │
│    │  erp-ferreteria-demo │              │  (ventas, stock, etc.)   │  │
│    │                      │              └──────────────────────────┘  │
│    │  Gunicorn + Flask    │                         ▲                    │
│    │  app.py              │                         │                    │
│    │  preDeploy: init_db  │                         │ pg_dump nocturno   │
│    └──────────▲───────────┘                         │ (PC oficina)       │
│               │                                     │                    │
│               │  git push → auto-deploy             │                    │
└───────────────┼─────────────────────────────────────┼────────────────────┘
                │                                     │
                ▼                                     ▼
     ┌────────────────────┐              ┌─────────────────────────┐
     │  GITHUB            │              │  PC DESARROLLO / OFICINA │
     │  mariobec/FERRETERIA│              │  · Respaldos .dump Neon  │
     │  rama main         │              │  · python app.py (QA)    │
     └────────────────────┘              │  · pytest (BD local)     │
                                         └─────────────────────────┘
```

### 1.2 Flujo de una venta (resumen)

```
  VENDEDORA                    INTERNET              RENDER              NEON
      │                           │                    │                  │
      │── login /punto_venta ────►│───────────────────►│── leer stock ───►│
      │◄── pantalla POS ──────────│◄───────────────────│◄─────────────────│
      │── agregar productos ─────►│───────────────────►│── vale Abierta ─►│
      │── finalizar_venta ───────►│───────────────────►│── Pendiente ─────►│
      │                           │                    │                  │
  TV CLIENTE                      │                    │                  │
      │── snapshot (cada ~1,5 s) ─►│───────────────────►│── recomendaciones│
      │◄── carrito + sugerencias ──│◄───────────────────│◄─────────────────│
      │                           │                    │                  │
  CAJERA                          │                    │                  │
      │── cobrar vale ────────────►│───────────────────►│── Pagado + caja ─►│
```

### 1.3 Qué está dónde (tabla)

| Componente | Ubicación hoy |
|------------|----------------|
| Aplicación ERP (Python/Flask) | Render |
| Base de datos | Neon (una BD producción) |
| URL tienda | www.lhexia.cl |
| POS, caja, inventario web | Navegador → internet → Render |
| TV pantalla cliente | Navegador → internet → API snapshot |
| Servidor 192.168.x.x en ferretería | **No** (solo pruebas dev opcionales) |
| Vender sin internet | **No** |
| Despliegue de cambios | git push a `main` → Render despliega |
| Respaldo datos | Consola Neon + pg_dump a PC (recomendado) |

### 1.4 Desarrollo vs producción

```
  DESARROLLO (PC Mario)                    PRODUCCIÓN (tienda)
  ─────────────────────                    ───────────────────
  http://127.0.0.1:5000                    https://www.lhexia.cl
  Postgres LOCAL (.env.local)              Neon (nube)
  No afecta clientes si no usa Neon prod   Todas las sucursales → misma BD
```

---

## 2. Modelo FUTURO — Intranet en sucursal (referencia SD-2)

*No está desplegado en operación hoy. Piloto posible post SD-1.*

### 2.1 Vista general

```
┌─ SUCURSAL (red Wi‑Fi / cable) ─────────────────────────────────────────┐
│                                                                          │
│   PC VENDEDORA ──────┐                                                   │
│   PC CAJA ───────────┼────►  http://192.168.1.50:5000  (SERVIDOR LAN)  │
│   TV CLIENTE ────────┘              │                                    │
│                                     ▼                                    │
│                         ┌───────────────────────────┐                  │
│                         │  MINI PC / NAS (servidor)  │                  │
│                         │  · Python (app.py/Gunicorn)│                  │
│                         │  · PostgreSQL (datos día)  │                  │
│                         └───────────────────────────┘                  │
│                                                                          │
│   VENDER NO REQUIERE INTERNET (solo red local)                           │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Internet OPCIONAL
                                      ▼
                         www.lhexia.cl + Neon
                         (copia nube / respaldo / acceso gerencia remota)
```

### 2.2 Comparación rápida

| | Nube (hoy) | Intranet (futuro) |
|--|------------|-------------------|
| Internet para vender | Obligatorio | No (solo LAN) |
| Servidor en tienda | No | Sí (IP fija) |
| Datos del día | Neon | Postgres local |
| lhexia.cl | Operación | Respaldo / remoto |
| Cortes ISP | Para operación | Solo backup/sync |

---

## 3. Contingencia sin internet (hoy)

```
  1. Plan operativo: vale en PAPEL + anotar cobro
  2. Cuando vuelve internet: cargar en www.lhexia.cl
  3. Medidas: internet de respaldo (4G/router), cable Ethernet
  4. A futuro: intranet (sección 2) o sync nocturno LAN ↔ Neon
```

---

## 4. Accesos directos y roles (nube actual)

| Rol | Entrada típica | Permiso clave |
|-----|----------------|---------------|
| Vendedora | /punto_venta | pos_emitir_vale |
| Cajera | /caja/vales_pendientes | caja_cobrar_vale, caja_cerrar |
| TV cliente | /pos/experience-wall?token=... | Token firmado (sin login) |
| Admin / gerencia | /inicio, módulos | Según RBAC |

*Bloqueo “solo POS” en PC vendedora: usuario Windows limitado + Chrome kiosk (operación TI), no instalador LhexIA aún.*

---

## 5. Referencias en el repo

| Documento | Contenido |
|---------|-----------|
| docs/MIGRACION_RENDER_NEON.md | Render, Neon, variables |
| docs/ERP_MAESTRO.md §4.14 | Live Wall / TV |
| docs/RESPALDO_PROYECTO.md | pg_dump y ZIP proyecto |
| docs/memory.md | Memoria viva y deploy reciente |

---

*Impresión sugerida: este archivo completo (3–5 páginas) o solo secciones 1 y 3 para operación actual.*
