-- Facturación electrónica Fase 1: CAF + columnas DTE en ventas (idempotente Postgres).
-- El código también aplica esto vía `_asegurar_tabla_cafs_y_columnas_ventas_fe()` al arrancar.

BEGIN;

CREATE TABLE IF NOT EXISTS cafs (
    id SERIAL PRIMARY KEY,
    tipo_dte INTEGER NOT NULL,
    rango_desde INTEGER NOT NULL,
    rango_hasta INTEGER NOT NULL,
    caf_xml TEXT NULL,
    fecha_autorizacion DATE NULL,
    usado_hasta INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE IF EXISTS ventas
  ADD COLUMN IF NOT EXISTS dte_tipo INTEGER NULL,
  ADD COLUMN IF NOT EXISTS dte_estado VARCHAR(32) NULL,
  ADD COLUMN IF NOT EXISTS dte_track_id VARCHAR(50) NULL,
  ADD COLUMN IF NOT EXISTS caf_id INTEGER NULL;

COMMIT;
