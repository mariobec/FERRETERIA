-- Crédito en cuotas: plan fijo (30/60/90 o 5/10/15/30 días desde la venta).
-- En despliegues con schema_sync + create_all, la tabla y columna suelen crearse solas;
-- ejecutar este script solo si la BD no se sincronizó automáticamente.

-- PostgreSQL / MySQL: columna en ventas
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS credito_plan_codigo VARCHAR(32) NULL;

-- MySQL 8 no tiene IF NOT EXISTS en ADD COLUMN; si falla, comentar la línea anterior y usar:
-- ALTER TABLE ventas ADD COLUMN credito_plan_codigo VARCHAR(32) NULL;

CREATE TABLE IF NOT EXISTS ventas_cuotas_credito (
    id SERIAL PRIMARY KEY,
    venta_id INTEGER NOT NULL,
    nro_cuota INTEGER NOT NULL,
    dias_plazo INTEGER NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    monto DOUBLE PRECISION NOT NULL,
    monto_pagado DOUBLE PRECISION NOT NULL DEFAULT 0,
    estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente'
);

-- MySQL equivalente (descomentar si aplica):
-- CREATE TABLE IF NOT EXISTS ventas_cuotas_credito (
--   id INT AUTO_INCREMENT PRIMARY KEY,
--   venta_id INT NOT NULL,
--   nro_cuota INT NOT NULL,
--   dias_plazo INT NOT NULL,
--   fecha_vencimiento DATE NOT NULL,
--   monto DOUBLE NOT NULL,
--   monto_pagado DOUBLE NOT NULL DEFAULT 0,
--   estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
--   INDEX idx_venta_cuotas_venta (venta_id)
-- );

CREATE INDEX IF NOT EXISTS idx_ventas_cuotas_credito_venta_id ON ventas_cuotas_credito (venta_id);
