-- Enrolamiento / toma en tiempo real: Chilemat, código interno, foto, sesiones de conteo.
-- MySQL. Idempotente.

SET NAMES utf8mb4;
SET @db := DATABASE();

-- productos: maestro Chilemat, código interno propio, miniatura
SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'codigo_chilemat';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN codigo_chilemat VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'codigo_interno';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN codigo_interno VARCHAR(32) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'imagen_url';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN imagen_url VARCHAR(500) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND INDEX_NAME = 'idx_productos_codigo_chilemat';
SET @q := IF(@exists = 0, 'CREATE INDEX idx_productos_codigo_chilemat ON productos (codigo_chilemat)', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND INDEX_NAME = 'idx_productos_codigo_interno';
SET @q := IF(@exists = 0, 'CREATE UNIQUE INDEX idx_productos_codigo_interno ON productos (codigo_interno)', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Tablas de sesión (conteo por operario / turno)
CREATE TABLE IF NOT EXISTS enrolamiento_toma_sesion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  usuario VARCHAR(80) NULL,
  id_almacen INT NULL,
  iniciado_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enrol_sesion_usuario (usuario),
  INDEX idx_enrol_sesion_almacen (id_almacen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enrolamiento_toma_linea (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sesion_id INT NOT NULL,
  producto_id INT NOT NULL,
  conteo INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_enrol_linea_sesion_prod (sesion_id, producto_id),
  INDEX idx_enrol_linea_prod (producto_id),
  CONSTRAINT fk_enrol_linea_sesion FOREIGN KEY (sesion_id) REFERENCES enrolamiento_toma_sesion(id) ON DELETE CASCADE,
  CONSTRAINT fk_enrol_linea_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
