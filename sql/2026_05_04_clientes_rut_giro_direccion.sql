-- Agrega columnas faltantes a `clientes` sin romper instalaciones existentes.
-- Motivo: el modelo `Cliente` en `app.py` usa rut/giro/direccion; si la BD no las tiene,
-- aparece error 1054 Unknown column 'clientes.rut' en búsquedas del POS.
--
-- Compatibilidad: MySQL/MariaDB sin "ADD COLUMN IF NOT EXISTS".
-- Ejecutar en la BD del ERP (la misma de SQLALCHEMY_DATABASE_URI).

SET @db := DATABASE();

-- 1) RUT (se deja NULL para no bloquear registros antiguos sin RUT)
SET @has_rut := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'rut'
);
SET @sql := IF(@has_rut = 0,
  'ALTER TABLE clientes ADD COLUMN rut VARCHAR(12) NULL',
  'SELECT ''OK: clientes.rut ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice único para rut (permite múltiples NULL)
SET @has_ux_rut := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND INDEX_NAME = 'ux_clientes_rut'
);
SET @sql := IF(@has_ux_rut = 0,
  'CREATE UNIQUE INDEX ux_clientes_rut ON clientes (rut)',
  'SELECT ''OK: indice ux_clientes_rut ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2) GIRO
SET @has_giro := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'giro'
);
SET @sql := IF(@has_giro = 0,
  'ALTER TABLE clientes ADD COLUMN giro VARCHAR(100) NULL',
  'SELECT ''OK: clientes.giro ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3) DIRECCION
SET @has_direccion := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'direccion'
);
SET @sql := IF(@has_direccion = 0,
  'ALTER TABLE clientes ADD COLUMN direccion VARCHAR(200) NULL',
  'SELECT ''OK: clientes.direccion ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

