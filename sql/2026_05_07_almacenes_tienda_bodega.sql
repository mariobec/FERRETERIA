-- Semilla / alta de almacenes estándar para POS y recepciones (idempotente).
-- Ejecutar en la misma BD que usa SQLALCHEMY_DATABASE_URI.

SET NAMES utf8mb4;

INSERT INTO almacenes (codigo, nombre, activo)
VALUES ('TIENDA', 'Tienda / Mostrador', 1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);

INSERT INTO almacenes (codigo, nombre, activo)
VALUES ('BODEGA', 'Bodega', 1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);
