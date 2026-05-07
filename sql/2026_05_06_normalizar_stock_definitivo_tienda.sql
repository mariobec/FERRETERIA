-- NORMALIZACION DEFINITIVA DE STOCK POR ALMACEN (TIENDA/BODEGA)
-- Objetivo: dejar stock_por_almacen como fuente única para POS/cobro.
--
-- Regla de normalización:
-- 1) Para productos SIN ninguna fila en stock_por_almacen:
--    - crear fila TIENDA = productos.stock (si stock > 0, si no 0)
--    - crear fila BODEGA = 0
-- 2) Para productos que ya tienen filas por almacén:
--    - no se sobrescriben cantidades existentes
-- 3) Recalcular productos.stock = SUM(stock_por_almacen)
--
-- Ejecutar una vez antes de operar en modo definitivo.

SET @COD_TIENDA := 'TIENDA';
SET @COD_BODEGA := 'BODEGA';

SET @ID_TIENDA := (
  SELECT id FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_TIENDA AND activo = 1
  ORDER BY id LIMIT 1
);

SET @ID_BODEGA := (
  SELECT id FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_BODEGA AND activo = 1
  ORDER BY id LIMIT 1
);

INSERT INTO almacenes (codigo, nombre, activo)
SELECT @COD_TIENDA, 'Tienda / Mostrador', 1
WHERE @ID_TIENDA IS NULL;

INSERT INTO almacenes (codigo, nombre, activo)
SELECT @COD_BODEGA, 'Bodega', 1
WHERE @ID_BODEGA IS NULL;

SET @ID_TIENDA := (
  SELECT id FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_TIENDA AND activo = 1
  ORDER BY id LIMIT 1
);

SET @ID_BODEGA := (
  SELECT id FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_BODEGA AND activo = 1
  ORDER BY id LIMIT 1
);

-- Productos que aún no tienen ninguna fila por almacén.
DROP TEMPORARY TABLE IF EXISTS tmp_prod_sin_filas;
CREATE TEMPORARY TABLE tmp_prod_sin_filas (
  id_producto INT PRIMARY KEY,
  stock_catalogo INT NOT NULL
);

INSERT INTO tmp_prod_sin_filas (id_producto, stock_catalogo)
SELECT p.id, GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0)
FROM productos p
LEFT JOIN (
  SELECT DISTINCT id_producto
  FROM stock_por_almacen
) s ON s.id_producto = p.id
WHERE s.id_producto IS NULL;

-- Insertar TIENDA para legacy sin filas.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT t.id_producto, @ID_TIENDA, t.stock_catalogo
FROM tmp_prod_sin_filas t
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- Insertar BODEGA=0 para legacy sin filas.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT t.id_producto, @ID_BODEGA, 0
FROM tmp_prod_sin_filas t
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- Recalcular total catálogo.
UPDATE productos p
JOIN (
  SELECT id_producto, COALESCE(SUM(cantidad), 0) AS total
  FROM stock_por_almacen
  GROUP BY id_producto
) s ON s.id_producto = p.id
SET p.stock = s.total;

-- Resumen.
SELECT
  (SELECT COUNT(*) FROM tmp_prod_sin_filas) AS productos_migrados_legacy,
  (SELECT COUNT(*) FROM stock_por_almacen WHERE id_almacen = @ID_TIENDA) AS filas_tienda,
  (SELECT COUNT(*) FROM stock_por_almacen WHERE id_almacen = @ID_BODEGA) AS filas_bodega;
