# Flujos críticos — stock, caja y bodega (ERP LhexIA)

Documento vivo alineado al [plan v2.0 Grok](./PLAN_TRABAJO_CONSOLIDADO_v2_GROK_10-10.md). Describe secuencias que **no deben romperse** al refactorizar.

---

## Invariante de stock por línea de vale

Para cada línea de `detalle_ventas`:

`consumo_registrado_bodega (JSON) + consumo_tienda_en_cobro ≤ consumo_total_en_unidades_stock`

- **Bodega (voz):** descuenta solo almacén bodega y acumula en `ventas.bodega_despacho_json`.
- **Caja (cobro):** descuenta tienda solo por el **remanente** no cubierto por bodega.
- **Validación:** `stock_validar_invariante_venta` (en `services/stock_service.py`) antes de persistir despacho o cobro.

---

## 1. Cobro de vale en caja (`procesar_cobro_caja`)

```mermaid
sequenceDiagram
    participant U as Cajero
    participant W as Web Caja
    participant DB as BD transacción
    participant T as Tienda stock
    participant K as Kardex

    U->>W: POST cobro (método, montos)
    W->>DB: rollback + cargar Venta + detalles
    W->>W: stock_validar_invariante_venta
    W->>DB: transaccion_critica (savepoint)
    W->>DB: actualizar venta (estado, método, caja…)
    loop Por línea con consumo_tienda > 0
        W->>T: descontar_stock_venta_tienda
        W->>K: SALIDA tienda
    end
    W->>DB: _audit_log cobro_vale
    W->>DB: commit
    W->>U: redirect ticket / flash
```

**Notas:** WhatsApp no forma parte de este flujo. Rollback ante cualquier error dentro del savepoint.

---

## 2. Despacho bodega por voz (`_bodega_voice_ejecutar` + API)

```mermaid
sequenceDiagram
    participant Op as Operador bodega
    participant API as POST /api/bodega/voice-command
    participant DB as BD
    participant B as Stock bodega
    participant K as Kardex
    participant WA as WhatsApp Cloud

    Op->>API: audio comando
    API->>DB: transaccion_critica
    API->>B: ajustar_stock_almacen (salida)
    API->>DB: actualizar JSON + estado + bodega_despacho_ultimo_at
    API->>API: stock_validar_invariante_venta
    API->>K: SALIDA bodega
    API->>DB: _audit_log bodega_despacho_voz
    API->>DB: commit
    API-->>WA: envío texto cliente (post-commit)
```

**Notas:** Si falla WA después del `commit`, el despacho **no** se revierte.

---

## 3. Anulación de vale en caja con despacho bodega (`anular_vale_caja`)

```mermaid
sequenceDiagram
    participant U as Cajero
    participant W as Web Caja
    participant P as Permisos
    participant DB as BD
    participant B as Stock bodega
    participant K as Kardex

    U->>W: POST anular + motivo
    W->>P: anular_vale_caja + si hay despacho: anular_vale_con_despacho_bodega o gestionar_usuarios
    alt Sin permiso con despacho
        W->>U: flash + redirect
    else Permitido
        W->>DB: transaccion_critica
        opt Hay JSON despacho
            W->>B: ENTRADA por líneas JSON
            W->>K: ENTRADA bodega
            W->>DB: limpiar JSON / estado / ultimo_at
        end
        W->>DB: venta estado Anulada + motivo
        W->>DB: _audit_log anular_vale
        W->>DB: commit
        W->>U: flash éxito
    end
```

---

## 4. Cron alertas vales despachados sin cobro

`POST /api/ventas/alertas-despachos-pendientes` (Bearer). Opcional: `use_view` si existe `vista_vales_riesgo_despacho`, `send_wa` cliente, `send_wa_interno` a número operaciones.

```mermaid
flowchart LR
    subgraph Entrada
        A[Bearer válido]
    end
    subgraph Datos
        B[Lista vales Pendiente + despacho + ref_ts antigua]
    end
    subgraph Salidas
        C[JSON items]
        D[WA cliente opcional]
        E[WA interno opcional]
    end
    A --> B --> C
    B --> D
    B --> E
```

---

## 5. Salud del sistema (operaciones)

`GET /api/sistema/salud` — requiere `gestionar_usuarios`. Implementación en `services/sistema_health_service.py`: conteo de vales en riesgo (misma lógica que el cron), vista SQL instalada, tabla `erp_audit_log`, eventos de auditoría últimas 24 h (si la tabla existe), hora de servidor y si hay webhook Slack configurado.

En el cron `POST /api/ventas/alertas-despachos-pendientes`, JSON opcional `notify_slack: true` envía un resumen a Slack (`SLACK_WEBHOOK_URL` o `ERP_SLACK_WEBHOOK_URL`) cuando los candidatos superan `VALES_RIESGO_SLACK_MIN` (default 1).

---

## Archivos relacionados

| Área | Ubicación |
|------|------------|
| Servicios stock / invariante | `services/stock_service.py` |
| Auditoría | `services/audit_service.py` |
| Savepoint crítico | `services/venta_service.py` → `transaccion_critica` |
| Rutas bodega registradas | `blueprints/bodega.py` + vistas en `app.py` |
| Rutas caja / cambios / cobro | `blueprints/caja.py` + vistas en `app.py` |
| Rutas POS | `blueprints/pos.py` + vistas en `app.py` |
| Rutas Customer 360 | `blueprints/c360.py` + `services/c360_service.py` |
| Salud / Slack cron | `services/sistema_health_service.py` |
| Vista SQL riesgo | `sql/2026_05_08_vista_vales_riesgo_despacho_*.sql` |
