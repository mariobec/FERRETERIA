-- Monto de línea en POS. Requiere columna descuento (migración 2026_05_04_detalle_ventas_descuento.sql).
-- Error sin esta columna: Unknown column 'detalle_ventas.subtotal' in 'field list'

ALTER TABLE detalle_ventas
  ADD COLUMN subtotal DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Monto línea: cantidad * precio_unitario * (1 - descuento/100)'
  AFTER descuento;

-- WHERE con clave primaria: exigido por MySQL Workbench en "Safe Updates" (evita error 1175).
UPDATE detalle_ventas
SET subtotal = cantidad * precio_unitario * (1 - IFNULL(descuento, 0) / 100)
WHERE id > 0;
