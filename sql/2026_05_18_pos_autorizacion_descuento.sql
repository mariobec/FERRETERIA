-- POS: autorización descuentos (tarjeta supervisor + PIN + traza en línea)
-- PostgreSQL / Neon. En local legacy, app.py también ejecuta ALTER vía _asegurar_*.

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS pin_autorizacion_hash TEXT NULL;

ALTER TABLE detalle_ventas
  ADD COLUMN IF NOT EXISTS descuento_autorizado_por_id INTEGER NULL,
  ADD COLUMN IF NOT EXISTS descuento_autorizado_en TIMESTAMP NULL,
  ADD COLUMN IF NOT EXISTS descuento_autorizado_metodo VARCHAR(24) NULL;

CREATE TABLE IF NOT EXISTS usuario_tarjeta_autorizacion (
  id SERIAL PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
  token_hash TEXT NOT NULL,
  etiqueta VARCHAR(80) NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revocado_en TIMESTAMP NULL,
  ultimo_uso_en TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_usuario_tarjeta_autorizacion_usuario
  ON usuario_tarjeta_autorizacion (usuario_id);

CREATE INDEX IF NOT EXISTS ix_usuario_tarjeta_autorizacion_activo
  ON usuario_tarjeta_autorizacion (activo) WHERE activo = TRUE;

-- Productos con descuento preaprobado en POS (sin tarjeta supervisor hasta el tope %)
ALTER TABLE productos
  ADD COLUMN IF NOT EXISTS pos_descuento_preautorizado BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS pos_descuento_preautorizado_pct NUMERIC(8,2) NULL;
