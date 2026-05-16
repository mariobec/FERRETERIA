-- Venta en verde (a pedido): líneas sin stock físico inmediato
ALTER TABLE detalle_ventas ADD COLUMN IF NOT EXISTS a_pedido BOOLEAN NOT NULL DEFAULT FALSE;
