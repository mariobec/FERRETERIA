# SD-1 — Cierre Fase 1 (VERTEX Bastión)

**Ecosistema:** LhexIA VERTEX · **Solución:** LhexIA Ferretería · **Cliente:** Santo Domingo  
**Fecha objetivo cierre:** _______________ · **Firma operación:** _______________

> Este documento es la **puerta de salida** de SD-1. Cuando todos los ítems obligatorios estén marcados, SD-1 queda **cerrado** y se abre SD-2 / demo red Chilemat.

**Aclaración operativa (2026-05-21):** Ferretería Santo Domingo es **un solo establecimiento** (una dirección / operación en piso). **No tiene sucursales.** En el ERP, el inventario se trabaja por **almacenes** (ej. tienda y bodega en el mismo local). La “red” y varias sucursales en Guardián corresponden a **Chilemat / VERTEX futuro**, no al alcance SD-1.

**Runbook piso:** [`CLIENTE_SANTO_DOMINGO.md`](CLIENTE_SANTO_DOMINGO.md)  
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
| A1 Smoke 113+ | [ ] | |
| A2 Casuísticas 11/11 | [ ] | |
| A3 Guardián API | [ ] | |
| A4 Preflight OK | [ ] | |
| A5 Deploy Render commit `________` | [ ] | |

---

## B. Inventario — por almacén (mismo establecimiento)

Listar **solo almacenes reales** de Santo Domingo (Admin → Almacenes). Típico: **Tienda** + **Bodega** (2 sesiones, no “3 sucursales”).

| Almacén | ID | Sesión enrolamiento cerrada | Fecha | Salud OK | Responsable |
|---------|-----|----------------------------|-------|----------|-------------|
| 1. _______________ | | [ ] | | [ ] | |
| 2. _______________ | | [ ] | | [ ] | |
| _(opcional)_ 3. _______ | | [ ] | | [ ] | |

- [ ] D0: almacenes activos verificados (nombres anotados para capacitación)
- [ ] Permisos `enrolamiento_inventario` a encargados
- [ ] Backup Neon antes de ajustes masivos: fecha _______

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

| Ítem | OK |
|------|-----|
| `/owner-mobile` en celular | [ ] |
| Mini semáforos + tarjetas | [ ] |
| Ventas hoy coherente con operación | [ ] |
| `OWNER_SUPERVISOR_TELEFONO` en Render | [ ] |

*Nota:* “3 sucursal(es)” en consolidado/desfalco red es **vista Chilemat/demo red**, no implica que SD tenga 3 locales.

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
| **D1** | Enrolamiento almacén Tienda + revisar salud |
| **D2** | Enrolamiento almacén Bodega + 1 vale/cobro retiro Bodega |
| **D3** | Vale Mixto o repetición flujo + capacitación + Guardián + sign-off |

---

*SD-1 cerrado = un ferreterón blindado. Chilemat / multi-sucursal = SD-2 y VERTEX Fase 2.*
