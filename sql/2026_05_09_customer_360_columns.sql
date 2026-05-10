-- Customer 360: fase de obra en productos + perfil predictivo en clientes.
-- PostgreSQL. Idempotente (ejecutar una vez o usar auto-migración en app).

ALTER TABLE productos ADD COLUMN IF NOT EXISTS fase_obra VARCHAR(32) NULL;

ALTER TABLE clientes ADD COLUMN IF NOT EXISTS c360_etapa_actual VARCHAR(32) NULL;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS c360_perfil_json TEXT NULL;

COMMENT ON COLUMN productos.fase_obra IS 'OBRA_GRUESA|INSTALACIONES|ACABADOS|TERMINACIONES — taxonomía obra para motor C360';
COMMENT ON COLUMN clientes.c360_etapa_actual IS 'Etapa foco venta/crédito inferida por motor';
COMMENT ON COLUMN clientes.c360_perfil_json IS 'JSON perfil_predictor: score, cupo sugerido, alertas, OCR mock';
