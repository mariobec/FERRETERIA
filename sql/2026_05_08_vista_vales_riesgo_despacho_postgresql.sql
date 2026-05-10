-- Vista para monitoreo / BI: vales Pendiente sin método de pago con despacho registrado en bodega.
-- horas_desde_ref: horas desde COALESCE(bodega_despacho_ultimo_at, fecha) hasta NOW().
-- Uso: SELECT * FROM vista_vales_riesgo_despacho WHERE horas_desde_ref >= 48 ORDER BY ref_despacho_o_emision;

CREATE OR REPLACE VIEW vista_vales_riesgo_despacho AS
SELECT
    v.id AS venta_id,
    v.cliente_id,
    v.usuario AS vendedor,
    v.monto_total,
    v.fecha AS fecha_emision,
    v.bodega_despacho_estado,
    COALESCE(v.bodega_despacho_ultimo_at, v.fecha) AS ref_despacho_o_emision,
    (EXTRACT(EPOCH FROM (NOW() - COALESCE(v.bodega_despacho_ultimo_at, v.fecha))) / 3600.0)::double precision AS horas_desde_ref
FROM ventas v
WHERE v.estado = 'Pendiente'
  AND (v.metodo_pago IS NULL OR TRIM(v.metodo_pago) = '')
  AND (
        (v.bodega_despacho_estado IS NOT NULL AND TRIM(v.bodega_despacho_estado) <> '')
        OR (v.bodega_despacho_json IS NOT NULL AND LENGTH(TRIM(v.bodega_despacho_json)) > 2)
  );
