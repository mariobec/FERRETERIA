# Prompt para Cursor — PC nuevo (cargar datos desde USB)

Copia **todo el bloque** entre las líneas `---` y pégalo en un chat nuevo de Cursor en el PC nuevo.

---

```
Contexto LhexIA ERP (Ferretería Santo Domingo). En este PC nuevo ya tengo:
- Cursor funcionando
- PostgreSQL instalado con base vacía (o recién creada)
- Repo clonado desde GitHub: https://github.com/mariobec/FERRETERIA.git
- venv y dependencias pueden faltar — instálalas si hace falta

Los datos están VACÍOS. Debo cargar todo desde un USB de migración.

## USB de migración

Ruta típica (ajusta la letra si no es E:):
`E:\LhexIA_Migracion_SD_20260525\`

Estructura:
- `01_BASE_DATOS\neon_*.dump` — volcado Neon (PRIORIDAD: misma BD que Render/celular)
- `01_BASE_DATOS\local_ferreteria_*.dump` — volcado Postgres de la PC vieja (respaldo; NO mezclar sin plan)
- `01_BASE_DATOS\verify_local_vs_neon.txt` y `AVISO_LOCAL_VS_NEON.txt` — local y Neon estaban distintos
- `02_CONFIG\.env.local` — credenciales (copiar al repo, no subir a Git)
- `03_CARGA_DATOS\` — CSV y datos RCV
- `04_DOCUMENTACION\CHECKLIST_MIGRACION_PC.md`
- `LEEME_MIGRACION.txt`

## Objetivo

1. Restaurar en PostgreSQL local el dump de **Neon** (paridad con producción Render).
2. Copiar y ajustar `.env.local` (DATABASE_URL=localhost, NEON_DATABASE_URL=Neon).
3. Verificar esquema y conteos (`sync_local_neon_render.py --verify-only`).
4. Probar login ERP y smoke test.
5. NO fusionar local→Neon ni Neon→local sin mi confirmación explícita (había divergencia de datos).

## Reglas

- Ejecuta comandos tú mismo en PowerShell; no solo listes pasos.
- Usa rutas absolutas que existan en este PC; si el USB tiene otra letra o fecha, búscala con `Get-ChildItem E:\, F:\, ... -Filter LhexIA_Migracion_SD_*`.
- Si `pg_restore` o `pg_dump` no están en PATH, busca en `C:\Program Files\PostgreSQL\*\bin\`.
- Nombre de BD local sugerido: `ferreteria_sd` o el que diga `.env.local` del USB.
- Después del restore: `python scripts/schema_sync_neon.py` si hace falta columnas nuevas.
- No imprimas contraseñas del `.env.local` en el chat.
- Al terminar: resumen (tablas con conteos, login OK sí/no, qué archivo dump usaste).

## Pasos que debes seguir

### A. Preparar entorno
- `cd` a la raíz del repo (donde está `app.py`)
- Activar venv si existe; si no: `python -m venv venv` y `pip install -r requirements.txt`
- Copiar `USB\02_CONFIG\.env.local` → raíz del repo
- Editar `.env.local`: `DATABASE_URL` debe apuntar a **localhost** y la BD que creaste; mantener `NEON_DATABASE_URL` del USB

### B. Crear BD vacía (si no existe)
- Crear rol/BD en PostgreSQL según credenciales del `.env.local`
- Confirmar conexión con `psql` o script Python mínimo

### C. Restaurar dump Neon (principal)
- Identificar el archivo `neon_*.dump` más reciente en `01_BASE_DATOS`
- `pg_restore --clean --if-exists --no-owner -h localhost -U ... -d ferreteria_sd "ruta\neon_....dump"`
- Si hay errores de rol/owner, documentar y continuar si las tablas quedaron pobladas

### D. Post-restore
- `python scripts/schema_sync_neon.py` (con NEON_DATABASE_URL en .env.local)
- `python scripts/sync_local_neon_render.py --verify-only` — debe acercar conteos local vs Neon; si falla, explicar por qué
- Contar filas en: usuarios, productos, ventas, clientes, caja

### E. Probar aplicación
- Arrancar Flask (`python app.py` o como indique el proyecto)
- Probar login con usuario admin del dump
- `pytest tests/test_agente_operador.py -q` si la BD de test es la misma o está configurada

### F. Archivos no-SQL
- Confirmar que `03_CARGA_DATOS` está accesible (no hace falta reimportar todo si ya está en el dump; solo verificar)

## No hacer sin permiso

- `python scripts/sync_local_neon_render.py` **sin** `--verify-only` (pisa Neon)
- Restaurar `local_ferreteria_*.dump` encima del neon sin plan de fusión
- Commit de `.env.local`

## Entregable final

Tabla resumen:
| Item | Estado |
|------|--------|
| USB detectado | ruta |
| Dump restaurado | archivo |
| usuarios / productos / ventas (conteos) | números |
| verify-only | OK / falla |
| Login ERP | OK / falla |
| Próximo paso recomendado | una línea |

Empieza detectando la ruta del USB y el dump neon_*.dump en este PC.
```

---

## Variante corta (si el chat es largo)

```
PC nuevo: repo LhexIA ERP desde git, Postgres vacío. USB en E:\LhexIA_Migracion_SD_20260525 con neon_*.dump y .env.local en 02_CONFIG. Restaura el dump Neon en local, configura .env.local (DATABASE_URL localhost), schema_sync_neon, verify-only, prueba login. Local y Neon estaban distintos — solo Neon como verdad. Ejecuta comandos tú mismo. No sync sin --verify-only sin mi OK.
```
