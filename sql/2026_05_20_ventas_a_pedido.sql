-- Compromiso de entrega / venta en verde (Fase 2 POS)
CREATE TABLE IF NOT EXISTS ventas_a_pedido (
    id SERIAL PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    detalle_venta_id INTEGER NOT NULL UNIQUE REFERENCES detalle_ventas(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL DEFAULT 1,
    fecha_promesa DATE NOT NULL,
    estado_entrega VARCHAR(32) NOT NULL DEFAULT 'por_pedir',
    retiro_tienda BOOLEAN NOT NULL DEFAULT TRUE,
    despacho_domicilio BOOLEAN NOT NULL DEFAULT FALSE,
    notificar_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
    telefono_notificacion VARCHAR(30) NULL,
    usuario VARCHAR(80) NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ventas_a_pedido_venta_id ON ventas_a_pedido(venta_id);
CREATE INDEX IF NOT EXISTS ix_ventas_a_pedido_estado ON ventas_a_pedido(estado_entrega);
CREATE INDEX IF NOT EXISTS ix_ventas_a_pedido_fecha ON ventas_a_pedido(fecha_promesa);
