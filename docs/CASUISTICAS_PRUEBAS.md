# Catálogo de casuísticas de prueba — ERP Lhexa

Documento maestro para **reproducir**, **automatizar** y **imprimir** escenarios de QA.
Cada casuística tiene un **ID** estable. Los tests automatizados referencian el mismo ID en `tests/test_casuisticas_catalogo.py`.

**Convención**

| Campo | Significado |
|-------|-------------|
| **ID** | Identificador único (módulo-número) |
| **Prioridad** | P0 crítico · P1 alto · P2 medio |
| **Automatizado** | `pytest tests/test_casuisticas_catalogo.py -k ID` o archivo indicado |
| **Precondiciones** | Caja abierta, usuario con permiso, datos TEST-* |

---

## Módulo POS — Punto de venta

### POS-001 — Escaneo agrega producto existente
- **Prioridad:** P0
- **Automatizado:** `test_pos_live_wall.py::test_escanear_incrementa_misma_linea`
- **Pasos:** Caja abierta → POS → escanear `TEST-MART-001` dos veces.
- **Esperado:** Una sola línea, cantidad 2; toast "Cantidad 2".

### POS-002 — Escaneo sin stock en vale actual
- **Prioridad:** P0
- **Automatizado:** `test_pos_live_wall.py::test_escanear_bloquea_si_supera_stock_en_vale`
- **Pasos:** Producto con stock tienda = 1 → escanear 2 veces en el mismo vale.
- **Esperado:** Segundo escaneo bloqueado (`sin_stock` o mensaje de máximo).

### POS-003 — Producto en vale pendiente de caja
- **Prioridad:** P0
- **Automatizado:** `test_pos_live_wall.py::test_escanear_avisa_si_producto_en_vale_pendiente`
- **Pasos:** Emitir vale con producto (queda Pendiente) → nueva venta → escanear mismo código.
- **Esperado:** Error `en_vale_pendiente` citando número de vale y "pendiente en caja".

### POS-004 — Código no registrado abre modal
- **Prioridad:** P1
- **Automatizado:** manual / E2E
- **Pasos:** Escanear código inexistente.
- **Esperado:** Modal alta rápida o búsqueda; sin flash amarillo de recarga.

### POS-005 — Emitir vale sin RUT (toggle POS desactivado)
- **Prioridad:** P1
- **Automatizado:** `test_casuisticas_catalogo.py::test_pos_005_emitir_sin_rut_opcional`
- **Precondiciones:** En POS pulsar **Sin RUT** (o default empresa sin exigir RUT).
- **Pasos:** POS sin identificar cliente → agregar ítems → Emitir vale → punto retiro.
- **Esperado:** Vale Pendiente como cliente final; redirección a **`/pos/ticket/<id>`** (ticket con animación).

### POS-006 — Emitir vale sin RUT (toggle POS activado)
- **Prioridad:** P1
- **Automatizado:** `test_casuisticas_catalogo.py::test_pos_006_emitir_exige_rut`
- **Precondiciones:** En POS botón **RUT obligatorio** activo (default).
- **Pasos:** POS sin cliente → agregar ítems → Emitir vale.
- **Esperado:** Mensaje claro: identificar RUT o F3 cliente final; no emite.

### POS-010 — Toggle RUT obligatorio en POS
- **Prioridad:** P1
- **Automatizado:** `test_casuisticas_catalogo.py::test_pos_010_toggle_rut_en_pos`
- **Pasos:** En POS pulsar el botón **RUT obligatorio** / **Sin RUT** (zona TV cliente).
- **Esperado:** Cambia estado en sesión; al desactivar permite emitir sin RUT; al activar exige identificación.

### POS-011 — Retiro mixto por línea (Tienda / Bodega)
- **Prioridad:** P1
- **Automatizado:** manual / regresión implícita en cobro y bodega
- **Precondiciones:** Admin → Empresa → activar **Retiro por línea en el POS**.
- **Pasos:** Agregar dos productos; en columna **Retiro** dejar uno en **Tienda** y otro en **Bodega** → emitir vale → cobrar en caja.
- **Esperado:** El vale queda con `punto_retiro` = **Mixto** si difieren; bodega ve cola si hay línea Bodega; descuenta stock tienda solo en líneas que correspondan al cobro.

### POS-007 — Cliente final explícito (F3)
- **Prioridad:** P1
- **Automatizado:** `test_routes_criticas.py::test_finalizar_venta_pos`
- **Pasos:** Marcar cliente final → emitir vale.
- **Esperado:** Vale Pendiente con cliente final; respuesta **`302`** hacia **`/pos/ticket/<id>`**.

### POS-008 — Vincular cliente nuevo en TV
- **Prioridad:** P2
- **Automatizado:** `test_pos_live_wall.py::test_vincular_registrar_cliente_nuevo`
- **Pasos:** API vincular con `registrar: true` y RUT nuevo.
- **Esperado:** Cliente creado y vitrina actualizada.

### POS-009 — Pantalla ticket tras emitir (animación + impresión)
- **Prioridad:** P2
- **Automatizado:** manual (impresión navegador)
- **Pasos:** Emitir vale con líneas.
- **Esperado:** Ruta **`/pos/ticket/<id>`** con total hero + ticket animado; disparo de impresión ~4,5 s después.

### POS-012 — Ticket por bloques Tienda/Bodega/Despacho y subtotales
- **Prioridad:** P1
- **Automatizado:** `tests/test_pos_ticket_despacho.py::test_pos_ticket_subtotales_agrupan_mixto` (helpers) + manual ticket
- **Precondiciones:** **Retiro por línea** activo; vale **Mixto** (líneas con retiros distintos).
- **Pasos:** Emitir vale → revisar pantalla ticket.
- **Esperado:** Bloques con separadores, prefijos **`[T]` `/ [B]` / `[D]`**, líneas **`TOTAL TIENDA`**, **`TOTAL BODEGA`**, **`TOTAL DESPACHO`** (si aplica) y **`TOTAL A PAGAR`**; tabla **PICKING BODEGA** sólo si hay líneas bodega.

### POS-013 — QR despacho opcional en ticket (misma URL para todos)
- **Prioridad:** P2
- **Automatizado:** manual
- **Precondiciones:** Admin → Empresa → **Código QR en el ticket del vale** activado.
- **Pasos:** Emitir vale → ver área QR bajo código de barras.
- **Esperado:** QR apunta a **`/pos/despacho/vale/<id>?t=<token>`** (token firmado; TTL por defecto 7 días, variable `POS_DESPACHO_VALE_TOKEN_MAX_AGE`).

---

## Módulo Despacho (POS/Bodega)

### DESP-001 — Lista filtrada por rol con mismo QR
- **Prioridad:** P1
- **Automatizado:** `tests/test_pos_ticket_despacho.py::test_pos_despacho_vale_rechaza_token_invalido` (token) + manual
- **Precondiciones:** Usuario con permiso **POS** o **bodega_operador**; sesión iniciada.
- **Pasos:** Abrir URL del QR (o construir con token válido).
- **Esperado:** **POS/caja** ven bloques **Tienda** y **Despacho**; **bodeguero/a** ve **Bodega** y **Despacho**; token inválido → flash y redirección. Evolución: marcas de salida / picking desde esta pantalla.

### DESP-002 — Menú Bodega «Despacho ticket (QR)»
- **Prioridad:** P2
- **Automatizado:** manual
- **Precondiciones:** Caja abierta; al menos un vale pendiente con retiro bodega/mixto con línea bodega.
- **Pasos:** Inventario / Bodega → **Despacho ticket (QR)** → **Abrir lista** en un vale.
- **Esperado:** Lista filtrada por caja abierta; enlace abre `/pos/despacho/vale/<id>?t=...` sin escanear papel. Sin caja abierta: mensaje y lista vacía.

---

## Módulo Caja

### CAJA-001 — Cobrar vale pendiente descuenta stock
- **Prioridad:** P0
- **Automatizado:** `test_end_to_end.py` (flujos cobro)
- **Pasos:** Vale Pendiente → Caja → cobrar efectivo.
- **Esperado:** Estado Pagado; stock tienda descontado; kardex SALIDA.

### CAJA-002 — No cobrar sin stock (varios vales mismo producto)
- **Prioridad:** P0
- **Automatizado:** revisión `venta_validar_stock_tienda` agrupado
- **Pasos:** Dos líneas o dos vales que superan stock real.
- **Esperado:** Bloqueo al emitir o al cobrar con mensaje de comprometido.

### CAJA-003 — Anular vale pendiente
- **Prioridad:** P1
- **Automatizado:** `test_routes_criticas.py::test_anular_vale_pendiente`

### CAJA-004 — Reimprimir ticket vale desde cola cobranza
- **Prioridad:** P2
- **Automatizado:** manual
- **Precondiciones:** Permiso **`caja_cobrar_vale`** o **`pos_emitir_vale`** (o admin); fila de vale real (no borrador POS).
- **Pasos:** Caja → Vales pendientes → **Ticket vale** (nueva pestaña).
- **Esperado:** Se abre `/pos/ticket/<id>` con bloques/subtotales y QR opcional según empresa.

---

## Módulo Inventario / Bodega

### INV-001 — Traslado tienda ↔ bodega
- **Prioridad:** P1
- **Automatizado:** `test_end_to_end.py` (traslados)

### INV-002 — Vale retiro bodega no consume stock tienda al escanear
- **Prioridad:** P2
- **Nota:** Punto retiro Bodega compromete bodega al cobrar, no tienda en POS.

---

## Módulo Créditos

### CRED-001 — Venta a crédito respeta cupo
- **Prioridad:** P0
- **Automatizado:** `test_end_to_end.py`

---

## Cómo ejecutar

```bash
# Catálogo POS automatizado
pytest tests/test_casuisticas_catalogo.py tests/test_pos_live_wall.py tests/test_pos_ticket_despacho.py -v

# Smoke rápido
pytest tests/ -m smoke -q

# Una casuística por ID en el nombre del test
pytest tests/test_casuisticas_catalogo.py -k pos_005 -v
```

---

## Registro de ejecución (imprimir)

| ID | Fecha | Tester | OK / Falla | Notas |
|----|-------|--------|-----------|-------|
| POS-001 | | | | |
| POS-003 | | | | |
| POS-005 | | | | |
| POS-010 | | | | |

*Ampliar esta tabla al validar cada módulo en QA o capacitación.*
