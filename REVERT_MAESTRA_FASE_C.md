# Revertir Fase C — Productos pendientes maestra

Crea productos con `codigo_interno` que empieza por **`MAESTRA-PEND-`**, `activo=False`, y vínculos `maestra-fase-c`.

## Revertir

```powershell
cd "C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
.\venv\Scripts\python.exe scripts\maestra_fase_c_revertir.py
```

## Activar productos validados (manual en ERP)

Cuando valide una fila en Excel `Maestra_productos_pendientes_creados.xlsx`:
1. Busque el producto por `codigo_interno` MAESTRA-PEND-…
2. Corrija nombre / precios si hace falta
3. Marque **activo = Sí**
4. Asigne código de barras definitivo para pistola si difiere del código factura
