# Refactor `app.py` — Oleada 1 concreta (venta + caja)

**Estado:** planificado · **solo documentado por hacer** (no implementar hasta OK Mario + ventana DEV)  
**Transporte / respaldo PRD:** [`PLAN_TRANSPORTE_RESPALDO_PRD.md`](PLAN_TRANSPORTE_RESPALDO_PRD.md)  
**Contexto:** `app.py` ~**27.860** líneas (mayo 2026 era ~22,3k). **64** modelos SQLAlchemy en un solo archivo.  
**Regla SD-1:** no bloquear POS/caja/inventario mañana; oleadas pequeñas + smoke + checkpoint git.

---

## Objetivo de la oleada 1

Sacar del monolito el **paquete crítico POS → vale → cobro → caja**, manteniendo **100 % compatibilidad** con:

```python
import app as m
m.Venta.query...
m.Caja.query...
```

(sin cambiar ~200 archivos que importan `app`).

**Meta numérica:** bajar `app.py` en **~900–1.200 líneas** en un solo PR acotado.

---

## Alcance IN (esta oleada)

| Qué | Destino |
|-----|---------|
| `extensions.db` (instancia SQLAlchemy) | `extensions.py` |
| Modelos `Venta`, `DetalleVenta`, `VentaCuotaCredito`, `VentaAPedido`, `Caf` | `models/venta_caja.py` |
| Modelos `Caja`, `MovimientoCaja` | `models/venta_caja.py` |
| Constantes `PLANES_CUOTA_CREDITO_*` | `models/venta_caja.py` |
| Helpers de monto bruto (`_ticket_linea_subtotal_clp`, `_venta_bruto_desde_detalles_lineas`, `_monto_cobro_venta_bruto_sql`, `_venta_count_detalles`) | `services/venta_totales_service.py` |
| Re-export en `app.py` | `from models.venta_caja import ...` (mismos nombres en módulo `app`) |

## Alcance OUT (oleadas 2+)

- `Producto`, `Cliente`, `OrdenCompra`, `RecepcionCompra`, Chilemat, SEO, Academy, etc.
- Mover rutas HTTP de `app.py` a blueprints.
- Multi-tenant.
- Cambiar firmas de `core/` use cases.

---

## Pre-requisitos (día 0, ~30 min)

1. **Checkpoint git** (flujo crítico):
   ```bash
   git tag checkpoint/pre-oleada1-venta-caja-$(date +%Y%m%d)
   ```
2. Rama dedicada: `refactor/oleada1-venta-caja`
3. Baseline tests:
   ```bash
   pytest tests/test_routes_criticas.py -k "venta or caja or pos or cobro" -q --tb=no
   pytest tests/test_end_to_end.py -m smoke -q --tb=no
   pytest tests/test_portal_ejecutivo_api.py tests/test_caja_vale_sla.py -q
   ```

---

## Pasos de implementación (orden estricto)

### Paso 1 — `extensions.py`

```python
# extensions.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```

En `app.py`:

- Reemplazar `db = SQLAlchemy(app)` por `from extensions import db` + `db.init_app(app)` **después** de crear `app = Flask(...)`.

**Riesgo:** bajo. **Verificación:** `python -c "import app; print(app.db)"` y smoke healthz.

### Paso 2 — `services/venta_totales_service.py`

Mover desde `app.py` (aprox. líneas 720–780):

- `_ticket_linea_subtotal_clp`
- `_venta_bruto_desde_detalles_lineas`
- `_venta_count_detalles`
- `_monto_cobro_venta_bruto_sql`

Importan `DetalleVenta` desde `models.venta_caja` (import tardío dentro de funciones si hace falta evitar ciclo en el paso 2; o hacer paso 3 antes y ajustar).

En `Venta.recalcular_total` / `desglosar_iva`: llamar al servicio en lugar de funciones privadas de `app.py`.

En `app.py` dejar **alias** por compatibilidad interna:

```python
from services.venta_totales_service import (
    venta_bruto_desde_detalles_lineas as _venta_bruto_desde_detalles_lineas,
    monto_cobro_venta_bruto_sql as _monto_cobro_venta_bruto_sql,
)
```

### Paso 3 — `models/venta_caja.py`

- `from extensions import db`
- Clases en orden de dependencia: `Caf` → `Venta` → `DetalleVenta` → `VentaCuotaCredito` → `VentaAPedido` → `Caja` → `MovimientoCaja`
- Métodos de instancia en `Venta` importan `venta_totales_service` (no `app`).

`models/__init__.py`: re-export del paquete.

### Paso 4 — Cableado en `app.py`

- Borrar definiciones duplicadas de clases/helpers movidos.
- Añadir al final de imports de modelos (o bloque dedicado):

```python
from models.venta_caja import (
    Caf, Venta, DetalleVenta, VentaCuotaCredito, VentaAPedido,
    Caja, MovimientoCaja,
    PLANES_CUOTA_CREDITO_DIAS, PLANES_CUOTA_CREDITO_OPCIONES,
)
```

- `schema_sync.py` / `init_db.py`: si importan modelos, asegurar `import models.venta_caja` antes de `create_all` (mismo patrón que hoy con `app`).

### Paso 5 — Blueprints / services

Solo si fallan imports circulares:

- `blueprints/_app_ref.app_module()` sigue válido.
- Servicios que hacen `from app import Venta` **no se tocan** en oleada 1.

### Paso 6 — Documentación

- Actualizar `memory.md`: «Oleada 1 venta+caja en `models/venta_caja.py`».
- Línea en `PLAN_PENDIENTES_DESARROLLO.md` con enlace a este archivo.

---

## Criterios de aceptación (sign-off)

| # | Criterio |
|---|----------|
| 1 | `app.Venta`, `app.Caja`, `app.DetalleVenta` existen y son las mismas tablas ORM |
| 2 | `pytest tests/test_routes_criticas.py -k venta -q` verde |
| 3 | `pytest tests/test_end_to_end.py -m smoke -q` verde |
| 4 | `pytest tests/test_caja_vale_sla.py tests/test_pos_*` (smoke POS/caja) verde |
| 5 | Prueba manual DEV: emitir vale TEST → cobrar efectivo → cierre caja visible/ciego según config |
| 6 | `app.py` bajó ≥ 800 líneas vs rama base |
| 7 | Tag `checkpoint/post-oleada1-venta-caja-YYYYMMDD` tras OK QAS |

---

## Rollback

```bash
git checkout checkpoint/pre-oleada1-venta-caja-YYYYMMDD
# o revert del merge commit en main
```

No transportar a PRD sin sign-off QAS (OT).

---

## Oleada 2 (siguiente, no mezclar en PR 1)

**Paquete catálogo + inventario:** `Producto`, `Almacen`, `StockPorAlmacen`, `MovimientoInventario`, códigos escaneo, `ProductoCodigoProveedor` → `models/catalogo_inventario.py`  
**Estimado:** ~1.500 líneas menos en `app.py`.

## Oleada 3

**Compras + cliente + crédito:** `Cliente`, `Proveedor`, `OrdenCompra`, `RecepcionCompra`, `AbonoCredito` → `models/compras_cliente.py`.

## Oleada 4

**Rutas gerencia/SEO/Chilemat** → blueprints (sin mover más modelos).

---

## Estimación

| Fase | Tiempo |
|------|--------|
| Implementación + arreglo imports | 4–6 h |
| Tests + prueba manual POS/caja | 2 h |
| QAS piso | 1 sesión |

**Total:** ~1 día DEV + ½ día QAS.

---

## Decisión para Mario (cuando se retome)

- [ ] Aprobar oleada 1 tal cual (venta + caja + extensions + venta_totales_service)
- [ ] O variante chica: solo `extensions.py` + `Almacen`/`StockPorAlmacen`
- [ ] Ejecutar en rama `refactor/oleada1-venta-caja` + checklist en `PLAN_TRANSPORTE_RESPALDO_PRD.md`
