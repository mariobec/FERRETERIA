# Estado del desarrollo — Optimización y modularización de `app.py`

**Última actualización:** 2026-05-17  
**Ejes relacionados:** **TEC-*** (estabilidad + servicios) · **CORE-*** (dominio en `core/`)  
**Índice maestro:** `../00-alineacion/PLAN_INDICE_LHEXIA.md`

> Este documento es la **vista única** del refactor del monolito. Antes estaba repartido entre `PLAN_TRABAJO_CONSOLIDADO_v2`, `ARQUITECTURA_CAPAS.md` y notas sueltas en `memory.md`.

---

## Qué significa “optimizar app” en LhexIA

No es solo “hacer más rápido” el servidor. Es **reducir riesgo y deuda** del monolito `app.py` (~20.5k líneas) sin romper POS, caja ni inventario:

| Tipo | Objetivo |
|------|----------|
| **Estabilidad (TEC-1A/1B)** | Transacciones atómicas, audit log, invariantes stock, alertas vales |
| **Servicios (TEC-2)** | Sacar lógica repetible a `services/*.py` |
| **Blueprints (TEC-3)** | Rutas por dominio (`pos`, `caja`, `bodega`, `c360`) |
| **Dominio (CORE-1.x)** | Use cases venta/cobro/stock en `core/` (Clean Architecture ligera) |

**Fuera de alcance inmediato:** mover todos los modelos ORM fuera de `app.py`, multi-tenant, Alembic masivo.

---

## Resumen ejecutivo (mayo 2026)

| Área | Estado | Documento detalle |
|------|--------|-------------------|
| TEC-1A Transacciones + audit + stock crítico | ✅ Cerrado | `../04-tecnico/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md` |
| TEC-1B Vales despachados sin cobro | ✅ Cerrado | Ídem |
| TEC-2 Extracción servicios | ✅ Cerrado (lista plan) | Ídem § Fase 2 |
| TEC-3 Blueprints | ✅ Cerrado | Ídem § Fase 3 |
| TEC-4 Salud + cron Slack | ✅ Cerrado v2 | Ídem § Fase 4 |
| **CORE-1.2** Venta + cobro (estado vale) | ✅ | `../04-tecnico/ARQUITECTURA_CAPAS.md` |
| **CORE-1.3** Stock + kardex al cobro | ✅ | Ídem |
| **CORE-1.4** Post-cobro crédito + saldo favor | ✅ | Ídem |
| **CORE-1.5** Flags bodega + carrito Abierta | ⏳ Sugerida | Ídem § Siguiente |
| Reducir líneas `app.py` global | 🟡 En curso | ~20.570 líneas; meta largo plazo |

---

## Commits y artefactos clave

| Fecha ref. | Commit / entrega | Qué cambió |
|------------|------------------|------------|
| Mayo 2026 | Plan TEC v2 **cerrado** | `transaccion_critica`, `erp_audit_log`, servicios, blueprints |
| Mayo 2026 | `e56c18d` — `feat(core): Fases 1.2-1.3 venta/cobro y stock al cobrar` | Paquete `core/`, wiring en `finalizar_venta` y `procesar_cobro_caja` |
| Mayo 2026 | CORE-1.4 (post-cobro) | `PostCobroCreditoService`, `PostCobroSaldoFavorService` + tests |

---

## Métricas del repo (referencia)

| Métrica | Valor aprox. (may 2026) |
|---------|-------------------------|
| Líneas `app.py` | ~20.570 |
| Líneas Python en `core/` | ~974 (26 archivos) |
| Módulos `services/` | 15 archivos (stock, kardex, venta, audit, whatsapp, POS búsqueda, FE, C360, …) |
| Tests dominio `core/` | `tests/test_core_domain_venta.py`, `tests/test_core_post_cobro.py` |
| Blueprints activos | `pos`, `caja`, `bodega`, `c360` |

`app.py` **sigue siendo** composition root: modelos SQLAlchemy, mayoría de rutas HTTP, FE, bodega pesada, C360 admin.

---

## TEC-2 — Servicios extraídos (`services/`)

Lógica que **ya no vive solo** en `app.py` (delegación o import directo):

| Servicio | Responsabilidad principal |
|----------|---------------------------|
| `venta_service.py` | `transaccion_critica()` — savepoints |
| `stock_service.py` | Stock tienda/bodega, invariante, POS, ajustes |
| `kardex_service.py` | Movimientos kardex |
| `audit_service.py` | `erp_audit_log` |
| `whatsapp_service.py` | Envío WhatsApp Cloud |
| `unidades_service.py` | Unidades de medida / factores |
| `pos_busqueda_service.py` | Búsqueda POS enriquecida |
| `pos_compromiso_entrega_service.py` | Compromiso entrega POS |
| `sistema_health_service.py` | Salud sistema / cron |
| `c360_service.py` | Customer 360 |
| `facturacion_*` | CAF, DTE, certificación SII |

**Pendiente TEC v3+:** seguir delegando rutas masivas legacy que aún no usan `transaccion_critica()`.

---

## CORE — Qué ya delega `app.py` a `core/`

### `finalizar_venta` (emitir vale)

```
app.py → build_finalizar_venta_use_case() → FinalizarVentaUseCase
         (estado Pendiente, validaciones dominio)
```

### `procesar_cobro_caja` (cobro)

```
app.py → preparar_lineas (stock, fuera savepoint)
      → ProcesarCobroUseCase (estado Pagado/Crédito)
      → PostCobroCreditoService | PostCobroSaldoFavorService
      → DescontarStockCobroService.aplicar_descontos (tienda + kardex)
      → flags bodega, audit, FE (aún en handler app.py)
```

### Árbol `core/` actual

```
core/
├── domain/venta/          entities, value_objects, exceptions
├── application/
│   ├── ventas/            use_cases, commands, post_cobro_saldo_favor
│   ├── creditos/          post_cobro_credito
│   ├── inventario/        stock_cobro
│   └── bootstrap.py       factories build_* 
└── infrastructure/
    ├── persistence/venta_repository.py
    └── adapters/          stock, cobro, post_cobro_*
```

---

## Qué sigue dentro de `app.py` (deuda conocida)

| Bloque | Por qué sigue ahí | Próximo paso sugerido |
|--------|-------------------|------------------------|
| Modelos ORM (~80+ tablas) | Histórico monolito | LX-1 / extracción gradual |
| Rutas HTTP mayoría | Registro directo `@app.route` | Más blueprints MOD-* |
| Flags bodega post-cobro | Acoplado a ORM venta | **CORE-1.5** |
| `agregar_producto_venta` / carrito | POS crítico en piso | **CORE-1.5** |
| Facturación electrónica | Integración SII | `services/facturacion_*` (ya parcial) |
| Customer 360 admin | Pantallas + APIs | `c360_service` + blueprint |
| Bodega voz / plataforma | Complejidad alta | Mantener en app hasta ventana estable |

---

## Reglas para no romper optimización

1. Flujos críticos: ver `docs/FLUJOS_CRITICOS.md` antes de mover código.
2. Cambios stock/caja/venta: dentro de `transaccion_critica()` cuando mutan BD.
3. Código nuevo de negocio crítico → preferir `core/` o `services/`, no expandir `app.py`.
4. **SD-1 manda:** no big-bang refactor durante toma inventario / go-live POS.

---

## Roadmap próximo (CORE / TEC)

| ID | Entrega | Prioridad |
|----|---------|-----------|
| **CORE-1.5** | Extraer flags bodega post-cobro a application service | Media (post SD-1) |
| **CORE-1.5** | Dominio carrito Abierta (`agregar_producto_venta`) | Media |
| **TEC-3+** | Más rutas bajo blueprints + tests rutas críticas | Baja continua |
| **META-ARCH** | Review deuda `app.py` vs `core/` (semana 1 agentes meta) | Paralelo doc |

---

## Dónde leer más

| Pregunta | Documento |
|----------|-----------|
| Plan TEC completo (cerrado) | `../04-tecnico/PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md` |
| Detalle capas y fases CORE | `../04-tecnico/ARQUITECTURA_CAPAS.md` |
| Flujos que no romper | `docs/FLUJOS_CRITICOS.md` |
| Mapa ERP vivo | `docs/ERP_MAESTRO.md` |
| Bitácora sesiones | `docs/memory.md` |
| Índice todos los planes | `../00-alineacion/PLAN_INDICE_LHEXIA.md` |

---

*Actualizar este archivo al cerrar CORE-1.5 o al mover un bloque grande fuera de `app.py`.*
