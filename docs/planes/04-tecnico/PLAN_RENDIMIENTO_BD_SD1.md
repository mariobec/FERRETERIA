# Plan rendimiento BD — SD-1 (Santo Domingo)

**ID:** SD-1.3-infra-rendimiento  
**Última actualización:** 2026-05-21  
**Índice:** `../00-alineacion/PLAN_INDICE_LHEXIA.md` (fila SD-1.3)

---

## Objetivo

Sostener **~4.000 productos** y operación diaria sin lentitud perceptible:

| Estación | Cantidad | Carga principal |
|----------|----------|-----------------|
| POS | 4 vendedoras | `/buscar_producto` |
| Caja | 1 cajera | Cola vales `Pendiente` / cobro |
| Bodega | 1 operador | Plataforma retiro + preparación |
| TV bodega | 1 pantalla | `/bodega/cuadro-mando/tv` — refresh **30 s** (baja) |

**Pico concurrente:** ~6–7 requests HTTP (4 búsquedas POS + caja + bodega). La TV no genera polling JSON agresivo.

**Presupuesto orientativo:** ~$60.000 CLP/mes (Render Standard + Neon Launch activo en horario tienda).

---

## Veredicto

| Pregunta | Respuesta |
|----------|-----------|
| ¿Alcanza Postgres + esta etapa? | **Sí** |
| ¿Cambiar de motor? | **No** |
| ¿Redis en etapa 1? | **No** (postergar si tras índices + hosting sigue lento) |
| ¿2 workers Gunicorn? | **No** al inicio |

---

## Checklist de implementación

### 1. Base de datos (Neon) — obligatorio

1. En Neon, usar **connection string con pooler** (`-pooler` en el host).
2. Ejecutar script (ventana de bajo tráfico):

   ```bash
   psql "$DATABASE_URL" -f sql/2026_05_21_rendimiento_sd1_postgresql.sql
   ```

   O pegar el contenido en **Neon → SQL Editor**.

3. Verificar extensión:

   ```sql
   SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';
   ```

### 2. Render — hosting

| Ajuste | Valor recomendado |
|--------|-------------------|
| Plan | **Standard** (2 GB RAM) |
| Gunicorn | `1` worker, **`6` threads** |
| `DATABASE_URL` | Neon **pooler** |
| `DB_POOL_SIZE` | `10` |
| `DB_MAX_OVERFLOW` | `5` |
| `DB_POOL_TIMEOUT` | `30` |

`render.yaml` en el repo refleja threads y variables sugeridas; el plan **Standard** se confirma en el dashboard de Render si el YAML no aplica el cambio de plan automáticamente.

### 3. Neon — compute

- Plan **Launch** (o superior).
- **Compute activo** en horario de tienda (evitar scale-to-zero en horario venta).

### 4. Código (incluido en repo)

- `buscar_producto` en PostgreSQL usa `LIKE` con `lower()` para que el planificador use índices **GIN pg_trgm** (antes usaba `strpos`, que no los aprovecha).

---

## Metas de latencia (piso)

| Prueba | Meta |
|--------|------|
| Búsqueda POS (2–3 letras) | &lt; 500 ms |
| Escaneo código de barras | &lt; 200 ms |
| Cola caja (carga inicial) | &lt; 1 s |
| TV cuadro de mando (refresh 30 s) | &lt; 2 s por recarga |

---

## Qué NO hacer en etapa 1

- Segundo worker Gunicorn sin redimensionar pool Neon.
- Redis / Meilisearch sin medir antes.
- Render Pro sin índices aplicados.
- TV cliente POS (polling 1,5 s) — fuera de alcance SD-1 bodega.

---

## Post SD-1 (solo si hace falta)

1. **Redis** (Upstash): caché búsqueda POS 30–60 s por sucursal.
2. Subir polling TV cliente si se activa Experience Wall.
3. Revisar `max_overflow` en `app.py` si hay timeouts bajo carga real.

---

## Archivos relacionados

| Archivo | Rol |
|---------|-----|
| `sql/2026_05_21_rendimiento_sd1_postgresql.sql` | Índices + `ANALYZE` |
| `render.yaml` | Gunicorn threads + env pool |
| `app.py` | `SQLALCHEMY_ENGINE_OPTIONS`, `buscar_producto` |
| `docs/planes/04-tecnico/ESTADO_OPTIMIZACION_APP.md` | Refactor monolito (paralelo) |

---

*Actualizar tras validación en piso Santo Domingo (marcar SD-1.3 ítems en `CLIENTE_SANTO_DOMINGO.md`).*
