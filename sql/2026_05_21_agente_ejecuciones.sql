-- PLAT-2.1 / IA-0 — Tabla única agente_ejecuciones (alertas Operador + HITL + logs)
-- PostgreSQL (Neon/local). Ejecutar en QA antes de prod.

CREATE TABLE IF NOT EXISTS agente_ejecuciones (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    agente_nombre VARCHAR(40) NOT NULL,
    tipo VARCHAR(32) NOT NULL,
    estado VARCHAR(32) NOT NULL,
    severidad VARCHAR(16),
    codigo VARCHAR(64),
    dedupe_key VARCHAR(128),
    titulo VARCHAR(255) NOT NULL,
    cuerpo TEXT,
    payload_json TEXT,
    tokens_total INTEGER NOT NULL DEFAULT 0,
    costo_api_usd NUMERIC(12, 4) NOT NULL DEFAULT 0,
    venta_id INTEGER REFERENCES ventas(id) ON DELETE SET NULL,
    caja_id INTEGER REFERENCES caja(id) ON DELETE SET NULL,
    aprobado_por VARCHAR(120),
    fecha_aprobacion TIMESTAMP,
    reconocido_por VARCHAR(120),
    fecha_reconocido TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_agente_ejec_tipo_estado
    ON agente_ejecuciones (tipo, estado);

CREATE INDEX IF NOT EXISTS ix_agente_ejec_agente_created
    ON agente_ejecuciones (agente_nombre, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agente_ejec_dedupe_abierta
    ON agente_ejecuciones (dedupe_key)
    WHERE dedupe_key IS NOT NULL AND estado IN ('abierta', 'pendiente_aprobacion');

COMMENT ON TABLE agente_ejecuciones IS 'Agentes IA: alertas operativas, borradores HITL y logs de ejecución';
