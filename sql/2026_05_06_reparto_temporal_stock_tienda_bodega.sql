-- REPARTO TEMPORAL DE STOCK PARA OPERAR SIN BLOQUEOS EN POS
-- Objetivo: que todo producto activo con stock tenga saldo en TIENDA y BODEGA.
-- Uso temporal hasta regularizar con inventario definitivo.
--
-- Política aplicada:
--   - TIENDA = CEIL(stock_catalogo / 2)
--   - BODEGA = FLOOR(stock_catalogo / 2)
--   - Si stock_catalogo > 0 y alguna parte queda 0, se fuerza a 1 para ambos
--     (puede sumar +1 en productos de stock muy bajo; aceptado por ser temporal).
--   - Luego se sincroniza productos.stock = TIENDA + BODEGA
--
-- Recomendación:
--   1) Respaldar base antes de ejecutar.
--   2) Ejecutar fuera de hora punta.
--   3) Al finalizar inventario real, volver a cargar stock correcto por almacén.

SET @COD_TIENDA := 'TIENDA';
SET @COD_BODEGA := 'BODEGA';

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

-- Crear almacenes si faltan.
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

-- 1) Construir staging temporal con reparto.
DROP TEMPORARY TABLE IF EXISTS tmp_reparto_stock;
CREATE TEMPORARY TABLE tmp_reparto_stock (
  id_producto INT PRIMARY KEY,
  stock_catalogo INT NOT NULL,
  stock_tienda INT NOT NULL,
  stock_bodega INT NOT NULL
);

INSERT INTO tmp_reparto_stock (id_producto, stock_catalogo, stock_tienda, stock_bodega)
SELECT
  p.id,
  GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) AS stock_catalogo,
  CASE
    WHEN GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) = 0 THEN 0
    WHEN CEIL(GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) / 2) < 1 THEN 1
    ELSE CEIL(GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) / 2)
  END AS stock_tienda,
  CASE
    WHEN GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) = 0 THEN 0
    WHEN FLOOR(GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) / 2) < 1 THEN 1
    ELSE FLOOR(GREATEST(COALESCE(CAST(p.stock AS SIGNED), 0), 0) / 2)
  END AS stock_bodega
FROM productos p
WHERE COALESCE(p.activo, 1) = 1;

-- 2) Upsert TIENDA.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT t.id_producto, @ID_TIENDA, t.stock_tienda
FROM tmp_reparto_stock t
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- 3) Upsert BODEGA.
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT t.id_producto, @ID_BODEGA, t.stock_bodega
FROM tmp_reparto_stock t
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- 4) Sincronizar total catálogo como suma por almacén (coherencia interna del sistema).
UPDATE productos p
JOIN (
  SELECT id_producto, COALESCE(SUM(cantidad), 0) AS total
  FROM stock_por_almacen
  GROUP BY id_producto
) s ON s.id_producto = p.id
SET p.stock = s.total;

-- 5) Resumen rápido.
SELECT
  COUNT(*) AS productos_afectados,
  SUM(stock_tienda) AS total_tienda_asignado,
  SUM(stock_bodega) AS total_bodega_asignado
FROM tmp_reparto_stock;

-- Muestra de control.
SELECT
  p.id,
  p.codigo_barra,
  p.nombre,
  p.stock AS stock_catalogo_total,
  st.cantidad AS stock_tienda,
  sb.cantidad AS stock_bodega
FROM productos p
LEFT JOIN stock_por_almacen st ON st.id_producto = p.id AND st.id_almacen = @ID_TIENDA
LEFT JOIN stock_por_almacen sb ON sb.id_producto = p.id AND sb.id_almacen = @ID_BODEGA
WHERE COALESCE(p.activo, 1) = 1
ORDER BY p.id DESC
LIMIT 50;
