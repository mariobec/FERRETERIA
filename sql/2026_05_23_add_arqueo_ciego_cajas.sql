-- Arqueo ciego + conciliación SII fusionados en tabla caja (PLAT-1.1 fusión)
-- PostgreSQL (Neon dev / local). No modifica ventas ni arqueo_caja legacy.

ALTER TABLE caja ADD COLUMN IF NOT EXISTS monto_declarado_cajero INTEGER NULL;
ALTER TABLE caja ADD COLUMN IF NOT EXISTS boletas_emitidas_qty INTEGER NOT NULL DEFAULT 0;
ALTER TABLE caja ADD COLUMN IF NOT EXISTS boletas_sincronizadas_qty INTEGER NOT NULL DEFAULT 0;
ALTER TABLE caja ADD COLUMN IF NOT EXISTS monto_total_sii INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN caja.monto_declarado_cajero IS 'Efectivo declarado a ciegas al cierre (CLP enteros)';
COMMENT ON COLUMN caja.boletas_emitidas_qty IS 'Ventas del turno con señal DTE (folio/estado)';
COMMENT ON COLUMN caja.boletas_sincronizadas_qty IS 'Ventas con Track ID SII exitoso en BD';
COMMENT ON COLUMN caja.monto_total_sii IS 'Suma CLP ventas con Track ID exitoso (proxy XML persistido)';
