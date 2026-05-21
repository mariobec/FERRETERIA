-- Vouchers tarjeta declarados en cierre a ciegas (PLAT-1.1 UI)
ALTER TABLE caja ADD COLUMN IF NOT EXISTS monto_declarado_tarjeta INTEGER NULL;

COMMENT ON COLUMN caja.monto_declarado_tarjeta IS 'Total vouchers Transbank/Getnet declarado por cajero al cierre';
