# SD-1 — Cierre Fase 1 (VERTEX Bastión)

**Ecosistema:** LhexIA VERTEX · **Solución:** LhexIA Ferretería · **Cliente:** Santo Domingo  
**Fecha objetivo cierre:** _______________ · **Firma operación:** _______________

> Este documento es la **puerta de salida** de SD-1. Cuando todos los ítems obligatorios estén marcados, SD-1 queda **cerrado** y se abre SD-2 / semana 2 VERTEX.

**Runbook piso:** [`CLIENTE_SANTO_DOMINGO.md`](CLIENTE_SANTO_DOMINGO.md)  
**Portal entrega:** [`SANTO_DOMINGO_ENTREGA.md`](SANTO_DOMINGO_ENTREGA.md)  
**Biblia VERTEX:** [`../../arquitectura/LHEXIA_VERTEX_VISION.md`](../../arquitectura/LHEXIA_VERTEX_VISION.md)

---

## Definición de “SD-1 cerrado”

| # | Criterio | Obligatorio |
|---|----------|-------------|
| C1 | **3 sucursales** con sesión de enrolamiento cerrada *o* plan escrito de corrección | Sí |
| C2 | **≥1 sucursal** (ideal 3) con flujo **vale → cobro → stock** sin bloqueo crítico | Sí |
| C3 | **Smoke tests** repo en verde (`pytest -m smoke`) | Sí |
| C4 | **Casuísticas** ventas (`pytest -m casuisticas`) en verde en BD QA | Sí |
| C5 | **Guardián** probado en celular (semáforos + ventas hoy + actualizar) | Sí |
| C6 | **≥2 usuarios** capacitados por módulo (POS, caja, inventario) | Sí |
| C7 | **Backup Neon** antes de ajustes masivos de stock | Sí |

---

## A. Tecnología — validación automática (Cursor / CI)

Ejecutar en PC con BD local o QA (no producción sin `ALLOW_TESTS_ON_REMOTE`):

```bash
pytest tests/ -m smoke -q --tb=no
pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -q
pytest tests/test_owner_dashboard_api.py -m smoke -q
python scripts/sd1_cierre_preflight.py
```

| Check | Comando / evidencia | Estado | Fecha |
|-------|---------------------|--------|-------|
| A1 | Smoke **113+ passed** | [ ] | |
| A2 | Casuísticas **11/11** | [ ] | |
| A3 | Guardián API smoke | [ ] | |
| A4 | Preflight script OK | [ ] | |
| A5 | Último deploy Render = commit `________` en `main` | [ ] | |

**Última corrida documentada (2026-05-21):** smoke 113 passed · casuísticas 11 passed · Guardián 7 passed.

---

## B. Inventario — 3 sucursales (piso)

| Sucursal / almacén | ID almacén | Sesión enrolamiento | Fecha cierre sesión | Salud revisada | Responsable |
|--------------------|------------|---------------------|---------------------|----------------|-------------|
| 1. _______________ | | [ ] | | [ ] | |
| 2. _______________ | | [ ] | | [ ] | |
| 3. _______________ | | [ ] | | [ ] | |

**Rutas:** `/inventario/enrolamiento` → `/inventario/salud` → export CSV si hay desajuste.

- [ ] D0: 3 almacenes activos verificados (Admin → Almacenes)
- [ ] Permisos `enrolamiento_inventario` asignados a encargados
- [ ] Backup Neon hecho antes de ajustes masivos: fecha _______

---

## C. POS y caja — operación real

| Sucursal | Vale emitido # | Cobro Pagado | Retiro (Tienda/Bodega/Mixto) | TV ticket | OK |
|----------|----------------|--------------|------------------------------|-----------|-----|
| Piloto (hecho) | 2584 / 2585 | [x] | [x] | [x] | [x] |
| Sucursal 2 | | [ ] | [ ] | [ ] | [ ] |
| Sucursal 3 | | [ ] | [ ] | [ ] | [ ] |

**Flujo:** `/punto_venta` → emitir vale → `/caja/vales_pendientes` → cobrar.

- [ ] Ctrl+F5 en POS tras último deploy
- [ ] Búsqueda con 2–3 caracteres; filtro **Catálogo** probado si Operativo vacío
- [ ] Cierre de caja del día sin error crítico

---

## D. LhexIA Guardián (Fase 1 VERTEX)

| Ítem | OK | Notas |
|------|-----|-------|
| `/owner-mobile` carga en celular | [ ] | |
| Mini semáforos (Caja Inv Créd OC) visibles | [ ] | |
| Ventas hoy reflejan operación del día | [ ] | |
| Botón Actualizar refresca datos | [ ] | |
| `OWNER_SUPERVISOR_TELEFONO` en Render | [ ] | |
| PWA instalada en pantalla inicio (opcional) | [ ] | |

---

## E. Capacitación mínima

| Módulo | Usuario 1 | Usuario 2 | Fecha |
|--------|-----------|-----------|-------|
| POS / vale | | | |
| Caja / cobro | | | |
| Inventario enrolamiento | | | |
| Guardián móvil (gerencia) | | | |

---

## F. Fuera de alcance (no bloquean cierre)

- Multi-tenant producción
- FE SII timbrado masivo
- Transporte / Retail / LhexIA Connect
- LLM / CrewAI en prod

---

## G. Sign-off

| Rol | Nombre | Fecha | OK SD-1 cerrado |
|-----|--------|-------|-----------------|
| Cliente / operación | | | [ ] |
| Producto (Mario) | | | [ ] |
| Técnico (LhexIA) | | | [ ] |

**Al firmar:** actualizar `SANTO_DOMINGO_ENTREGA.md` §2 estado → **SD-1 ✅ Cerrado** y `VERTEX_SPRINT_TRACKER.md` Semana 1 → completada.

---

## H. Día 1–3 sugerido (cerrar en 72 h)

| Día | Foco | Entregable |
|-----|------|------------|
| **D1** | Inventario sucursal 1 + 2 | 2 filas tabla §B completas |
| **D2** | Inventario sucursal 3 + 1 vale/cobro suc. 2 | Tabla §B + §C |
| **D3** | Vale/cobro suc. 3 + capacitación + Guardián + sign-off | §E + §G |

---

*SD-1 cerrado = Fase 1 VERTEX Bastión lista para demo Chilemat (SD-2 comercial).*
