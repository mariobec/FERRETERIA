# SD-1 — Cierre Fase 1 (VERTEX Bastión)

**Ecosistema:** LhexIA VERTEX · **Solución:** LhexIA Ferretería · **Cliente:** Santo Domingo  
**Fecha objetivo cierre:** _______________ · **Firma operación:** _______________

> Este documento es la **puerta de salida** de SD-1. Cuando todos los ítems obligatorios estén marcados, SD-1 queda **cerrado** y se abre SD-2 / demo red Chilemat.

**Aclaración operativa (2026-05-21):** Santo Domingo hoy es **un solo establecimiento** en piso (sin locales adicionales). El inventario va por **almacenes** (tienda + bodega). **LhexIA VERTEX sí será multi-sucursal** (crear sucursales, caja/POS por local) — ver [`../../arquitectura/VERTEX_MULTI_SUCURSAL.md`](../../arquitectura/VERTEX_MULTI_SUCURSAL.md). Eso se implementa **después** de cerrar SD-1; en Guardián, textos tipo “3 sucursales” son **vista demo red** (Chilemat), no la operación actual de SD.

**Runbook piso:** [`CLIENTE_SANTO_DOMINGO.md`](CLIENTE_SANTO_DOMINGO.md)  
**Día 1 hoy:** [`SD1_DIA1_PISO.md`](SD1_DIA1_PISO.md) · **Imprimir:** [`SD1_DIA1_PISO_HOJA_1_PAGINA.md`](SD1_DIA1_PISO_HOJA_1_PAGINA.md) · `python scripts/sd1_estado_piso.py`  
**Backup C7:** [`SD1_BACKUP_NEON_C7.md`](SD1_BACKUP_NEON_C7.md)  
**Portal entrega:** [`SANTO_DOMINGO_ENTREGA.md`](SANTO_DOMINGO_ENTREGA.md)

---

## Definición de “SD-1 cerrado”

| # | Criterio | Obligatorio |
|---|----------|-------------|
| C1 | **Todos los almacenes activos** del establecimiento con sesión de enrolamiento cerrada *o* plan de corrección documentado | Sí |
| C2 | **≥1 día operativo** con flujo **vale → cobro → stock** sin bloqueo crítico (ideal: Tienda + Bodega + Mixto) | Sí |
| C3 | **Smoke tests** repo en verde (`pytest -m smoke`) | Sí |
| C4 | **Casuísticas** ventas (`pytest -m casuisticas`) en verde en BD QA | Sí |
| C5 | **Guardián** probado en celular (semáforos + ventas hoy + actualizar) | Sí |
| C6 | **≥2 usuarios** capacitados por módulo (POS, caja, inventario) | Sí |
| C7 | **Backup Neon** antes de ajustes masivos de stock | Sí |

---

## A. Tecnología — validación automática

```bash
pytest tests/ -m smoke -q --tb=no
pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -q
pytest tests/test_owner_dashboard_api.py -m smoke -q
python scripts/sd1_cierre_preflight.py
```

| Check | Estado | Fecha |
|-------|--------|-------|
| A1 Smoke 144 passed, 3 skipped | [x] | 2026-05-23 |
| A2 Casuísticas 11/11 | [x] | 2026-05-21 |
| A3 Guardián API + global_maestro | [x] | 2026-05-21 |
| A4 Preflight OK (2 almacenes) | [x] | 2026-05-23 |
| A5 Deploy Render commit `7b0079b` *(repo local; confirmar en Render)* | [ ] | 2026-05-23 |

---

## B. Inventario — por almacén (mismo establecimiento)

Listar **solo almacenes reales** de Santo Domingo (Admin → Almacenes). Típico: **Tienda** + **Bodega** (2 sesiones, no “3 sucursales”).

| Almacén | ID | Sesión enrolamiento cerrada | Fecha | Salud OK | Responsable |
|---------|-----|----------------------------|-------|----------|-------------|
| 1. TIENDA — Tienda / Mostrador | 1 | [ ] | | [ ] | |
| 2. BODEGA — Bodega | 2 | [ ] | | [ ] | |
| _(preflight 2026-05-21; ajustar si Admin difiere)_ | | | | | |

- [x] D0: maestro Chilemat en Neon (~4.899 SKU, stock 0, `PEND-*`) — 2026-05-22
- [ ] D0: almacenes activos verificados en piso (nombres anotados para capacitación)
- [ ] D1: piloto pistola TIENDA (50–80 SKU) — ver `PAUSA_D1_PILOTO_PISTOLA.md`
- [ ] Permisos `enrolamiento_inventario` a encargados
- [ ] Backup Neon antes de ajustes masivos: fecha _______ — guía [`SD1_BACKUP_NEON_C7.md`](SD1_BACKUP_NEON_C7.md)

**Rutas:** `/inventario/enrolamiento` → por cada almacén → `/inventario/salud`

---

## C. POS y caja — mismo local

| Escenario | Vale # | Cobro Pagado | Retiro | TV | OK |
|-----------|--------|--------------|--------|-----|-----|
| Piloto (validado 2026-05-21) | 2584 / 2585 | [x] | Tienda / Bodega | [x] | [x] |
| Tienda (si distinto del piloto) | | [ ] | Tienda | [ ] | [ ] |
| Bodega | | [ ] | Bodega | [ ] | [ ] |
| Mixto (opcional) | | [ ] | Mixto | [ ] | [ ] |

- [ ] Ctrl+F5 POS tras último deploy
- [ ] Cierre de caja del día sin error crítico

---

## D. LhexIA Guardián

**Alcance cerrado SD-1:** [`GUARDIAN_SD1_ALCANCE_CERRADO.md`](GUARDIAN_SD1_ALCANCE_CERRADO.md)

| Ítem | OK |
|------|-----|
| `/owner-mobile` en celular (semáforos + ventas hoy) | [ ] |
| Mini semáforos + tarjetas + feed operador | [ ] |
| **Voz (mic)** en PWA | **N/A SD-1** — botón muestra “próximamente SD-2”; no probar |
| **Llamar supervisor** (`+56923739904` en Render) | [ ] pegar env y probar `tel:` en celular |

*Nota:* “3 sucursal(es)” en consolidado = demo red Chilemat. La voz de **bodega** es otro módulo (`/bodega/...`), no Guardián.

---

## E. Capacitación mínima

| Módulo | Usuario 1 | Usuario 2 | Fecha |
|--------|-----------|-----------|-------|
| POS / vale | | | |
| Caja / cobro | | | |
| Inventario enrolamiento | | | |
| Guardián (gerencia) | | | |

---

## F. Sign-off

| Rol | Nombre | Fecha | OK |
|-----|--------|-------|-----|
| Operación SD | | | [ ] |
| Mario | | | [ ] |

**Al firmar:** `SANTO_DOMINGO_ENTREGA.md` → SD-1 ✅ Cerrado.

---

## G. Plan sugerido (1 establecimiento — 2–3 días)

| Día | Foco |
|-----|------|
| **D1** | [`SD1_DIA1_PISO.md`](SD1_DIA1_PISO.md) — TIENDA + salud + `sd1_estado_piso.py` |
| **D2** | Enrolamiento almacén Bodega + 1 vale/cobro retiro Bodega |
| **D3** | Vale Mixto o repetición flujo + capacitación + Guardián + sign-off |

---

*SD-1 cerrado = un ferreterón blindado. Multi-sucursal (alta de sucursales, Chilemat) = SD-2 + LX-1 VERTEX.*
