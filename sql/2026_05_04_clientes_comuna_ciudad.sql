-- Comuna y ciudad del receptor (factura/boleta 80 mm, datos de cliente).
-- Si Error 1060 Duplicate column: omitir la línea correspondiente.

SET @db := DATABASE();

SET @has_comuna := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'comuna'
);
SET @sql := IF(@has_comuna = 0,
  'ALTER TABLE clientes ADD COLUMN comuna VARCHAR(80) NULL',
  'SELECT ''OK: clientes.comuna ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ciudad := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'ciudad'
);
SET @sql := IF(@has_ciudad = 0,
  'ALTER TABLE clientes ADD COLUMN ciudad VARCHAR(80) NULL',
  'SELECT ''OK: clientes.ciudad ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
