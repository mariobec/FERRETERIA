# Completar base de productos (maestro materiales)

Ver también `docs/MAESTRA_COMPLETAR_BASE.md` si está disponible.

Unifica **historial de compras**, **catálogo consolidado** (EAN, familia) y el **ERP**:

| Operación | Campo / tabla |
|-----------|----------------|
| Escanear POS / enrolamiento | `productos.codigo_barra` |
| Stock tienda/bodega | `stock_por_almacen` (0 al crear) |
| Costo | `productos.precio_compra` |
| Código factura proveedor | `producto_codigo_proveedor` |

## Archivos en `docs/Maestro Materiales/`

- `Maestra_Ferreteria_Santo_Domingo.xlsx` — **Hoja1** (compras)
- `Consolidacion_Maestro_Materiales.xlsx` — catálogo EAN

## Comando principal

```powershell
.\venv\Scripts\python.exe scripts\maestra_completar_base_maxima.py
.\venv\Scripts\python.exe scripts\maestra_completar_base_maxima.py --aplicar --dry-run
.\venv\Scripts\python.exe scripts\maestra_completar_base_maxima.py --aplicar --limit-enriquecer 2000 --limit-crear-activo 100 --limit-crear-pendiente 200
```

Salida: `respaldos/maestra_completar/`

## Fases legacy

`maestra_fase_a_enriquecer.py` → `maestra_fase_b_aplicar.py` → `maestra_fase_c_crear_pendientes.py`

El script **completar_base_maxima** las integra y añade consolidación + EAN en barra.
