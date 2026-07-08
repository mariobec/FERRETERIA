# Chilemat — cargas locales (masivo/selectivo)

Script principal: `scripts/chilemat_cargas_local.py`

## 1) Sincronizar staging Chilemat (sin tocar ERP)

```powershell
cd "c:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion sync_staging
```

Incremental:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion sync_staging --solo-faltantes
```

## 2) Reset total (borra y recarga todo desde Chilemat)

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion reset_total --forzar
```

Sin llamar API (usa staging actual):

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion reset_total --forzar --sin-sync
```

## 3) Taxonomía ERP (categorías/subcategorías)

Reemplazar completa:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion reset_taxonomia --forzar
```

Reemplazar solo un rubro:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion reset_taxonomia --forzar --rubro "Pinturas"
```

## 4) Borrado de productos ERP

Masivo (TRUNCATE CASCADE):

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion borrar_productos --masivo --forzar
```

Selectivo por rubro:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion borrar_productos --rubro "Pinturas"
```

Selectivo por búsqueda:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion borrar_productos --q "barniz"
```

## 5) Carga de productos ERP (desde staging Chilemat)

Carga masiva:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion cargar_productos
```

Carga selectiva por rubro:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion cargar_productos --rubro "Pinturas"
```

Carga selectiva por filtro + límite:

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion cargar_productos --q "broca" --limit 200
```

## 6) Preview (sin escribir)

```powershell
.\.venv\Scripts\python.exe scripts\chilemat_cargas_local.py --accion cargar_productos --rubro "Pinturas" --preview
```

---

## Notas importantes

- El script está pensado para **BD local**.
- `reset_total` y `reset_taxonomia` requieren `--forzar`.
- `borrar_productos --masivo` requiere `--forzar`.
- En selectivo, el set se arma desde staging Chilemat usando filtros `--rubro`, `--rubro-vtex-id`, `--q`, `--limit`.

