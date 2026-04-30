# Guia rapida: cargar 5000 productos desde Excel

## Objetivo

Tomar un Excel "desordenado", homologarlo automaticamente y cargarlo al ERP sin trabajo manual fila por fila.

## 1) Instalar dependencias

En tu entorno virtual:

```bash
pip install -r requirements.txt
```

## 2) Ejecutar homologacion

```bash
python homologar_productos_excel.py --input "ruta/a/tu/archivo.xlsx" --output "productos_homologados.csv"
```

Opcionalmente genera archivo de errores:

```bash
python homologar_productos_excel.py --input "ruta/a/tu/archivo.xlsx" --output "productos_homologados.csv" --errores "productos_errores.csv"
```

## 3) Revisar resultado

- `productos_homologados.csv`: listo para subir en **Productos > Carga CSV**.
- `productos_errores.csv`: filas sin `nombre` o `codigo_barra` (corregir y volver a homologar).

## 4) Cargar al ERP

1. Entra a `Productos`.
2. Usa la opcion de carga masiva CSV.
3. Selecciona `productos_homologados.csv`.

## Columnas objetivo del ERP

- nombre
- codigo_barra
- precio_compra
- precio_venta
- precio_mayoreo
- unidad_compra
- unidad_venta
- factor_conversion
- stock
- categoria
- subcategoria
- ubicacion_pasillo
- ubicacion_estante
- ubicacion_nivel

## Notas utiles

- El script mapea aliases comunes automaticamente (`descripcion`, `sku`, `pvp`, etc.).
- Normaliza numeros con formato chileno/internacional.
- Si `precio_mayoreo` viene vacio, usa `precio_venta`.
- Si faltan unidades, usa `Unidad` por defecto.
