-- Customer 360 P0: auditoría de sugerencias / predicciones por cliente.
-- Idempotente para PostgreSQL.

BEGIN;

CREATE TABLE IF NOT EXISTS cliente_prediccion_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    tipo_recomendacion VARCHAR(48) NOT NULL,
    payload_json TEXT NULL,
    usuario_origen VARCHAR(100) NULL,
    resultado VARCHAR(32) NOT NULL DEFAULT 'ignorada',
    venta_asociada_id INTEGER NULL REFERENCES ventas(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cliente_prediccion_log_cliente ON cliente_prediccion_log(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cliente_prediccion_log_tipo ON cliente_prediccion_log(tipo_recomendacion);
CREATE INDEX IF NOT EXISTS idx_cliente_prediccion_log_created_at ON cliente_prediccion_log(created_at);

COMMIT;
