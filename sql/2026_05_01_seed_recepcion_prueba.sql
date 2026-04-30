-- Seed de pruebas: recepción de mercadería + productos base.
-- Recomendación: ejecutar primero migraciones de kardex/ubicaciones.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

-- 1) Proveedor de prueba (solo si no existe)
INSERT INTO proveedores (nombre, contacto, telefono, email)
SELECT 'Proveedor Pruebas Recepcion', 'Bodega QA', '999999999', 'qa.recepcion@example.com'
FROM DUAL
WHERE NOT EXISTS (
  SELECT 1 FROM proveedores WHERE nombre = 'Proveedor Pruebas Recepcion'
);

-- 2) Productos de prueba (usa codigo_barra único)
INSERT INTO productos (
  nombre, codigo_barra, precio_compra, precio_venta, precio_mayoreo,
  unidad, unidad_compra, unidad_venta, factor_conversion, stock,
  categoria, subcategoria, ubicacion_pasillo, ubicacion_estante, ubicacion_nivel, activo
)
SELECT
  'Tornillo Zincado 1in (Prueba)', 'PRB-TORN-001', 12500, 220, 200,
  'Unidad', 'Caja', 'Unidad', 100, 1200,
  'Herramientas', 'Tornillos', 'P02', 'E04', 'N1', 1
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM productos WHERE codigo_barra = 'PRB-TORN-001');

INSERT INTO productos (
  nombre, codigo_barra, precio_compra, precio_venta, precio_mayoreo,
  unidad, unidad_compra, unidad_venta, factor_conversion, stock,
  categoria, subcategoria, ubicacion_pasillo, ubicacion_estante, ubicacion_nivel, activo
)
SELECT
  'Cadena Galvanizada 6mm (Prueba)', 'PRB-CAD-001', 18500, 980, 900,
  'Metro', 'Rollo', 'Metro', 25, 180,
  'Construccion', 'Cadenas', 'P05', 'E01', 'N2', 1
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM productos WHERE codigo_barra = 'PRB-CAD-001');

INSERT INTO productos (
  nombre, codigo_barra, precio_compra, precio_venta, precio_mayoreo,
  unidad, unidad_compra, unidad_venta, factor_conversion, stock,
  categoria, subcategoria, ubicacion_pasillo, ubicacion_estante, ubicacion_nivel, activo
)
SELECT
  'Cable THHN 2.5mm (Prueba)', 'PRB-CAB-001', 38000, 1290, 1190,
  'Metro', 'Rollo', 'Metro', 100, 250,
  'Electricidad', 'Cables', 'P06', 'E03', 'N3', 1
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM productos WHERE codigo_barra = 'PRB-CAB-001');

-- 3) Crear recepción de prueba (una sola vez)
SET @id_proveedor_prueba := (
  SELECT id FROM proveedores WHERE nombre = 'Proveedor Pruebas Recepcion' ORDER BY id DESC LIMIT 1
);

INSERT INTO recepciones_compra (
  proveedor_id, documento_tipo, documento_numero, fecha_recepcion, usuario_bodega, estado
)
SELECT
  @id_proveedor_prueba, 'Factura', 'PRB-REC-001', NOW(), 'Seeder SQL', 'Finalizada'
FROM DUAL
WHERE NOT EXISTS (
  SELECT 1 FROM recepciones_compra WHERE documento_numero = 'PRB-REC-001'
);

SET @id_recepcion_prueba := (
  SELECT id FROM recepciones_compra WHERE documento_numero = 'PRB-REC-001' ORDER BY id DESC LIMIT 1
);

-- 4) Detalle recepción + actualización stock + kardex (evita duplicar)
SET @id_prod_torn := (SELECT id FROM productos WHERE codigo_barra = 'PRB-TORN-001' LIMIT 1);
SET @id_prod_cad  := (SELECT id FROM productos WHERE codigo_barra = 'PRB-CAD-001' LIMIT 1);

INSERT INTO detalle_recepcion (recepcion_id, producto_id, cantidad_documento, cantidad_recibida)
SELECT @id_recepcion_prueba, @id_prod_torn, 50, 48
FROM DUAL
WHERE @id_recepcion_prueba IS NOT NULL
  AND @id_prod_torn IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM detalle_recepcion
    WHERE recepcion_id = @id_recepcion_prueba AND producto_id = @id_prod_torn
  );

UPDATE productos
SET stock = stock + 48
WHERE id = @id_prod_torn
  AND NOT EXISTS (
    SELECT 1 FROM movimientos_inventario
    WHERE referencia_tipo = 'recepcion' AND referencia_id = @id_recepcion_prueba
      AND id_producto = @id_prod_torn AND tipo_movimiento = 'ENTRADA'
  );

INSERT INTO movimientos_inventario (
  id_producto, id_almacen, tipo_movimiento, cantidad, motivo, usuario, fecha, referencia_tipo, referencia_id, stock_saldo
)
SELECT
  @id_prod_torn, 1, 'ENTRADA', 48,
  CONCAT('Recepcion PRB-REC-001 #', @id_recepcion_prueba),
  'Seeder SQL', NOW(), 'recepcion', @id_recepcion_prueba,
  (SELECT stock FROM productos WHERE id = @id_prod_torn)
FROM DUAL
WHERE @id_prod_torn IS NOT NULL
  AND @id_recepcion_prueba IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM movimientos_inventario
    WHERE referencia_tipo = 'recepcion' AND referencia_id = @id_recepcion_prueba
      AND id_producto = @id_prod_torn AND tipo_movimiento = 'ENTRADA'
  );

INSERT INTO detalle_recepcion (recepcion_id, producto_id, cantidad_documento, cantidad_recibida)
SELECT @id_recepcion_prueba, @id_prod_cad, 20, 20
FROM DUAL
WHERE @id_recepcion_prueba IS NOT NULL
  AND @id_prod_cad IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM detalle_recepcion
    WHERE recepcion_id = @id_recepcion_prueba AND producto_id = @id_prod_cad
  );

UPDATE productos
SET stock = stock + 20
WHERE id = @id_prod_cad
  AND NOT EXISTS (
    SELECT 1 FROM movimientos_inventario
    WHERE referencia_tipo = 'recepcion' AND referencia_id = @id_recepcion_prueba
      AND id_producto = @id_prod_cad AND tipo_movimiento = 'ENTRADA'
  );

INSERT INTO movimientos_inventario (
  id_producto, id_almacen, tipo_movimiento, cantidad, motivo, usuario, fecha, referencia_tipo, referencia_id, stock_saldo
)
SELECT
  @id_prod_cad, 1, 'ENTRADA', 20,
  CONCAT('Recepcion PRB-REC-001 #', @id_recepcion_prueba),
  'Seeder SQL', NOW(), 'recepcion', @id_recepcion_prueba,
  (SELECT stock FROM productos WHERE id = @id_prod_cad)
FROM DUAL
WHERE @id_prod_cad IS NOT NULL
  AND @id_recepcion_prueba IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM movimientos_inventario
    WHERE referencia_tipo = 'recepcion' AND referencia_id = @id_recepcion_prueba
      AND id_producto = @id_prod_cad AND tipo_movimiento = 'ENTRADA'
  );
