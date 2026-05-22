-- RCV SII: estado borrador recepciones + metadatos folio/montos + RUT proveedor.
-- PostgreSQL (Neon). Ejecutar: python scripts/apply_sql_neon.py sql/2026_05_22_rcv_sii_recepciones.sql

-- Proveedor: RUT para cruce RCV / factura
ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS rut VARCHAR(12) NULL;
CREATE INDEX IF NOT EXISTS idx_proveedores_rut ON proveedores (rut) WHERE rut IS NOT NULL;

-- Recepción: montos y origen importación
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS monto_neto DOUBLE PRECISION NULL;
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS monto_total DOUBLE PRECISION NULL;
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS rut_proveedor_doc VARCHAR(12) NULL;
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS razon_social_doc VARCHAR(200) NULL;
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS fecha_documento DATE NULL;
ALTER TABLE recepciones_compra ADD COLUMN IF NOT EXISTS origen_importacion VARCHAR(30) NULL;

-- Nuevo estado enum (PostgreSQL 15+ / Neon). Una sola sentencia: compatible con apply_sql_neon.py
ALTER TYPE recepciones_estado_enum ADD VALUE IF NOT EXISTS 'Pendiente de Items';
