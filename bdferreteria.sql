			-- Desactivar temporalmente la revisión de llaves foráneas (opcional, por seguridad)
SET FOREIGN_KEY_CHECKS = 0;

-- Borrar las tablas si existen
DROP TABLE IF EXISTS subcategorias;
DROP TABLE IF EXISTS categorias;

-- Reactivar la revisión de llaves foráneas
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Crear tabla de Categorías (Padres)
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

-- 2. Crear tabla de Subcategorías (Hijos)
CREATE TABLE IF NOT EXISTS subcategorias (
    id_subcategoria INT PRIMARY KEY,
    id_categoria INT,
    nombre VARCHAR(100) NOT NULL,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);
-- 1. Crear tabla de Categorías (Padres)
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

-- 2. Crear tabla de Subcategorías (Hijos)
CREATE TABLE IF NOT EXISTS subcategorias (
    id_subcategoria INT PRIMARY KEY,
    id_categoria INT,
    nombre VARCHAR(100) NOT NULL,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);

-- 3. Insertar Categorías Principales
INSERT INTO categorias (id_categoria, nombre) VALUES 
(100, 'Construcción'),
(200, 'Herramientas'),
(300, 'Piso y Pared'),
(400, 'Electricidad e Iluminación'),
(500, 'Ferretería General'),
(600, 'Jardín y Aire Libre'),
(700, 'Baño y Cocina'),
(800, 'Hogar y Electro');

-- 4. Insertar Subcategorías detalladas
INSERT INTO subcategorias (id_subcategoria, id_categoria, nombre) VALUES 
-- Construcción
(101, 100, 'Aceros, Alambres y Mallas'),
(102, 100, 'Cemento, Cal y Aditivos'),
(103, 100, 'Maderas y Tableros'),
(104, 100, 'Techumbre y Accesorios'),
(105, 100, 'Aislación y Sellado'),
-- Herramientas
(201, 200, 'Herramientas Eléctricas'),
(202, 200, 'Herramientas Manuales'),
(203, 200, 'Maquinaria de Construcción'),
(204, 200, 'Medición y Nivelación'),
(205, 200, 'Cajas y Organizadores'),
-- Piso y Pared
(301, 300, 'Cerámicas y Porcelanatos'),
(302, 300, 'Pinturas y Barnices'),
(303, 300, 'Adhesivos y Fragües'),
(304, 300, 'Revestimientos y Terminaciones'),
-- Electricidad
(401, 400, 'Cables y Alambres'),
(402, 400, 'Interruptores y Enchufes'),
(403, 400, 'Iluminación Interior/Exterior'),
(404, 400, 'Canalización y Tableros'),
-- Ferretería
(501, 500, 'Fijaciones y Pernería'),
(502, 500, 'Quincallería y Cerraduras'),
(503, 500, 'Seguridad y EPP'),
(504, 500, 'Escaleras y Cuerdas'),
-- Jardín
(601, 600, 'Riego y Motobombas'),
(602, 600, 'Maquinaria de Jardín'),
(603, 600, 'Piscinas y Químicos'),
(604, 600, 'Camping y Parrillas'),
-- Baño y Cocina
(701, 700, 'Grifería y Accesorios'),
(702, 700, 'Loza Sanitaria'),
(703, 700, 'Lavaplatos y Muebles'),
-- Hogar
(801, 800, 'Línea Blanca'),
(802, 800, 'Calefacción y Ventilación'),
(803, 800, 'Aseo y Organización');

-- Renombrar rfc a rut (si tu versión de MySQL es 8.0+)
ALTER TABLE proveedores CHANGE COLUMN rfc rut VARCHAR(12) NOT NULL;

-- Agregar la columna rubro_principal
ALTER TABLE proveedores ADD COLUMN rubro_principal VARCHAR(100) AFTER ciudad;

-- Asegurar que el RUT sea único
ALTER TABLE proveedores ADD UNIQUE (rut);
INSERT INTO proveedores (nombre, rut, ciudad, rubro_principal, sitio_web, activo) VALUES 
('MELON HORMIGONES S.A.', '91.211.000-0', 'Santiago', 'Cemento y Hormigón', 'www.melon.cl', 1),
('CEMENTOS BIO BIO S.A.', '90.012.000-K', 'Concepción', 'Cemento y Cal', 'www.cbb.cl', 1),
('MAKITA CHILE S.A.', '76.014.285-1', 'Santiago', 'Herramientas Eléctricas', 'www.makita.cl', 1),
('ROBERT BOSCH S.A.', '90.224.000-2', 'Santiago', 'Herramientas y Accesorios', 'www.bosch.cl', 1),
('PIZARREÑO S.A.', '96.505.410-6', 'Maipú', 'Techumbres y Planchas', 'www.pizarreno.cl', 1),
('CINTAC S.A.', '93.138.000-1', 'Maipú', 'Perfiles y Aceros', 'www.cintac.cl', 1),
('STANLEY BLACK & DECKER CHILE', '77.587.210-9', 'Santiago', 'Herramientas Manuales', 'www.stanleytools.cl', 1),
('HENKEL CHILE S.A. (Bekron)', '96.538.110-7', 'Santiago', 'Adhesivos y Fragües', 'www.bekron.cl', 1),
('VINILIT S.A.', '83.435.900-1', 'San Bernardo', 'Tuberías y Gasfitería', 'www.vinilit.cl', 1),
('CERAMICAS CORDILLERA S.A.', '96.657.440-5', 'Lampa', 'Pisos y Cerámicas', 'www.cordillera.cl', 1),
('PINTURAS TRICOLOR S.A.', '96.501.120-2', 'Viña del Mar', 'Pinturas y Barnices', 'www.tricolor.cl', 1),
('INDURA S.A.', '96.506.330-K', 'Cerrillos', 'Soldaduras y Gases', 'www.indura.cl', 1),
('CHILEMAT S.P.A.', '96.963.920-6', 'San Bernardo', 'Distribuidor Mayorista', '://chilemat.com', 1);
INSERT INTO proveedores (nombre, rut, ciudad, rubro_principal, sitio_web, activo) VALUES 
('LEGRAND CHILE S.A.', '91.565.000-6', 'Santiago', 'Electricidad y Canalización', 'www.legrand.cl', 1),
('SCHNEIDER ELECTRIC CHILE', '92.512.000-0', 'Santiago', 'Tableros y Protección Eléctrica', '://se.com', 1),
('PHILIPS CHILE S.A. (Signify)', '90.315.000-2', 'Santiago', 'Iluminación LED y Técnica', 'www.lighting.philips.cl', 1),
('COMPAÑIA INDUSTRIAL EL VOLCAN', '90.046.000-5', 'Santiago', 'Aislación y Yeso Cartón', 'www.volcan.cl', 1),
('FAMA PRODUCTOS DE SEGURIDAD', '78.213.910-6', 'Santiago', 'Seguridad y EPP', 'www.fama.cl', 1),
('STIHL CHILE LIMITADA', '77.345.540-3', 'Lampa', 'Maquinaria de Jardín y Bosque', 'www.stihl.cl', 1),
('DUCTOTEC S.A. (Hoffens)', '96.953.510-9', 'Lampa', 'Conducción de Fluidos y PVC', '://hoffens.com', 1),
('CERRADURAS POLI S.A.', '90.279.000-2', 'Santiago', 'Cerraduras y Quincallería', 'www.poli.cl', 1),
('SCANAVINI S.A.', '90.219.000-5', 'Santiago', 'Cerraduras de Seguridad', 'www.scanavini.cl', 1),
('BOSTIK CHILE S.A.', '93.532.000-3', 'Santiago', 'Selladores y Adhesivos', '://bostik.com', 1),
('TUPER S.A.', '96.533.910-0', 'Maipú', 'Fijaciones y Clavos', 'www.tuper.cl', 1),
('SOPROLE S.A. (División Industrial)', '90.134.000-3', 'Santiago', 'Pegamentos Especiales', 'www.soprole.cl', 1),
('REUTTER S.A. (División Ferretería)', '90.413.000-K', 'Santiago', 'Artículos de Aseo e Industrial', 'www.reutter.cl', 1);
CREATE OR REPLACE VIEW vista_maestra_chilemat AS
SELECT 
    p.id AS 'ID_Producto',
    p.codigo_barra AS 'SKU',
    p.nombre AS 'Producto',
    c.nombre AS 'Categoria_Principal',
    s.nombre AS 'Subcategoria',
    p.precio_venta AS 'Precio_Publico',
    p.stock AS 'Stock_Actual',
    p.unidad AS 'Unidad_Medida',
    -- Ajuste de nombres de columna según tus tablas: prov.id y p.id
    (SELECT prov.nombre 
     FROM proveedores prov 
     JOIN productos_proveedores pp ON prov.id = pp.id_proveedor 
     WHERE pp.id_producto = p.id 
     LIMIT 1) AS 'Proveedor_Principal'
FROM productos p
LEFT JOIN subcategorias s ON p.subcategoria = s.id_subcategoria
LEFT JOIN categorias c ON s.id_categoria = c.id_categoria
WHERE p.activo = 1;

#-- Insertar productos reales con lógica de precios (Venta = Compra + ~30% margen)
INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
-- Construcción (Cat 100) -> Sub: Cemento (102), Fierro (101), Techumbre (104)
('Cemento Melón Especial 25kg', '5000000101', 3450, 4490, 100, 'Saco', 100, 102, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Fierro Estriado 8mm x 6mt', '5000000202', 4800, 6290, 50, 'Tira', 100, 101, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Plancha Zinc Alum 0.35x2.5mt', '5000000303', 8500, 11990, 40, 'Plancha', 100, 104, 1);

-- Herramientas (Cat 200) -> Sub: Eléctricas (201), Manuales (202)
INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Taladro Percutor Makita 13mm 600W', '088381616744', 45000, 59990, 12, 'Unidad', 200, 201, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Esmeril Angular Bosch 4 1/2 700W', '316514082917', 38000, 49990, 8, 'Unidad', 200, 201, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Set Destornilladores Stanley 6 pzs', '747752601051', 9500, 14990, 25, 'Set', 200, 202, 1);

#-- Piso y Pared (Cat 300) -> Sub: Adhesivos (303), Pinturas (302)
INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Adhesivo Bekron AC 25kg', '780123456789', 5200, 6990, 150, 'Saco', 300, 303, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Látex Extracubriente Tricolor Blanco 1gal', '780650000123', 12500, 17990, 30, 'Galón', 300, 302, 1);

#-- Electricidad (Cat 400) -> Sub: Cables (401), Enchufes (402)
INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Cable THHN 14 AWG Verde 100mt', '780461011222', 28000, 38990, 10, 'Rollo', 400, 401, 1);

INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Interruptor 9/12 Legrand Blanco', '324506077001', 1800, 2990, 60, 'Unidad', 400, 402, 1);

#-- Jardín y Aire Libre (Cat 600) -> Sub: Riego (601)
INSERT INTO productos (nombre, codigo_barra, precio_compra, precio_venta, stock, unidad, categoria, subcategoria, activo) VALUES 
('Motosierra Stihl MS 170', '795711446622', 145000, 199990, 5, 'Unidad', 600, 602, 1);



CREATE OR REPLACE VIEW vista_valorizacion_inventario AS
SELECT 
    id AS ID,
    nombre AS Producto,
    stock AS Stock_Actual,
    precio_compra AS Costo_Unitario,
    precio_venta AS Venta_Unitaria,
    (stock * precio_compra) AS Inversion_Total_Stock,
    (stock * precio_venta) AS Valor_Venta_Total,
    ((stock * precio_venta) - (stock * precio_compra)) AS Margen_Bruto_Proyectado
FROM productos
WHERE activo = 1;


/* 1. Limpiamos ventas de prueba anteriores (Opcional) */
-- DELETE FROM detalle_ventas;
-- DELETE FROM ventas;

/* 2. Insertamos ventas para los últimos 7 días */
INSERT INTO ventas (fecha, monto_total, usuario, estado, metodo_pago) VALUES 
(CURDATE() - INTERVAL 6 DAY, 155000, 'Mario', 'Completada', 'Efectivo'),
(CURDATE() - INTERVAL 5 DAY, 210000, 'Mario', 'Completada', 'Tarjeta'),
(CURDATE() - INTERVAL 4 DAY, 185000, 'Mario', 'Completada', 'Transferencia'),
(CURDATE() - INTERVAL 3 DAY, 320000, 'Mario', 'Completada', 'Tarjeta'),
(CURDATE() - INTERVAL 2 DAY, 280000, 'Mario', 'Completada', 'Efectivo'),
(CURDATE() - INTERVAL 1 DAY, 450000, 'Mario', 'Completada', 'Tarjeta'),
(CURDATE(), 125000, 'Mario', 'Completada', 'Efectivo');

/* 3. Verificamos que se insertaron correctamente */
SELECT * FROM ventas ORDER BY fecha DESC LIMIT 7;
