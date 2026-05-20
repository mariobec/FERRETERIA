# ADR-001 — POS Offline-First (Continuidad Operacional)

**Estado:** Aprobado (2026-05-20)  
**Decisores:** Negocio Santo Domingo / LhexIA  
**Contexto:** [`ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md`](ROADMAP_POS_CONTINUIDAD_OPERACIONAL.md)

---

## Contexto

El POS depende de Render + Neon y de servicios SII. Cortes de ISP, caídas de hosting o indisponibilidad de Maullín no deben detener ventas en mostrador. La política tributaria ya está centralizada en `core/domain/shared/iva_chile.py` (`desglosar_iva_clp`, commit `d9a9594`).

---

## Decisión

### 1. Persistencia primaria en el navegador del POS

- **IndexedDB** gestionado con **Dexie.js 4.x**.
- Nombre de BD: `lhexia_pos_offline`, schema version `1`.
- **SQLite** solo como agente opcional en PC Windows (fase posterior); no en el browser.

### 2. Fuente de verdad operativa en contingencia

| Modo | Fuente de verdad ventas | Catálogo precios |
|------|-------------------------|------------------|
| ONLINE | Neon (PostgreSQL) | Neon + cache local |
| CONTINGENCIA | IndexedDB (`ventas_contingencia`) | IndexedDB (`productos`) |

Al reconectar, Neon vuelve a ser fuente de verdad **tras sync exitoso**.

### 3. Cálculo monetario offline

- Réplica JS: `static/js/offline/iva-chile.js`.
- **Prohibido** `float` / `Math.round` banker's en montos CLP; enteros + redondeo half-up explícito.
- Tests de paridad Python ↔ JS obligatorios en CI (Node si disponible; vectors documentados si no).

### 4. Identificación de ventas offline

- `client_uuid` (UUID v4) — idempotencia en servidor.
- `numero_local`: `OFF-{YYYYMMDD}-{caja_id}-{seq4}`.
- Estado local: `PENDIENTE_SINCRONIZACION` → `ENVIADA` | `ERROR`.

### 5. Circuit breaker (resumen)

- Ping: `GET /api/health/ping`, timeout 3 s, cada 20 s.
- 3 fallos consecutivos → `MODO_CONTINGENCIA`.
- SII FE en circuito separado; **no bloquea** venta en contingencia.

### 6. Límites v1 (explícitos)

| Permitido offline | Bloqueado offline |
|-------------------|-------------------|
| Venta efectivo/débito con espejo catálogo | Emisión DTE / consulta SII |
| Descuento preautorizado en producto | Descuento supervisor PIN (API) |
| Ticket interno “NO VÁLIDO TRIBUTARIO” | Crédito con validación cupo remota |
| Sync catálogo si hubo red al inicio | Anulación remota de vales |

### 7. Stock en contingencia

- `stock_referencial` en espejo — **informativo**.
- Al sync: política **servidor gana**; alerta kardex si queda negativo.

### 8. FE / SII

- Sin timbraje (Form. 3230 pendiente): ventas online igual pueden quedar `PENDIENTE_ENVIO`.
- Post-sync offline: encolar `post_cobro_emision_fe` solo con red + CAF.

---

## Consecuencias

### Positivas

- Continuidad en mostrador ante caídas cloud.
- Misma política IVA que DTE (menos Status 7).
- Adapter pattern (`OfflineStorePort`) desacopla UI de Dexie.

### Negativas / costos

- Complejidad sync y pruebas E2E offline.
- Catálogo puede desfasarse hasta 60 min.
- Dos fuentes temporales de verdad → requiere Fase 4 (auditoría).

---

## Alternativas rechazadas

| Alternativa | Motivo rechazo |
|-------------|----------------|
| Solo localStorage | Sin índices; límite tamaño |
| PWA Service Worker como DB | No apto para cola transaccional |
| SQLite en browser (sql.js) | Pesado; peor soporte |
| Venta offline sin IVA desglosado | Status 7 / conciliación imposible |
| Sync bidireccional catálogo | Fuera de alcance v1 |

---

## Cumplimiento

- [x] ADR documentado
- [x] Contrato API v1: [`OFFLINE_API_V1_CONTRACT.md`](OFFLINE_API_V1_CONTRACT.md)
- [x] Paridad IVA JS: `static/js/offline/iva-chile.js`
- [ ] Tag `checkpoint/offline-design-2026-05-20` tras merge
- [ ] Fase 1: `indexeddb-store.js` (siguiente sprint)

---

*ADR LhexIA ERP — TEC-OFFLINE*
