# Lhexia Guardián v3 — Propuesta de máxima potencia

**Estado:** V3.0 MVP **cerrado SD-1** (semáforos, feed, KPI, llamada `tel:` opcional). Voz/Push/multi-sucursal real = **SD-2+**. Ver [`GUARDIAN_SD1_ALCANCE_CERRADO.md`](GUARDIAN_SD1_ALCANCE_CERRADO.md).  
**Base actual:** v3 (`/api/v1/owner/dashboard?v=3`, PWA `/owner-mobile`)  
**Alineación:** SD-1 primero · IA-1 post SD-1 · SD-2 multi-sucursal caja  

---

## 1. Visión en una frase

**Guardián v3** deja de ser un “tablero semáforo” y pasa a ser el **copiloto ejecutivo en el bolsillo**: detecta, explica, prioriza, notifica y propone la **siguiente acción** (con voz, push y un toque), por sucursal y por red, con trazabilidad del Agente Operador.

---

## 2. Qué ya tenemos (v2) vs. el techo

| Capacidad | v2 hoy | Techo v3 |
|-----------|--------|----------|
| Perfiles | Dueño global / Supervisor sucursal (heurística rol) | Perfiles + **sucursal_id real** en BD |
| Semáforos | Caja + inventario (2 tarjetas) | **6 dominios** (caja, stock, crédito, compras, FE, operador) |
| IA | `mensaje_ia` texto estático desde reglas | **Operador enriquecido** + resumen LLM acotado |
| Consolidado | Descuadre acumulado red | P&L flash, ventas vs ayer, ranking sucursales |
| Acciones | Llamar / Control / Actualizar / Mic (toast) | **Acciones contextuales** + voz + push |
| Offline | SW básico | Cola offline + último snapshot firmado |
| Icono | Isotipo 2D | **Escudo Guardián 3D** maskable 512 |

---

## 3. Los 6 pilares v3 (máxima potencia)

### Pilar A — **Centro de mando vivo (feed)**

Un **timeline** vertical (no solo tarjetas estáticas):

- Eventos del Agente Operador (`agente_ejecuciones`) en tiempo real.
- Filtro: Crítico · Caja · Inventario · Crédito · Compras.
- Cada ítem: título, monto CLP, sucursal, “hace X min”, CTA (Ver vale / Ir a caja / Aprobar HITL).

**API:** `GET /api/v1/owner/feed?cursor=&perfil=`  
**UI:** debajo del hero; pull-to-refresh nativo.

### Pilar B — **Inteligencia explicable (no caja negra)**

1. **Capa reglas** (ya existe Operador) — fuente de verdad.
2. **Capa narrativa** — `mensaje_ia` generado desde payload enriquecido (sin inventar cifras).
3. **Capa opcional LLM** (post SD-1, flag `GUARDIAN_LLM=1`) — solo parafrasea y prioriza; **nunca** escribe en BD.

Ejemplo v3:

> “Don Mario: en SD-1 hay descuadre de **+$360** en 1 cierre; en la red el acumulado es **+$8.168.790**. Inventario estable (1 SKU bajo mínimo). Recomiendo llamar al supervisor de turno antes de las 18:00.”

### Pilar C — **Multi-sucursal real (fin de heurísticas)**

Prerrequisito ligero SD-2:

- `Caja.id_sucursal` o tabla `UsuarioSucursal` (usuario ↔ almacén/sucursal).
- Dashboard filtra SQL por `sucursal_id`, no por texto en `usuario_apertura`.

**Dueño:** mapa / lista de sucursales con semáforo mini (verde/ámbar/rojo).  
**Supervisor:** solo su `sucursal_id`.

### Pilar D — **Acciones en un toque (CTA matrix)**

| Estado | CTA primaria | CTA secundaria |
|--------|--------------|----------------|
| Caja rojo | Llamar supervisor | Abrir Control Center → caja |
| Inventario rojo | Ver quiebre IA | Orden compra sugerida |
| Crédito ámbar | Clientes morosos top 5 | Estado de cuenta |
| Operador crítico | Reconocer alerta | Ver detalle agente |

**API:** cada tarjeta trae `acciones: [{ id, label, url, tipo: 'tel'|'nav'|'api' }]`.

### Pilar E — **Voz + Push (SD-2 Guardián)**

- **Voz:** `POST /api/v1/owner/voice` — Whisper → intent (`estado_caja`, `ventas_hoy`, `llamar_supervisor`) → respuesta TTS opcional.
- **Web Push:** suscripción en PWA; alerta crítica dispara push aunque app cerrada.
- **WhatsApp** (ya hay servicio): duplicar solo alertas `critical` a lista dueño (env var).

### Pilar F — **Confianza y performance**

- JWT corto opcional para API móvil (además de cookie).
- Respuesta dashboard **&lt; 200 ms** (cache 15 s en Redis/memoria por perfil+sucursal).
- `ETag` / `If-None-Match` para ahorrar datos en 4G.
- Auditoría: cada vista dashboard → `erp_audit_log` (ligero).

---

## 4. API v3 — contrato propuesto

```http
GET /api/v1/owner/dashboard?v=3
```

```json
{
  "status": "success",
  "data": {
    "version": "guardian_v3",
    "perfil": "alta_gerencia",
    "alcance": "global",
    "nombre_usuario": "Mario Becerra",
    "saludo": "¡Hola, Don Mario!",
    "status_caja": "red",
    "status_inventario": "green",
    "status_credito": "amber",
    "status_global": "red",
    "mensaje_ia": "...",
    "supervisor_telefono": "+569...",
    "consolidado": {
      "visible": true,
      "ventas_hoy_clp": 12500000,
      "ventas_hoy_fmt": "$12.500.000",
      "var_vs_ayer_pct": 8.2,
      "descuadre_acumulado_clp": 8168790,
      "descuadre_acumulado_fmt": "+$8.168.790",
      "sucursales": [
        { "id": 1, "label": "Casa Matriz", "status_caja": "green", "status_stock": "green" },
        { "id": 2, "label": "SD-1", "status_caja": "red", "status_stock": "green" }
      ]
    },
    "tarjetas": [
      {
        "dominio": "caja",
        "estado": "rojo",
        "status": "red",
        "titulo": "Alerta Crítica: Caja",
        "mensaje": "...",
        "prioridad": 1,
        "acciones": [
          { "id": "call", "label": "Llamar supervisor", "tipo": "tel", "href": "tel:+56..." },
          { "id": "cc", "label": "Control Center", "tipo": "nav", "href": "/admin/control-center" }
        ]
      }
    ],
    "feed_preview": [
      { "id": 901, "tipo": "alerta", "severidad": "critical", "titulo": "...", "hace": "Ahora" }
    ],
    "meta": {
      "generado_en": "2026-05-21T20:00:00",
      "poll_recomendado_ms": 30000,
      "alertas_abiertas": 2
    }
  }
}
```

Compatibilidad: mantener `tarjeta_caja` / `tarjeta_inventario` como alias durante 1 release.

---

## 5. UI v3 — pantalla única rediseñada

```
┌─────────────────────────────────────┐
│ [Escudo 3D] Lhexia Guardián         │
│ ¡Hola, Don Mario!        [Instalar] │
│ ● En línea · 2 alertas              │
├─────────────────────────────────────┤
│ CONSOLIDADO RED                     │
│ $12.5M ventas hoy  +8.2% vs ayer    │
│ Desfalco red +$8.168.790  ← pulso   │
├─────────────────────────────────────┤
│ 🤖 Agente: "Prioridad caja SD-1…"   │
├─────────────────────────────────────┤
│ ▌ ALERTA CRÍTICA · Caja      [›]   │
│ ▌ OK · Inventario            [›]   │
│ ▌ ATENCIÓN · Crédito         [›]   │
├─────────────────────────────────────┤
│ Timeline · hace 2 min               │
│ · Vale #2584 pendiente >4h          │
├─────────────────────────────────────┤
│ ╭───────────────────────────────╮   │
│ │ 📞 Llamar    │  🎤 Agente IA  │   │
│ │ Control │ Actualizar          │   │
│ ╰───────────────────────────────╯   │
└─────────────────────────────────────┘
```

**Detalles premium:** haptic en alerta roja (Android), `prefers-reduced-motion`, brillo lateral animado solo en críticos.

---

## 6. Roadmap de entrega (realista)

| Fase | Nombre | Entregable | Depende de | Esfuerzo |
|------|--------|------------|------------|----------|
| **V3.0** | Mando ampliado | 4º y 5º semáforo (crédito + compras), `acciones[]`, feed_preview 5 ítems, sucursal en env mejorada | SD-1 estable | ~3–4 días dev |
| **V3.1** | Sucursal real | `id_sucursal` en Caja + filtro SQL + mini-mapa sucursales Dueño | SD-2 lite | ~5 días |
| **V3.2** | Agente + voz | Voz Whisper intent, push Web, narrativa Operador enrich | IA-0 tools lectura | ~7–10 días |
| **V3.3** | Icono & offline | Asset 3D maskable, snapshot offline, ETag API | Diseño asset | ~3 días |

**No mezclar V3.1+ con cierre de toma inventario SD-1** (regla proyecto).

---

## 7. Criterios de éxito (KPIs)

| KPI | Meta v3 |
|-----|---------|
| Tiempo hasta “entender el día” | &lt; 10 s desde abrir PWA |
| Dueño abre PWA / día | ≥ 2× (push ayuda) |
| Alertas críticas con CTA usada | ≥ 40% tocan “Llamar” o “Control” |
| API p95 | &lt; 300 ms |
| Tests smoke Guardián | ≥ 12 tests API + 3 E2E |

---

## 8. Qué pedirle a Cursor cuando digas “aplícalo”

1. Checkpoint git: `git tag checkpoint/guardian-v3-YYYY-MM-DD`
2. Implementar **V3.0** primero (máximo valor, mínimo riesgo).
3. Tests: `tests/test_owner_dashboard_api.py` ampliado + marker `guardian_v3`.
4. Actualizar `owner-dashboard.js` para tarjetas dinámicas + feed.
5. Doc validación: `OWNER_PWA_VALIDACION_PROD.md` § v3.

---

## 9. Decisión recomendada

**Empezar por V3.0** en la semana siguiente al cierre SD-1 checklist §8:

- No toca modelo masivo ni CrewAI en prod.
- Multiplica percepción de “potencia” (más dominios + feed + CTAs).
- Deja **sucursal_id** y **voz** para V3.1–3.2 cuando SD-2 y IA estén listos.

---

*Documento propuesta — LhexIA ERP · Santo Domingo · Mayo 2026*
