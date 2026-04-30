-- Bitácora de costos de compra por recepción (proveedor/producto)
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS bitacora_costos_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  producto_id INT NOT NULL,
  proveedor_id INT NULL,
  recepcion_id INT NULL,
  costo_anterior DOUBLE NOT NULL DEFAULT 0,
  costo_nuevo DOUBLE NOT NULL DEFAULT 0,
  variacion_pct DOUBLE NULL,
  precio_venta_referencia DOUBLE NULL,
  margen_proyectado DOUBLE NULL,
  usuario VARCHAR(100) NULL,
  observacion VARCHAR(255) NULL,
  CONSTRAINT fk_bcc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  KEY idx_bcc_fecha (fecha),
  KEY idx_bcc_producto_fecha (producto_id, fecha),
  KEY idx_bcc_proveedor_fecha (proveedor_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
