-- Campo para definir dónde se retira la mercadería (lo define la vendedora al emitir vale).
ALTER TABLE ventas
  ADD COLUMN punto_retiro VARCHAR(30) NULL DEFAULT 'Bodega' AFTER usuario_anulacion;
