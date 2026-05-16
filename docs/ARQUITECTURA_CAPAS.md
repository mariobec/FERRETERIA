# Arquitectura por capas (refactor progresivo)

> **Estado:** Fase **1.3** — dominio Venta+Cobro y **stock/kardex al cobro** en `core/` conectados a `app.py` y fixtures QA.

## Árbol activo (Fase 1.3)

```
sistema_ventas_limpio/
├── core/
│   ├── domain/venta/           # entities, value_objects, exceptions
│   ├── application/
│   │   ├── ventas/             # commands, use_cases
│   │   ├── inventario/         # stock_cobro (DescontarStockCobroService)
│   │   └── bootstrap.py        # build_*_use_case, build_descontar_stock_cobro_service
│   └── infrastructure/
│       ├── persistence/venta_repository.py
│       └── adapters/
│           ├── stock_tienda_validator.py
│           └── cobro_stock_adapter.py   # AppCobroStockAdapter
├── app.py                      # Handlers; delega estado + stock cobro a core
├── blueprints/
└── services/                   # transaccion_critica, stock_service, …
```

## Fase 1.2 — Venta + Cobro (estado del vale)

| Componente | Estado |
|------------|--------|
| Dominio `Venta` / `DetalleVenta` | ✅ |
| `FinalizarVentaUseCase` / `ProcesarCobroUseCase` | ✅ |
| `AppStockTiendaValidator` → `_venta_validar_stock_tienda` | ✅ |
| `SqlAlchemyVentaRepository` | ✅ |
| **`finalizar_venta`** usa `FinalizarVentaUseCase` | ✅ |
| **`procesar_cobro_caja`** usa `ProcesarCobroUseCase` | ✅ |
| Tests dominio `test_core_domain_venta.py` | ✅ 8 tests |

## Fase 1.3 — Stock + kardex al cobro

| Componente | Estado |
|------------|--------|
| `LineaStockCobro`, puertos preparar/aplicar | ✅ `application/inventario/stock_cobro.py` |
| `DescontarStockCobroService` | ✅ |
| `AppCobroStockAdapter` (lógica ex `procesar_cobro_caja`) | ✅ |
| `procesar_cobro_caja` → `build_descontar_stock_cobro_service()` | ✅ |
| `cobrar_venta_efectivo` (conftest) alineado | ✅ |
| Post-cobro: cuotas, saldo favor, bodega, FE, audit | ✅ en handler `app.py` |
| Alembic | ⏳ postergado |

## Flujo wiring (actual)

**Emitir vale (`finalizar_venta`):**

1. Validaciones HTTP + cliente (ORM, igual que antes).
2. Dentro de `transaccion_critica`: `build_finalizar_venta_use_case(validar_stock=False).execute(FinalizarVentaCommand(...))`.
3. Stock ya validado arriba con `_venta_validar_stock_tienda`.

**Cobrar (`procesar_cobro_caja`):**

1. Validaciones HTTP + `_venta_validar_stock_tienda`.
2. **Fuera del savepoint:** `stock_cobro_svc.preparar_lineas(venta.id)` (valida agrupado tienda + líneas bodega/tienda).
3. `rollback` + relectura venta (evita `InFailedSqlTransaction`).
4. Dentro de `transaccion_critica`:
   - `ProcesarCobroUseCase.execute(...)` (estado Pagado/Crédito, vuelto, etc.).
   - Cuotas / saldo favor / flags bodega (ORM en handler).
   - `stock_cobro_svc.aplicar_descontos(...)` (tienda + kardex SALIDA).
   - `_audit_log`.
5. `commit` + FE post-commit.

Errores de dominio → `VentaDomainError` → flash / JSON 400.  
Errores de stock → `ValueError` → flash / JSON 500.

## Siguiente (Fase 1.4 sugerida)

- Extraer cuotas crédito + `saldo_deudor` post-cobro.
- `agregar_producto_venta` / carrito Abierta → dominio.
- Tests unitarios con mocks para `DescontarStockCobroService`.

## Reglas de dependencia

```
app.py (handlers) → core.application → core.domain
core.infrastructure → implementa repos / adapters
domain ↛ flask, sqlalchemy
```

## Referencias

- `core/application/bootstrap.py`
- `tests/test_core_domain_venta.py`
- `tests/conftest.py` → `cobrar_venta_efectivo`
- `memory.md`
