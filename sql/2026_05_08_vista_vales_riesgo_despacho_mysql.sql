-- Vista para monitoreo / BI: vales Pendiente sin método de pago con despacho registrado en bodega.
-- La columna horas_desde_ref se calcula respecto a COALESCE(bodega_despacho_ultimo_at, fecha).
-- Filtrar por umbral en la consulta: WHERE horas_desde_ref >= @horas (app / cron).
-- Requiere columnas bodega_despacho_* en ventas (misma migración que despacho voz).

CREATE OR REPLACE VIEW vista_vales_riesgo_despacho AS
SELECT
    v.id AS venta_id,
    v.cliente_id,
    v.usuario AS vendedor,
    v.monto_total,
    v.fecha AS fecha_emision,
    v.bodega_despacho_estado,
    COALESCE(v.bodega_despacho_ultimo_at, v.fecha) AS ref_despacho_o_emision,
    (TIMESTAMPDIFF(MINUTE, COALESCE(v.bodega_despacho_ultimo_at, v.fecha), NOW()) / 60.0) AS horas_desde_ref
FROM ventas v
WHERE v.estado = 'Pendiente'
  AND (v.metodo_pago IS NULL OR TRIM(IFNULL(v.metodo_pago, '')) = '')
  AND (
        (v.bodega_despacho_estado IS NOT NULL AND TRIM(v.bodega_despacho_estado) <> '')
        OR (v.bodega_despacho_json IS NOT NULL AND LENGTH(TRIM(v.bodega_despacho_json)) > 2)
  );
