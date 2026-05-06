-- Descuento por línea en POS (%). Alinear BD con modelo DetalleVenta en app.py.
-- Error sin esta columna: Unknown column 'detalle_ventas.descuento' in 'field list'
-- Si MySQL devuelve 1060 Duplicate column 'descuento': la columna ya existe, no ejecutes este bloque.
-- Después, si falta subtotal: ejecutar 2026_05_05_detalle_ventas_subtotal.sql

ALTER TABLE detalle_ventas
  ADD COLUMN descuento DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Porcentaje de descuento 0-100'
  AFTER precio_unitario;
