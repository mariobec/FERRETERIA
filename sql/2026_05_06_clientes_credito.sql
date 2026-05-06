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
