# Arquitectura por capas (refactor progresivo)

> **Estado:** Fase **1.4** — además de 1.2–1.3, **cuotas crédito + saldo_deudor** y **saldo a favor** post-cobro en `core/`.

## Árbol activo (Fase 1.3)

```
sistema_ventas_limpio/
├── core/
│   ├── domain/venta/           # entities, value_objects, exceptions
│   ├── application/
│   │   ├── ventas/             # commands, use_cases, post_cobro_saldo_favor
│   │   ├── creditos/           # post_cobro_credito
│   │   ├── inventario/         # stock_cobro
│   │   └── bootstrap.py
│   └── infrastructure/
│       ├── persistence/venta_repository.py
│       └── adapters/
│           ├── stock_tienda_validator.py
│           ├── cobro_stock_adapter.py
│           ├── post_cobro_credito_adapter.py
│           └── post_cobro_saldo_favor_adapter.py
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
| Post-cobro: cuotas + `saldo_deudor` | ✅ `PostCobroCreditoService` |
| Post-cobro: saldo a favor (débito) | ✅ `PostCobroSaldoFavorService` |
| Post-cobro: flags bodega, FE, audit | ✅ en handler `app.py` |
| Tests `test_core_post_cobro.py` | ✅ |
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
   - `PostCobroCreditoService` o `PostCobroSaldoFavorService` según método.
   - Flags bodega (ORM en handler).
   - `stock_cobro_svc.aplicar_descontos(...)` (tienda + kardex SALIDA).
   - `_audit_log`.
5. `commit` + FE post-commit.

Errores de dominio → `VentaDomainError` → flash / JSON 400.  
Errores de stock → `ValueError` → flash / JSON 500.

## Fase 1.4 — Crédito y saldo a favor post-cobro

| Componente | Estado |
|------------|--------|
| `PostCobroCreditoService` + `AppPostCobroCreditoAdapter` | ✅ |
| `PostCobroSaldoFavorService` + `AppPostCobroSaldoFavorAdapter` | ✅ |
| `procesar_cobro_caja` delega plan + cuotas + saldo_deudor | ✅ |
| `procesar_cobro_caja` delega débito saldo favor | ✅ |

## Siguiente (Fase 1.5 sugerida)

- Extraer flags bodega post-cobro.
- `agregar_producto_venta` / carrito Abierta → dominio.
- Test HTTP cobro crédito con plan en rutas críticas.

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
