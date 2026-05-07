-- Seed de prueba para validar coherencia POS vs Cobro en stock de TIENDA.
-- Crea/actualiza 3 productos de prueba:
--   STK-P1: tiene fila en TIENDA con stock > 0  -> debe venderse y cobrarse.
--   STK-P2: TIENDA = 0 y BODEGA > 0            -> no debe venderse en POS.
--   STK-P3: sin filas por almacen, stock legacy > 0 -> debe venderse (fallback).
--
-- Uso:
--   1) Ejecutar este script en MySQL.
--   2) Probar flujo POS/cobro con codigos:
--      TEST-STK-P1, TEST-STK-P2, TEST-STK-P3

SET @COD_TIENDA := 'TIENDA';
SET @COD_BODEGA := 'BODEGA';

-- Resolver almacenes activos por codigo; si faltan, crearlos.
SET @ID_TIENDA := (
  SELECT id
  FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_TIENDA AND activo = 1
  ORDER BY id
  LIMIT 1
);

SET @ID_BODEGA := (
  SELECT id
  FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_BODEGA AND activo = 1
  ORDER BY id
  LIMIT 1
);

INSERT INTO almacenes (codigo, nombre, activo)
SELECT @COD_TIENDA, 'Tienda / Mostrador', 1
WHERE @ID_TIENDA IS NULL;

INSERT INTO almacenes (codigo, nombre, activo)
SELECT @COD_BODEGA, 'Bodega', 1
WHERE @ID_BODEGA IS NULL;

SET @ID_TIENDA := (
  SELECT id
  FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_TIENDA AND activo = 1
  ORDER BY id
  LIMIT 1
);

SET @ID_BODEGA := (
  SELECT id
  FROM almacenes
  WHERE UPPER(TRIM(codigo)) = @COD_BODEGA AND activo = 1
  ORDER BY id
  LIMIT 1
);

-- Crear o actualizar productos de prueba.
INSERT INTO productos (nombre, codigo_barra, precio_venta, precio_mayoreo, precio_compra, stock, categoria, activo)
VALUES
  ('[TEST] Producto Stock TIENDA OK', 'TEST-STK-P1', 4490, 0, 2500, 5, 'TEST', 1),
  ('[TEST] Producto Solo BODEGA', 'TEST-STK-P2', 5990, 0, 3000, 10, 'TEST', 1),
  ('[TEST] Producto Legacy Sin Filas Almacen', 'TEST-STK-P3', 3490, 0, 1800, 8, 'TEST', 1)
ON DUPLICATE KEY UPDATE
  nombre = VALUES(nombre),
  precio_venta = VALUES(precio_venta),
  precio_mayoreo = VALUES(precio_mayoreo),
  precio_compra = VALUES(precio_compra),
  stock = VALUES(stock),
  categoria = VALUES(categoria),
  activo = VALUES(activo);

SET @P1 := (SELECT id FROM productos WHERE codigo_barra = 'TEST-STK-P1' LIMIT 1);
SET @P2 := (SELECT id FROM productos WHERE codigo_barra = 'TEST-STK-P2' LIMIT 1);
SET @P3 := (SELECT id FROM productos WHERE codigo_barra = 'TEST-STK-P3' LIMIT 1);

-- Limpiar stock por almacen previo solo en productos de prueba.
DELETE FROM stock_por_almacen
WHERE id_producto IN (@P1, @P2, @P3);

-- Caso 1: TIENDA con stock.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
VALUES (@P1, @ID_TIENDA, 5);

-- Caso 2: TIENDA 0 y BODEGA con stock.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
VALUES
  (@P2, @ID_TIENDA, 0),
  (@P2, @ID_BODEGA, 10);

-- Caso 3: legacy SIN filas por almacen para probar fallback (P3).
-- No insertar filas para @P3.

-- Verificacion rapida.
SELECT
  p.id,
  p.codigo_barra,
  p.nombre,
  p.stock AS stock_catalogo,
  spa_t.cantidad AS stock_tienda,
  spa_b.cantidad AS stock_bodega
FROM productos p
LEFT JOIN stock_por_almacen spa_t
  ON spa_t.id_producto = p.id AND spa_t.id_almacen = @ID_TIENDA
LEFT JOIN stock_por_almacen spa_b
  ON spa_b.id_producto = p.id AND spa_b.id_almacen = @ID_BODEGA
WHERE p.codigo_barra IN ('TEST-STK-P1', 'TEST-STK-P2', 'TEST-STK-P3')
ORDER BY p.codigo_barra;
