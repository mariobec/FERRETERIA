# VERTEX — ERP multi-sucursal (diseño producto)

**Ecosistema:** LhexIA VERTEX · **Versión diseño:** 1.0 · Mayo 2026  
**Estado:** Norte de producto — implementación por fases (no big-bang en SD-1 piso)

---

## 1. Norte en una frase

**LhexIA debe permitir crear y operar muchas sucursales bajo un mismo cliente (tenant)**, con stock, caja, POS y Guardián **por sucursal**, y vista **consolidada** para gerencia.

Eso es distinto del **cliente #1 hoy:**

| | Santo Domingo (SD-1) | Producto VERTEX |
|---|----------------------|-----------------|
| Sucursales en piso | **1 local** (sin sucursales físicas) | Capacidad de **N sucursales** |
| Inventario | Por **almacén** (tienda + bodega mismo predio) | Por almacén **ligado a una sucursal** |
| Cierre Fase 1 | Un ferreterón estable | Prueba de concepto |
| Siguiente demo comercial | — | **Chilemat** (red multi-local) |

---

## 2. Modelo de datos objetivo

```
Tenant (empresa cliente)
  └── Sucursal[]          ← Admin VERTEX: "Nueva sucursal"
        ├── Almacen[]     (tienda, bodega, depósito…)
        ├── Caja[]        (apertura/cierre por sucursal)
        ├── UsuarioSucursal[]  (vendedor/cajero acotado)
        └── KPIs / Guardián filtrados por sucursal_id
```

### Entidades mínimas (LX-1 / SD-2)

| Tabla / campo | Rol |
|---------------|-----|
| `tenant_id` | Empresa (SD, Chilemat, futuro cliente) |
| `sucursales` | Catálogo de locales: código, nombre, dirección, activo |
| `almacenes.id_sucursal` | Todo stock enrolamiento/kardex acotado |
| `caja.id_sucursal` | Arqueo y desfalco por tienda |
| `ventas.id_sucursal` | Reportes y ventas hoy por sucursal |
| `usuarios` + `usuario_sucursales` | Rol global (dueño) vs supervisor de una sucursal |

### Reglas de negocio

1. **Crear sucursal** — solo roles `admin` / `gestionar_usuarios` / permiso futuro `admin_sucursales`.
2. **Alta de almacenes** — al crear sucursal, wizard opcional: almacén Tienda + Bodega por defecto.
3. **POS** — vendedor trabaja en **su** sucursal (caja y stock de esa sucursal).
4. **Guardián dueño** — consolidado red = suma de sucursales del tenant.
5. **Guardián supervisor** — solo semáforos de **su** `sucursal_id`.
6. **Traslados** — entre almacenes de la **misma** sucursal sin fricción; entre sucursales = documento de traslado (fase posterior).

---

## 3. UI / módulos (roadmap)

| Módulo | Función multi-sucursal |
|--------|-------------------------|
| **Admin VERTEX** | CRUD sucursales, asignar usuarios, activar/desactivar |
| **POS** | Selector sucursal (o implícito por login); stock solo de esa sucursal |
| **Caja** | Una caja abierta **por sucursal** (SD-2) |
| **Inventario** | Enrolamiento filtrado por almacenes de la sucursal |
| **Control Center** | Tabla sucursales con semáforo caja/stock (ya prototipado) |
| **Guardián** | Mapa sucursales + consolidado (V3.1+) |

---

## 4. Estado en código hoy (mayo 2026)

| Capacidad | Estado |
|-----------|--------|
| Tabla `Sucursal` dedicada | ❌ No existe |
| `Almacen` sin `id_sucursal` | ✅ Solo almacenes globales |
| Heurística Guardián por texto usuario/caja | 🟡 Prototipo dueño vs supervisor |
| `OWNER_GUARDIAN_SUCURSALES_N=3` | 🟡 Demo **vista red** (Chilemat), no SD real |
| Control Center multi-tarjeta | 🟡 Datos reales parciales |
| Filtro obligatorio `sucursal_id` en queries prod | ❌ Post SD-1 |

**SD-1 no bloquea el diseño:** se puede sembrar **1 sucursal lógica** “Santo Domingo” y migrar después.

---

## 5. Plan de implementación (sin romper piso)

### Fase A — Semilla (post cierre SD-1, ~1 semana)

- Migración SQL: tabla `sucursales`, `id_sucursal` nullable en `almacenes`, `caja`, `ventas`.
- Seed SD: una fila `sucursal` “Santo Domingo” + enlazar almacenes existentes.
- Queries: si `id_sucursal` es NULL → tratar como sucursal default (compat).

### Fase B — Admin “Nueva sucursal” (~1 semana)

- Pantalla Admin → Sucursales: crear, editar, listar.
- Al crear: opción crear almacenes Tienda/Bodega.
- Tests smoke CRUD + permisos.

### Fase C — Operación multi-sucursal (~2–3 semanas, SD-2)

- Caja: una abierta por `sucursal_id`.
- POS: contexto sucursal en sesión.
- Guardián V3.1: filtro SQL real (fin heurísticas).
- Reportes ventas hoy por sucursal.

### Fase D — Chilemat piloto

- Tenant `Chilemat` o sucursales 2..N en mismo tenant SD según contrato.
- Demo comercial: dueño ve mapa 3+ semáforos reales.

---

## 6. Qué NO hacer en SD-1

- Obligar `sucursal_id` en cada query de producción antes del seed.
- Pedir a SD que abra “3 sucursales” que no existen en piso.
- Mezclar migración masiva con toma de inventario abierta.

---

## 7. Centro de Mandos Global (plataforma LhexIA)

Ver contrato píldora y evolución Master Core: [`VERTEX_MASTER_CORE.md`](VERTEX_MASTER_CORE.md).

| Pieza | Ruta / parámetro |
|-------|------------------|
| API maestro | `GET /api/v1/owner/dashboard?scope=global_maestro` |
| UI cascarón | `GET /owner/vertex-control` (permiso `gestionar_usuarios`) |
| Servicio | `services/vertex_control_center_service.py` |
| Píldoras | `services/vertex_pildora_contract.py` |

Cliente **live:** Santo Domingo. **Demo:** Sodimac/Easy con píldoras persistidas en `agente_ejecuciones` (`agente_nombre=vertex_hub`).

---

## 8. Referencias

- Biblia: [`LHEXIA_VERTEX_VISION.md`](LHEXIA_VERTEX_VISION.md)
- Cierre un local: [`../planes/01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md`](../planes/01-entrega-santo-domingo/SD1_CIERRE_FASE1_VERTEX.md)
- SD-2 eje: [`../planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md`](../planes/01-entrega-santo-domingo/SANTO_DOMINGO_ENTREGA.md) § SD-2
- Guardián V3.1: [`../planes/01-entrega-santo-domingo/GUARDIAN_V3_PROPUESTA.md`](../planes/01-entrega-santo-domingo/GUARDIAN_V3_PROPUESTA.md)

---

*LhexIA VERTEX — el ERP crece con cada sucursal nueva; SD-1 valida el primer local.*
