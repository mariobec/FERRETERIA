# Importar RCV SII → borradores de recepción

**Script:** `scripts/importar_rcv_sii.py`  
**Servicio:** `services/rcv_sii_import_service.py`  
**SQL Neon:** `sql/2026_05_22_rcv_sii_recepciones.sql`

## Qué hace

1. Lee CSV/TXT del **Registro de Compras** (export portal SII; separador `;` habitual).
2. Detecta columnas: Tipo Doc, RUT emisor, Folio, Fecha, Monto Neto, Monto Total, Razón social.
3. Por cada **factura de compra** (tipos 33, 34, 46 por defecto) crea `RecepcionCompra` en estado **`Pendiente de Items`** (sin líneas).
4. Resuelve o crea **Proveedor** por RUT (columna `proveedores.rut`).
5. Evita duplicados: mismo proveedor + Factura + folio.

Luego en **Recepciones → detalle**: adjuntar PDF y **Importar líneas (IA)** — el match usa folio/proveedor ya cargados.

## Uso

```bash
# 1) Migración (una vez en Neon)
python scripts/apply_sql_neon.py sql/2026_05_22_rcv_sii_recepciones.sql

# 2) Simulación
python scripts/importar_rcv_sii.py --input "compras_rcv_2026.csv" --dry-run

# 3) Import real (producción Neon / www.lhexia.cl)
python scripts/importar_rcv_sii.py --neon --input "compras_rcv_2026.csv"

# Solo facturas electrónicas 33
python scripts/importar_rcv_sii.py -i compras.csv --tipos 33
```

## Archivo SII

- Exportar **compras** del RCV (no ventas).
- Primera fila = encabezados; delimitador `;` o `,`.
- Si el Excel usa columna genérica `SKU` / `Codigo`, usar `--maestro` no aplica aquí; el parser mapea alias `Rut Emisor`, `Tipo Doc`, etc.

## Estados recepción

| Estado | Significado |
|--------|-------------|
| Pendiente de Items | Borrador RCV: falta adjuntar PDF y líneas (IA o manual) |
| Incompleta | Ya tiene al menos una línea |
| Finalizada | Cerrada |
| Archivado RCV | Histórico tributario (fuera de cola bodega) |

## Listado `/recepciones` (D2)

- Filtros: estado, año (2025/2026), orden **fecha** o **monto (Pareto)**.
- Paginación: 50 por página.
- Atajo **Pareto 2026 (monto)** → top facturas del año para checklist D2.
- **Archivar RCV 2025 (lote)** → pasa Pendiente de ítems 2025 a `Archivado RCV`.

Migración enum archivado (una vez Neon):

```bash
python scripts/apply_sql_neon.py sql/2026_05_22_recepciones_archivado_rcv.sql
```
