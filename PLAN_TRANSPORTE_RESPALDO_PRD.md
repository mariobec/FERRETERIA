# Transporte a productivo y respaldo (por hacer)

**Estado:** documentado · **no ejecutar** hasta ventana acordada y sign-off QAS.  
**Paisaje:** DEV → QAS (SAMBOX) → PRD (Render + Neon). Regla: `.cursor/rules/entornos-desarrollo-sambox-productivo.mdc`.

---

## Qué sí / qué no llevar a PRD de golpe

| Tipo de cambio | ¿Cambia tablas Neon? | Llevar a PRD |
|----------------|----------------------|--------------|
| Features ya probadas en QAS (portal, vitrina, etc.) | Solo si hubo OT-Datos | Sí, vía OT tras sign-off |
| Refactor oleada 1 (`models/venta_caja.py`) | **No** (solo código) | Sí, **solo** tras QAS + tag checkpoint |
| Sacar los 64 modelos de `app.py` en un solo paso | No, pero alto riesgo imports | **No** — usar oleadas 1→4 |
| Sync BD local → Neon | **Sí** | Solo OT-Datos + dump previo |

---

## Respaldo obligatorio (volver atrás si hay error)

### 1. Código

```powershell
git tag checkpoint/pre-cambio-YYYYMMDD
# opcional: git push origin checkpoint/pre-cambio-YYYYMMDD
```

**Rollback código:** `git checkout` al tag o revert del merge en `main` · Render vuelve al deploy del commit anterior.

### 2. Base de datos productiva (Neon)

Antes de **OT-Datos** o `sync_local_neon_render.py`:

```powershell
python scripts/backup_neon_dump.py --url-key NEON_DATABASE_URL --out-dir respaldos\pre_prd_YYYYMMDD
```

**Rollback datos:** `pg_restore` del `.dump` guardado (ver `scripts/instalar_piloto_tienda.bat` / `restaurar_piloto_tienda.bat` en paquetes OT).

### 3. Paquete OT (manifiesto completo)

```powershell
.\scripts\ot_emitir.ps1 -Destino qas   # primero QAS
# tras SIGNOFF_QAS.txt:
.\scripts\ot_emitir.ps1 -Destino prd -OtQasRef "OT-XXXX-qas"
```

Salida: `respaldos/transporte/OT-.../` (`01_CODIGO`, `02_DATOS`, `orden.json`, instrucciones).

**No importar en PRD sin OK QAS.**

---

## Checklist por tipo de OT

### OT-Código (refactor, portal, POS UI, etc.)

- [ ] Tag `checkpoint/pre-...` en DEV
- [ ] `pytest -m smoke` + rutas críticas venta/caja si toca POS
- [ ] OT → SAMBOX → prueba piso (emitir vale, cobrar, caja)
- [ ] `SIGNOFF_QAS.txt` en carpeta OT
- [ ] Deploy Render (push tag/commit acordado)
- [ ] Tag `checkpoint/post-...` tras OK PRD

### OT-Datos (catálogo, sync Neon)

- [ ] Dump Neon **antes** (`backup_neon_dump.py`)
- [ ] Pausar escrituras en Render durante sync (si aplica)
- [ ] `--verify-only` tras sync
- [ ] Plan de rollback = ruta del dump pre-sync anotada en `orden.json`

---

## Relación con refactor `app.py`

- Oleada 1 **no requiere** migración de esquema en Neon.
- Mismo flujo OT-Código que cualquier release; respaldo Neon recomendable por precaución, no obligatorio si **solo** cambia Python.
- Plan técnico oleada 1: [`PLAN_REFACTOR_OLEADA1_VENTA_CAJA.md`](PLAN_REFACTOR_OLEADA1_VENTA_CAJA.md).

---

## Referencias en repo

- `scripts/ot_emitir.ps1`
- `scripts/backup_neon_dump.py`
- `scripts/sync_local_neon_render.py`
- `scripts/CHECKLIST_MIGRACION_PC.md`
- `respaldos/transporte/` (OT históricas)
