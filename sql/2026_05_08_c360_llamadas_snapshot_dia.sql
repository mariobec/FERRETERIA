-- Snapshot diario de clientes con recomendar_llamada (Customer 360 / worker nocturno).
-- La app también crea la tabla con SQLAlchemy checkfirst si falta.
CREATE TABLE IF NOT EXISTS c360_llamadas_snapshot_dia (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    etapa_sugerida VARCHAR(32),
    cupo_sugerido_clp INTEGER NOT NULL DEFAULT 0,
    score_snapshot DOUBLE PRECISION,
    run_at TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT uq_c360_snap_fecha_cliente UNIQUE (fecha, cliente_id)
);
CREATE INDEX IF NOT EXISTS ix_c360_llamadas_snapshot_dia_fecha ON c360_llamadas_snapshot_dia (fecha);
CREATE INDEX IF NOT EXISTS ix_c360_llamadas_snapshot_dia_cliente_id ON c360_llamadas_snapshot_dia (cliente_id);
