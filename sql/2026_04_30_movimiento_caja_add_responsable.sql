-- Movimiento de caja: columnas dedicadas para retiros y trazabilidad.
-- Ejecutar en la base MySQL del proyecto (schema ferreteria o el que uses).

ALTER TABLE movimiento_caja
  ADD COLUMN responsable_retiro VARCHAR(120) NULL AFTER concepto,
  ADD COLUMN usuario_registro VARCHAR(80) NULL AFTER responsable_retiro;

-- Ampliar concepto para evitar truncamiento al separar responsable del texto libre.
ALTER TABLE movimiento_caja
  MODIFY COLUMN concepto VARCHAR(255) NULL;

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
