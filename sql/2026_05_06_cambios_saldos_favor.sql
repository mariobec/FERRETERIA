-- Módulo de cambios sin nota de crédito + saldos a favor

CREATE TABLE IF NOT EXISTS cambios_operacion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
  cliente_id INT NULL,
  caja_id INT NULL,
  usuario_id INT NULL,
  venta_origen_id INT NULL,
  total_devuelto DOUBLE NOT NULL DEFAULT 0,
  total_entregado DOUBLE NOT NULL DEFAULT 0,
  saldo_usado DOUBLE NOT NULL DEFAULT 0,
  monto_pagado DOUBLE NOT NULL DEFAULT 0,
  monto_devuelto_efectivo DOUBLE NOT NULL DEFAULT 0,
  saldo_generado DOUBLE NOT NULL DEFAULT 0,
  observacion VARCHAR(500) NULL,
  KEY idx_cambio_cliente (cliente_id),
  KEY idx_cambio_caja (caja_id),
  KEY idx_cambio_usuario (usuario_id),
  KEY idx_cambio_venta_origen (venta_origen_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cambios_detalle (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cambio_id INT NOT NULL,
  producto_id INT NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  cantidad INT NOT NULL DEFAULT 1,
  precio_unitario DOUBLE NOT NULL DEFAULT 0,
  subtotal DOUBLE NOT NULL DEFAULT 0,
  KEY idx_cdet_cambio (cambio_id),
  KEY idx_cdet_producto (producto_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS clientes_saldos_favor (
  cliente_id INT PRIMARY KEY,
  saldo DOUBLE NOT NULL DEFAULT 0,
  actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS movimientos_saldo_favor (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
  cliente_id INT NOT NULL,
  cambio_id INT NULL,
  tipo VARCHAR(20) NOT NULL,
  monto DOUBLE NOT NULL DEFAULT 0,
  saldo_resultante DOUBLE NOT NULL DEFAULT 0,
  observacion VARCHAR(255) NULL,
  KEY idx_ms_cliente (cliente_id),
  KEY idx_ms_cambio (cambio_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
