# Revertir Fase A — Maestra de compras

La Fase A **no modifica la base de datos** ni el catálogo ERP. Solo agrega:

- `scripts/maestra_fase_a_enriquecer.py`
- Carpeta `respaldos/maestra_fase_a/<fecha>/` con CSV y `RESUMEN.md`
- Este archivo

## Si algo falla o no te sirve el resultado

1. **Borrar salidas** (opcional):
   ```powershell
   Remove-Item -Recurse -Force "respaldos\maestra_fase_a"
   ```

2. **Quitar script y doc** (opcional):
   ```powershell
   Remove-Item scripts\maestra_fase_a_enriquecer.py
   Remove-Item REVERT_MAESTRA_FASE_A.md
   ```

3. **Volver al código anterior** (si commiteaste otros cambios mezclados):
   ```powershell
   git checkout checkpoint/maestra-fase-a-pre-2026-05-27 -- .
   ```
   O solo archivos nuevos:
   ```powershell
   git clean -fd respaldos/maestra_fase_a
   ```

## Checkpoint git

Tag: **`checkpoint/maestra-fase-a-pre-2026-05-27`**

Creado **antes** de ejecutar Fase A. Para ver el commit:
```powershell
git show checkpoint/maestra-fase-a-pre-2026-05-27 --no-patch
```

## Volver a generar

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\venv\Scripts\python.exe scripts\maestra_fase_a_enriquecer.py
```

Ruta maestra por defecto: `C:\ERP FERRETERIA\Maestra_Ferreteria_Santo_Domingo.xlsx`
