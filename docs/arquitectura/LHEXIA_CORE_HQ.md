# LhexIA Core HQ — Centro de Comando (Capa Plataforma)

**Estado:** Fase 1 — UI + mock data (mayo 2026)  
**Código:** repositorio Git **independiente** en carpeta local `lhexia-core-hq/` (Next.js). **No** forma parte del historial del repo ERP ferretería (ignorado en `.gitignore` del monolito).

## Propósito

Software **exclusivo del dueño de la plataforma SaaS** (no operadores de ferretería):

- Observabilidad multi-tenant (Neon, Render, tickets)
- Laboratorio IA (visión facturas, bots marketing)
- Finanzas API y margen por cliente
- Factory: aprovisionar ERP + licencias
- Wiki roadmap y backups

## Separación de responsabilidades

| Superficie | Usuario | Repo / ruta |
|------------|---------|-------------|
| **Core HQ** | Mario · platform owner | `lhexia-core-hq/` |
| **ERP Ferretería** | SD-1, Chilemat, etc. | `sistema_ventas_limpio` (Flask) |
| **Guardián / vertex-control** | Dueño en móvil (demo red) | `/owner/vertex-control` en ERP |
| **Control Center** | Admin un tenant | `/admin/control-center` |

## Fase 1 (actual)

- Dashboard grilla 5 módulos
- Mock: SD-1, Chilemat piloto, métricas Neon/Render, tickets, API spend CLP/USD
- Factory: simulación aprovisionamiento + toggle licencia UI

## Fase 2 (roadmap)

1. Auth owner-only (gateway VERTEX)
2. APIs reales: Neon metrics, Render health, OpenAI usage billing
3. Factory scripts: `neon branch create`, seed `productos_homologados_sd.csv`, Render deploy
4. CRM: webhook formulario lhexia.cl
5. Backup rollback con confirmación 2FA

## Arranque local

```bash
cd lhexia-core-hq && npm run dev
```

Ver `lhexia-core-hq/README.md`.
