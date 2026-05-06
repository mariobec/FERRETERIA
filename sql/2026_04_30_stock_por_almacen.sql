-- Inventario por almacén: tablas almacenes + stock_por_almacen + semilla BODEGA/TIENDA.
-- Idempotente (MySQL). Copia stock histórico del catálogo hacia TIENDA; BODEGA queda en 0.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS almacenes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(20) NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_almacenes_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_por_almacen (
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL,
  cantidad INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id_producto, id_almacen),
  CONSTRAINT fk_spa_producto FOREIGN KEY (id_producto) REFERENCES productos(id) ON DELETE CASCADE,
  CONSTRAINT fk_spa_almacen FOREIGN KEY (id_almacen) REFERENCES almacenes(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO almacenes (codigo, nombre, activo) VALUES ('BODEGA', 'Bodega / CD', 1)
  ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);
INSERT INTO almacenes (codigo, nombre, activo) VALUES ('TIENDA', 'Tienda', 1)
  ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);

SET @id_bodega := (SELECT id FROM almacenes WHERE codigo = 'BODEGA' LIMIT 1);
SET @id_tienda := (SELECT id FROM almacenes WHERE codigo = 'TIENDA' LIMIT 1);

-- Stock existente en catálogo -> TIENDA
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id, @id_tienda, COALESCE(p.stock, 0)
FROM productos p
WHERE COALESCE(p.stock, 0) <> 0
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- Fila BODEGA en 0 para todos los productos (si no existe)
INSERT IGNORE INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id, @id_bodega, 0
FROM productos p;
