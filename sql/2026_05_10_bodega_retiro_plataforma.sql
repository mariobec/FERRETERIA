-- Retiro bodega post-cobro + cola de preparación (ERP LexIA)
-- Nota: la app también intenta crear estas columnas al arrancar (_asegurar_columnas_bodega_retiro en app.py).
-- Ejecutar manualmente si preferís DDL explícito en MySQL / Postgres.

-- MySQL 8+ (ajustar si usás otra versión)
-- ALTER TABLE ventas ADD COLUMN bodega_preparacion_estado VARCHAR(24) NULL;
-- ALTER TABLE ventas ADD COLUMN bodega_preparacion_usuario VARCHAR(80) NULL;
-- ALTER TABLE ventas ADD COLUMN bodega_preparacion_at DATETIME NULL;
-- ALTER TABLE detalle_ventas ADD COLUMN cantidad_entregada_retiro_bodega INT NOT NULL DEFAULT 0;

-- PostgreSQL
-- ALTER TABLE ventas ADD COLUMN IF NOT EXISTS bodega_preparacion_estado VARCHAR(24) NULL;
-- ALTER TABLE ventas ADD COLUMN IF NOT EXISTS bodega_preparacion_usuario VARCHAR(80) NULL;
-- ALTER TABLE ventas ADD COLUMN IF NOT EXISTS bodega_preparacion_at TIMESTAMP NULL;
-- ALTER TABLE detalle_ventas ADD COLUMN IF NOT EXISTS cantidad_entregada_retiro_bodega INTEGER NOT NULL DEFAULT 0;
