# Guardián — Alcance cerrado SD-1 (sin actividades abiertas)

**Fecha cierre documental:** 2026-05-21  
**PWA:** `/owner-mobile` · **API:** `GET /api/v1/owner/dashboard?v=3`

---

## Qué SÍ está en SD-1 (listo para demo)

**UI presentación (2026-05-21):** hero con anillo de estado, ventas destacadas, copiloto VERTEX, 4 tarjetas visibles, feed con iconos. **Admin → Empresa → Un establecimiento** (`operacion_un_local=1`, default) evita copy “3 sucursales”; env `OWNER_GUARDIAN_UN_LOCAL` solo override.

| Función | Comportamiento |
|---------|----------------|
| Semáforos | Caja, inventario, crédito, OC + mini semáforos |
| Ventas hoy | KPI desde API (`consolidado`) |
| Feed | Últimos eventos Agente Operador (`feed_preview`) |
| Mensaje IA | Texto por reglas (no LLM) |
| Actualizar | Poll ~45 s + botón refrescar |
| Instalar PWA | Manifest + pantalla de inicio |
| Navegación | Tarjetas → Control Center / abastecimiento / créditos / OC |
| **Llamar supervisor** | Ver sección abajo |

---

## Voz en Guardián — **fuera de SD-1** (cerrado como SD-2)

El botón **micrófono** en la barra inferior **no graba ni envía audio**.

- Muestra: *«Agente de voz: próximamente (SD-2)»*.
- No existe `POST /api/v1/owner/voice` en producción.
- La **voz en bodega** (`/api/bodega/voice-command`) es **otro módulo** (despacho bodega), no el Guardián dueño.

**Decisión:** no probar voz en Guardián hasta SD-2. No es deuda abierta de SD-1.

---

## Llamar supervisor — cómo funciona (2 minutos)

### No llama “al móvil registrado del usuario logueado”

El ERP **no** usa el teléfono del usuario que hizo login. Usa un número **fijo de operación** configurado en el servidor:

```env
OWNER_SUPERVISOR_TELEFONO=+56923739904
```

(O alias `OWNER_SUPERVISOR_TEL`.)

### Qué hace el botón

1. La API devuelve `supervisor_telefono` en el JSON del dashboard.
2. Si hay número → el botón **Llamar supervisor** se habilita con `href="tel:+569..."`.
3. En **celular**, al tocar abre la **app Teléfono** con ese número marcado (el dueño elige llamar o no).
4. Si **no** hay variable en Render → botón gris; al tocar: *Configure OWNER_SUPERVISOR_TELEFONO…*

### Validación SD-1 (opcional, 1 paso)

| Paso | OK |
|------|-----|
| Poner en Render `OWNER_SUPERVISOR_TELEFONO` con el móvil del supervisor de turno | [ ] |
| Redeploy / reinicio servicio | [ ] |
| En `/owner-mobile`, botón **Llamar supervisor** activo (no gris) | [ ] |
| Tocar → abre marcador con ese número | [ ] |

Si no configuran el env: **SD-1 igual puede cerrarse**; la llamada queda como mejora operativa, no bloqueante de código.

---

## Centro de Mandos global

`/owner/vertex-control` y `?scope=global_maestro` = **vista maestro LhexIA** (demo red). No es requisito de piso Santo Domingo.

---

## Post SD-1 (no abiertos ahora)

| Ítem | Fase |
|------|------|
| Voz Guardián (`/api/v1/owner/voice`) | SD-2 |
| Web Push alertas | SD-2 |
| `sucursal_id` real en semáforos | SD-2 |
| Feed paginado `?cursor=` | V3.1 |

Ver: [`GUARDIAN_V3_PROPUESTA.md`](GUARDIAN_V3_PROPUESTA.md)

---

## Checklist rápido “Guardián cerrado SD-1”

- [x] Código V3.0 + tests API
- [ ] §D piso: semáforos + ventas hoy en celular (5 min)
- [x] Voz: explícitamente **N/A SD-1**
- [ ] Llamada: opcional si configuran `OWNER_SUPERVISOR_TELEFONO`

*Con esto no quedan hilos sueltos: lo no probado es lo que no existe o es opcional por env.*
