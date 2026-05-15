# Vista `vista_vales_riesgo_despacho`

Monitoreo de **vales en estado Pendiente**, sin método de pago, con **despacho de bodega** ya registrado (`bodega_despacho_estado` y/o `bodega_despacho_json`), calculando **horas** desde `COALESCE(bodega_despacho_ultimo_at, fecha)` hasta el momento de la consulta.

## Instalación (ejecutar una vez por base)

| Motor      | Script |
|-----------|--------|
| PostgreSQL | `2026_05_08_vista_vales_riesgo_despacho_postgresql.sql` |
| MySQL      | `2026_05_08_vista_vales_riesgo_despacho_mysql.sql` |

Requisitos previos: columnas `ventas.bodega_despacho_*` (la app puede crearlas vía `_asegurar_columnas_ventas_bodega_despacho`).

## Columnas devueltas

| Columna | Descripción |
|---------|-------------|
| `venta_id` | ID del vale |
| `cliente_id` | Cliente |
| `vendedor` | `ventas.usuario` |
| `monto_total` | Total del vale |
| `fecha_emision` | `ventas.fecha` |
| `bodega_despacho_estado` | Estado despacho |
| `ref_despacho_o_emision` | Timestamp de referencia para la métrica |
| `horas_desde_ref` | Horas transcurridas (filtro típico: `>= VALE_DESPACHO_SIN_COBRO_ALERTA_HORAS`) |

## Uso desde API

`POST /api/ventas/alertas-despachos-pendientes` con JSON `{"use_view": true, "dry_run": true}` usa esta vista si existe (`insp.get_view_names()`). Si la vista no está creada, usar la misma ruta sin `use_view` (consulta ORM equivalente).

## Consulta manual

```sql
SELECT * FROM vista_vales_riesgo_despacho
WHERE horas_desde_ref >= 48
ORDER BY ref_despacho_o_emision ASC
LIMIT 100;
```

## Verificación en despliegue

- En `GET /api/sistema/salud` (usuario con permiso `gestionar_usuarios`) el campo **`vista_riesgo_despacho_instalada`** debe ser `true` tras ejecutar el script en esa base.
- Los campos **`bodega_voice_*_auditoria_24h`** reflejan uso reciente del endpoint de voz (auditoría `erp_audit_log`); no sustituyen esta vista.
