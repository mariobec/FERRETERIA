-- Log de recordatorios de cobranza por WhatsApp (una fila por cuota y día).
-- PostgreSQL. Idempotente.

CREATE TABLE IF NOT EXISTS cobranza_recordatorio_whatsapp (
    id                       SERIAL PRIMARY KEY,
    venta_cuota_credito_id   INTEGER NOT NULL REFERENCES ventas_cuotas_credito(id) ON DELETE CASCADE,
    cliente_id               INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    fecha_envio              DATE NOT NULL,
    usuario_id               INTEGER NULL,
    created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cobranza_rec_cuota_dia UNIQUE (venta_cuota_credito_id, fecha_envio)
);

CREATE INDEX IF NOT EXISTS idx_cobranza_rec_cliente ON cobranza_recordatorio_whatsapp (cliente_id);
CREATE INDEX IF NOT EXISTS idx_cobranza_rec_fecha ON cobranza_recordatorio_whatsapp (fecha_envio);
