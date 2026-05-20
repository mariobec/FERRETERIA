# Contrato API — Offline v1 (`/api/offline/*`)

**Versión:** 1.0  
**Fecha:** 2026-05-20  
**Estado:** Especificación (implementación Fase 1)

Autenticación: misma sesión Flask-Login que POS (`@login_required` + permiso `pos_emitir_vale` o equivalente).

---

## 1. Health / Circuit Breaker

### `GET /api/health/ping`

**Uso:** Heartbeat del Circuit Breaker ERP (no valida SII).

**Respuesta 200:**

```json
{
  "ok": true,
  "ts": "2026-05-20T18:00:00-04:00",
  "db": "ok"
}
```

**Timeout cliente:** 3000 ms.  
**Fallo:** timeout, 5xx, `ok: false` → cuenta como fallo breaker.

---

## 2. Catálogo espejo (Local Cache)

### `GET /api/offline/catalogo`

| Query | Tipo | Descripción |
|-------|------|-------------|
| `full` | `0` \| `1` | `1` = snapshot completo |
| `since` | string | Checksum o ISO timestamp delta (Fase 1.1) |
| `caja_id` | int | Opcional — filtro sucursal futuro |

**Respuesta 200 (gzip recomendado):**

```json
{
  "version": 1,
  "generated_at": "2026-05-20T08:05:00-04:00",
  "checksum": "sha256:abc...",
  "config_pos": {
    "pos_descuento_umbral_pin_pct": 20,
    "pos_descuento_autorizacion_por_cliente": 0,
    "pos_retiro_por_linea": 1
  },
  "productos": [
    {
      "id": 101,
      "sku": "CEM-42-K",
      "codigo_barra": "7801234567890",
      "nombre_corto": "Cemento 42kg",
      "precio_bruto_clp": 5990,
      "precio_mayoreo_clp": 5490,
      "stock_referencial": 120,
      "unidad_venta": "UN",
      "pos_descuento_preautorizado": false,
      "pos_descuento_preautorizado_pct": 0,
      "activo": true,
      "updated_at": "2026-05-19T22:00:00Z"
    }
  ],
  "reglas_descuento": [
    {
      "id": "preauth:101",
      "tipo": "PREAUTORIZADO",
      "producto_id": 101,
      "pct_max": 15,
      "requiere_pin": false
    }
  ]
}
```

**Regla precio efectivo (cliente):** `max(precio_bruto_clp, precio_mayoreo_clp)`.

**Triggers sync:** apertura caja, cada 60 min, botón manual.

---

## 3. Batch ventas contingencia (Reconciliation)

### `POST /api/offline/ventas/batch`

**Headers:** `Content-Type: application/json`

**Body:**

```json
{
  "caja_id": 3,
  "usuario": "cajero1",
  "ventas": [
    {
      "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "numero_local": "OFF-20260520-0003-0007",
      "created_at_local": "2026-05-20T14:32:01-04:00",
      "metodo_pago": "Efectivo",
      "cliente_rut": null,
      "tipo_documento": "Boleta",
      "punto_retiro": "Tienda",
      "lineas": [
        {
          "producto_id": 101,
          "codigo_barra": "7801234567890",
          "cantidad": 2,
          "precio_unitario_bruto_clp": 5990,
          "descuento_pct": 0,
          "subtotal_bruto_clp": 11980,
          "punto_retiro_linea": "Tienda"
        }
      ],
      "montos": {
        "bruto": 11980,
        "neto": 10067,
        "iva": 1913,
        "total": 11980
      }
    }
  ]
}
```

**Validación servidor:**

1. Recalcular montos con `desglosar_iva_clp` — rechazar si diff &gt; 0 CLP vs payload.
2. `client_uuid` UNIQUE — idempotente.
3. Procesar en orden `created_at_local` ASC.

**Respuesta 200:**

```json
{
  "procesadas": [
    { "client_uuid": "550e...", "venta_id": 98123, "estado": "OK" }
  ],
  "rechazadas": [
    { "client_uuid": "660e...", "motivo": "STOCK_INSUFICIENTE", "detalle": "Producto 101" }
  ]
}
```

**Códigos error:** `409` duplicado parcial, `422` montos inválidos, `423` caja cerrada.

---

## 4. Reporte cola local (Auditoría cierre)

### `GET /api/offline/cola-pendiente`

**Query:** `caja_id`

**Respuesta:**

```json
{
  "pendientes": 0,
  "bloquea_cierre": false
}
```

*(Fase 4: POS reporta también vía sessionStorage flag.)*

---

## 5. Modelo de errores común

```json
{
  "ok": false,
  "error": "codigo_maquina",
  "mensaje": "Texto humano"
}
```

---

## Índices DB servidor (migración Fase 3)

```sql
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS offline_client_uuid VARCHAR(36) UNIQUE;
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS origen_sync VARCHAR(32);
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS numero_local_offline VARCHAR(40);
```

---

*Contrato v1 — implementación en `blueprints/offline_sync.py` (pendiente).*
