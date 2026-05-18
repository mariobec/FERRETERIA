# LhexIA ERP — Arquitectura (estado y objetivo)

## Hoy (producción)

```
                    ┌─────────────────┐
                    │  Render (web)   │
                    │  gunicorn app   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     app.py      │
                    │  modelos + HTTP │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    blueprints/        services/          core/
    pos,caja,bodega    stock,kardex      venta,cobro
           │                 │                 │
           └─────────────────┼─────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  PostgreSQL     │
                    │  (Neon)         │
                    └─────────────────┘
```

- **Un tenant implícito:** Ferretería Santo Domingo (una BD, una instancia).
- **Config empresa:** JSON local / ruta configurable (`obtener_config_empresa()`).
- **Auth:** Flask-Login + RBAC (`Rol`, `Permiso`, `permisos_required`).

## Módulos listos para go-live (inventario + POS)

| Módulo | Rutas principales | Servicios |
|--------|-------------------|-----------|
| POS vendedor | `/punto_venta`, `/api/pos/*` | `pos_busqueda_service`, `pos.js` |
| Caja | `/caja/*`, `procesar_cobro_caja` | `venta_service.transaccion_critica`, `core` cobro |
| Stock | `stock_por_almacen`, `productos.stock` | `stock_service.py` |
| Enrolamiento | `/inventario/enrolamiento` | APIs enrolamiento en `app.py` |
| Salud | `/inventario/salud` | Comparación maestro vs almacenes |
| Kardex | `/kardex` | `kardex_service.py` |
| Auditoría | móvil + `auditorias_inventario` | Ajuste automático + kardex |

## Refactor en curso (`core/`)

Ver `../04-tecnico/ARQUITECTURA_CAPAS.md` — Fase 1.4: dominio venta/cobro, stock al cobro, post-cobro crédito.

**Regla:** nuevo código de negocio crítico → preferir `core/` o `services/`; no expandir `app.py` sin necesidad.

## Objetivo producto (12 meses)

```
lhexia/
├── tenant/          # contexto, scoping, onboarding
├── domain/
├── application/
├── infrastructure/
└── agents/          # CrewAI, schedulers (plan IA-*)
app.py               # factory delgada
clients/{slug}/      # por ferretería
```

**Plan Agentes IA:** `../06-agentes-ia/PLAN_AGENTES_IA_v1.md` — CrewAI + LangGraph, tools seguros, Celery/Redis, Chroma/Qdrant.

Migración **incremental**; Santo Domingo permanece `tenant_id=1` cuando exista la columna.

## Integraciones

| Sistema | Uso |
|---------|-----|
| SII / FE | `facturacion_*_service` |
| WhatsApp | Cobranza, alertas |
| OpenAI | Bodega voz, C360 |
| Slack | Health / alertas ops |

## Deploy

- `render.yaml` — auto-deploy en push `main`
- `init_db.py` pre-deploy — sync esquema
- Docs: `docs/MIGRACION_RENDER_NEON.md`
