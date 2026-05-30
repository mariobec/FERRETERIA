# DOCUMENTACION_AUDITORIA.md

**Proyecto:** LhexIA ERP — Ferretería Santo Domingo (SD-1)  
**Repositorio:** `sistema_ventas_limpio`  
**Stack:** Flask monolítico + PostgreSQL + Jinja2 + JS vanilla + blueprints  
**Commit referencia:** `ec2cf5d` (main, mayo 2026)  
**Audiencia:** auditoría externa (Claude u otro LLM) — contexto completo en un solo documento.

---

## 1. Resumen ejecutivo

ERP vertical ferretería (~26k líneas en `app.py` + blueprints/services). Un solo tenant hoy (Santo Domingo). Tres ambientes acordados:

| Ambiente LhexIA | Rol SAP | BD / deploy |
|-----------------|---------|-------------|
| **DESARROLLO** | DEV | Postgres `localhost` |
| **SAMBOX** | QAS | Postgres local en PC tienda |
| **PRODUCTIVO** | PRD | Render + Neon (www.lhexia.cl) |

**Flujo TMS:** DEV → release/OT → QAS (validación) → import → PRD (operación diaria).

---

## 2. Árbol del proyecto (principales)

```
sistema_ventas_limpio/
├── app.py                    # Monolito Flask: modelos SQLAlchemy, rutas legacy, registro blueprints
├── run.py                    # Entrypoint desarrollo
├── requirements.txt
├── pytest.ini
├── .env.local                # DATABASE_URL local (no commitear)
├── arrancar_erp.bat          # Arranque Windows tienda/dev
│
├── blueprints/               # Módulos Flask desacoplados
│   ├── pos.py                # Punto de venta (parcial)
│   ├── caja.py               # Caja, vales pendientes
│   ├── bodega.py             # Plataforma bodega
│   ├── tienda_publica.py     # Vitrina web + Liz + carrito
│   ├── chilemat_catalogo.py
│   ├── ecommerce.py
│   └── owner_api.py          # Guardián móvil
│
├── services/                 # Lógica de negocio (~40 módulos)
│   ├── venta_service.py      # transaccion_critica(), savepoints
│   ├── stock_service.py      # Stock tienda/bodega
│   ├── pos_busqueda_service.py # Semáforo POS, enriquecimiento búsqueda
│   ├── pos_tv_vitrina_service.py  # Carrusel TV carrito vacío
│   ├── vitrina_tienda_service.py  # Liz, catálogo web, carrito
│   ├── producto_relacion_service.py
│   ├── chilemat_cargas_service.py
│   ├── chilemat_ficha_service.py
│   └── ollama_client.py        # Liz / Ollama remoto
│
├── templates/                # Jinja2 (~150 HTML)
│   ├── punto_venta.html
│   ├── pos_live_wall_cliente.html   # TV Experience Wall
│   ├── tienda/ferreteria_santo_domingo.html
│   └── pos/includes/         # Fragmentos carrito POS
│
├── static/
│   ├── css/                  # design-system.css, pos-experience-wall-cfm.css
│   └── js/                   # pos.js, pos-experience-wall.js, pos-tv-vitrina-carousel.js
│
├── scripts/                  # CLI migración, maestro, piloto, sync Neon
│   ├── chilemat_cargas_local.py
│   ├── sync_local_neon_render.py
│   ├── maestra_cargar_erp_chilemat_sd.py
│   └── seed_demo_data.py
│
├── tests/                    # ~200 tests pytest
│   ├── conftest.py
│   ├── test_routes_criticas.py
│   └── test_end_to_end.py
│
├── sql/                      # Migraciones SQL manuales
├── docs/                     # ERP_MAESTRO, planes VERTEX, arquitectura
├── respaldos/                # Dumps, OT transporte, maestra (gitignored parcial)
└── .venv/                    # Entorno virtual Python (no transportar entre sistemas)
```

**Nota:** `app.py` concentra modelos ORM y muchas rutas históricas; blueprints registrados al final de `app.py` (~L25090).

---

## 3. Base de datos PostgreSQL

### 3.1 Conexión

- Variable: `DATABASE_URL` (SQLAlchemy via Flask-SQLAlchemy).
- Local típico: `postgresql://...@localhost:5432/ferreteria_local`
- Producción (PRD): Neon (`*.neon.tech`) — Render usa la misma URL.
- Tests bloquean Neon salvo `ALLOW_TESTS_ON_REMOTE=1` (`tests/conftest.py`).

### 3.2 Tabla `productos` (maestro ERP)

Modelo: `Producto` en `app.py` (`__tablename__ = 'productos'`).

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | INTEGER PK | Identificador interno |
| `nombre` | VARCHAR(100) | Descripción comercial |
| `codigo_barra` | VARCHAR(50) UNIQUE | EAN / código escaneo |
| `codigo_chilemat` | VARCHAR(80) | Referencia red Chilemat |
| `codigo_interno` | VARCHAR(32) | SKU interno SD |
| `imagen_url` | VARCHAR(500) | Foto ERP o enriquecida Chilemat |
| `precio_compra` | FLOAT | Costo último / maestro |
| `precio_venta` | FLOAT | Precio lista POS |
| `precio_mayoreo` | FLOAT | Mayoreo |
| `unidad`, `unidad_compra`, `unidad_venta` | VARCHAR | UM |
| `factor_conversion` | FLOAT | Compra → venta |
| `stock` | INTEGER | Total agregado (legacy + sync almacenes) |
| `categoria`, `subcategoria` | VARCHAR(50) | Taxonomía |
| `subcategoria_catalogo_id` | FK | → `catalogo_subcategorias` |
| `ubicacion_pasillo/estante/nivel` | VARCHAR | Ubicación física |
| `activo` | BOOLEAN | Soft delete catálogo |
| `pos_descuento_preautorizado(_pct)` | BOOL/FLOAT | Descuento POS sin supervisor |
| `fase_obra` | VARCHAR(32) | Taxonomía obra (C360) |

**Stock dual:** `productos.stock` + tabla `stock_por_almacen` (tienda/bodega) — ver `stock_service.py`.

**Volumen referencia (post-maestro SD, mayo 2026):** ~9.000–9.200 productos activos en SAMBOX/DEV.

### 3.3 Tabla `producto_relacion` (cross-sell)

Modelo: `ProductoRelacion` en `app.py`.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | INTEGER PK | |
| `producto_id` | FK → productos | Producto **ancla** (en carrito / vitrina) |
| `relacionado_id` | FK → productos | Producto **sugerido** |
| `tipo` | VARCHAR(32) | Default `complemento` |
| `fuente` | VARCHAR(32) | `chilemat_vtex`, `historico_sd`, `manual`, etc. |
| `peso` | FLOAT | Ranking (mayor = más prioritario) |
| `activo` | BOOLEAN | Filtro consultas |
| `fecha_sync` | TIMESTAMP | Última sync |

**Constraint:** `UNIQUE (producto_id, relacionado_id, tipo, fuente)`

**Índice parcial:** `ix_producto_relacion_ancla ON producto_relacion (producto_id) WHERE activo IS TRUE`

**Uso:**
- POS / TV recomendaciones: `services/producto_relacion_service.py` → `sugerencias_para_carrito()`
- Vitrina TV escenas Chilemat: `services/pos_tv_vitrina_service.py`
- Live wall snapshot: `_pos_live_wall_recomendaciones_tv()` en `app.py`

### 3.4 Tabla `chilemat_vtex_producto` (staging web)

| Columna | Descripción |
|---------|-------------|
| `vtex_product_id` | PK VTEX |
| `product_reference` | Ref. web Chilemat |
| `producto_id` | FK opcional → ERP |
| `nombre`, `link`, `categoria_path`, `brand` | Catálogo web |
| `precio_lista`, `ean`, `imagen_url` | Ficha comercial |
| `descripcion_web`, `descripcion_corta` | Texto SEO |
| `synced_at` | Última sync API |

Puente ERP ↔ Chilemat: `services/chilemat_ficha_service.py` → `fichas_resumen_carrito_por_productos()`.

### 3.5 Otras tablas críticas (referencia)

| Tabla | Rol |
|-------|-----|
| `ventas`, `detalle_ventas` | POS, vales, TV live wall |
| `stock_por_almacen`, `movimiento_inventario` | Kardex, inventario |
| `cajas`, `movimiento_caja` | Caja registradora |
| `clientes`, `abonos_credito` | Crédito ferretería |
| `ordenes_compra`, `recepciones_compra` | Compras |
| `erp_audit_log` | Auditoría |
| `usuarios`, `roles`, `permisos` | RBAC Flask-Login |

Esquema completo legacy: `bdferreteria.sql`, migraciones en `sql/`.

---

## 4. Endpoints clave

### 4.1 Chat Liz (asistente vitrina)

**Nota para auditor:** el endpoint HTTP **no está definido inline en `app.py`**; se registra vía blueprint.

**Registro** (`app.py` ~L25090):

```python
from blueprints.tienda_publica import register_tienda_publica_routes
register_tienda_publica_routes(app)
```

**Ruta:** `POST /api/tienda/<slug>/asistente`  
**Slug producción:** `ferreteria-santo-domingo`  
**Handler:** `blueprints/tienda_publica.py` → `tienda_asistente()`

```python
def tienda_asistente(slug: str):
    if not vt.tienda_habilitada() or slug != vt.TIENDA_SLUG_SD:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    mensaje = (data.get('mensaje') or '').strip()
    producto_id = data.get('producto_id')
    try:
        pid = int(producto_id) if producto_id is not None else None
    except (TypeError, ValueError):
        pid = None
    carrito = data.get('carrito') or data.get('carrito_lineas')
    if not isinstance(carrito, list):
        carrito = None
    try:
        out = vt.respuesta_asistente(
            slug=slug,
            mensaje=mensaje,
            producto_id=pid,
            carrito_lineas=carrito,
            cliente_nombre=(data.get('cliente_nombre') or '').strip(),
            cliente_telefono=(data.get('cliente_telefono') or '').strip(),
        )
        out['ia_local_disponible'] = vt.ollama_vitrina_disponible()
        return jsonify({'ok': True, **out})
    except Exception as ex:
        logging.getLogger(__name__).exception('tienda_asistente: %s', ex)
        return jsonify({'ok': False, 'error': 'asistente_error', 'mensaje': str(ex)[:200]}), 500
```

**Motor de respuesta:** `services/vitrina_tienda_service.py` → `respuesta_asistente()`:

```python
def respuesta_asistente(
    *,
    slug: str,
    mensaje: str,
    producto_id: int | None = None,
    carrito_lineas: list[dict[str, Any]] | None = None,
    cliente_nombre: str = '',
    cliente_telefono: str = '',
) -> dict[str, Any]:
    """Liz — asistente de ventas vitrina (reglas ERP+Chilemat + Ollama opcional)."""
    # 1) Normaliza carrito y totales
    # 2) Intención cierre → vale PED-WEB-###### si pedido_web_habilitado()
    # 3) Contexto producto_id → stock, sugeridos, ficha
    # 4) Búsqueda catálogo ERP/Chilemat por texto
    # 5) Fallback Ollama (VITRINA_OLLAMA_* env) si reglas no resuelven
    # Retorna: { reply, cards[], ui{}, carrito_totales, vale_pedido?, ... }
```

**Frontend:** `templates/tienda/includes/liz_asistente.html` + `static/js/tienda-vitrina.js`.

**Variables entorno Liz/Ollama:** ver `VITRINA_OLLAMA_PRODUCCION.md`.

### 4.2 POS — búsqueda productos (con miniatura)

`GET /buscar_producto?q=...&origen=pos&enriquecido=1`

Implementación: `_buscar_productos_json()` en `app.py` → enriquece con `imagen_url` vía `fichas_resumen_carrito_por_productos()`.

### 4.3 TV Experience Wall

| Ruta | Rol |
|------|-----|
| `GET /pos/experience-wall?token=...` | Pantalla cliente TV |
| `GET /api/pos/live-wall/snapshot?token=...` | Poll JSON carrito / vitrina / recomendaciones |

Servicios: `pos_tv_vitrina_service.py`, JS: `pos-experience-wall.js`, `pos-tv-vitrina-carousel.js`.

### 4.4 Chilemat cargas (ERP UI)

`GET/POST /compras/chilemat/cargas` — pantalla ERP; lógica en `services/chilemat_cargas_service.py`.

---

## 5. Script `scripts/chilemat_cargas_local.py` (completo)

CLI para operaciones masivas/selectivas Chilemat → ERP (DEV/SAMBOX).

```python
#!/usr/bin/env python3
"""
Kit local Chilemat: borrado/carga masiva o selectiva.

Ver también pantalla ERP: Compras → Cargas Chilemat (/compras/chilemat/cargas)

Ejemplos:
  python scripts/chilemat_cargas_local.py --accion sync_staging
  python scripts/chilemat_cargas_local.py --accion reset_total --forzar
  python scripts/chilemat_cargas_local.py --accion borrar_productos --forzar --rubro "Pinturas"
  python scripts/chilemat_cargas_local.py --accion cargar_productos --rubro "Pinturas"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app import app
    from services import chilemat_cargas_service as svc

    ap = argparse.ArgumentParser(description='Cargas Chilemat local: masivo/selectivo')
    ap.add_argument('--accion', required=True, choices=list(svc.ACCIONES))
    ap.add_argument('--sin-sync', action='store_true', help='No llamar API Chilemat; usar staging actual')
    ap.add_argument('--solo-faltantes', action='store_true', help='Solo aplica para sync_staging')
    ap.add_argument('--max-productos', type=int, default=0, help='Solo aplica para sync_staging')
    ap.add_argument('--rubro', default='', help='Filtro por nombre rubro (categoria_path)')
    ap.add_argument('--rubro-vtex-id', type=int, default=0, help='Filtro por vtex_id de categoría')
    ap.add_argument('--q', default='', help='Filtro por nombre/ref/ean/vtex_id')
    ap.add_argument('--limit', type=int, default=0, help='Top N del set filtrado')
    ap.add_argument('--preview', action='store_true', help='No escribe; solo muestra conteos')
    ap.add_argument('--masivo', action='store_true', help='Para borrar_productos: TRUNCATE productos CASCADE')
    ap.add_argument('--forzar', action='store_true', help='Confirmación explícita para acciones destructivas')
    args = ap.parse_args()

    confirmacion = 'RESET TOTAL' if args.accion == 'reset_total' and args.forzar else ''

    with app.app_context():
        if args.accion in ('reset_total', 'reset_taxonomia') and not args.forzar:
            raise RuntimeError(f'{args.accion} requiere --forzar.')

        out = svc.ejecutar(
            accion=args.accion,
            sin_sync=bool(args.sin_sync),
            solo_faltantes_sync=bool(args.solo_faltantes),
            rubro=args.rubro,
            rubro_vtex_id=(args.rubro_vtex_id or None),
            q=args.q,
            limit=(args.limit if args.limit > 0 else None) or (
                args.max_productos if args.max_productos > 0 and args.accion == 'sync_staging' else None
            ),
            masivo=bool(args.masivo),
            forzar=bool(args.forzar),
            preview=bool(args.preview),
            confirmacion=confirmacion,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0 if out.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
```

**Acciones (`chilemat_cargas_service.ACCIONES`):**

| Acción | Efecto |
|--------|--------|
| `sync_staging` | API Chilemat → `chilemat_vtex_producto` |
| `reset_total` | Borra ERP + recarga desde staging (--forzar) |
| `reset_taxonomia` | Categorías/subcategorías ERP |
| `borrar_productos` | Masivo TRUNCATE o selectivo por rubro |
| `cargar_productos` | Staging → `productos` ERP |

**Maestro SD (pipeline separado):** `scripts/maestra_cargar_erp_chilemat_sd.py`, `maestra_activar_cm_compras.py`, `maestra_completar_catalogo_sd.py`.

---

## 6. Flujo de datos: local ↔ Neon (nube)

### 6.1 Paisaje (no confundir roles)

```
DESARROLLO (DEV)     ──OT/export──►  SAMBOX (QAS)     ──OK/sign-off──►  PRODUCTIVO (PRD)
Postgres localhost       dump/git         Postgres local PC tienda          Neon + Render
```

- **Operación diaria ferretería** = PRD (Neon).
- **SAMBOX** = espejo para validar antes de importar a PRD (no reemplaza prod en horario pico).
- **DEV** = construcción y pruebas.

### 6.2 Sincronización DEV/SAMBOX → Neon

Script: `scripts/sync_local_neon_render.py`

1. Lee `DATABASE_URL` (origen local) y `NEON_DATABASE_URL` (destino).
2. Aplica migraciones SQL en ambos.
3. `TRUNCATE` tablas comunes en Neon y copia filas desde local.
4. Verifica conteos (`productos`, `ventas`, `clientes`, etc.).

```bash
python scripts/sync_local_neon_render.py
python scripts/sync_local_neon_render.py --verify-only
```

**Cuidado:** pisa datos en Neon. Backup previo: `scripts/backup_neon_dump.py`.

### 6.3 Render (aplicación)

- `render.yaml` — deploy Flask.
- `DATABASE_URL` en Render apunta a Neon → misma BD que sync.
- Código: `git push` tras tag/OT validada en QAS.

### 6.4 Chilemat (datos externos)

```
API VTEX Chilemat  →  sync_staging  →  chilemat_vtex_producto
                                    →  cargar_productos  →  productos (ERP)
                                    →  vinculación  →  producto_id
Relaciones web/ histórico  →  producto_relacion  →  TV / POS / Liz
```

No hay sync bidireccional automático ERP → Neon en tiempo real; es **batch** vía scripts/OT.

---

## 7. Módulos críticos SD-1 (estado mayo 2026)

| Módulo | Archivos | Estado |
|--------|----------|--------|
| POS + caja | `app.py`, `blueprints/caja.py`, `static/js/pos.js` | Estable piloto |
| Búsqueda + semáforo | `pos_busqueda_service.py`, `design-system.css` | + miniaturas |
| TV Experience Wall | `pos_live_wall_cliente.html`, vitrina carousel | Estable |
| Vitrina web + Liz | `tienda_publica.py`, `vitrina_tienda_service.py` | Piloto |
| Maestro productos | scripts `maestra_*`, ~9k SKUs | Cargado SAMBOX |
| Tests | 200 tests, smoke CI | `.github/workflows/tests.yml` |

---

## 8. Anexo — Propuesta «Fábrica de Color LhexIA» (150% vs Sodimac)

Referencia: [Sodimac Fábrica de Color](https://www.sodimac.cl/sodimac-cl/content/fabrica-de-color) — wizard 4 pasos: ambiente → color/brillo → cantidad → calidad.

### 8.1 Mejoras propuestas (+150%)

| Sodimac | LhexIA (propuesta) |
|---------|-------------------|
| Wizard genérico nacional | Contexto **Santo Domingo + Chilemat** con stock real tienda |
| Paleta marca Kölor/Topex | Paleta desde **productos ERP** rubro Pinturas + códigos cartilla |
| Visualizador estático | Overlay color + **Liz** explica brillo (mate/satinado) en chat |
| Sin cierre venta | Paso 4 → **vale POS / WhatsApp / QR mostrador** |
| Sin cross-sell | `producto_relacion`: rodillo, thinner, cinta según ambiente |
| Solo web | Misma UX en **vitrina web** + **kiosk TV** opcional |

### 8.2 Arquitectura (módulo aislado — mayo 2026)

**No es parte del catálogo vitrina.** El cliente accede solo si caja/POS lo habilita, o en lab con flag preview.

```
/services/fabrica_color_service.py          # wizard: paleta, m², SKUs pintura ERP
/services/modulo_pinturas_session_service.py # tokens firmados + preview lab
/blueprints/modulo_pinturas.py              # rutas módulo cliente
/templates/modulos/fabrica_color.html
/templates/modulos/pinturas_lab.html
/static/js/fabrica-color.js
/static/css/fabrica-color.css
```

| Ruta | Quién | Cuándo |
|------|-------|--------|
| `GET /modulos/pinturas/lab` | Dev/QA | `VITRINA_FABRICA_COLOR_PREVIEW=1` |
| `GET /modulos/pinturas/lab/iniciar` | Dev/QA | Wizard en lab |
| `GET /modulos/pinturas/<token>` | Cliente TV/tablet | Token emitido por caja |
| `POST /api/modulos/pinturas/<token>/cotizar` | Wizard | Misma sesión |
| `POST /api/caja/modulo-pinturas/habilitar` | Cajero/vendedor | Caja vales pendientes |

**Flujo piso:** cajero → «Habilitar para cliente» → abre URL en TV → wizard → carrito/WhatsApp/vale.

**Legacy 404:** `/tienda/<slug>/fabrica-de-color` (ya no publicado en vitrina).

**Datos:** tabla futura opcional `pintura_color_cartilla`; mientras tanto filtrar `productos` rubro Pinturas.

**Integración Liz:** botón «Preguntar a Liz» con contexto `{ ambiente, color, brillo, m² }`.

### 8.3 Fuera de alcance SD-1 inmediato

- Integración máquina tintométrica (API fabricante).
- Multi-tenant / multi-sucursal en queries prod.

---

## 9. Checklist auditoría rápida

- [ ] `pytest tests/ -m smoke -q` en DEV (no Neon prod sin flag).
- [ ] Conteo `SELECT COUNT(*) FROM productos WHERE activo IS NOT FALSE`.
- [ ] Conteo `SELECT COUNT(*) FROM producto_relacion WHERE activo`.
- [ ] `GET /healthz` → 200.
- [ ] POS: `/buscar_producto?q=TEST&enriquecido=1` (fixtures QA).
- [ ] TV: `/pos/experience-wall?token=...` snapshot JSON.
- [ ] Liz: `POST /api/tienda/ferreteria-santo-domingo/asistente` body `{"mensaje":"pintura"}`.

---

## 10. Referencias internas

| Documento | Ruta |
|-----------|------|
| Biblia ERP | `docs/ERP_MAESTRO.md` |
| VERTEX / SD-1 | `docs/planes/01-entrega-santo-domingo/` |
| Entornos DEV/QAS/PRD | `.cursor/rules/entornos-desarrollo-sambox-productivo.mdc` |
| Chilemat cargas | `CHILEMAT_CARGAS_LOCAL.md` |
| Ollama Liz prod | `VITRINA_OLLAMA_PRODUCCION.md` |

---

*Generado para auditoría externa — LhexIA ERP Santo Domingo. Actualizar commit hash al exportar nueva versión.*
