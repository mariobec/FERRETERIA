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
