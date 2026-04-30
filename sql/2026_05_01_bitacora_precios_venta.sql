CREATE TABLE IF NOT EXISTS bitacora_precios_venta (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  producto_id INT NOT NULL,
  precio_anterior DECIMAL(12,2) NOT NULL DEFAULT 0,
  precio_nuevo DECIMAL(12,2) NOT NULL DEFAULT 0,
  costo_referencia DECIMAL(12,2) NULL,
  margen_objetivo DECIMAL(8,4) NULL,
  usuario VARCHAR(100) NULL,
  motivo VARCHAR(255) NULL,
  CONSTRAINT fk_bitacora_precio_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
