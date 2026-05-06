-- Catálogo maestro categoría → subcategoría (orden lógico) + enlace opcional en productos.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS catalogo_categorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_cat_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS catalogo_subcategorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  categoria_id INT NOT NULL,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_sub (categoria_id, nombre),
  CONSTRAINT fk_catalogo_sub_categoria FOREIGN KEY (categoria_id) REFERENCES catalogo_categorias(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'subcategoria_catalogo_id'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN subcategoria_catalogo_id INT NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'productos'
        AND constraint_name = 'fk_productos_subcategoria_catalogo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD CONSTRAINT fk_productos_subcategoria_catalogo FOREIGN KEY (subcategoria_catalogo_id) REFERENCES catalogo_subcategorias(id) ON DELETE SET NULL'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
