# Checklist migración — datos completos + PC nuevo (apagar PC ex tienda)

**Objetivo:** Llevar **usuarios, ventas, productos, cajas, clientes, alertas Operador** y el resto de la BD al **PC nuevo**, con **PostgreSQL local espejo** de Neon, para **apagar esta máquina** y seguir desarrollo (y opcionalmente Ollama) en el PC nuevo.

**Repo:** `https://github.com/mariobec/FERRETERIA.git`  
**Checklist en Git:** `scripts/CHECKLIST_MIGRACION_PC.md` (haz `git pull` en el PC nuevo)

> **No subir a Git:** `.env.local`, archivos `.dump`, carpeta `respaldos/` con contraseñas.

---

## Antes de empezar — ¿De dónde salen los datos?

| Fuente | Cuándo es la “verdad” |
|--------|------------------------|
| **Neon** (nube) | Si POS/Render y Guardián ya operan contra Neon → **prioridad** |
| **Postgres local** (esta PC) | Si hubo días trabajando solo en local sin sync |
| **Ambos distintos** | Hay que alinear **antes** de apagar esta PC (ver Tarea 0) |

Comando de diagnóstico (en **esta PC**, con `.env.local` con `DATABASE_URL` local + `NEON_DATABASE_URL`):

```powershell
cd "D:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
python scripts/sync_local_neon_render.py --verify-only
```

Interpretación:

- Si **local = neon** en `usuarios`, `ventas`, `productos`, etc. → puedes volcar desde **cualquiera** (recomendado: Neon con `backup_neon_dump.py`).
- Si **local ≠ neon** → **no apagues** hasta decidir: subir local→Neon (`sync_local_neon_render.py` **pisa Neon**) o bajar Neon→local (`pg_restore` desde dump de Neon).

---

## Tarea 0 — Alinear fuente de verdad (esta PC, hoy)

- [ ] `.env.local` respaldado en USB (sin subir a Git)
- [ ] `python scripts/sync_local_neon_render.py --verify-only`
- [ ] Anotar tablas con conteo distinto (si hay `NO`)
- [ ] Decisión firmada:
  - [ ] **A)** Neon manda → migración desde Neon (`backup_neon_dump.py`)
  - [ ] **B)** Local manda → `sync_local_neon_render.py` (sin `--verify-only`) y luego backup Neon
  - [ ] **C)** Solo desarrollo en PC nuevo contra Neon (sin Postgres local) — no es espejo offline
- [ ] Avisar si Render está desplegado; en sync masivo conviene **pausar** o evitar ventas durante copia

**Tablas que el script verifica** (muestra): `productos`, `clientes`, `ventas`, `detalle_ventas`, `cotizaciones`, OC, recepciones.  
El **dump completo** incluye además: `usuarios`, `roles`, `caja`, `movimiento_caja`, `agente_ejecuciones`, `erp_audit_log`, stock, etc.

---

## Tarea 1 — Exportar todo desde esta PC (antes de apagarla)

### 1.1 Respaldo completo de Neon (recomendado si Neon es la verdad)

Requisitos: `pg_dump` (instalado con PostgreSQL). En `.env.local` usar URL **directa** (host **sin** `-pooler`).

```powershell
cd "D:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
python scripts/backup_neon_dump.py
# Salida: respaldos/neon_YYYYMMDD_HHMMSS.dump
```

- [ ] Dump generado OK (anotar ruta y tamaño MB)
- [ ] Copiar carpeta `respaldos\` a USB / red hacia PC nuevo

### 1.2 Respaldo Postgres local (por si local tenía datos distintos)

```powershell
# Ajustar usuario, BD y ruta según tu instalación local
$env:PGPASSWORD = "TU_PASSWORD_LOCAL"
pg_dump -h localhost -p 5432 -U postgres -d ferreteria_sd -Fc --no-owner --no-acl -f "respaldos\local_YYYYMMDD.dump"
```

- [ ] Dump local generado (opcional pero prudente)
- [ ] Copiado a USB

### 1.3 Archivos fuera de la BD (esta PC)

- [ ] `.env.local` y `.env`
- [ ] Carpeta `CARGA DE DATOS\` (CSV maestros, importaciones)
- [ ] `datos_rcv\` / facturas SII si los usan
- [ ] Certificados / CAF / `.pfx` si facturación electrónica local
- [ ] `respaldos\` (dumps)
- [ ] (Opcional) `static/uploads` o rutas de adjuntos si existen en el proyecto
- [ ] Exportar lista tareas Windows **LhexIA-Operador-SD** (captura pantalla o XML) por si replicás Operador en PC nuevo

### 1.4 Código

- [ ] `git push origin main` hecho en esta PC (último commit en GitHub)
- [ ] Anotar commit: `git log -1 --oneline`

---

## Tarea 2 — PC nuevo: espejo + desarrollo (reemplaza esta máquina)

### 2.1 Software base

- [ ] Git, Python 3.11+, Cursor
- [ ] **PostgreSQL** instalado (servicio automático)
- [ ] Crear BD local, ej. `ferreteria_sd` y usuario con clave
- [ ] (Opcional) **Ollama** + modelo 3B si esta PC asume el rol de enrich (antes en ex tienda)

### 2.2 Clonar proyecto

```powershell
git clone https://github.com/mariobec/FERRETERIA.git sistema_ventas_limpio
cd sistema_ventas_limpio
git pull origin main
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- [ ] Repo en commit reciente (`cbf2658+` o posterior)
- [ ] venv OK

### 2.3 Restaurar datos (espejo local ← Neon)

Pegar `.env.local` desde USB y **ajustar** `DATABASE_URL` al Postgres del PC nuevo.

```powershell
# Crear BD vacía en PostgreSQL antes del restore
# Ejemplo restore (ajustar rutas y nombres):
$env:PGPASSWORD = "TU_PASSWORD_LOCAL"
pg_restore --clean --if-exists --no-owner -h localhost -U postgres -d ferreteria_sd "D:\ruta\respaldos\neon_YYYYMMDD_HHMMSS.dump"
```

- [ ] `pg_restore` terminó sin error fatal
- [ ] `python scripts/schema_sync_neon.py` (alinea columnas en Neon si hace falta; con `NEON_DATABASE_URL` en `.env.local`)
- [ ] Ajustar `.env.local` modo **espejo**:

```env
DATABASE_URL=postgresql://USER:PASS@localhost:5432/ferreteria_sd
NEON_DATABASE_URL=postgresql://...@....neon.tech/neondb?sslmode=require
```

- [ ] `python scripts/sync_local_neon_render.py --verify-only` → conteos **local = neon**
- [ ] Si falla verify: revisar si restore incompleto o Neon cambió durante migración

### 2.4 Verificación de datos críticos (manual o SQL)

En local (pgAdmin o `psql`), comprobar que existen filas recientes:

- [ ] `usuarios` (login admin / cajeros)
- [ ] `roles`, `permisos`, `rol_permisos`
- [ ] `productos`, `stock_por_almacen`
- [ ] `clientes`, `proveedores`
- [ ] `caja`, `movimiento_caja`, `ventas`, `detalle_ventas`
- [ ] `agente_ejecuciones` (alertas Guardián / Operador)
- [ ] `recepciones_compra` / OC si los usan

### 2.5 Arrancar ERP en PC nuevo (prueba)

```powershell
# .env.local con DATABASE_URL=localhost para probar espejo offline
$env:FLASK_DEBUG = "0"
python app.py
# o flask run — según cómo lo ejecutabas
```

- [ ] Login con usuario existente
- [ ] Buscar producto, ver stock
- [ ] Abrir historial ventas / caja
- [ ] `pytest tests/test_agente_operador.py -q` (con BD de test o QA según tu `.env`)

### 2.6 Paridad con Render (sigue en la nube)

- [ ] Render `DATABASE_URL` = **misma Neon** (no cambiar sin querer)
- [ ] Deploy `main` OK (cierre caja → alerta inmediata, Guardián 15 s)
- [ ] Celular Guardián apunta a Render (no a IP local)

**Con internet:** Neon + Render = operación tienda y móvil.  
**PC nuevo local** = espejo para desarrollo y contingencia sin internet.

### 2.7 Operador + Ollama (si los movés al PC nuevo)

- [ ] `.env.local`: `AGENTE_OPERADOR_USE_NEON=1`, `AGENTE_OLLAMA_ENABLED=1`
- [ ] Tarea programada: `python scripts/agente_operador_ciclo.py` cada 10 min
- [ ] `python scripts/verificar_operador_ollama.py`

---

## Tarea 3 — Apagar PC ex tienda (solo cuando)

- [ ] Tarea 2.4 y 2.5 OK
- [ ] `--verify-only` OK (local = neon) o decisión documentada si solo usás Neon en dev
- [ ] USB con dumps guardado en lugar seguro
- [ ] Operador desactivado **aquí** o tarea eliminada (evitar dos PCs escribiendo enrich)
- [ ] Documentar: “BD espejo vive en PC nuevo; Neon sigue en Render”

---

## Qué NO hace falta copiar de esta PC

| Item | Motivo |
|------|--------|
| Carpeta completa del repo sin Git | `git clone` en PC nuevo |
| `venv/` | Recrear con pip |
| `node_modules/` | Reinstalar si hace falta frontend |
| Esta PC como “servidor nube” | Neon sigue siendo la nube |

---

## Comandos rápidos (referencia)

```powershell
# Verificar alineación local vs Neon
python scripts/sync_local_neon_render.py --verify-only

# Backup Neon → archivo .dump
python scripts/backup_neon_dump.py

# Subir espejo local → Neon (CUIDADO: pisa tablas en Neon)
python scripts/sync_local_neon_render.py

# Esquema tablas nuevas en Neon
python scripts/schema_sync_neon.py
```

---

## Flujo operativo post-migración

```text
Tienda / celular → Render → Neon (oficial)
PC nuevo dev     → Postgres local (espejo) + Cursor
Sin internet     → Flask local + DATABASE_URL=localhost
Vuelta internet  → verify-only; sync solo si procedimiento definido
```

---

## Hecho cuando

| # | Criterio |
|---|----------|
| 0 | Decisión Neon vs local documentada |
| 1 | Dumps + `.env.local` + CSV en USB |
| 2 | PC nuevo: restore OK, login ERP, verify conteos |
| 3 | PC ex tienda apagada sin perder datos |

---

## Si algo sale mal

| Problema | Acción |
|----------|--------|
| `pg_dump` falla con pooler | Usar `NEON_DATABASE_URL` **sin** `-pooler` en `.env.local` |
| `verify-only` distinto | No apagar PC vieja; repetir Tarea 0 |
| Login falla en PC nuevo | Revisar `usuarios` en local; `SECRET_KEY` igual que Render si compartís cookies |
| Render y local divergen después | Operar solo Neon en producción; reprogramar sync puntual |
