# Sets de prueba operativos — ERP Lhexa

Datos y guías para validar **casuísticas** en local o ferretería (sin mezclar con demo comercial).

| Carpeta / script | Uso |
|------------------|-----|
| [`pos_semaforo/`](pos_semaforo/) | Semáforo POS (verde / amarillo / azul), venta en verde, badge carro |
| `python scripts/seed_pos_semaforo_pruebas.py` | Carga idempotente en la BD configurada (`.env.local`) |
| `sql/2026_05_20_seed_pos_semaforo_pruebas.sql` | Misma carga vía SQL (Postgres) |
| [`../docs/CASUISTICAS_PRUEBAS.md`](../docs/CASUISTICAS_PRUEBAS.md) | Catálogo maestro de IDs (POS-*, CAJA-*, etc.) |

**Prefijo de códigos de barra:** `POS-SEM-*`  
**Búsqueda sugerida en POS:** `PRUEBA POS` o `POS-SEM` (asistente manual, ≥3 caracteres).

**Importante:** con el checkbox **«Solo vendibles»** activo, la API solo lista productos con **stock en tienda > 0**. Para ver ítems **amarillo** o **azul** en el dropdown, desmarque «Solo vendibles» o escanee el código `POS-SEM-*` directamente.
