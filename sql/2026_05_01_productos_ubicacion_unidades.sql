-- Gestión de Ubicaciones (Pasillo-Estante-Nivel) + Unidades compuestas.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

-- unidad_compra
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_compra'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_compra VARCHAR(20) NULL AFTER unidad'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- unidad_venta
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_venta'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_venta VARCHAR(20) NULL AFTER unidad_compra'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- factor_conversion
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'factor_conversion'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN factor_conversion DOUBLE NOT NULL DEFAULT 1 AFTER unidad_venta'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación pasillo
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_pasillo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_pasillo VARCHAR(12) NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación estante
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_estante'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_estante VARCHAR(12) NULL AFTER ubicacion_pasillo'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación nivel
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_nivel'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_nivel VARCHAR(12) NULL AFTER ubicacion_estante'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Backfill de unidades para no dejar nulos
UPDATE productos
SET unidad_venta = COALESCE(NULLIF(unidad_venta, ''), NULLIF(unidad, ''), 'Unidad'),
    unidad_compra = COALESCE(NULLIF(unidad_compra, ''), COALESCE(NULLIF(unidad, ''), 'Unidad'))
WHERE id > 0;
