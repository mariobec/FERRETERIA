-- Set PRUEBA POS — semáforo verde / amarillo / azul (venta en verde)
-- Equivalente a: python scripts/seed_pos_semaforo_pruebas.py
-- Catálogo: pruebas/pos_semaforo/productos.json

INSERT INTO almacenes (codigo, nombre, activo)
SELECT 'TIENDA', 'Tienda / Mostrador', TRUE
WHERE NOT EXISTS (SELECT 1 FROM almacenes WHERE UPPER(TRIM(codigo)) = 'TIENDA' AND activo = TRUE);

INSERT INTO almacenes (codigo, nombre, activo)
SELECT 'BODEGA', 'Bodega', TRUE
WHERE NOT EXISTS (SELECT 1 FROM almacenes WHERE UPPER(TRIM(codigo)) = 'BODEGA' AND activo = TRUE);

CREATE TEMP TABLE _pos_sem_seed (
  codigo_barra TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  precio_venta NUMERIC NOT NULL,
  stock_tienda INT NOT NULL,
  stock_bodega INT NOT NULL
);

INSERT INTO _pos_sem_seed (codigo_barra, nombre, precio_venta, stock_tienda, stock_bodega) VALUES
  ('POS-SEM-V1', '[PRUEBA POS] Semáforo VERDE — solo tienda', 4990, 15, 0),
  ('POS-SEM-V2', '[PRUEBA POS] Semáforo VERDE — tienda y bodega', 7990, 8, 35),
  ('POS-SEM-A1', '[PRUEBA POS] Semáforo AMARILLO — solo bodega', 6490, 0, 22),
  ('POS-SEM-A2', '[PRUEBA POS] Semáforo AMARILLO — bodega baja', 2990, 0, 3),
  ('POS-SEM-Z1', '[PRUEBA POS] Semáforo AZUL — venta en verde', 12990, 0, 0),
  ('POS-SEM-Z2', '[PRUEBA POS] AZUL — sin stock (alias búsqueda martillo)', 15990, 0, 0),
  ('POS-SEM-Q1', '[PRUEBA POS] Límite stock tienda — 2 unidades', 1990, 2, 50),
  ('POS-SEM-Q2', '[PRUEBA POS] Sin stock visual — agotado en lista', 990, 0, 0);

INSERT INTO productos (nombre, codigo_barra, precio_venta, precio_mayoreo, precio_compra, stock, categoria, activo, unidad, unidad_venta)
SELECT s.nombre, s.codigo_barra, s.precio_venta, 0, ROUND(s.precio_venta * 0.55)::int,
       s.stock_tienda + s.stock_bodega, 'PRUEBA_POS', TRUE, 'Unidad', 'Unidad'
FROM _pos_sem_seed s
ON CONFLICT (codigo_barra) DO UPDATE SET
  nombre = EXCLUDED.nombre,
  precio_venta = EXCLUDED.precio_venta,
  categoria = EXCLUDED.categoria,
  activo = EXCLUDED.activo,
  stock = EXCLUDED.stock;

DELETE FROM stock_por_almacen spa
USING productos p, _pos_sem_seed s
WHERE spa.id_producto = p.id AND p.codigo_barra = s.codigo_barra;

INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id,
  (SELECT id FROM almacenes WHERE UPPER(TRIM(codigo)) = 'TIENDA' AND activo = TRUE ORDER BY id LIMIT 1),
  s.stock_tienda
FROM productos p
JOIN _pos_sem_seed s ON s.codigo_barra = p.codigo_barra
ON CONFLICT (id_producto, id_almacen) DO UPDATE SET cantidad = EXCLUDED.cantidad;

INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id,
  (SELECT id FROM almacenes WHERE UPPER(TRIM(codigo)) = 'BODEGA' AND activo = TRUE ORDER BY id LIMIT 1),
  s.stock_bodega
FROM productos p
JOIN _pos_sem_seed s ON s.codigo_barra = p.codigo_barra
ON CONFLICT (id_producto, id_almacen) DO UPDATE SET cantidad = EXCLUDED.cantidad;

UPDATE productos p
SET stock = COALESCE((
  SELECT SUM(spa.cantidad) FROM stock_por_almacen spa WHERE spa.id_producto = p.id
), 0)
WHERE p.codigo_barra LIKE 'POS-SEM-%';

SELECT p.codigo_barra, p.nombre,
  spa_t.cantidad AS stock_tienda,
  spa_b.cantidad AS stock_bodega,
  p.stock AS stock_catalogo
FROM productos p
JOIN _pos_sem_seed s ON s.codigo_barra = p.codigo_barra
LEFT JOIN stock_por_almacen spa_t ON spa_t.id_producto = p.id
  AND spa_t.id_almacen = (SELECT id FROM almacenes WHERE UPPER(TRIM(codigo)) = 'TIENDA' AND activo = TRUE ORDER BY id LIMIT 1)
LEFT JOIN stock_por_almacen spa_b ON spa_b.id_producto = p.id
  AND spa_b.id_almacen = (SELECT id FROM almacenes WHERE UPPER(TRIM(codigo)) = 'BODEGA' AND activo = TRUE ORDER BY id LIMIT 1)
ORDER BY p.codigo_barra;

DROP TABLE _pos_sem_seed;
