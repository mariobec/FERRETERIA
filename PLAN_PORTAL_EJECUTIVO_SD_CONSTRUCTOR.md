# Portal ejecutivo · SD Constructor

**Cliente:** SD Constructor (marca operativa; antes Ferretería Santo Domingo en vitrina).  
**Producto:** portal de lectura gerencial **dentro del ERP**, no LhexIA branding.  
**Acceso:** roles con `panel_gerencia`, `ver_gerencia` o `gestionar_usuarios` (gerentes y dueños).

## P1 (implementado)

| Entrega | Ruta |
|--------|------|
| Vista shell 5 pestañas (2 activas) | `GET /portal-ejecutivo` |
| Resumen KPI | `GET /api/portal/resumen?periodo=mes\|trim\|anio` |
| Activos / rotación | `GET /api/portal/activos?periodo=...` |
| Stubs P2/P3 | `/api/portal/margenes`, `flujo`, `proyeccion` → 501 |

### Config (`data/empresa_config.json` o **Administración → Datos de empresa**)

| Clave | Uso |
|-------|-----|
| `portal_marca` | Título UI (default: SD Constructor) |
| `portal_gastos_op_mensual_clp` | Gasto operacional **fijo mensual** (×1 mes / ×3 trim / ×12 año) |
| `portal_activos_fijos_clp` | Activos fijos manuales hasta módulo AF |
| `portal_meta_ventas_anual_clp` | Meta anual → referencia semanal en gráfico |

Edición en UI: `/admin/empresa` → sección **Portal ejecutivo · SD Constructor**.

### Reglas de cálculo

- Ventas: solo `Venta.estado == 'Pagado'`.
- CMV: `cantidad × precio_compra`.
- Inventario: stock tienda+bodega × costo; excluye `TEST-` / `DEMO-`.
- CxC: suma `Cliente.saldo_deudor`.
- Caja: `monto_inicial` de caja abierta.
- Comprometido: OC `Borrador` / `Enviada` / `Parcial` (estimado).
- Utilidad operativa est. = margen bruto − gasto operacional del período.

## P2 / P3 (pendiente)

- Márgenes por categoría, flujo caja/movimientos, proyección con metas.

## Menú ERP

Gerencia y fiscal → **SD Constructor · Portal**
