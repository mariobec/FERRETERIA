# Revertir Fase B — Maestra → ERP

Fase B **sí modifica la BD**:
- Inserta/actualiza `producto_codigo_proveedor` (usuario `maestra-fase-b`)
- Actualiza `precio_compra` y puede completar `categoria` / `subcategoria` vacías
- Bitácora de costo con observación de importación maestra

## Revertir con script (recomendado)

Usa el backup de la misma corrida:

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\venv\Scripts\python.exe scripts\maestra_fase_b_revertir.py --dry-run
.\venv\Scripts\python.exe scripts\maestra_fase_b_revertir.py
```

Carpeta típica: `respaldos\maestra_fase_b\<fecha_hora>\backup_productos_antes.json` y `meta.json` (incluye `proveedores_creados` si se crearon al importar).

La corrida **2026-05-27_1522** creó proveedores nuevos (IDs en `meta.json`); el revert los elimina si no tienen otros vínculos.

## Checkpoint git (código)

Tag antes de Fase B: **`checkpoint/maestra-fase-b-pre-2026-05-27`**

Tag antes de Fase A: **`checkpoint/maestra-fase-a-pre-2026-05-27`**

```powershell
git checkout checkpoint/maestra-fase-b-pre-2026-05-27 -- scripts/maestra_fase_b_aplicar.py
```

(Los datos en PostgreSQL no se revierten con git; use `maestra_fase_b_revertir.py`.)

## Volver a aplicar

```powershell
.\venv\Scripts\python.exe scripts\maestra_fase_b_aplicar.py --dry-run
.\venv\Scripts\python.exe scripts\maestra_fase_b_aplicar.py
```
