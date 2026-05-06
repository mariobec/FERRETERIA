-- Agrega columnas faltantes a `almacenes` para inventario multi-almacén.
-- Motivo: el modelo `Almacen` en `app.py` usa codigo/activo.
--
-- Compatibilidad: MySQL/MariaDB sin "ADD COLUMN IF NOT EXISTS".
-- Ejecutar en la BD del ERP (la misma de SQLALCHEMY_DATABASE_URI).

SET @db := DATABASE();

-- 1) codigo
SET @has_codigo := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'almacenes' AND COLUMN_NAME = 'codigo'
);
SET @sql := IF(@has_codigo = 0,
  'ALTER TABLE almacenes ADD COLUMN codigo VARCHAR(20) NOT NULL',
  'SELECT ''OK: almacenes.codigo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2) activo
SET @has_activo := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'almacenes' AND COLUMN_NAME = 'activo'
);
SET @sql := IF(@has_activo = 0,
  'ALTER TABLE almacenes ADD COLUMN activo BOOL NULL DEFAULT 1',
  'SELECT ''OK: almacenes.activo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

