-- Tercer nivel del maestro (p. ej. Categorias.xlsx): categoría 1 + sub nivel 2 + sub nivel 3.
-- Nota: el UNIQUE (categoria_id, nombre) suele ser el índice que soporta la FK hacia catalogo_categorias;
-- hay que crear otro índice con prefijo categoria_id ANTES de DROP INDEX (error 1553 si no).

SET NAMES utf8mb4;
SET @db_name := DATABASE();

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND column_name = 'nivel2'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD COLUMN nivel2 VARCHAR(80) NOT NULL DEFAULT \'\' AFTER categoria_id'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice no único para que la FK fk_catalogo_sub_categoria siga teniendo soporte al quitar el UNIQUE antiguo.
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'ix_catalogo_subcategorias_fk_categoria'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD INDEX ix_catalogo_subcategorias_fk_categoria (categoria_id)'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND INDEX_NAME = 'uq_catalogo_sub'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_sub',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_subcategoria_cat_nombre'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_subcategoria_cat_nombre',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_sub_cat_nivel_nombre'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD UNIQUE KEY uq_catalogo_sub_cat_nivel_nombre (categoria_id, nivel2, nombre)'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- El UNIQUE nuevo ya empieza por categoria_id; el índice auxiliar es redundante.
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'ix_catalogo_subcategorias_fk_categoria'
    )
    AND EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_sub_cat_nivel_nombre'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX ix_catalogo_subcategorias_fk_categoria',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
