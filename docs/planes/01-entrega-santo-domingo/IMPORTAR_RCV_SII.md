# Importar RCV SII → borradores de recepción (SD-1)

**Script:** `scripts/importar_rcv_sii.py`  
**Servicio:** `services/rcv_sii_import_service.py`  
**SQL Neon:** `sql/2026_05_22_rcv_sii_recepciones.sql`  
**Listado UI:** `/recepciones` (filtros, Pareto por monto, folio, archivar 2025)

---

## Alcance SD-1 (qué es automático y qué no)

| Paso | Automático | Cómo |
|------|------------|------|
| **Encabezados RCV** (CSV SII) | **Sí — dedup en BD** | Mismo proveedor + Factura + **folio** → fila omitida (`omitidas_duplicado`). Reimportar el mismo CSV **no duplica** borradores. |
| **Nuevos CSV en carpeta** | **No** | No hay vigilancia de `datos_rcv/`. Hay que ejecutar el script o `reimportar_rcv_neon_todos.ps1`. |
| **PDF en carpeta del PC** | **No** | No se lee ninguna carpeta de PDFs del repositorio ni del servidor. |
| **PDF “ya leído”** | **No** | No hay registro por nombre de archivo; cada PDF se sube **a mano** en la recepción. |
| **Líneas de factura (IA)** | **Manual, 1 a 1** | Por recepción: adjuntar PDF → (opcional) Analizar con IA → aplicar líneas. Requiere `OPENAI_API_KEY` en Render. |
| **Líneas sin IA** | **Manual** | Registrar línea en `/recepciones/<id>`. |

**Volumen Pareto SD-1:** encabezados masivos por CSV + PDF/líneas **manual** en el top 300–500 facturas 2026 es el flujo acordado.

---

## Flujo recomendado (Santo Domingo)

### A. Maestro productos (D0 — antes de matchear facturas)

1. Homologar matriz Chilemat → `productos_homologados_sd.csv` (`homologar_productos_excel.py --maestro`).
2. Carga masiva en **www.lhexia.cl** → Productos, **o** script Neon:

```powershell
cd "d:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
python scripts/cargar_maestro_productos_neon.py --neon -i "CARGA DE DATOS\productos_homologados_sd.csv"
```

3. Verificar en Productos: ~4.913 activos, `codigo_chilemat`, stock 0, barras `PEND-*`.

### B. Encabezados RCV (borradores sin líneas)

1. Exportar **compras** del portal SII (no ventas) → CSV `RCV_COMPRA_REGISTRO_*.csv`.
2. Copiar a `datos_rcv/` en el proyecto (no se sube al repo; solo local).
3. Migración SQL (una vez por base):

```powershell
python scripts/apply_sql_neon.py sql/2026_05_22_rcv_sii_recepciones.sql
python scripts/apply_sql_neon.py sql/2026_05_22_recepciones_archivado_rcv.sql
```

4. Simulación:

```powershell
python scripts/importar_rcv_sii.py --neon -i "datos_rcv\RCV_COMPRA_REGISTRO_8054120-1_202601.csv" --dry-run
```

5. Import real (un archivo):

```powershell
python scripts/importar_rcv_sii.py --neon -i "datos_rcv\RCV_COMPRA_REGISTRO_8054120-1_202601.csv"
```

6. Lote todos los CSV de la carpeta:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\reimportar_rcv_neon_todos.ps1
# Solo simular: .\scripts\reimportar_rcv_neon_todos.ps1 -DryRun
```

**Salida esperada:** `creadas` (folios nuevos) + `omitidas_duplicado` (ya en BD). No hace falta revisar duplicados a mano.

### C. Trabajo Pareto en UI (D2)

1. [www.lhexia.cl/recepciones](https://www.lhexia.cl/recepciones)
2. Filtro año **2026** → orden **Pareto (monto)** o atajo Pareto 2026.
3. Buscar folio: caja azul / `?folio=NUMERO` en la URL.
4. Abrir recepción → **Documento de compra** → elegir PDF desde el PC → **Adjuntar**.
5. Líneas: **Registrar línea** (siempre) o **Analizar documento con IA** (si hay API key).
6. Opcional: **Archivar RCV 2025 (lote)** para achicar ruido histórico.

### D. Limpiar cola 2025 (opcional)

En listado Recepciones → botón **Archivar RCV 2025 (lote)** (estado `Archivado RCV`).

---

## Comandos rápidos (copiar/pegar)

```powershell
cd "d:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"

# Neon = misma BD que Render (NEON_DATABASE_URL en .env.local)
python scripts/importar_rcv_sii.py --neon --input "datos_rcv\ARCHIVO.csv" --dry-run
python scripts/importar_rcv_sii.py --neon --input "datos_rcv\ARCHIVO.csv"

# Solo facturas electrónicas tipo 33
python scripts/importar_rcv_sii.py --neon -i "datos_rcv\ARCHIVO.csv" --tipos 33

# Carga masiva maestro (post-homologación)
python scripts/cargar_maestro_productos_neon.py --neon -i "CARGA DE DATOS\productos_homologados_sd.csv" --lote 400
```

**Importante:** sin `--neon` el script usa `DATABASE_URL` local (prototipo), no producción.

---

## PDF y almacenamiento en Render

| Tema | Detalle |
|------|---------|
| **Dónde NO van los PDF** | No en `datos_rcv/`, no en GitHub, no en carpeta del repo en el servidor. |
| **Dónde SÍ van** | Subida desde el navegador → `static/uploads/recepciones/recepcion_{id}_{nombre}` en el **disco del contenedor Render**. |
| **Persistencia** | El disco de Render es **efímero**: un **redeploy** puede borrar adjuntos. Tras deploy, volver a **Adjuntar** el PDF si hace falta. |
| **IA en producción** | Variable `OPENAI_API_KEY` en Render → Environment. Sin ella solo aparece el aviso; no hay botón Analizar. Opcional: `IA_FACTURA_PDF_PAGINAS=2`. |
| **Neon (BD)** | Folios, proveedor, montos y **líneas** sí persisten en Postgres; los archivos PDF no están en Neon. |

---

## Qué hace el import RCV (técnico)

1. Lee CSV/TXT del Registro de Compras (`;` o `,`).
2. Mapea columnas: Tipo Doc, RUT, Folio, Fecha, Montos, Razón social.
3. Tipos compra por defecto: **33, 34, 46**.
4. Crea `RecepcionCompra` en **`Pendiente de Items`** (sin líneas).
5. Crea proveedor por RUT si no existe.
6. **Dedup:** `proveedor_id` + `documento_tipo='Factura'` + `documento_numero=folio`.

---

## Estados recepción

| Estado | Significado |
|--------|-------------|
| Pendiente de Items | Borrador RCV: falta PDF y/o líneas |
| Incompleta | Al menos una línea |
| Finalizada | Cerrada |
| Archivado RCV | Histórico tributario (fuera de cola operativa) |

---

## Listado `/recepciones`

- Filtros: estado, año (2025/2026), orden fecha o **monto (Pareto)**.
- Paginación: 50 por página.
- Búsqueda por **folio** (UI + `?folio=`).
- **Pareto 2026 (monto)** para checklist D2.

---

## Purga maestro Neon (solo si se repite carga Chilemat desde cero)

```powershell
python scripts/purge_maestro_productos_neon.py --neon --dry-run
$env:CONFIRMAR_PURGA_MAESTRO='SI'
python scripts/purge_maestro_productos_neon.py --neon
```

No usar en operación normal con catálogo ya cargado.

---

## QA local (no producción)

Catálogo `SD-PRUEBA-*` / `SD PRUEBA PRODUCTO` solo en BD local para pytest:

```powershell
python scripts/seed_sd_prueba_casuisticas.py --clean
pytest tests/test_ventas_casuisticas_flujo.py -m casuisticas -q
```

Ver `docs/CASUISTICAS_VENTAS_QA.md`.

---

## Siguiente fase (post SD-1, no implementado)

- Import automático al detectar CSV nuevos en carpeta.
- Emparejar PDF por folio en nombre de archivo (`149885.pdf` → recepción 149885).
- Registro de archivos ya procesados.
