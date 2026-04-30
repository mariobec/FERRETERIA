-- Kardex (movimientos de inventario) y tablas de recepción de mercadería.
-- Ejecutar en la base ferreteria (MySQL). Ajustar si las tablas ya existen.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS movimientos_inventario (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL DEFAULT 1,
  tipo_movimiento VARCHAR(20) NOT NULL,
  cantidad INT NOT NULL,
  motivo VARCHAR(500) NULL,
  usuario VARCHAR(100) NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  referencia_tipo VARCHAR(40) NULL,
  referencia_id INT NULL,
  stock_saldo INT NULL,
  CONSTRAINT fk_kardex_producto FOREIGN KEY (id_producto) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_kardex_producto_fecha (id_producto, fecha),
  KEY idx_kardex_tipo (tipo_movimiento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Compatibilidad MySQL (sin IF NOT EXISTS en ADD COLUMN)
SET @db_name := DATABASE();

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'referencia_tipo'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN referencia_tipo VARCHAR(40) NULL AFTER fecha'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'referencia_id'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN referencia_id INT NULL AFTER referencia_tipo'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'stock_saldo'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN stock_saldo INT NULL AFTER referencia_id'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS recepciones_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  documento_tipo ENUM('Factura', 'Guia de Despacho') NOT NULL,
  documento_numero VARCHAR(50) NOT NULL,
  fecha_recepcion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  usuario_bodega VARCHAR(100) NULL,
  estado ENUM('Pendiente', 'Incompleta', 'Finalizada') NOT NULL DEFAULT 'Pendiente',
  CONSTRAINT fk_recv_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS detalle_recepcion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  recepcion_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad_documento INT NOT NULL,
  cantidad_recibida INT NOT NULL,
  CONSTRAINT fk_detrecv_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_detrecv_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_detrecv_recepcion (recepcion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
