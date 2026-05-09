-- Modulo de cotizaciones rapidas (LexIA IA ERP).
-- PostgreSQL. Idempotente.

-- ============================================================
-- 1) Tabla principal de cotizaciones
-- ============================================================
CREATE TABLE IF NOT EXISTS cotizaciones (
    id              SERIAL PRIMARY KEY,
    numero          VARCHAR(20) NOT NULL UNIQUE,
    fecha           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validez_dias    INTEGER NOT NULL DEFAULT 15,
    fecha_vencimiento DATE,
    cliente_id      INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    cliente_nombre  VARCHAR(150),
    cliente_rut     VARCHAR(20),
    cliente_telefono VARCHAR(40),
    monto_total     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    neto            NUMERIC(14, 2) NOT NULL DEFAULT 0,
    iva             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    descuento_global NUMERIC(14, 2) NOT NULL DEFAULT 0,
    notas           TEXT,
    estado          VARCHAR(20) NOT NULL DEFAULT 'Vigente',
    usuario_creador VARCHAR(100),
    venta_id        INTEGER REFERENCES ventas(id) ON DELETE SET NULL,
    fecha_estado    TIMESTAMP,
    motivo_estado   VARCHAR(300)
);

CREATE INDEX IF NOT EXISTS idx_cotizaciones_estado ON cotizaciones(estado);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_fecha ON cotizaciones(fecha);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_cliente_id ON cotizaciones(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_cliente_rut ON cotizaciones(cliente_rut);

-- ============================================================
-- 2) Detalle de cotizacion
-- ============================================================
CREATE TABLE IF NOT EXISTS cotizacion_detalles (
    id              SERIAL PRIMARY KEY,
    cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,
    producto_id     INTEGER REFERENCES productos(id) ON DELETE SET NULL,
    codigo          VARCHAR(80),
    nombre          VARCHAR(200) NOT NULL,
    cantidad        NUMERIC(14, 4) NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(14, 2) NOT NULL DEFAULT 0,
    descuento       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    subtotal        NUMERIC(14, 2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cot_det_cotizacion_id ON cotizacion_detalles(cotizacion_id);
CREATE INDEX IF NOT EXISTS idx_cot_det_producto_id ON cotizacion_detalles(producto_id);

-- ============================================================
-- 3) Trazabilidad: agregar cotizacion_origen_id a ventas (opcional)
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ventas' AND column_name = 'cotizacion_origen_id'
    ) THEN
        ALTER TABLE ventas ADD COLUMN cotizacion_origen_id INTEGER
            REFERENCES cotizaciones(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_ventas_cotizacion_origen ON ventas(cotizacion_origen_id);
    END IF;
END$$;

-- ============================================================
-- 4) Datos de facturacion adicionales en cotizaciones
-- ============================================================
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS cliente_giro VARCHAR(150);
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS cliente_direccion VARCHAR(250);
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS cliente_comuna VARCHAR(100);
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS cliente_ciudad VARCHAR(100);
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS cliente_correo VARCHAR(150);
