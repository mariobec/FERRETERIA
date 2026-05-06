-- Auditoría de anulación de vale en caja (cliente no retorna, error de emisión, etc.).
-- MySQL. Idempotente: solo agrega columnas si no existen.

SET NAMES utf8mb4;
SET @db := DATABASE();

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'motivo_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN motivo_anulacion VARCHAR(500) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'fecha_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN fecha_anulacion DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'usuario_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN usuario_anulacion VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;
