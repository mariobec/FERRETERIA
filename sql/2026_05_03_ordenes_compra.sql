-- Órdenes de compra (Fase 1) + enlace opcional en recepciones_compra.
-- MySQL / InnoDB. Idempotente en lo posible.

SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS ordenes_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  numero VARCHAR(50) NOT NULL,
  fecha_emision DATE NOT NULL,
  estado ENUM('Borrador','Enviada','Parcial','Cerrada','Anulada') NOT NULL DEFAULT 'Borrador',
  observacion VARCHAR(500) NULL,
  usuario_creador VARCHAR(100) NULL,
  fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_oc_proveedor_numero (proveedor_id, numero),
  CONSTRAINT fk_oc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_oc_proveedor (proveedor_id),
  KEY idx_oc_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS detalle_orden_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  orden_compra_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad DECIMAL(14,4) NOT NULL DEFAULT 0,
  precio_unitario DECIMAL(14,4) NOT NULL DEFAULT 0,
  CONSTRAINT fk_doc_oc FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_doc_oc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_doc_oc_orden (orden_compra_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra' AND column_name = 'orden_compra_id'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD COLUMN orden_compra_id INT NULL AFTER proveedor_id'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra'
        AND constraint_name = 'fk_recv_orden_compra'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD CONSTRAINT fk_recv_orden_compra FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id) ON DELETE SET NULL ON UPDATE CASCADE'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
