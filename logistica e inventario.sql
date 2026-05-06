-- ============================================================
-- 1. TABLAS PARA EL MÓDULO DE RECEPCIÓN (Entrada de Camiones)
-- ============================================================

CREATE TABLE recepciones_compra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proveedor_id INT NOT NULL,
    documento_tipo ENUM('Factura', 'Guia de Despacho') NOT NULL,
    documento_numero VARCHAR(50) NOT NULL,
    fecha_recepcion DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_bodega VARCHAR(100),
    observaciones TEXT,
    estado ENUM('Pendiente', 'Incompleta', 'Finalizada') DEFAULT 'Pendiente',
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
) ENGINE=InnoDB;

CREATE TABLE detalle_recepcion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recepcion_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad_documento INT NOT NULL, -- Lo que dice el papel
    cantidad_recibida INT NOT NULL,  -- Lo que contó el bodeguero
    FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
) ENGINE=InnoDB;


-- ============================================================
-- 2. TABLAS PARA EL MÓDULO DE TOMA DE INVENTARIO (Auditoría)
-- ============================================================

CREATE TABLE auditorias_inventario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_fin DATETIME NULL,
    usuario_auditor VARCHAR(100),
    sector_bodega VARCHAR(50), -- Ej: "Pasillo 1", "Patio Patio de maderas"
    estado ENUM('En Proceso', 'Finalizada', 'Ajustada') DEFAULT 'En Proceso'
) ENGINE=InnoDB;

CREATE TABLE detalle_auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auditoria_id INT NOT NULL,
    producto_id INT NOT NULL,
    stock_sistema INT NOT NULL, -- Lo que el ERP dice que hay
    stock_fisico INT NOT NULL,  -- Lo que el bodeguero contó
    diferencia INT GENERATED ALWAYS AS (stock_fisico - stock_sistema) STORED,
    FOREIGN KEY (auditoria_id) REFERENCES auditorias_inventario(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
) ENGINE=InnoDB;

-- ============================================================
-- 3. TABLA PARA PICKING (Preparación de pedidos para clientes)
-- ============================================================

CREATE TABLE ordenes_picking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT NOT NULL, -- Relación con el "Vale" generado en el ERP
    usuario_bodeguero VARCHAR(100),
    estado_picking ENUM('Pendiente', 'Preparando', 'Listo', 'Entregado') DEFAULT 'Pendiente',
    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (venta_id) REFERENCES ventas(id)
) ENGINE=InnoDB;
DELIMITER //
CREATE TRIGGER tr_actualizar_kpi_articulos
AFTER INSERT ON detalle_ventas
FOR EACH ROW
BEGIN
    UPDATE dashboard_stats 
    SET articulos_rotados = articulos_rotados + NEW.cantidad
    WHERE fecha = CURDATE();
END //
DELIMITER ;

-- Esto recalcula los datos de hoy manualmente
INSERT INTO dashboard_stats (fecha, total_venta_clp, cantidad_tickets, articulos_rotados, ticket_promedio)
SELECT 
    CURDATE(), 
    SUM(monto_total), 
    COUNT(*), 
    (SELECT SUM(cantidad) FROM detalle_ventas WHERE id_venta IN (SELECT id FROM ventas WHERE DATE(fecha) = CURDATE())),
    AVG(monto_total)
FROM ventas 
WHERE DATE(fecha) = CURDATE()
ON DUPLICATE KEY UPDATE 
    total_venta_clp = VALUES(total_venta_clp),
    cantidad_tickets = VALUES(cantidad_tickets),
    articulos_rotados = VALUES(articulos_rotados),
    ticket_promedio = VALUES(ticket_promedio);

-- Primero agregamos la columna
ALTER TABLE ventas 
ADD COLUMN cliente_id INT AFTER id;

-- Luego creamos la relación (Foreign Key)
ALTER TABLE ventas 
ADD CONSTRAINT fk_cliente_venta 
FOREIGN KEY (cliente_id) REFERENCES clientes(id) 
ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS cuentas_por_cobrar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    venta_id INT NOT NULL,
    monto_total DECIMAL(12,2) NOT NULL,
    monto_pagado DECIMAL(12,2) DEFAULT 0.00,
    fecha_vencimiento DATE,
    estado ENUM('Pendiente', 'Parcial', 'Pagado') DEFAULT 'Pendiente',
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS abonos_clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cuenta_id INT NOT NULL,
    fecha_pago DATETIME DEFAULT CURRENT_TIMESTAMP,
    monto_abono DECIMAL(12,2) NOT NULL,
    metodo_pago VARCHAR(50),
    usuario_recibe VARCHAR(50),
    FOREIGN KEY (cuenta_id) REFERENCES cuentas_por_cobrar(id)
) ENGINE=InnoDB;


DROP TRIGGER IF EXISTS tr_actualizar_kpi_venta;

DELIMITER //
CREATE TRIGGER tr_actualizar_kpi_venta
AFTER UPDATE ON ventas
FOR EACH ROW
BEGIN
    -- Solo actuamos si el monto_total cambió de 0 al valor real
    IF OLD.monto_total = 0 AND NEW.monto_total > 0 THEN
        INSERT INTO dashboard_stats (fecha, total_venta_clp, cantidad_tickets)
        VALUES (CURDATE(), NEW.monto_total, 1)
        ON DUPLICATE KEY UPDATE 
            total_venta_clp = total_venta_clp + NEW.monto_total,
            cantidad_tickets = cantidad_tickets + 1,
            ticket_promedio = total_venta_clp / cantidad_tickets;
    END IF;
END //
DELIMITER ;

DELIMITER //
CREATE TRIGGER tr_gestion_premium_ventas
AFTER UPDATE ON ventas
FOR EACH ROW
BEGIN
    -- CASO A: Se emite un vale (Monto total sube de 0 y sigue pendiente)
    IF OLD.monto_total = 0 AND NEW.monto_total > 0 AND NEW.estado != 'Pagado' THEN
        INSERT INTO dashboard_stats (fecha, monto_en_vuelo)
        VALUES (CURDATE(), NEW.monto_total)
        ON DUPLICATE KEY UPDATE monto_en_vuelo = monto_en_vuelo + NEW.monto_total;
    
    -- CASO B: El cliente paga el vale (Sale de vuelo y entra a caja)
    ELSEIF OLD.estado != 'Pagado' AND NEW.estado = 'Pagado' THEN
        INSERT INTO dashboard_stats (fecha, total_venta_clp, monto_en_vuelo, cantidad_tickets)
        VALUES (CURDATE(), NEW.monto_total, 0, 1)
        ON DUPLICATE KEY UPDATE 
            total_venta_clp = total_venta_clp + NEW.monto_total,
            monto_en_vuelo = monto_en_vuelo - OLD.monto_total, -- Lo sacamos de "vuelo"
            cantidad_tickets = cantidad_tickets + 1,
            ticket_promedio = total_venta_clp / cantidad_tickets;
    END IF;
END //
DELIMITER ;

DROP TRIGGER IF EXISTS tr_gestion_premium_ventas;

DELIMITER //
CREATE TRIGGER tr_gestion_premium_ventas
AFTER UPDATE ON ventas
FOR EACH ROW
BEGIN
    -- Recalculamos todo el día de una vez para asegurar precisión absoluta
    INSERT INTO dashboard_stats (fecha, total_venta_clp, monto_en_vuelo, cantidad_tickets, ticket_promedio)
    SELECT 
        CURDATE(), 
        IFNULL(SUM(CASE WHEN estado = 'Pagado' THEN monto_total ELSE 0 END), 0),
        IFNULL(SUM(CASE WHEN estado != 'Pagado' AND monto_total > 0 THEN monto_total ELSE 0 END), 0),
        COUNT(CASE WHEN estado = 'Pagado' THEN 1 END),
        IFNULL(AVG(CASE WHEN estado = 'Pagado' THEN monto_total END), 0)
    FROM ventas 
    WHERE DATE(fecha) = CURDATE()
    ON DUPLICATE KEY UPDATE 
        total_venta_clp = VALUES(total_venta_clp),
        monto_en_vuelo = VALUES(monto_en_vuelo),
        cantidad_tickets = VALUES(cantidad_tickets),
        ticket_promedio = VALUES(ticket_promedio);
END //
SET SQL_SAFE_UPDATES = 0;

UPDATE ventas SET monto_total = monto_total WHERE DATE(fecha) = CURDATE();

SET SQL_SAFE_UPDATES = 1;

DROP TRIGGER IF EXISTS tr_gestion_premium_ventas;

DELIMITER //
CREATE TRIGGER tr_gestion_premium_ventas
AFTER UPDATE ON ventas
FOR EACH ROW
BEGIN
    -- Recalculamos los totales de HOY de forma masiva para que no haya errores
    INSERT INTO dashboard_stats (fecha, total_venta_clp, monto_en_vuelo, cantidad_tickets, ticket_promedio)
    SELECT 
        CURDATE(), 
        IFNULL(SUM(CASE WHEN estado = 'Pagado' THEN monto_total ELSE 0 END), 0),
        IFNULL(SUM(CASE WHEN estado IN ('Pendiente', 'Abierta') AND monto_total > 0 THEN monto_total ELSE 0 END), 0),
        COUNT(CASE WHEN estado = 'Pagado' THEN 1 END),
        IFNULL(AVG(CASE WHEN estado = 'Pagado' AND monto_total > 0 THEN monto_total END), 0)
    FROM ventas 
    WHERE DATE(fecha) = CURDATE()
    ON DUPLICATE KEY UPDATE 
        total_venta_clp = VALUES(total_venta_clp),
        monto_en_vuelo = VALUES(monto_en_vuelo),
        cantidad_tickets = VALUES(cantidad_tickets),
        ticket_promedio = VALUES(ticket_promedio);
END //
DELIMITER ;

DROP TRIGGER IF EXISTS tr_gestion_premium_ventas;


DROP TRIGGER IF EXISTS tr_gestion_premium_ventas;
DROP TRIGGER IF EXISTS tr_actualizar_kpi_venta;

SET SQL_SAFE_UPDATES = 0;

UPDATE caja 
SET estado = 'Cerrada', fecha_cierre = NOW() 
WHERE estado = 'Abierta';

SET SQL_SAFE_UPDATES = 1;

-- 1. Ver todas las ventas de la última caja abierta
-- Esto te dirá si las ventas realmente se están asociando a la caja
SELECT 
    v.id AS Folio, 
    v.fecha, 
    v.monto_total, 
    v.metodo_pago, 
    v.estado, 
    v.caja_id
FROM ventas v
WHERE v.caja_id = (SELECT id FROM caja WHERE estado = 'Abierta' ORDER BY id DESC LIMIT 1);

-- 2. Resumen rápido de totales por método de pago para la caja actual
-- Aquí verás si hay errores de escritura (ej. "Efectivo" vs "efectivo")
SELECT 
    metodo_pago, 
    SUM(monto_total) AS Total_Suma, 
    COUNT(*) AS Cantidad_Ventas
FROM ventas
WHERE caja_id = (SELECT id FROM caja WHERE estado = 'Abierta' ORDER BY id DESC LIMIT 1)
GROUP BY metodo_pago;

-- 3. Buscar ventas "Huérfanas" (Ventas que no tienen caja asignada)
-- Si este resultado te da datos, significa que tu código de 'guardar_venta' no está vinculando la caja
SELECT * FROM ventas WHERE caja_id IS NULL;



-- 1. Agregamos campos tributarios a la tabla de VENTAS
ALTER TABLE ventas 
ADD COLUMN tipo_documento VARCHAR(20) DEFAULT 'Boleta' AFTER estado,
ADD COLUMN nro_documento INT NULL AFTER tipo_documento,
ADD COLUMN neto DOUBLE DEFAULT 0 AFTER monto_total,
ADD COLUMN iva DOUBLE DEFAULT 0 AFTER neto;

-- 2. Agregamos campos obligatorios para Facturación a la tabla de CLIENTES
-- El 'Giro' es vital para las facturas en Chile
ALTER TABLE clientes 
ADD COLUMN razon_social VARCHAR(150) NULL AFTER nombre,
ADD COLUMN comuna VARCHAR(50) NULL AFTER direccion,
ADD COLUMN ciudad VARCHAR(50) NULL AFTER comuna;

-- 3. (Opcional) Crear una tabla para controlar los FOLIOS
-- Esto evitará que los números de boleta se repitan
CREATE TABLE IF NOT EXISTS folios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo_documento VARCHAR(20) UNIQUE,
    ultimo_folio INT DEFAULT 0
);

-- Insertamos los contadores iniciales
INSERT IGNORE INTO folios (tipo_documento, ultimo_folio) VALUES ('Boleta', 0);
INSERT IGNORE INTO folios (tipo_documento, ultimo_folio) VALUES ('Factura', 0);

-- Agregar saldo deudor al cliente
ALTER TABLE clientes ADD COLUMN saldo_deudor DOUBLE DEFAULT 0;
ALTER TABLE clientes ADD COLUMN limite_credito DOUBLE DEFAULT 500000; -- Ejemplo 500 mil
-- Saldo para el cliente
ALTER TABLE clientes ADD COLUMN saldo_deudor DOUBLE DEFAULT 0;
ALTER TABLE clientes ADD COLUMN limite_credito DOUBLE DEFAULT 500000;

-- Tabla de Abonos Pro
CREATE TABLE abonos_credito (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT,
    monto_abono DOUBLE,
    saldo_anterior DOUBLE,
    nuevo_saldo DOUBLE,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    metodo_pago VARCHAR(20),
    caja_id INT, -- Vital para tu cierre
    usuario_id INT, -- Quién recibió el dinero
    comentario TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

-- Verificar si las columnas existen
DESCRIBE clientes;

-- Si no aparecen, agrégalas manualmente para que coincidan con tu código:
ALTER TABLE clientes ADD COLUMN saldo_deudor DOUBLE DEFAULT 0;
ALTER TABLE clientes ADD COLUMN limite_credito DOUBLE DEFAULT 500000;
ALTER TABLE clientes ADD COLUMN estado_credito VARCHAR(20) DEFAULT 'Activo';

-- Movimiento de caja: columnas dedicadas para retiros y trazabilidad.
-- Ejecutar en la base MySQL del proyecto (schema ferreteria o el que uses).

-- Backfill desde formato legacy: "[RESP:Nombre] Motivo..."
-- Workbench suele tener SQL_SAFE_UPDATES=1 y bloquea UPDATE sin clave en WHERE.
SET @OLD_SAFE := @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;

UPDATE movimiento_caja
SET
  responsable_retiro = TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(concepto, ']', 1), '[RESP:', -1)),
  concepto = TRIM(SUBSTRING(concepto, LOCATE(']', concepto) + 1))
WHERE id > 0
  AND tipo = 'Egreso'
  AND concepto LIKE '[RESP:%]%'
  AND (responsable_retiro IS NULL OR responsable_retiro = '');

SET SQL_SAFE_UPDATES = @OLD_SAFE;

-- Kardex (movimientos de inventario) y tablas de recepción de mercadería.
-- Ejecutar en la base ferreteria (MySQL). Ajustar si las tablas ya existen.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS movimientos_inventario (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL DEFAULT 1,
  tipo_movimiento VARCHAR(20) NOT NULL,
  cantidad INT NOT NULL,
  motivo VARCHAR(500) NULL,
  usuario VARCHAR(100) NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  referencia_tipo VARCHAR(40) NULL,
  referencia_id INT NULL,
  stock_saldo INT NULL,
  CONSTRAINT fk_kardex_producto FOREIGN KEY (id_producto) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_kardex_producto_fecha (id_producto, fecha),
  KEY idx_kardex_tipo (tipo_movimiento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS recepciones_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  documento_tipo ENUM('Factura', 'Guia de Despacho') NOT NULL,
  documento_numero VARCHAR(50) NOT NULL,
  fecha_recepcion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  usuario_bodega VARCHAR(100) NULL,
  estado ENUM('Pendiente', 'Incompleta', 'Finalizada') NOT NULL DEFAULT 'Pendiente',
  CONSTRAINT fk_recv_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS detalle_recepcion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  recepcion_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad_documento INT NOT NULL,
  cantidad_recibida INT NOT NULL,
  CONSTRAINT fk_detrecv_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_detrecv_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_detrecv_recepcion (recepcion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Kardex (movimientos de inventario) y tablas de recepción de mercadería.
-- Ejecutar en la base ferreteria (MySQL). Ajustar si las tablas ya existen.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS movimientos_inventario (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL DEFAULT 1,
  tipo_movimiento VARCHAR(20) NOT NULL,
  cantidad INT NOT NULL,
  motivo VARCHAR(500) NULL,
  usuario VARCHAR(100) NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  referencia_tipo VARCHAR(40) NULL,
  referencia_id INT NULL,
  stock_saldo INT NULL,
  CONSTRAINT fk_kardex_producto FOREIGN KEY (id_producto) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_kardex_producto_fecha (id_producto, fecha),
  KEY idx_kardex_tipo (tipo_movimiento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



-- Bitácora de costos de compra por recepción (proveedor/producto)
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS bitacora_costos_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  producto_id INT NOT NULL,
  proveedor_id INT NULL,
  recepcion_id INT NULL,
  costo_anterior DOUBLE NOT NULL DEFAULT 0,
  costo_nuevo DOUBLE NOT NULL DEFAULT 0,
  variacion_pct DOUBLE NULL,
  precio_venta_referencia DOUBLE NULL,
  margen_proyectado DOUBLE NULL,
  usuario VARCHAR(100) NULL,
  observacion VARCHAR(255) NULL,
  CONSTRAINT fk_bcc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  KEY idx_bcc_fecha (fecha),
  KEY idx_bcc_producto_fecha (producto_id, fecha),
  KEY idx_bcc_proveedor_fecha (proveedor_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



-- Gestión de Ubicaciones (Pasillo-Estante-Nivel) + Unidades compuestas.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

-- unidad_compra
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_compra'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_compra VARCHAR(20) NULL AFTER unidad'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- unidad_venta
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_venta'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_venta VARCHAR(20) NULL AFTER unidad_compra'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- factor_conversion
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'factor_conversion'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN factor_conversion DOUBLE NOT NULL DEFAULT 1 AFTER unidad_venta'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación pasillo
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_pasillo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_pasillo VARCHAR(12) NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación estante
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_estante'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_estante VARCHAR(12) NULL AFTER ubicacion_pasillo'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación nivel
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_nivel'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_nivel VARCHAR(12) NULL AFTER ubicacion_estante'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Backfill de unidades para no dejar nulos
UPDATE productos
SET unidad_venta = COALESCE(NULLIF(unidad_venta, ''), NULLIF(unidad, ''), 'Unidad'),
    unidad_compra = COALESCE(NULLIF(unidad_compra, ''), COALESCE(NULLIF(unidad, ''), 'Unidad'))
WHERE id > 0;

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


SELECT id, estado, documento_numero FROM recepciones_compra ORDER BY id DESC;
SELECT * FROM detalle_recepcion ORDER BY id DESC LIMIT 20;
SELECT * FROM movimientos_inventario WHERE referencia_tipo='recepcion' ORDER BY id DESC LIMIT 20;
SELECT * FROM almacenes



-- Limpia filas inválidas (si existen)
DELETE FROM almacenes WHERE id IS NULL;
-- Crea un almacén válido base
INSERT INTO almacenes (nombre, ubicacion)
VALUES ('Almacén Central', 'Bodega Principal');


SELECT * FROM almacenes;
DELETE FROM almacenes
WHERE nombre IS NULL
  AND ubicacion IS NULL;
CREATE TABLE IF NOT EXISTS bitacora_precios_venta (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  producto_id INT NOT NULL,
  precio_anterior DECIMAL(12,2) NOT NULL DEFAULT 0,
  precio_nuevo DECIMAL(12,2) NOT NULL DEFAULT 0,
  costo_referencia DECIMAL(12,2) NULL,
  margen_objetivo DECIMAL(8,4) NULL,
  usuario VARCHAR(100) NULL,
  motivo VARCHAR(255) NULL,
  CONSTRAINT fk_bitacora_precio_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



CREATE TABLE IF NOT EXISTS unidades_medida (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(10) NOT NULL UNIQUE,
  nombre VARCHAR(50) NOT NULL,
  tipo VARCHAR(20) NOT NULL DEFAULT 'unidad',
  activo TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversiones_unidad (
  id INT AUTO_INCREMENT PRIMARY KEY,
  unidad_origen_id INT NOT NULL,
  unidad_destino_id INT NOT NULL,
  factor DECIMAL(18,6) NOT NULL DEFAULT 1,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_conversion_unidad (unidad_origen_id, unidad_destino_id),
  CONSTRAINT fk_conv_unidad_origen FOREIGN KEY (unidad_origen_id) REFERENCES unidades_medida(id),
  CONSTRAINT fk_conv_unidad_destino FOREIGN KEY (unidad_destino_id) REFERENCES unidades_medida(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO unidades_medida (codigo, nombre, tipo)
SELECT 'UN', 'Unidad', 'unidad' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM unidades_medida WHERE codigo = 'UN');
INSERT INTO unidades_medida (codigo, nombre, tipo)
SELECT 'KG', 'Kilogramo', 'peso' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM unidades_medida WHERE codigo = 'KG');
INSERT INTO unidades_medida (codigo, nombre, tipo)
SELECT 'M', 'Metro', 'longitud' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM unidades_medida WHERE codigo = 'M');
INSERT INTO unidades_medida (codigo, nombre, tipo)
SELECT 'CJ', 'Caja', 'empaque' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM unidades_medida WHERE codigo = 'CJ');



-- Catálogo maestro categoría → subcategoría (orden lógico) + enlace opcional en productos.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS catalogo_categorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_cat_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS catalogo_subcategorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  categoria_id INT NOT NULL,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_sub (categoria_id, nombre),
  CONSTRAINT fk_catalogo_sub_categoria FOREIGN KEY (categoria_id) REFERENCES catalogo_categorias(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'subcategoria_catalogo_id'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN subcategoria_catalogo_id INT NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'productos'
        AND constraint_name = 'fk_productos_subcategoria_catalogo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD CONSTRAINT fk_productos_subcategoria_catalogo FOREIGN KEY (subcategoria_catalogo_id) REFERENCES catalogo_subcategorias(id) ON DELETE SET NULL'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- Tercer nivel del maestro (p. ej. Categorias.xlsx): categoría 1 + sub nivel 2 + sub nivel 3.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND column_name = 'nivel2'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD COLUMN nivel2 VARCHAR(80) NOT NULL DEFAULT \'\' AFTER categoria_id'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Quitar unique (categoria_id, nombre) creado por la migración inicial o por SQLAlchemy (solo 2 columnas).
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND INDEX_NAME = 'uq_catalogo_sub'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_sub',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_subcategoria_cat_nombre'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_subcategoria_cat_nombre',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_sub_cat_nivel_nombre'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD UNIQUE KEY uq_catalogo_sub_cat_nivel_nombre (categoria_id, nivel2, nombre)'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;



-- Tercer nivel del maestro (p. ej. Categorias.xlsx): categoría 1 + sub nivel 2 + sub nivel 3.
-- Nota: el UNIQUE (categoria_id, nombre) suele ser el índice que soporta la FK hacia catalogo_categorias;
-- hay que crear otro índice con prefijo categoria_id ANTES de DROP INDEX (error 1553 si no).

SET NAMES utf8mb4;
SET @db_name := DATABASE();

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND column_name = 'nivel2'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD COLUMN nivel2 VARCHAR(80) NOT NULL DEFAULT \'\' AFTER categoria_id'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice no único para que la FK fk_catalogo_sub_categoria siga teniendo soporte al quitar el UNIQUE antiguo.
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'ix_catalogo_subcategorias_fk_categoria'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD INDEX ix_catalogo_subcategorias_fk_categoria (categoria_id)'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias' AND INDEX_NAME = 'uq_catalogo_sub'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_sub',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_subcategoria_cat_nombre'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX uq_catalogo_subcategoria_cat_nombre',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_sub_cat_nivel_nombre'
    ),
    'SELECT 1',
    'ALTER TABLE catalogo_subcategorias ADD UNIQUE KEY uq_catalogo_sub_cat_nivel_nombre (categoria_id, nivel2, nombre)'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- El UNIQUE nuevo ya empieza por categoria_id; el índice auxiliar es redundante.
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'ix_catalogo_subcategorias_fk_categoria'
    )
    AND EXISTS(
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = @db_name AND table_name = 'catalogo_subcategorias'
        AND INDEX_NAME = 'uq_catalogo_sub_cat_nivel_nombre'
    ),
    'ALTER TABLE catalogo_subcategorias DROP INDEX ix_catalogo_subcategorias_fk_categoria',
    'SELECT 1'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Órdenes de compra (Fase 1) + enlace opcional en recepciones_compra.
-- MySQL / InnoDB. Idempotente en lo posible.

SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS ordenes_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  numero VARCHAR(50) NOT NULL,
  fecha_emision DATE NOT NULL,
  estado ENUM('Borrador','Enviada','Parcial','Cerrada','Anulada') NOT NULL DEFAULT 'Borrador',
  observacion VARCHAR(500) NULL,
  usuario_creador VARCHAR(100) NULL,
  fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_oc_proveedor_numero (proveedor_id, numero),
  CONSTRAINT fk_oc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_oc_proveedor (proveedor_id),
  KEY idx_oc_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS detalle_orden_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  orden_compra_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad DECIMAL(14,4) NOT NULL DEFAULT 0,
  precio_unitario DECIMAL(14,4) NOT NULL DEFAULT 0,
  CONSTRAINT fk_doc_oc FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_doc_oc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_doc_oc_orden (orden_compra_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra' AND column_name = 'orden_compra_id'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD COLUMN orden_compra_id INT NULL AFTER proveedor_id'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra'
        AND constraint_name = 'fk_recv_orden_compra'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD CONSTRAINT fk_recv_orden_compra FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id) ON DELETE SET NULL ON UPDATE CASCADE'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- Auditoría de anulación de vale en caja (cliente no retorna, error de emisión, etc.).
-- MySQL. Idempotente: solo agrega columnas si no existen.

SET NAMES utf8mb4;
SET @db := DATABASE();

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'motivo_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN motivo_anulacion VARCHAR(500) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'fecha_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN fecha_anulacion DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'usuario_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN usuario_anulacion VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;
vista_maestra_chilemat

-- correción base de datos
-- Movimiento de caja: columnas dedicadas para retiros y trazabilidad.
-- Ejecutar en la base MySQL del proyecto (schema ferreteria o el que uses).
-- Kardex (movimientos de inventario) y tablas de recepción de mercadería.
-- Ejecutar en la base ferreteria (MySQL). Ajustar si las tablas ya existen.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS movimientos_inventario (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL DEFAULT 1,
  tipo_movimiento VARCHAR(20) NOT NULL,
  cantidad INT NOT NULL,
  motivo VARCHAR(500) NULL,
  usuario VARCHAR(100) NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  referencia_tipo VARCHAR(40) NULL,
  referencia_id INT NULL,
  stock_saldo INT NULL,
  CONSTRAINT fk_kardex_producto FOREIGN KEY (id_producto) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_kardex_producto_fecha (id_producto, fecha),
  KEY idx_kardex_tipo (tipo_movimiento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Compatibilidad MySQL (sin IF NOT EXISTS en ADD COLUMN)
SET @db_name := DATABASE();

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'referencia_tipo'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN referencia_tipo VARCHAR(40) NULL AFTER fecha'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'referencia_id'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN referencia_id INT NULL AFTER referencia_tipo'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = @db_name
        AND table_name = 'movimientos_inventario'
        AND column_name = 'stock_saldo'
    ),
    'SELECT 1',
    'ALTER TABLE movimientos_inventario ADD COLUMN stock_saldo INT NULL AFTER referencia_id'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS recepciones_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  documento_tipo ENUM('Factura', 'Guia de Despacho') NOT NULL,
  documento_numero VARCHAR(50) NOT NULL,
  fecha_recepcion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  usuario_bodega VARCHAR(100) NULL,
  estado ENUM('Pendiente', 'Incompleta', 'Finalizada') NOT NULL DEFAULT 'Pendiente',
  CONSTRAINT fk_recv_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS detalle_recepcion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  recepcion_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad_documento INT NOT NULL,
  cantidad_recibida INT NOT NULL,
  CONSTRAINT fk_detrecv_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_detrecv_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_detrecv_recepcion (recepcion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bitácora de costos de compra por recepción (proveedor/producto)
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS bitacora_costos_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  producto_id INT NOT NULL,
  proveedor_id INT NULL,
  recepcion_id INT NULL,
  costo_anterior DOUBLE NOT NULL DEFAULT 0,
  costo_nuevo DOUBLE NOT NULL DEFAULT 0,
  variacion_pct DOUBLE NULL,
  precio_venta_referencia DOUBLE NULL,
  margen_proyectado DOUBLE NULL,
  usuario VARCHAR(100) NULL,
  observacion VARCHAR(255) NULL,
  CONSTRAINT fk_bcc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_bcc_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  KEY idx_bcc_fecha (fecha),
  KEY idx_bcc_producto_fecha (producto_id, fecha),
  KEY idx_bcc_proveedor_fecha (proveedor_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Gestión de Ubicaciones (Pasillo-Estante-Nivel) + Unidades compuestas.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

-- unidad_compra
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_compra'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_compra VARCHAR(20) NULL AFTER unidad'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- unidad_venta
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'unidad_venta'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN unidad_venta VARCHAR(20) NULL AFTER unidad_compra'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- factor_conversion
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'factor_conversion'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN factor_conversion DOUBLE NOT NULL DEFAULT 1 AFTER unidad_venta'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación pasillo
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_pasillo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_pasillo VARCHAR(12) NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación estante
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_estante'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_estante VARCHAR(12) NULL AFTER ubicacion_pasillo'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ubicación nivel
SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'ubicacion_nivel'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN ubicacion_nivel VARCHAR(12) NULL AFTER ubicacion_estante'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Backfill de unidades para no dejar nulos
UPDATE productos
SET unidad_venta = COALESCE(NULLIF(unidad_venta, ''), NULLIF(unidad, ''), 'Unidad'),
    unidad_compra = COALESCE(NULLIF(unidad_compra, ''), COALESCE(NULLIF(unidad, ''), 'Unidad'))
WHERE id > 0;

-- Inventario por almacén: tablas almacenes + stock_por_almacen + semilla BODEGA/TIENDA.
-- Idempotente (MySQL). Copia stock histórico del catálogo hacia TIENDA; BODEGA queda en 0.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS almacenes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(20) NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_almacenes_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_por_almacen (
  id_producto INT NOT NULL,
  id_almacen INT NOT NULL,
  cantidad INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id_producto, id_almacen),
  CONSTRAINT fk_spa_producto FOREIGN KEY (id_producto) REFERENCES productos(id) ON DELETE CASCADE,
  CONSTRAINT fk_spa_almacen FOREIGN KEY (id_almacen) REFERENCES almacenes(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO almacenes (codigo, nombre, activo) VALUES ('BODEGA', 'Bodega / CD', 1)
  ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);
INSERT INTO almacenes (codigo, nombre, activo) VALUES ('TIENDA', 'Tienda', 1)
  ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), activo = VALUES(activo);

SET @id_bodega := (SELECT id FROM almacenes WHERE codigo = 'BODEGA' LIMIT 1);
SET @id_tienda := (SELECT id FROM almacenes WHERE codigo = 'TIENDA' LIMIT 1);

-- Stock existente en catálogo -> TIENDA
INSERT INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id, @id_tienda, COALESCE(p.stock, 0)
FROM productos p
WHERE COALESCE(p.stock, 0) <> 0
ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad);

-- Fila BODEGA en 0 para todos los productos (si no existe)
INSERT IGNORE INTO stock_por_almacen (id_producto, id_almacen, cantidad)
SELECT p.id, @id_bodega, 0
FROM productos p;

-- Catálogo maestro categoría → subcategoría (orden lógico) + enlace opcional en productos.
SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS catalogo_categorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_cat_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS catalogo_subcategorias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  categoria_id INT NOT NULL,
  nombre VARCHAR(80) NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catalogo_sub (categoria_id, nombre),
  CONSTRAINT fk_catalogo_sub_categoria FOREIGN KEY (categoria_id) REFERENCES catalogo_categorias(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'productos' AND column_name = 'subcategoria_catalogo_id'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD COLUMN subcategoria_catalogo_id INT NULL AFTER subcategoria'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'productos'
        AND constraint_name = 'fk_productos_subcategoria_catalogo'
    ),
    'SELECT 1',
    'ALTER TABLE productos ADD CONSTRAINT fk_productos_subcategoria_catalogo FOREIGN KEY (subcategoria_catalogo_id) REFERENCES catalogo_subcategorias(id) ON DELETE SET NULL'
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Órdenes de compra (Fase 1) + enlace opcional en recepciones_compra.
-- MySQL / InnoDB. Idempotente en lo posible.

SET NAMES utf8mb4;
SET @db_name := DATABASE();

CREATE TABLE IF NOT EXISTS ordenes_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proveedor_id INT NOT NULL,
  numero VARCHAR(50) NOT NULL,
  fecha_emision DATE NOT NULL,
  estado ENUM('Borrador','Enviada','Parcial','Cerrada','Anulada') NOT NULL DEFAULT 'Borrador',
  observacion VARCHAR(500) NULL,
  usuario_creador VARCHAR(100) NULL,
  fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_oc_proveedor_numero (proveedor_id, numero),
  CONSTRAINT fk_oc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_oc_proveedor (proveedor_id),
  KEY idx_oc_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS detalle_orden_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  orden_compra_id INT NOT NULL,
  producto_id INT NOT NULL,
  cantidad DECIMAL(14,4) NOT NULL DEFAULT 0,
  precio_unitario DECIMAL(14,4) NOT NULL DEFAULT 0,
  CONSTRAINT fk_doc_oc FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_doc_oc_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  KEY idx_doc_oc_orden (orden_compra_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra' AND column_name = 'orden_compra_id'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD COLUMN orden_compra_id INT NULL AFTER proveedor_id'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    EXISTS(
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = @db_name AND table_name = 'recepciones_compra'
        AND constraint_name = 'fk_recv_orden_compra'
    ),
    'SELECT 1',
    'ALTER TABLE recepciones_compra ADD CONSTRAINT fk_recv_orden_compra FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id) ON DELETE SET NULL ON UPDATE CASCADE'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Auditoría de anulación de vale en caja (cliente no retorna, error de emisión, etc.).
-- MySQL. Idempotente: solo agrega columnas si no existen.

SET NAMES utf8mb4;
SET @db := DATABASE();

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'motivo_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN motivo_anulacion VARCHAR(500) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'fecha_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN fecha_anulacion DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'usuario_anulacion';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN usuario_anulacion VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Monto de línea en POS. Requiere columna descuento (migración 2026_05_04_detalle_ventas_descuento.sql).
-- Error sin esta columna: Unknown column 'detalle_ventas.subtotal' in 'field list'

ALTER TABLE detalle_ventas
  ADD COLUMN subtotal DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Monto línea: cantidad * precio_unitario * (1 - descuento/100)'
  AFTER descuento;

UPDATE detalle_ventas
SET subtotal = cantidad * precio_unitario * (1 - IFNULL(descuento, 0) / 100);

-- Monto de línea en POS. Requiere columna descuento (migración 2026_05_04_detalle_ventas_descuento.sql).
-- Error sin esta columna: Unknown column 'detalle_ventas.subtotal' in 'field list'

ALTER TABLE detalle_ventas
  ADD COLUMN subtotal DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Monto línea: cantidad * precio_unitario * (1 - descuento/100)'
  AFTER descuento;
-- Campos de crédito en `clientes` (modelo Cliente en app.py).
-- Sin ellas falla /inicio: SELECT sum(clientes.saldo_deudor) ...
-- Si aparece Error 1060 Duplicate column: esa columna ya existe; comenta o omite esa línea.

ALTER TABLE clientes
  ADD COLUMN saldo_deudor DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Monto adeudado actual';

ALTER TABLE clientes
  ADD COLUMN limite_credito DOUBLE NOT NULL DEFAULT 500000
  COMMENT 'Tope de crédito';

ALTER TABLE clientes
  ADD COLUMN estado_credito VARCHAR(20) NOT NULL DEFAULT 'Activo'
  COMMENT 'Activo o Bloqueado';



-- Campos de crédito en `clientes` (modelo Cliente en app.py).
-- Sin ellas falla /inicio: SELECT sum(clientes.saldo_deudor) ...
-- Si aparece Error 1060 Duplicate column: esa columna ya existe; comenta o omite esa línea.

ALTER TABLE clientes
  ADD COLUMN saldo_deudor DOUBLE NOT NULL DEFAULT 0
  COMMENT 'Monto adeudado actual';

ALTER TABLE clientes
  ADD COLUMN limite_credito DOUBLE NOT NULL DEFAULT 500000
  COMMENT 'Tope de crédito';

ALTER TABLE clientes
  ADD COLUMN estado_credito VARCHAR(20) NOT NULL DEFAULT 'Activo'
  COMMENT 'Activo o Bloqueado';


-- Agrega columnas faltantes a `clientes` sin romper instalaciones existentes.
-- Motivo: el modelo `Cliente` en `app.py` usa rut/giro/direccion; si la BD no las tiene,
-- aparece error 1054 Unknown column 'clientes.rut' en búsquedas del POS.
--
-- Compatibilidad: MySQL/MariaDB sin "ADD COLUMN IF NOT EXISTS".
-- Ejecutar en la BD del ERP (la misma de SQLALCHEMY_DATABASE_URI).

SET @db := DATABASE();

-- 1) RUT (se deja NULL para no bloquear registros antiguos sin RUT)
SET @has_rut := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'rut'
);
SET @sql := IF(@has_rut = 0,
  'ALTER TABLE clientes ADD COLUMN rut VARCHAR(12) NULL',
  'SELECT ''OK: clientes.rut ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice único para rut (permite múltiples NULL)
SET @has_ux_rut := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND INDEX_NAME = 'ux_clientes_rut'
);
SET @sql := IF(@has_ux_rut = 0,
  'CREATE UNIQUE INDEX ux_clientes_rut ON clientes (rut)',
  'SELECT ''OK: indice ux_clientes_rut ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2) GIRO
SET @has_giro := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'giro'
);
SET @sql := IF(@has_giro = 0,
  'ALTER TABLE clientes ADD COLUMN giro VARCHAR(100) NULL',
  'SELECT ''OK: clientes.giro ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3) DIRECCION
SET @has_direccion := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'direccion'
);
SET @sql := IF(@has_direccion = 0,
  'ALTER TABLE clientes ADD COLUMN direccion VARCHAR(200) NULL',
  'SELECT ''OK: clientes.direccion ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- Agrega columnas faltantes a `almacenes` para inventario multi-almacén.
-- Motivo: el modelo `Almacen` en `app.py` usa codigo/activo.
--
-- Compatibilidad: MySQL/MariaDB sin "ADD COLUMN IF NOT EXISTS".
-- Ejecutar en la BD del ERP (la misma de SQLALCHEMY_DATABASE_URI).

SET @db := DATABASE();

-- 1) codigo
SET @has_codigo := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'almacenes' AND COLUMN_NAME = 'codigo'
);
SET @sql := IF(@has_codigo = 0,
  'ALTER TABLE almacenes ADD COLUMN codigo VARCHAR(20) NOT NULL',
  'SELECT ''OK: almacenes.codigo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2) activo
SET @has_activo := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'almacenes' AND COLUMN_NAME = 'activo'
);
SET @sql := IF(@has_activo = 0,
  'ALTER TABLE almacenes ADD COLUMN activo BOOL NULL DEFAULT 1',
  'SELECT ''OK: almacenes.activo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;





-- Comuna y ciudad del receptor (factura/boleta 80 mm, datos de cliente).
-- Si Error 1060 Duplicate column: omitir la línea correspondiente.

SET @db := DATABASE();

SET @has_comuna := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'comuna'
);
SET @sql := IF(@has_comuna = 0,
  'ALTER TABLE clientes ADD COLUMN comuna VARCHAR(80) NULL',
  'SELECT ''OK: clientes.comuna ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ciudad := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'clientes' AND COLUMN_NAME = 'ciudad'
);
SET @sql := IF(@has_ciudad = 0,
  'ALTER TABLE clientes ADD COLUMN ciudad VARCHAR(80) NULL',
  'SELECT ''OK: clientes.ciudad ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;



-- Copia archivada del documento tributario (boleta/factura 80 mm) en PDF para recuperación desde historial.
-- MySQL. Idempotente.

SET NAMES utf8mb4;
SET @db := DATABASE();

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'copia_documento_pdf_at';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN copia_documento_pdf_at DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'ventas' AND COLUMN_NAME = 'copia_documento_pdf';
SET @q := IF(@exists = 0, 'ALTER TABLE ventas ADD COLUMN copia_documento_pdf LONGBLOB NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;



 -- Enrolamiento / toma en tiempo real: Chilemat, código interno, foto, sesiones de conteo.
-- MySQL. Idempotente.

SET NAMES utf8mb4;
SET @db := DATABASE();

-- productos: maestro Chilemat, código interno propio, miniatura
SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'codigo_chilemat';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN codigo_chilemat VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'codigo_interno';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN codigo_interno VARCHAR(32) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND COLUMN_NAME = 'imagen_url';
SET @q := IF(@exists = 0, 'ALTER TABLE productos ADD COLUMN imagen_url VARCHAR(500) NULL', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND INDEX_NAME = 'idx_productos_codigo_chilemat';
SET @q := IF(@exists = 0, 'CREATE INDEX idx_productos_codigo_chilemat ON productos (codigo_chilemat)', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @exists FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'productos' AND INDEX_NAME = 'idx_productos_codigo_interno';
SET @q := IF(@exists = 0, 'CREATE UNIQUE INDEX idx_productos_codigo_interno ON productos (codigo_interno)', 'SELECT 1');
PREPARE stmt FROM @q; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Tablas de sesión (conteo por operario / turno)
CREATE TABLE IF NOT EXISTS enrolamiento_toma_sesion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  usuario VARCHAR(80) NULL,
  id_almacen INT NULL,
  iniciado_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enrol_sesion_usuario (usuario),
  INDEX idx_enrol_sesion_almacen (id_almacen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enrolamiento_toma_linea (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sesion_id INT NOT NULL,
  producto_id INT NOT NULL,
  conteo INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_enrol_linea_sesion_prod (sesion_id, producto_id),
  INDEX idx_enrol_linea_prod (producto_id),
  CONSTRAINT fk_enrol_linea_sesion FOREIGN KEY (sesion_id) REFERENCES enrolamiento_toma_sesion(id) ON DELETE CASCADE,
  CONSTRAINT fk_enrol_linea_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
