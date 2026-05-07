-- Migración "catch-up" para Neon Postgres (Render).
-- Objetivo: actualizar bases legacy con columnas/tablas que el código actual espera.
-- Es idempotente: usa IF NOT EXISTS para poder ejecutarse más de una vez.

BEGIN;

-- =========================
-- caja
-- =========================
ALTER TABLE IF EXISTS caja
  ADD COLUMN IF NOT EXISTS monto_teorico_cierre NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS monto_contado_cierre NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS diferencia_cierre NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS observacion_cierre VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS supervisor_cierre VARCHAR(80) NULL,
  ADD COLUMN IF NOT EXISTS usuario_cierre VARCHAR(50) NULL;

-- =========================
-- ventas
-- =========================
ALTER TABLE IF EXISTS ventas
  ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS nro_documento INTEGER NULL,
  ADD COLUMN IF NOT EXISTS neto NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS iva NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS monto_recibido NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS vuelto NUMERIC(14,2) NULL,
  ADD COLUMN IF NOT EXISTS prioridad INTEGER NULL,
  ADD COLUMN IF NOT EXISTS motivo_anulacion VARCHAR(500) NULL,
  ADD COLUMN IF NOT EXISTS fecha_anulacion TIMESTAMP NULL,
  ADD COLUMN IF NOT EXISTS usuario_anulacion VARCHAR(80) NULL,
  ADD COLUMN IF NOT EXISTS punto_retiro VARCHAR(30) NULL;

UPDATE ventas
SET punto_retiro = 'Bodega'
WHERE (punto_retiro IS NULL OR punto_retiro = '');

-- =========================
-- productos
-- =========================
ALTER TABLE IF EXISTS productos
  ADD COLUMN IF NOT EXISTS codigo_chilemat VARCHAR(80) NULL,
  ADD COLUMN IF NOT EXISTS codigo_interno VARCHAR(32) NULL,
  ADD COLUMN IF NOT EXISTS imagen_url VARCHAR(500) NULL,
  ADD COLUMN IF NOT EXISTS unidad_compra VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS unidad_venta VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS factor_conversion NUMERIC(12,4) NULL,
  ADD COLUMN IF NOT EXISTS subcategoria_catalogo_id INTEGER NULL,
  ADD COLUMN IF NOT EXISTS ubicacion_pasillo VARCHAR(12) NULL,
  ADD COLUMN IF NOT EXISTS ubicacion_estante VARCHAR(12) NULL,
  ADD COLUMN IF NOT EXISTS ubicacion_nivel VARCHAR(12) NULL;

-- =========================
-- detalle_ventas
-- =========================
ALTER TABLE IF EXISTS detalle_ventas
  ADD COLUMN IF NOT EXISTS precio_unitario NUMERIC(14,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS descuento NUMERIC(8,2) NULL,
  ADD COLUMN IF NOT EXISTS subtotal NUMERIC(14,2) NULL;

-- =========================
-- Cambios / devoluciones + saldos a favor
-- =========================
CREATE TABLE IF NOT EXISTS cambios_operacion (
  id SERIAL PRIMARY KEY,
  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  cliente_id INTEGER NULL,
  caja_id INTEGER NULL,
  usuario_id INTEGER NULL,
  venta_origen_id INTEGER NULL,
  total_devuelto NUMERIC(14,2) NOT NULL DEFAULT 0,
  total_entregado NUMERIC(14,2) NOT NULL DEFAULT 0,
  saldo_usado NUMERIC(14,2) NOT NULL DEFAULT 0,
  monto_pagado NUMERIC(14,2) NOT NULL DEFAULT 0,
  monto_devuelto_efectivo NUMERIC(14,2) NOT NULL DEFAULT 0,
  saldo_generado NUMERIC(14,2) NOT NULL DEFAULT 0,
  observacion VARCHAR(500) NULL
);

-- Si la tabla existía sin venta_origen_id, lo agregamos.
ALTER TABLE IF EXISTS cambios_operacion
  ADD COLUMN IF NOT EXISTS venta_origen_id INTEGER NULL;

CREATE INDEX IF NOT EXISTS idx_cambio_cliente ON cambios_operacion(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cambio_caja ON cambios_operacion(caja_id);
CREATE INDEX IF NOT EXISTS idx_cambio_usuario ON cambios_operacion(usuario_id);
CREATE INDEX IF NOT EXISTS idx_cambio_venta_origen ON cambios_operacion(venta_origen_id);

CREATE TABLE IF NOT EXISTS cambios_detalle (
  id SERIAL PRIMARY KEY,
  cambio_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  cantidad INTEGER NOT NULL DEFAULT 1,
  precio_unitario NUMERIC(14,2) NOT NULL DEFAULT 0,
  subtotal NUMERIC(14,2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cdet_cambio ON cambios_detalle(cambio_id);
CREATE INDEX IF NOT EXISTS idx_cdet_producto ON cambios_detalle(producto_id);

CREATE TABLE IF NOT EXISTS clientes_saldos_favor (
  cliente_id INTEGER PRIMARY KEY,
  saldo NUMERIC(14,2) NOT NULL DEFAULT 0,
  actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movimientos_saldo_favor (
  id SERIAL PRIMARY KEY,
  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  cliente_id INTEGER NOT NULL,
  cambio_id INTEGER NULL,
  tipo VARCHAR(20) NOT NULL,
  monto NUMERIC(14,2) NOT NULL DEFAULT 0,
  saldo_resultante NUMERIC(14,2) NOT NULL DEFAULT 0,
  observacion VARCHAR(255) NULL
);

CREATE INDEX IF NOT EXISTS idx_ms_cliente ON movimientos_saldo_favor(cliente_id);
CREATE INDEX IF NOT EXISTS idx_ms_cambio ON movimientos_saldo_favor(cambio_id);

COMMIT;

