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
