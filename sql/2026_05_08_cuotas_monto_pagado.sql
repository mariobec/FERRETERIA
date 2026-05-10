-- Abonos en cascada sobre cuotas: monto ya cubierto dentro de cada cuota (permite estado Parcial).
-- PostgreSQL:
ALTER TABLE ventas_cuotas_credito ADD COLUMN IF NOT EXISTS monto_pagado DOUBLE PRECISION NOT NULL DEFAULT 0;
UPDATE ventas_cuotas_credito SET monto_pagado = COALESCE(monto, 0) WHERE estado = 'Pagada';

-- MySQL (ejecutar manualmente si aplica; quitar IF NOT EXISTS si la versión no lo soporta):
-- ALTER TABLE ventas_cuotas_credito ADD COLUMN monto_pagado DOUBLE NOT NULL DEFAULT 0;
-- UPDATE ventas_cuotas_credito SET monto_pagado = COALESCE(monto, 0) WHERE estado = 'Pagada';
