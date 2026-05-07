-- Persistencia de cuadratura y control de cierre de caja
ALTER TABLE caja
    ADD COLUMN monto_teorico_cierre DOUBLE NULL AFTER monto_final,
    ADD COLUMN monto_contado_cierre DOUBLE NULL AFTER monto_teorico_cierre,
    ADD COLUMN diferencia_cierre DOUBLE NULL AFTER monto_contado_cierre,
    ADD COLUMN observacion_cierre VARCHAR(255) NULL AFTER diferencia_cierre,
    ADD COLUMN supervisor_cierre VARCHAR(80) NULL AFTER observacion_cierre;
