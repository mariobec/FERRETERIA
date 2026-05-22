-- Hito PLAT-1.1 — ArqueoCaja (esquema canónico, CLP enteros)
-- Neon desarrollo / PostgreSQL. No modifica tablas de ventas.
--
-- Si aplicó sql/2026_05_22_arqueo_caja.sql (borrador anterior), ejecutar antes:
--   DROP TABLE IF EXISTS arqueo_caja CASCADE;

CREATE TABLE IF NOT EXISTS arqueo_caja (
    id SERIAL PRIMARY KEY,
    cajero_id VARCHAR(50) NOT NULL,
    fecha_apertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre TIMESTAMP NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'ABIERTO',

    monto_apertura INTEGER NOT NULL DEFAULT 0,
    monto_esperado_efectivo INTEGER NOT NULL DEFAULT 0,
    monto_esperado_tarjeta INTEGER NOT NULL DEFAULT 0,
    monto_declarado_cajero INTEGER NULL,
    monto_descuadre INTEGER NOT NULL DEFAULT 0,

    boletas_emitidas_qty INTEGER NOT NULL DEFAULT 0,
    boletas_sincronizadas_qty INTEGER NOT NULL DEFAULT 0,
    monto_total_ventas INTEGER NOT NULL DEFAULT 0,
    monto_total_sii INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT ck_arqueo_caja_estado CHECK (
        estado IN ('ABIERTO', 'PENDIENTE_CONCILIACION', 'CONCILIADO')
    ),
    CONSTRAINT ck_arqueo_caja_montos_base CHECK (
        monto_apertura >= 0
        AND monto_esperado_efectivo >= 0
        AND monto_esperado_tarjeta >= 0
        AND boletas_emitidas_qty >= 0
        AND boletas_sincronizadas_qty >= 0
        AND monto_total_ventas >= 0
        AND monto_total_sii >= 0
    )
);

CREATE INDEX IF NOT EXISTS ix_arqueo_caja_cajero ON arqueo_caja (cajero_id);
CREATE INDEX IF NOT EXISTS ix_arqueo_caja_estado ON arqueo_caja (estado);
CREATE INDEX IF NOT EXISTS ix_arqueo_caja_fecha_apertura ON arqueo_caja (fecha_apertura DESC);

COMMENT ON TABLE arqueo_caja IS 'Arqueo por turno: cierre a ciegas y cruce ERP/SII (PLAT-1.1)';
