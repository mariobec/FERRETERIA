# Bodega «ultra premium» — modelo consolidado (LexIA ERP)

Documento de **producto + arquitectura** alineado al código existente (mayo 2026). No sustituye la lectura de `app.py` para detalle de rutas.

---

## Principio

**Un solo flujo de verdad por concepto**, varias **pantallas especializadas** enlazadas desde un **cuadro de mando** (`/bodega/cuadro-mando`), en lugar de una mega-vista que mezcla todo.

---

## Capas ya implementadas (coherentes entre sí)

| Capa | Ruta / recurso | Rol |
|------|----------------|-----|
| **Cuadro de mando** | `GET /bodega/cuadro-mando` | Visibilidad: conteos, últimos vales post-cobro, vales pre-cobro bodega (ordenados con «sugerido preparar» primero), top SKU pendiente retiro, enlaces rápidos. |
| **Plataforma retiro** | `GET /bodega/plataforma` | Cola operativa **post-cobro**: trabajar la preparación y abrir detalle por vale. |
| **Detalle retiro** | `GET /bodega/vale/<id>/retiro` | Líneas, cantidades parciales, confirmación de retiro físico (stock bodega + kardex). |
| **Despacho voz (pre-cobro)** | `GET /bodega/despachos` + `POST /api/bodega/voice-command` | Salida anticipada de bodega **antes** del cobro (`bodega_despacho_json`), con permiso y reglas ya definidas. |
| **Cobro caja** | `procesar_cobro_caja` | Si retiro = Bodega: valida stock bodega, **no** descuenta tienda al pagar; crea cola `bodega_preparacion_*`. |
| **Avisos** | `GET /api/bodega/retiros-cola-snapshot` + script en `base.html` | Pitido + toast para `bodega_operador` al aparecer nuevo ID en cola post-cobro. |

---

## ¿Unificar vistas o mantenerlas enlazadas?

**Recomendación explícita: mantenerlas enlazadas** (como ahora).

- **Cuadro de mando** = tablero y **navegación** (KPI + alertas visuales + accesos).
- **Plataforma** = lista filtrable para **ejecución** del día.
- **Detalle** = **acciones por línea** (formularios, validaciones).
- **Voz** = **modo manos libres** distinto; no conviene fundirlo con tablas densas.

Unificar todo en una sola página suele **empeorar UX en tablet / PC de bodega** y complica permisos y pruebas. Si en el futuro se quiere **modo TV pantalla completa**, se puede hacer una **cuarta vista** solo lectura que consuma los mismos datos del mando.

---

## Definición «ultra premium» (roadmap por fases)

### Fase actual (v1 operativa)

- Post-cobro con retiro bodega, entregas parciales, preparación por estados, auditoría, aviso sonoro, **cuadro de mando** con agregados y top SKU pendiente.

### Fase 2 (proactividad sin romper caja) — implementada

- **Cola visual «sugerido preparar»** en el cuadro de mando: vales `Pendiente` + retiro bodega + sin método de pago; Marcar/Quitar vía `POST /bodega/vale/<id>/sugerido-preparar`. Es **solo etiqueta / orden** en la lista (**no** reserva ni descuenta stock).
- Columnas en `ventas`: `bodega_sugerido_preparar` (0/1), `bodega_sugerido_preparar_at`, `bodega_sugerido_preparar_usuario`. Al pasar a **Pagado** en caja se limpian (el marcador aplica solo mientras está pendiente).
- Integración opcional con **recepciones** (qué ingresó hoy y desbloquea faltantes en el mando): pendiente de producto.

### Fase 3 (premium fuerte)

- **SLA** (minutos desde pago / desde listo), ranking por operador, export del día.
- **Segunda pantalla** o URL dedicada solo mando (sin menú lateral).
- **WebSocket / SSE** si el negocio exige sub-segundo (hoy: polling ~8 s).

### Fase 4 (opcional industrial)

- Ubicaciones pick path, olas por zona, handheld con escaneo masivo.

---

## Referencias en código

- Rutas bodega: `blueprints/bodega.py` (incluye `bodega_vale_sugerido_preparar_post`)
- Lógica principal: `app.py` (`bodega_cuadro_mando`, `bodega_plataforma`, `bodega_vale_retiro`, `bodega_vale_sugerido_preparar_post`, `procesar_cobro_caja`, `api_bodega_retiros_cola_snapshot`)
- Stock: `services/stock_service.py`
