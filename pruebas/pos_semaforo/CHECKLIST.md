# Checklist manual — POS semáforo y venta en verde

Ejecutar tras `python scripts/seed_pos_semaforo_pruebas.py` (BD local recomendada).

| ID | Código | Paso | Resultado esperado |
|----|--------|------|-------------------|
| POS-SEM-001 | `POS-SEM-V1` | Búsqueda `PRUEBA POS` → elegir V1 | Luz **verde**, agrega directo, sin banner azul |
| POS-SEM-002 | `POS-SEM-V2` | Misma búsqueda | Verde; línea stock muestra tienda **y** bodega |
| POS-SEM-003 | `POS-SEM-A1` | Filtro **Operativo** (default) → buscar `POS-SEM-A1` | Luz **amarilla**; agrega sin `a_pedido` |
| POS-SEM-004 | `POS-SEM-A2` | Lista con V1+V2+A1+A2 | Orden: verdes primero, luego amarillos |
| POS-SEM-005 | `POS-SEM-Z1` | 1.er clic en tarjeta azul | Solo aviso (paso 1): toast + banner «Paso 2» |
| POS-SEM-005b | `POS-SEM-Z1` | 2.º clic, **Confirmar y agregar** o **Enter** | Agrega al vale; recarga con badge **A pedido** |
| POS-SEM-006 | `POS-SEM-Z1` | Tras paso 2 | Fila carro celeste; emitir vale OK sin error de stock |
| POS-SEM-007 | `POS-SEM-Q1` | Escanear 3 veces mismo vale | 3.er intento: mensaje sin stock (no a pedido) |
| POS-SEM-008 | `POS-SEM-Z2` | Buscar `martillo sem` | Z2 atenuado; mismo flujo azul que Z1 |
| POS-SEM-009 | Config | Admin: `pos_permite_venta_verde=0` | Z1 no debe ofrecer confirmación a pedido (backend) |
| POS-SEM-010 | Caja | Cobrar vale con línea Z1 | Stock tienda **no** descuenta línea `a_pedido` |

**Filtros búsqueda:** **Operativo** (verde+amarillo+azul) · **Solo tienda** (solo verde) · **Catálogo** (todo).

**Atajos (layout premium vendedora):** F8 emitir · F4 cotizar · F2 buscar · F3 cliente final.

Automatización relacionada: `tests/test_pos_busqueda_semaforo.py`, `tests/test_routes_criticas.py` (buscar_producto).

## Checkpoints git (revertir layout premium)

| Tag | Contenido |
|-----|-----------|
| `checkpoint/pos-premium-vendedor-2026-05-20` | Con layout 3 columnas vendedora + filtros + compromiso entrega |
| `checkpoint/pos-pre-premium-vendedor-2026-05-20` | Sin layout ni fases 1.5–3 (solo Fase 1 verde operativa local) |
| `checkpoint/pos-premium-layout-2026-05-20` | Semáforo en prod (`ed9aede`), antes de todo lo anterior |

**Si al cliente no le gusta el layout:** volver al commit del tag anterior al premium:

```bash
git checkout checkpoint/pos-pre-premium-vendedor-2026-05-20 -- templates/punto_venta.html templates/base.html static/js/pos.js static/css/pos-premium-layout.css static/css/design-system.css app.py blueprints/pos.py
git rm -f static/css/pos-premium-layout.css templates/pos/includes/premium_historial_hoy.html 2>nul
```

O desplegar/ramificar desde `checkpoint/pos-pre-premium-vendedor-2026-05-20` para quitar todo el bloque POS nuevo.
