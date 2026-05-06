-- Copia archivada del documento tributario (boleta/factura 80 mm) en PDF para recuperación desde historial.
-- MySQL. Idempotente.

SET NAMES utf8mb4;
SET @db := DATABASE();

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'copia_documento_pdf_at';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN copia_documento_pdf_at DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'copia_documento_pdf';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN copia_documento_pdf LONGBLOB NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;
