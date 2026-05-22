# LhexIA Guardián — API v1 (VERTEX Agente)

**Ecosistema:** LhexIA VERTEX · **Solución:** Ferretería (SD-1)  
**Base URL:** `https://www.lhexia.cl`

---

## GET `/api/v1/owner/dashboard`

Dashboard PWA dueño (Guardián V3).

| Query | Descripción |
|-------|-------------|
| `v=3` | Versión payload (`guardian_v3`) |
| `nocache=1` | Evitar cache intermedia |

**Auth:** cookie sesión Flask-Login. Sin sesión → `401` `login_required`.

**Headers respuesta:** `Cache-Control: no-store`

**Permisos:** `panel_gerencia` \| `ver_gerencia` \| `gestionar_usuarios` (admin bypass).

### Respuesta (resumen)

```json
{
  "status": "success",
  "data": {
    "version": "guardian_v3",
    "ecosystem": "lhexia_vertex",
    "perfil": "alta_gerencia",
    "alcance": "global",
    "saludo": "¡Hola, Don Mario!",
    "status_caja": "red",
    "status_inventario": "green",
    "status_credito": "green",
    "status_compras": "green",
    "status_global": "red",
    "mensaje_ia": "...",
    "supervisor_telefono": "+569...",
    "consolidado": {
      "ventas_hoy_fmt": "$31.890",
      "ventas_hoy_clp": 31890,
      "transacciones_hoy": 1,
      "var_vs_ayer_pct": null,
      "visible": true,
      "descuadre_acumulado_fmt": "+$360"
    },
    "tarjetas": [
      {
        "dominio": "caja",
        "estado": "rojo",
        "status": "red",
        "titulo": "Alerta Crítica: Caja",
        "mensaje": "...",
        "acciones": [
          { "id": "cc", "label": "Control Center", "tipo": "nav", "href": "/admin/control-center" }
        ]
      }
    ],
    "tarjeta_caja": {},
    "tarjeta_inventario": {},
    "feed_preview": [],
    "meta": {
      "version": "guardian_v3",
      "ecosystem": "lhexia_vertex",
      "alertas_abiertas": 0,
      "poll_recomendado_ms": 30000
    }
  }
}
```

### Compatibilidad

- `tarjeta_caja`, `tarjeta_inventario`, `tarjeta_credito`, `tarjeta_compras` se mantienen 1 release mínimo.
- Estados semáforo UI: `verde` \| `amarillo` \| `rojo` (API `status`: `green` \| `amber` \| `red`).

---

## PWA

| Ruta | Rol |
|------|-----|
| `/owner-mobile` | Shell Guardián |
| `/owner/vertex-control` | Centro de Mandos Global (maestro multi-cliente) |
| `?scope=global_maestro` | API red VERTEX — clientes + feed global (píldora v1.0, ver [`VERTEX_MASTER_CORE.md`](VERTEX_MASTER_CORE.md)) |
| `/owner-pwa/manifest.webmanifest` | Instalación |
| `/owner-pwa/sw.js` | Service worker (scope PWA) |

---

## Próximo (VERTEX Fase 3)

- `GET /api/v1/owner/feed?cursor=`
- `POST /api/v1/owner/voice`
- Web Push subscription

---

*Ver biblia:* [`LHEXIA_VERTEX_VISION.md`](LHEXIA_VERTEX_VISION.md)
