# STATUS SD-1 — ancla rápida (actualizar al cerrar cada sesión)

**Prod (main):** `16a2dfe` — Operador IA, Guardián, Academy, Render.
**Local (sin commit):** paquete QA/UI + stock entero + deep links Mentor/ayuda.

## En vuelo ahora
- **UI HUD:** `static/css/design-system.css` (`erp-ops-space` v7), `templates/base.html?v=erp-ops-v7`
- **Caja cola:** `templates/caja_pendientes.html` — sin bloque amarillo; badge gris + tabla limpia
- **Lógica:** `services/unidades_service.py`, `services/stock_service.py` (consumo gramos enteros)
- **Tests:** `tests/test_unidades_stock_entero.py` · smoke ~144 passed (1 DTE e2e flaky)

## No releer salvo pedido explícito
- `app.py` monolito · POS (`punto_venta.html`, IDs `#posBuscarManual`, `#posBarcodeWedge`) · refactor big-bang

## Próximo paso acordado
1. Validar visual `/caja/vales_pendientes` (Ctrl+F5)
2. Si OK → commit + tag `checkpoint/qa-ui-sd1-YYYY-MM-DD` + push
3. Post SD-1: multi-tenant, Ollama PC SD, cron Operador Render

## Prompt ancla (copiar al abrir chat)
```
Lee docs/STATUS_SD1.md. Prod=16a2dfe. Hoy solo: [tarea]. No releer app.py/POS.
```
