# Casuísticas QA — venta, caja, entrega y compras

Set reproducible para Santo Domingo / SD-1: productos, clientes, ofertas POS y pruebas HTTP del flujo completo.

## Archivos

| Archivo | Rol |
|---------|-----|
| `tests/qa_catalogo_casuisticas.py` | Maestro de datos + `upsert` / `limpiar` |
| `scripts/seed_ventas_casuisticas_qa.py` | Sembrar en BD local (`--clean`, `--con-ventas-ejemplo`) |
| `tests/test_ventas_casuisticas_flujo.py` | Suite pytest (`-m casuisticas`) |
| `tests/conftest.py` | Fixture `catalogo_casuisticas_qa` + helpers HTTP |

## Productos (`TEST-CAS-*`)

| Código | Uso |
|--------|-----|
| `TEST-CAS-CEM-001` | Cemento — cross-sell obra + C360 `OBRA_GRUESA` |
| `TEST-CAS-ARE-001` | Arena — complemento cross-sell |
| `TEST-CAS-PVC-001` | Tubería PVC — retiro bodega |
| `TEST-CAS-PEG-001` | Pegamento — par PVC |
| `TEST-CAS-LLV-001` | Herramienta terminaciones |
| `TEST-CAS-OFE-001` | **Oferta POS** — descuento preautorizado 15% |
| `TEST-CAS-OFE-002` | **Oferta POS** — descuento preautorizado 10% |

Stock en **tienda** y **bodega** al sembrar.

## Clientes

| RUT | Perfil |
|-----|--------|
| `22.222.222-2` | Saldo a favor inicial $25.000 |
| `33.333.333-3` | Obra gruesa (`c360_etapa_actual=OBRA_GRUESA`) |
| `44.444.444-4` | Crédito — cupo $800.000, deuda inicial $150.000 |

Además existen los clientes base de pytest (`11.111.111-1` crédito, cliente final del sistema).

## Escenarios (IDs)

| ID | Descripción |
|----|-------------|
| CAS-V01 | POS → `finalizar_venta` → `procesar_cobro_caja` efectivo, retiro Tienda |
| CAS-V02 | Vale Bodega → cobro → `POST /bodega/vale/<id>/preparacion` |
| CAS-V03 | Vale **Mixto** (línea Tienda + línea Bodega) |
| CAS-V04 | Cobro **Crédito** — aumenta `saldo_deudor` |
| CAS-V05 | Cobro con **saldo a favor** parcial |
| CAS-V06 | Producto con `pos_descuento_preautorizado` |
| CAS-V07 | Cross-sell al escanear cemento (`data/cross_sell_associations.json`) |
| CAS-V08 | Cliente obra + producto `fase_obra` alineados |
| CAS-C01 | OC borrador con producto CAS |

## Comandos

```bash
# Sembrar catálogo en BD local
python scripts/seed_ventas_casuisticas_qa.py --clean

# Con 2 vales Pendiente de ejemplo para probar caja a mano
python scripts/seed_ventas_casuisticas_qa.py --clean --con-ventas-ejemplo

# Solo tests de casuísticas
pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -q

# Incluir en smoke CI (opcional)
pytest tests/ -m "smoke or casuisticas" -q
```

## Flujo técnico (referencia)

1. **POS:** `GET /punto_venta` → `POST /api/pos/escanear-agregar` → `POST /finalizar_venta`
2. **Caja:** `POST /procesar_cobro_caja/<id>` (`metodo_pago`, `usar_saldo_favor`, …)
3. **Bodega:** `POST /bodega/vale/<id>/preparacion` → `POST /bodega/vale/<id>/retiro-linea`
4. **Compras:** `POST /compras/ordenes/nueva`

Helpers en `tests/conftest.py`: `pos_emitir_vale_http`, `procesar_cobro_http`, `crear_venta_pendiente` (soporta retiro por línea).

## Proyecto / recomendaciones

No hay tabla `proyecto`. Se modela con:

- `Cliente.c360_etapa_actual` (etapa de obra)
- `Producto.fase_obra`
- Reglas en `data/cross_sell_associations.json`
- Motor C360 (`services/c360_service.py`) para ofertas proactivas y llamadas

El cliente `TEST CAS Cliente Obra Gruesa` + cemento alimentan pruebas de coherencia etapa/producto.
