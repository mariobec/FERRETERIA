-- SD-1 — Rendimiento PostgreSQL (Neon / producción)
-- Idempotente. Ejecutar una vez en ventana de bajo tráfico (minutos de lock en productos/ventas).
--
--   psql "$DATABASE_URL" -f sql/2026_05_21_rendimiento_sd1_postgresql.sql
-- o Neon → SQL Editor → pegar este archivo.
--
-- Contexto: ~4k SKU, 4 POS + 1 caja + 1 bodega + TV cuadro de mando (refresh 30s).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- --- Productos: búsqueda POS (/buscar_producto) y tienda pública (_buscar_productos_db) ---
CREATE INDEX IF NOT EXISTS idx_productos_nombre_trgm
  ON productos USING gin (lower(nombre) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_productos_codigo_barra_trgm
  ON productos USING gin (lower(COALESCE(codigo_barra, '')) gin_trgm_ops)
  WHERE codigo_barra IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_codigo_interno_trgm
  ON productos USING gin (lower(COALESCE(codigo_interno, '')) gin_trgm_ops)
  WHERE codigo_interno IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_codigo_chilemat_trgm
  ON productos USING gin (lower(COALESCE(codigo_chilemat, '')) gin_trgm_ops)
  WHERE codigo_chilemat IS NOT NULL;

-- Escáner POS: upper(trim(codigo))
CREATE INDEX IF NOT EXISTS idx_productos_codigo_barra_upper
  ON productos (upper(trim(codigo_barra)))
  WHERE codigo_barra IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_codigo_interno_upper
  ON productos (upper(trim(codigo_interno)))
  WHERE codigo_interno IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_codigo_chilemat_upper
  ON productos (upper(trim(codigo_chilemat)))
  WHERE codigo_chilemat IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_activo_id
  ON productos (id)
  WHERE activo IS TRUE;

-- --- Stock por almacén (semáforo POS: tienda + bodega por lote de ids) ---
-- PK (id_producto, id_almacen) ya existe; este índice ayuda filtros por almacén.
CREATE INDEX IF NOT EXISTS idx_stock_por_almacen_almacen_producto
  ON stock_por_almacen (id_almacen, id_producto);

-- --- Ventas: caja, cola bodega, cuadro de mando / TV ---
CREATE INDEX IF NOT EXISTS idx_ventas_estado
  ON ventas (estado);

CREATE INDEX IF NOT EXISTS idx_ventas_estado_fecha
  ON ventas (estado, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_ventas_fecha_desc
  ON ventas (fecha DESC);

CREATE INDEX IF NOT EXISTS idx_ventas_caja_estado
  ON ventas (caja_id, estado);

CREATE INDEX IF NOT EXISTS idx_ventas_bodega_cola_abierta
  ON ventas (fecha DESC)
  WHERE estado = 'Pagado'
    AND bodega_preparacion_estado IS NOT NULL
    AND bodega_preparacion_estado <> 'CERRADO';

CREATE INDEX IF NOT EXISTS idx_ventas_pre_cobro_bodega
  ON ventas (bodega_sugerido_preparar DESC, fecha ASC)
  WHERE estado = 'Pendiente'
    AND (metodo_pago IS NULL OR metodo_pago = '');

CREATE INDEX IF NOT EXISTS idx_ventas_caja_usuario_abierta
  ON ventas (caja_id, usuario)
  WHERE estado = 'Abierta';

-- --- Detalle ventas: subquery cola bodega (retiro línea BODEGA en vales Mixto) ---
CREATE INDEX IF NOT EXISTS idx_detalle_ventas_id_venta
  ON detalle_ventas (id_venta);

CREATE INDEX IF NOT EXISTS idx_detalle_ventas_retiro_linea_bodega
  ON detalle_ventas (id_venta)
  WHERE upper(trim(COALESCE(punto_retiro_linea, ''))) = 'BODEGA';

ANALYZE productos;
ANALYZE stock_por_almacen;
ANALYZE ventas;
ANALYZE detalle_ventas;
